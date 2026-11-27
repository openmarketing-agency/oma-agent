"""One managed Analyst turn for scheduled and requested analytics refreshes."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from hermes_cli.oma_campaigns.source import _member, read_mapping

JOB_ID = "oma-campaign-analytics"
JOB_NAME = "Campaign analytics"
_LEGACY_COLLECTOR = "oma-managed-campaign-analytics.py"
SCHEDULE = "every 6h"
PROMPT = (
    "Refresh analytics for your own campaign. Load the analytics-dataset skill and read existing observations first. "
    "Use ga4-analytics, google-search-analytics, and social-media-analytics for the campaign's relevant connected "
    "sources; use composio-analytics when discovering reads through Composio. Fetch only missing or stale "
    "measurements through authorized read-only tools for verified properties or accounts. Start with recent complete "
    "periods and bounded pages. Save and read back verified observations using the campaign analytics CLI. "
    "Summarize what you saved and which sources were unavailable or partial. Do not publish, reply, manage "
    "connections, or treat unavailable metrics as zero."
)


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
    legacy = job.get("script") == _LEGACY_COLLECTOR and job.get("no_agent") is True
    native = not job.get("script") and job.get("no_agent") is False and job.get("prompt") == PROMPT
    return (job.get("id") == JOB_ID and (native or legacy)
            and job.get("deliver") == "local" and job.get("failure_deliver") in (None, "local")
            and analyst_profile(profile))


def ensure_job(profile: Path) -> None:
    from cron.extra_fire import RESTORE_KEY, queued
    from cron.jobs import _jobs_lock, load_jobs, parse_schedule, save_jobs, use_cron_store

    schedule = parse_schedule(SCHEDULE)
    now = datetime.now(UTC)
    next_slot = (now + timedelta(minutes=schedule["minutes"])).isoformat()
    with use_cron_store(profile), _jobs_lock():
        jobs = load_jobs()
        previous = next((job for job in jobs if job.get("id") == JOB_ID), None)
        job = {**(previous or {
            "created_at": now.isoformat(), "enabled": True, "state": "scheduled",
            "repeat": {"times": None, "completed": 0}, "next_run_at": next_slot,
        }), "id": JOB_ID, "name": JOB_NAME, "script": None, "no_agent": False, "prompt": PROMPT,
            "schedule": schedule, "schedule_display": SCHEDULE, "deliver": "local", "failure_deliver": None}
        if previous and previous.get("schedule") != schedule:
            if queued(previous):
                job[RESTORE_KEY] = next_slot
            elif previous.get("next_run_at"):
                job["next_run_at"] = next_slot
                job.pop("pending_slot", None)
        if previous != job:
            save_jobs([job])


def _status(job: dict | None) -> dict:
    from cron.constants import FIRE_CLAIM_TTL_SECONDS
    from cron.executions import cancellable_execution, latest_execution
    from cron.jobs import _claim_is_live

    if not job:
        return {"state": "unavailable", "running": False, "run_id": None,
                "last_outcome": None, "last_finished_at": None}
    live = cancellable_execution(JOB_ID)
    latest = latest_execution(JOB_ID)
    running = bool(live and live["status"] == "running")
    now = datetime.now(UTC)
    # A due slot can be reserved before an execution row has been created.
    pending = job.get("manual_run_at") or next((
        job[key]["at"] for key in ("pending_slot", "fire_claim")
        if _claim_is_live(job.get(key), now, FIRE_CLAIM_TTL_SECONDS)
    ), None)
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

    directory, profile, config = _config(home, campaign_id)
    with bind_profile_scope(profile, hydrate_secrets=False), use_cron_store(profile):
        job = get_job(JOB_ID) if profile.is_dir() and analyst_profile(profile) else None
        status = _status(job if job and is_managed_job(profile, job) else None)
    if status["state"] == "queued" and config.get("lifecycle_state") != "resumed":
        status.update(state="idle", run_id=None)
    return {"campaign_id": campaign_id, **status, **last_refresh(directory)}


def refresh_analytics(home: Path, campaign_id: str) -> dict:
    from cron.jobs import _jobs_lock, _queue_run_now, get_job, is_job_runnable, use_cron_store
    from hermes_cli.oma_campaigns.analytics import AnalyticsError

    directory, profile, _ = _config(home, campaign_id)
    if not profile.is_dir():
        raise AnalyticsError(409, "Start the campaign and install its analyst before refreshing analytics.")
    with bind_profile_scope(profile, hydrate_secrets=False), use_cron_store(profile), _jobs_lock():
        config = read_mapping(_member(directory, "config.yaml"))
        if config.get("lifecycle_state") != "resumed" or not analyst_profile(profile):
            raise AnalyticsError(409, "Start the campaign and install its analyst before refreshing analytics.")
        job = get_job(JOB_ID)
        if not job or not is_managed_job(profile, job) or not is_job_runnable(job):
            raise AnalyticsError(409, "The campaign analyst job is unavailable or paused.")
        status = _status(job)
        if status["state"] == "idle":
            if job.get("no_agent"):
                ensure_job(profile)
                job = get_job(JOB_ID)
            queued = _queue_run_now(job) if job else None
            if not queued or not queued.get("manual_run_at"):
                raise AnalyticsError(503, "Could not queue the campaign analyst.")
            status.update(state="queued", running=False, run_id=queued["manual_run_at"])
    return {"campaign_id": campaign_id, **status}


def refresh_publications(profile: Path, job: dict, cancel_event=None) -> int:
    from hermes_cli.oma_campaigns.analytics import AnalyticsError, save_observations
    from hermes_cli.oma_campaigns.install import _install_lock
    from hermes_cli.oma_campaigns.storage import connect_campaign_data

    if not is_managed_job(profile, job):
        raise AnalyticsError(409, "Invalid managed campaign analyst job.")
    campaign_id = profile.name.partition("__")[0]
    home = profile.parent.parent
    directory, _, _ = _config(home, campaign_id)
    config_path = directory / "config.yaml"
    with _install_lock(config_path):
        if (cancel_event is not None and cancel_event.is_set()) or read_mapping(config_path).get("lifecycle_state") != "resumed":
            raise AnalyticsError(409, "Analytics collection cancelled because the campaign is stopped.")
        rows = []
        with connect_campaign_data(directory) as conn:
            if conn:
                for metric, day, total in conn.execute("""
                    SELECT 'drafts_created', substr(created_at, 1, 10), COUNT(*) FROM publications GROUP BY 2
                    UNION ALL
                    SELECT 'published', substr(json_extract(result, '$.published_at'), 1, 10), COUNT(*)
                    FROM publications WHERE status='published' AND json_extract(result, '$.published_at') IS NOT NULL
                    GROUP BY 2
                """):
                    rows.append(dict(source="oma-publications", account=campaign_id, metric=metric, value=total,
                                     unit="count", dimensions={}, period_start=day,
                                     period_end=(date.fromisoformat(day) + timedelta(days=1)).isoformat()))
        return save_observations(home, campaign_id, rows, refresh_complete=True)
