"""Apply a campaign's durable pause/resume intent without stopping the host gateway."""

from datetime import UTC, datetime
import json
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from cron.jobs import (_jobs_lock, cancel_job_run, compute_next_run, is_job_runnable, list_jobs,
                       load_jobs, resume_job, save_jobs, update_job, use_cron_store)
from gateway.control_socket import rescan_gateway_profiles
from gateway.status import resolve_gateway_liveness
from hermes_cli import kanban_db
from hermes_cli.config import atomic_config_write
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.kanban_db_connect import _dispatch_tick_lock, connect_closing
from hermes_cli.oma_campaigns.install import _campaign_config_path, _campaigns_dir, _install_lock, _status
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping
from utils.files import atomic_json_write


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


def _control_cron(profiles: list[Path], *, park: bool) -> None:
    for profile in profiles:
        cron = _member(profile, "cron")
        jobs_file = _member(cron, "jobs.json")
        snapshot = _member(cron, "oma-control-jobs.json")
        if not (snapshot.exists() or jobs_file.exists()):
            continue
        with use_cron_store(profile), _jobs_lock():
            parked = json.loads(snapshot.read_text(encoding="utf-8-sig")) if snapshot.exists() else []
            jobs = load_jobs()
            if park and jobs:
                by_id = {job["id"]: job for job in [*parked, *jobs]}
                atomic_json_write(snapshot, list(by_id.values()), mode=0o600, fsync_dir=True)
                save_jobs([], replace=True)
            elif not park and snapshot.exists():
                # Keep the live copy on retry if a previous restore was interrupted.
                by_id = {job["id"]: job for job in [*parked, *jobs]}
                save_jobs(list(by_id.values()), replace=True)
                snapshot.unlink()


def set_mode(home: Path, campaign_id: str, mode: str) -> dict:
    require_file_tooling("OMA campaign mode")
    path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(path):
        config = read_mapping(path)
        updated = {**config, "mode": mode}
        validate_record("campaign", updated, path)
        status = _status(home, campaign_id, config)
        if status["state"] == "incomplete" or (status["state"] == "installed" and status["lifecycle_state"] != "paused"):
            raise ValueError("Stop the campaign before changing its mode.")
        profiles = [home / "profiles" / name for name in status["present_profiles"]]
        if mode == "control":
            # Block new registrations before taking the snapshot; this is retryable if parking fails.
            atomic_config_write(path, updated)
            _control_cron(profiles, park=True)
        else:
            _control_cron(profiles, park=False)
            atomic_config_write(path, updated)
    return {"id": campaign_id, "mode": mode}


def _activate_new_jobs(profiles: list[Path]) -> None:
    from hermes_cli.oma_campaigns.role_jobs import AWAITING_ACTIVATION

    for profile in profiles:
        with bind_profile_scope(profile), use_cron_store(profile):
            for job in list_jobs(include_disabled=True):
                if job.get("oma_job_id") and job.get("paused_reason") == AWAITING_ACTIVATION:
                    schedule = job["schedule"]
                    if schedule.get("kind") != "once" or compute_next_run(schedule, timezone=job.get("timezone")):
                        resume_job(job["id"])


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
        model = config.get("model")
        model_id = model.get("default") if isinstance(model, dict) else model
        if not isinstance(model_id, str) or not model_id.strip():
            return {**result, "state": "paused", "missing_model": True}
        if config.get("mode") == "control":
            _control_cron(profiles, park=True)
        else:
            _control_cron(profiles, park=False)
            if config.get("mode") in ("yolo", "approve"):
                _activate_new_jobs(profiles)
            _skip_missed_recurring_jobs(profiles)
        atomic_config_write(path, {**config, "lifecycle_state": "resumed"})
    rescan_gateway_profiles(home)
    return {"id": campaign_id, "state": "resumed"}
