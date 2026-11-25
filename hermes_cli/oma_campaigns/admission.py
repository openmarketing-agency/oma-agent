"""Read the OMA lifecycle latch at the native admission boundaries."""

from pathlib import Path
import re
import sqlite3

from hermes_constants import get_default_hermes_root
from hermes_cli.oma_campaigns.source import DEFAULT_CAMPAIGN_MODE, _member, read_mapping

_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _blocked(home: Path, campaign: str, *, profile: str | None = None,
             cron: bool = False, task_id: str | None = None) -> bool:
    if not _ID.fullmatch(campaign):
        return False
    path = home / "oma" / "campaigns" / campaign / "config.yaml"
    try:
        if path.resolve() != path.absolute():
            return True
        run = read_mapping(_member(path.parent, path.name))
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    if run.get("id") != campaign:
        return True
    roster = run.get("agents", [])
    if not isinstance(roster, list):
        return True
    if profile is not None and profile not in roster:
        return False
    mode = run.get("mode", DEFAULT_CAMPAIGN_MODE)
    if mode not in ("yolo", "approve", "control") or (cron and mode == "control"):
        return True
    installed = run.get("installation_state") == "installed"
    if run.get("installation_state") == "installing" or run.get(
        "lifecycle_state", "resumed" if installed else "paused") != "resumed":
        return True
    if task_id is not None and mode == "control":
        from hermes_cli.oma_campaigns.publications import human_approved_task
        return not human_approved_task(path.parent, task_id)
    return False


def profile_work_paused(home: Path, *, cron: bool = False) -> bool:
    home = Path(home)
    if home.parent.name != "profiles" or "__" not in home.name:
        return False
    return _blocked(home.parent.parent, home.name.split("__", 1)[0], profile=home.name, cron=cron)


def profile_cron_disabled(home: Path) -> bool:
    home = Path(home)
    if home.parent.name != "profiles" or "__" not in home.name:
        return False
    campaign = home.name.split("__", 1)[0]
    path = home.parent.parent / "oma" / "campaigns" / campaign / "config.yaml"
    try:
        config = read_mapping(_member(path.parent, path.name))
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    return home.name in config.get("agents", []) and config.get("mode") == "control"


def campaign_cron_paused(home: Path, job: dict | None = None) -> bool:
    if not profile_work_paused(home, cron=True):
        return False
    if profile_work_paused(home) or not profile_cron_disabled(home):
        return True
    from hermes_cli.oma_campaigns.analytics_cron import analyst_profile, is_managed_job

    return not (analyst_profile(home) if job is None else is_managed_job(home, job))


def board_work_paused(conn: sqlite3.Connection, *, task_id: str | None = None) -> bool:
    # Claim paths can be called without a board slug; use the DB the caller actually opened.
    for _, name, filename in conn.execute("PRAGMA database_list"):
        if name != "main" or not filename:
            continue
        path = Path(filename)
        if path.parent.parent.name == "boards" and path.parent.name.startswith("campaign-"):
            return _blocked(get_default_hermes_root(), path.parent.name.removeprefix("campaign-"), task_id=task_id)
    return False
