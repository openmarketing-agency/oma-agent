"""Collect and persist campaign observations without running an agent turn."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from hermes_cli.oma_campaigns.analytics import AnalyticsError, campaign_dir, save_observations
from hermes_cli.oma_campaigns.analytics_mcp import collect_mcp, observation
from hermes_cli.oma_campaigns.source import _member, read_mapping
from hermes_cli.oma_campaigns.storage import connect_campaign_data


def _publications(directory: Path, campaign_id: str, today: date) -> list[dict]:
    first_day = today - timedelta(days=6)
    with connect_campaign_data(directory) as conn:
        rows = conn.execute("""
            SELECT substr(created_at,1,10) AS day, COUNT(*) AS total
            FROM publications WHERE created_at >= ? GROUP BY day
        """, (first_day.isoformat(),)).fetchall() if conn else []
        sent = conn.execute("""
            SELECT substr(json_extract(result,'$.published_at'),1,10) AS day, COUNT(*) AS total
            FROM publications WHERE status='published' AND json_extract(result,'$.published_at') >= ? GROUP BY day
        """, (first_day.isoformat(),)).fetchall() if conn else []
    return [observation("oma-publications", campaign_id, metric, date.fromisoformat(row["day"]), row["total"], "count")
            for metric, group in (("drafts_created", rows), ("published", sent)) for row in group]


def _active(config_path: Path, cancel_event) -> None:
    config = read_mapping(config_path)
    if (cancel_event is not None and cancel_event.is_set()) or config.get("lifecycle_state") != "resumed":
        raise AnalyticsError(409, "Analytics collection cancelled because the campaign is stopped.")


def collect(home: Path, campaign_id: str, profile: Path, cancel_event=None) -> int:
    from hermes_cli.oma_campaigns.install import _install_lock

    directory = campaign_dir(home, campaign_id)
    config_path = _member(directory, "config.yaml")
    _active(config_path, cancel_event)
    config = read_mapping(config_path)
    today = datetime.now(UTC).date()
    rows = _publications(directory, campaign_id, today)
    brand_path = _member(_member(_member(home, "oma"), "brand"), "config.yaml")
    website = read_mapping(brand_path).get("website", {}) if brand_path.is_file() else {}  # config-reader: ok — OMA record
    url = website.get("url", "") if isinstance(website, dict) and website.get("status") == "verified" else ""
    with bind_profile_scope(profile):
        measured, failures = collect_mcp(config.get("integrations", []), url, today,
                                         lambda: _active(config_path, cancel_event))
    rows.extend(measured)
    # No campaign lock or SQL connection is held across MCP calls.
    with _install_lock(config_path):
        _active(config_path, cancel_event)
        count = save_observations(home, campaign_id, rows, refresh_complete=not failures)
    if failures:
        raise AnalyticsError(503, "Analytics refresh was incomplete: " + ", ".join(sorted(set(failures))) + ".")
    return count
