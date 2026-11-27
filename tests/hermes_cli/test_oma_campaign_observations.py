"""Campaign analytics retains saved observations but no longer polls providers."""

from datetime import datetime
import io
import json

import pytest

from hermes_cli.oma_campaigns.analytics import AnalyticsError, last_refresh, list_analytics, save_observations
from hermes_cli.oma_campaigns.analytics_cron import JOB_ID, analytics_status, ensure_job, refresh_publications
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.storage import connect_campaign_data
from hermes_yaml import safe_dump
from tests import oma_campaign_fixtures

bundle = oma_campaign_fixtures.bundle


def test_start_provisions_legacy_campaign_analyst_with_analytics_skills(bundle, tmp_path):
    from agent.runtime_scope import bind_profile_scope
    from cron.jobs import list_jobs, parse_schedule, use_cron_store
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping
    from tools.skills_tool import skill_view

    home, source, main = bundle
    path = source / "campaigns/demo/config.yaml"
    atomic_config_write(path, {**read_mapping(path), "model": "provider/test-model"})
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__analyst"
    profile.rename(tmp_path / "old-analyst")
    record = read_mapping(path)
    atomic_config_write(path, {**record, "agents": [name for name in record["agents"] if name != profile.name]})
    assert main(["lifecycle", "demo", "resumed"]) == 0
    assert profile.name in read_mapping(path)["agents"]
    with bind_profile_scope(profile, hydrate_secrets=False), use_cron_store(profile):
        [job] = list_jobs(include_disabled=True)
        assert (job["id"], job["schedule"], job["no_agent"]) == (JOB_ID, parse_schedule("every 6h"), False)
        for name in ("ga4-analytics", "google-search-analytics", "social-media-analytics",
                     "composio-analytics", "analytics-dataset"):
            result = json.loads(skill_view(name, preprocess=False))
            assert result["success"], result


def test_analyst_can_save_and_read_observations_only_for_own_campaign(tmp_path, monkeypatch, capsys):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.oma_campaigns.__main__ import main

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    analyst = tmp_path / "profiles/demo__analyst"
    analyst.mkdir(parents=True)
    for campaign_id in ("demo", "other"):
        campaign = tmp_path / "oma/campaigns" / campaign_id
        campaign.mkdir(parents=True)
        (campaign / "config.yaml").write_text(safe_dump({"id": campaign_id, "installation_state": "installed",
                                                         "agents": [f"{campaign_id}__analyst"]}), encoding="utf-8")
    row = {"source": "google-analytics", "account": "property-1", "metric": "sessions", "unit": "count",
           "period_start": "2026-01-01", "period_end": "2026-01-02", "dimensions": {}, "value": 14}
    with bind_profile_scope(analyst, hydrate_secrets=False):
        for target, source in (("other", "google-analytics"), ("demo", "oma-publications")):
            monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([{**row, "source": source}])))
            assert main(["analytics-save", target]) == 1
            assert capsys.readouterr().err
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([row])))
        assert main(["analytics-save", "demo"]) == 0
        assert json.loads(capsys.readouterr().out)["saved"] == 1
        assert main(["analytics-read", "demo", "--source", "google-analytics", "--metric", "sessions"]) == 0
        [saved] = json.loads(capsys.readouterr().out)["observations"]
        assert (saved["account"], saved["value"]) == ("property-1", 14)
        assert main(["analytics-read", "other"]) == 1
    assert not (tmp_path / "oma/campaigns/other/data.sqlite3").exists()
    assert last_refresh(tmp_path / "oma/campaigns/demo")["last_successful_refresh_at"] is None


def test_managed_refresh_counts_local_publications_without_discovering_mcp(tmp_path, monkeypatch):
    campaign = tmp_path / "oma/campaigns/demo"
    campaign.mkdir(parents=True)
    profile = tmp_path / "profiles/demo__analyst"
    profile.mkdir(parents=True)
    config = {"id": "demo", "name": "Demo", "description": "Campaign fixture",
              "installation_state": "installed", "lifecycle_state": "resumed",
              "orchestrator": "demo__orchestrator", "agents": [profile.name, "demo__orchestrator"],
              "integrations": ["google-analytics", "google-search-console", "stripe"],
              "analytics_datasets": {"retired": {"tool": "never-call"}}}
    path = campaign / "config.yaml"
    path.write_text(safe_dump(config), encoding="utf-8")
    brand = tmp_path / "oma/brand"
    brand.mkdir()
    (brand / "config.yaml").write_text("website: {status: verified, url: 'https://example.test/'}", encoding="utf-8")
    (profile / "config.yaml").write_text("mcp_servers: {composio: {command: 'unused'}}\n", encoding="utf-8")

    def unexpected_mcp(*args, **kwargs):
        pytest.fail("Local refresh must not discover any provider tools")

    monkeypatch.setattr("tools.mcp_tool_discovery.discover_mcp_tools", unexpected_mcp)
    with connect_campaign_data(campaign, write=True) as conn:
        conn.execute("""INSERT INTO publications(id, revision, status, created_at, updated_at, result)
                        VALUES ('one', 1, 'published', '2020-01-01', '2020-01-02', ?)""",
                     ('{"published_at":"2020-01-02"}',))

    save_observations(tmp_path, "demo", [{
        "source": "google-analytics", "account": "property-1", "metric": "sessions", "unit": "count",
        "period_start": "2020-01-01", "period_end": "2020-01-02", "dimensions": {}, "value": 14,
    }])
    previous = list_analytics(tmp_path, "demo", source="google-analytics")["observations"]
    from cron.jobs import get_job, use_cron_store

    ensure_job(profile)
    with use_cron_store(profile):
        job = get_job(JOB_ID)
    assert job is not None
    assert refresh_publications(profile, job) == 2
    rows = list_analytics(tmp_path, "demo", source="oma-publications")["observations"]
    assert {(row["metric"], datetime.fromisoformat(row["period_start"]).date().isoformat(), row["value"]) for row in rows} == {
        ("drafts_created", "2020-01-01", 1), ("published", "2020-01-02", 1),
    }
    assert list_analytics(tmp_path, "demo", source="google-analytics")["observations"] == previous
    status = analytics_status(tmp_path, "demo")
    assert status["last_successful_refresh_at"]
    assert "datasets" not in status
    path.write_text(safe_dump({**config, "lifecycle_state": "paused"}), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="stopped"):
        refresh_publications(profile, job)
    assert last_refresh(campaign)["last_successful_refresh_at"] == status["last_successful_refresh_at"]


def test_retired_dataset_setting_is_inert_on_an_installed_campaign(tmp_path):
    record = {"id": "demo", "name": "Demo", "description": "Demo", "orchestrator": "demo__orchestrator",
              "agents": ["demo__orchestrator"], "analytics_datasets": {"old": "unused"}}
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_record("campaign", record, tmp_path)
    validate_record("campaign", {**record, "installation_state": "installed"}, tmp_path)


def test_campaign_observations_keep_flexible_values_and_upsert(tmp_path):
    for slug in ("seo", "social"):
        campaign = tmp_path / "oma" / "campaigns" / slug
        campaign.mkdir(parents=True)
        (campaign / "config.yaml").write_text(f"id: {slug}\n", encoding="utf-8")
    base = {"source": "search", "account": "property-1", "metric": "clicks", "period_start": "2026-01-01",
            "period_end": "2026-01-02", "unit": "count", "dimensions": {"country": "US"}}
    save_observations(tmp_path, "seo", [{**base, "value": 12},
                                        {**base, "metric": "report", "value": {"rank": 3.4, "sampled": False}},
                                        {**base, "value": 5, "dimensions": {"breakdown": "page", "page": "/"}}])
    save_observations(tmp_path, "seo", [{**base, "value": 14}])
    [row] = list_analytics(tmp_path, "seo", metric="clicks")["observations"]
    assert (row["value"], row["dimensions"]) == (14, {"country": "US"})
    assert list_analytics(tmp_path, "seo", metric="report")["observations"][0]["value"] == {
        "rank": 3.4, "sampled": False,
    }
    [breakdown] = list_analytics(tmp_path, "seo", breakdown="page")["observations"]
    assert breakdown["value"] == 5
    assert list_analytics(tmp_path, "social")["observations"] == []
    assert not (tmp_path / "oma/campaigns/social/data.sqlite3").exists()
