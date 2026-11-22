"""Read the OMA lifecycle latch at the native admission boundaries."""

from pathlib import Path
import re
import sqlite3

from hermes_constants import get_default_hermes_root
from hermes_cli.oma_campaigns.source import _member, read_mapping

_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _blocked(home: Path, campaign: str, *, profile: str | None = None) -> bool:
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
    installed = run.get("installation_state") == "installed"
    return run.get("installation_state") == "installing" or run.get(
        "lifecycle_state", "resumed" if installed else "paused") != "resumed"


def profile_work_paused(home: Path) -> bool:
    home = Path(home)
    if home.parent.name != "profiles" or "__" not in home.name:
        return False
    return _blocked(home.parent.parent, home.name.split("__", 1)[0], profile=home.name)


def board_work_paused(conn: sqlite3.Connection) -> bool:
    # Claim paths can be called without a board slug; use the DB the caller actually opened.
    for _, name, filename in conn.execute("PRAGMA database_list"):
        if name != "main" or not filename:
            continue
        path = Path(filename)
        if path.parent.parent.name == "boards" and path.parent.name.startswith("campaign-"):
            return _blocked(get_default_hermes_root(), path.parent.name.removeprefix("campaign-"))
    return False
