"""Collect and persist campaign observations without running an agent turn."""

from datetime import UTC, date, datetime
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from hermes_cli.oma_campaigns.analytics import AnalyticsError, campaign_dir, save_observations
from hermes_cli.oma_campaigns.analytics_mcp import observation
from hermes_cli.oma_campaigns.analytics_sync.collector import collect_integrations
from hermes_cli.oma_campaigns.analytics_sync.data import Dataset, mark_unseen, save_page
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping
from hermes_cli.oma_campaigns.storage import connect_campaign_data


def _publications(directory: Path, campaign_id: str) -> list[dict]:
    with connect_campaign_data(directory) as conn:
        rows = conn.execute("""
            SELECT substr(created_at,1,10) AS day, COUNT(*) AS total
            FROM publications GROUP BY day
        """).fetchall() if conn else []
        sent = conn.execute("""
            SELECT substr(json_extract(result,'$.published_at'),1,10) AS day, COUNT(*) AS total
            FROM publications WHERE status='published' AND json_extract(result,'$.published_at') IS NOT NULL GROUP BY day
        """).fetchall() if conn else []
    return [observation("oma-publications", campaign_id, metric, date.fromisoformat(row["day"]), row["total"], "count")
            for metric, group in (("drafts_created", rows), ("published", sent)) for row in group]


def _active(config_path: Path, cancel_event) -> dict:
    config = read_mapping(config_path)
    if (cancel_event is not None and cancel_event.is_set()) or config.get("lifecycle_state") != "resumed":
        raise AnalyticsError(409, "Analytics collection cancelled because the campaign is stopped.")
    return config


def collect(home: Path, campaign_id: str, profile: Path, cancel_event=None) -> int:
    from hermes_cli.oma_campaigns.install import _install_lock

    directory = campaign_dir(home, campaign_id)
    config_path = _member(directory, "config.yaml")
    config = _active(config_path, cancel_event)
    if "analytics_datasets" in config:
        validate_record("campaign", config, config_path)
    today = datetime.now(UTC).date()
    rows = _publications(directory, campaign_id)
    brand_path = _member(_member(_member(home, "oma"), "brand"), "config.yaml")
    website = read_mapping(brand_path).get("website", {}) if brand_path.is_file() else {}  # config-reader: ok — OMA record
    url = website.get("url", "") if isinstance(website, dict) and website.get("status") == "verified" else ""
    seen: set[Dataset] = set()

    def check_active() -> None:
        latest = _active(config_path, cancel_event)
        keys = ("integrations", "mcp_servers", "analytics_datasets")
        if any(latest.get(key) != config.get(key) for key in keys):
            raise AnalyticsError(409, "Campaign analytics settings changed during collection.")

    def persist(dataset, progress, state, **page) -> int:
        with _install_lock(config_path):
            check_active()
            count = save_page(directory, dataset, progress, state, **page)
            seen.add(dataset)
            return count

    with bind_profile_scope(profile):
        count, failures = collect_integrations(directory, config, url, today, check_active, persist)
    # No campaign lock or SQL connection is held across MCP calls.
    with _install_lock(config_path):
        check_active()
        mark_unseen(directory, seen)
        count += save_observations(home, campaign_id, rows, refresh_complete=not failures)
    if failures:
        raise AnalyticsError(503, "Analytics refresh was incomplete: " + ", ".join(sorted(failures)) + ".")
    return count
