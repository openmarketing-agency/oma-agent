"""Apply a campaign's durable pause/resume intent without stopping the host gateway."""

from datetime import UTC, datetime
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from cron.jobs import cancel_job_run, compute_next_run, is_job_runnable, list_jobs, update_job, use_cron_store
from gateway.control_socket import rescan_gateway_profiles
from gateway.status import resolve_gateway_liveness
from hermes_cli import kanban_db
from hermes_cli.config import atomic_config_write
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.kanban_db_connect import _dispatch_tick_lock, connect_closing
from hermes_cli.oma_campaigns.install import _campaign_config_path, _campaigns_dir, _install_lock, _status
from hermes_cli.oma_campaigns.integrations import missing_integrations
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import read_mapping


def _stop_work(home: Path, board: str, profiles: list[Path]) -> bool:
    # A dispatcher that passed the latch before we wrote it must settle before reclaim.
    db_path = kanban_db.kanban_db_path(board=board)
    with _dispatch_tick_lock(db_path) as held:
        if not held:
            return False
        with connect_closing(board=board) as conn:
            for task in kanban_db.list_tasks(conn, status="running"):
                kanban_db.reclaim_task(conn, task.id, reason="OMA campaign paused", require_stopped=True)
            pending = bool(kanban_db.list_tasks(conn, status="running"))
    for profile in profiles:
        with bind_profile_scope(profile), use_cron_store(profile):
            for job in list_jobs(include_disabled=True):
                if cancel_job_run(job["id"], reason="OMA campaign paused")["cancelled"]:
                    pending = True
    # Native reconciliation retires only profiles filtered out by the campaign latch, interrupting
    # their turns and leaving the launch profile and other campaigns alone.
    states = [resolve_gateway_liveness(profile_dir=profile, use_cache=False) for profile in profiles]
    if any(state.running for state in states):
        rescan_gateway_profiles(home)
        states = [resolve_gateway_liveness(profile_dir=profile, use_cache=False) for profile in profiles]
    return not pending and not any(state.running or state.probe_error for state in states)


def _skip_missed_recurring_jobs(profiles: list[Path]) -> None:
    now = datetime.now(UTC)
    for profile in profiles:
        with bind_profile_scope(profile), use_cron_store(profile):
            for job in list_jobs():
                schedule = job["schedule"]
                due = job.get("next_run_at")
                if (is_job_runnable(job) and schedule.get("kind") in {"cron", "interval"} and due
                        and datetime.fromisoformat(due) <= now):
                    next_run = compute_next_run(schedule, now.isoformat(), timezone=job.get("timezone"))
                    if next_run:
                        update_job(job["id"], {"next_run_at": next_run, "manual_run_at": None})


def set_lifecycle(home: Path, campaign_id: str, target: str) -> dict:
    require_file_tooling("OMA campaign lifecycle")
    if target not in {"paused", "resumed"}:
        raise ValueError("Campaign lifecycle state must be paused or resumed")
    path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(path):
        config = read_mapping(path)
        validate_record("campaign", config, path)
        status = _status(home, campaign_id, config)
        if status["state"] != "installed":
            raise ValueError("Install the campaign before changing its lifecycle")
        current = status["lifecycle_state"]
        profiles = [home / "profiles" / name for name in status["present_profiles"]]
        result = {"id": campaign_id, "state": current}
        if current == target:
            return result
        if target == "paused" or current == "pausing":
            config = {**config, "lifecycle_state": "pausing"}
            atomic_config_write(path, config)
            if not _stop_work(home, status["kanban_board"], profiles):
                return {**result, "state": "pausing"}
            config["lifecycle_state"] = "paused"
            atomic_config_write(path, config)
            if target == "paused":
                return {**result, "state": "paused"}
        # Console sync puts the campaign's Composio session and key into its roster,
        # not the workspace's default profile. Probe the campaign's own session when set.
        connection_home = (home / "profiles" / status["orchestrator"]
                           if config.get("mcp_servers", {}).get("composio") else home)
        missing = missing_integrations(home, config.get("integrations", []), connection_home=connection_home)
        if missing:
            return {**result, "state": "paused", "missing_integrations": missing}
        _skip_missed_recurring_jobs(profiles)
        atomic_config_write(path, {**config, "lifecycle_state": "resumed"})
    rescan_gateway_profiles(home)
    return {"id": campaign_id, "state": "resumed"}
