"""One campaign-owned collector job, shared by scheduled and requested refreshes."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from hermes_cli.oma_campaigns.source import _member, read_mapping

JOB_ID = "oma-campaign-analytics"
JOB_NAME = "Campaign analytics"
COLLECTOR = "oma-managed-campaign-analytics.py"


def analyst_profile(profile: Path) -> bool:
    from hermes_cli.oma_campaigns.analytics import campaign_dir

    campaign, sep, role = profile.name.partition("__")
    if not sep or role != "analyst" or profile.parent.name != "profiles":
        return False
    try:
        config = read_mapping(_member(campaign_dir(profile.parent.parent, campaign), "config.yaml"))
    except (OSError, ValueError):
        return False
    roster = config.get("agents")
    return (config.get("id") == campaign and config.get("installation_state") == "installed"
            and isinstance(roster, list) and profile.name in roster)


def is_managed_job(profile: Path, job: dict) -> bool:
    return (job.get("id") == JOB_ID and job.get("script") == COLLECTOR and job.get("no_agent") is True
            and job.get("deliver") == "local" and job.get("failure_deliver") in (None, "local")
            and analyst_profile(profile))


def ensure_job(profile: Path) -> None:
    from cron.jobs import _jobs_lock, load_jobs, parse_schedule, save_jobs, use_cron_store

    schedule = parse_schedule("every 1h")
    now = datetime.now(UTC)
    with use_cron_store(profile), _jobs_lock():
        jobs = load_jobs()
        previous = next((job for job in jobs if job.get("id") == JOB_ID), None)
        job = {**(previous or {
            "created_at": now.isoformat(), "enabled": True, "state": "scheduled",
            "repeat": {"times": None, "completed": 0}, "next_run_at": (now + timedelta(hours=1)).isoformat(),
        }), "id": JOB_ID, "name": JOB_NAME, "script": COLLECTOR, "no_agent": True, "prompt": "",
            "schedule": schedule, "schedule_display": "every 1h", "deliver": "local", "failure_deliver": None}
        if previous != job:
            save_jobs([job])


def _status(job: dict | None) -> dict:
    from cron.executions import cancellable_execution, latest_execution

    if not job:
        return {"state": "unavailable", "running": False, "run_id": None,
                "last_outcome": None, "last_finished_at": None}
    live = cancellable_execution(JOB_ID)
    latest = latest_execution(JOB_ID)
    running = bool(live and live["status"] == "running")
    pending = job.get("manual_run_at")
    return {"state": "running" if running else "queued" if live or pending else "idle", "running": running,
            "run_id": live["id"] if live else pending,
            "last_outcome": job.get("last_status"), "last_finished_at": (latest or {}).get("finished_at")}


def _config(home: Path, campaign_id: str) -> tuple[Path, Path, dict]:
    from hermes_cli.oma_campaigns.analytics import campaign_dir

    directory = campaign_dir(home, campaign_id)
    profile = _member(_member(home, "profiles"), f"{campaign_id}__analyst")
    return directory, profile, read_mapping(_member(directory, "config.yaml"))


def analytics_status(home: Path, campaign_id: str) -> dict:
    from cron.jobs import get_job, use_cron_store
    from hermes_cli.oma_campaigns.analytics import last_refresh
    from hermes_cli.oma_campaigns.analytics_sync.data import coverage

    directory, profile, config = _config(home, campaign_id)
    with bind_profile_scope(profile, hydrate_secrets=False), use_cron_store(profile):
        job = get_job(JOB_ID) if profile.is_dir() and analyst_profile(profile) else None
        status = _status(job if job and is_managed_job(profile, job) else None)
    if status["state"] == "queued" and config.get("lifecycle_state") != "resumed":
        status.update(state="idle", run_id=None)
    return {"campaign_id": campaign_id, **status, **last_refresh(directory), "datasets": coverage(directory)}


def refresh_analytics(home: Path, campaign_id: str) -> dict:
    from cron.jobs import _jobs_lock, get_job, is_job_runnable, trigger_job, use_cron_store
    from hermes_cli.oma_campaigns.analytics import AnalyticsError
    from hermes_cli.oma_campaigns.install import _install_lock

    directory, profile, _ = _config(home, campaign_id)
    with _install_lock(directory / "config.yaml"), bind_profile_scope(profile, hydrate_secrets=False), use_cron_store(profile):
        config = read_mapping(_member(directory, "config.yaml"))
        if config.get("mode") == "control":
            raise AnalyticsError(409, "Analytics refresh is disabled in control mode.")
        if config.get("lifecycle_state") != "resumed" or not analyst_profile(profile) or not profile.is_dir():
            raise AnalyticsError(409, "Start the campaign and install its analyst before refreshing analytics.")
        with _jobs_lock():
            job = get_job(JOB_ID)
            if not job or not is_managed_job(profile, job) or not is_job_runnable(job):
                raise AnalyticsError(409, "The campaign analyst job is unavailable or paused.")
            status = _status(job)
            if status["state"] == "idle":
                queued = trigger_job(JOB_ID)
                if not queued or not queued.get("manual_run_at"):
                    raise AnalyticsError(503, "Could not queue the campaign analyst.")
                status.update(state="queued", running=False, run_id=queued["manual_run_at"])
    return {"campaign_id": campaign_id, **status}


def run_managed_job(profile: Path, job: dict, cancel_event=None) -> int:
    from hermes_cli.oma_campaigns.analytics import AnalyticsError
    from hermes_cli.oma_campaigns.analytics_sources import collect

    if not is_managed_job(profile, job):
        raise AnalyticsError(409, "Invalid managed campaign analyst job.")
    campaign_id = profile.name.partition("__")[0]
    return collect(profile.parent.parent, campaign_id, profile, cancel_event)
