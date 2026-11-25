"""Campaign analytics must retain typed observations and never splice campaign datasets."""

from pathlib import Path

import pytest

from hermes_cli.oma_campaigns.analytics import list_analytics, save_observations
from hermes_cli.oma_campaigns import analytics_sources


def test_campaign_analytics_keeps_flexible_values_and_upserts(tmp_path: Path):
    for slug in ("seo", "social"):
        campaign = tmp_path / "oma" / "campaigns" / slug
        campaign.mkdir(parents=True)
        (campaign / "config.yaml").write_text(
            f"id: {slug}\nname: Campaign\ndescription: Example\n"
            f"orchestrator: {slug}__orchestrator\nagents: [{slug}__orchestrator]\n",
            encoding="utf-8",
        )
    base = {"source": "search", "account": "property-1", "metric": "clicks",
            "period_start": "2026-01-01", "period_end": "2026-01-02", "unit": "count",
            "dimensions": {"country": "US", "segments": ["mobile"]}}
    save_observations(tmp_path, "seo", [{**base, "value": 12},
                                        {**base, "metric": "report", "value": {"rank": 3.4, "sampled": False}}])
    save_observations(tmp_path, "seo", [{**base, "value": 14}])
    assert (tmp_path / "oma/campaigns/seo/data.sqlite3").is_file()
    result = list_analytics(tmp_path, "seo", source="search", metric="clicks", account="property-1",
                            start="2026-01-01", end="2026-01-02")
    [item] = result["observations"]
    assert item["value"] == 14
    assert item["dimensions"] == base["dimensions"]
    assert list_analytics(tmp_path, "seo", metric="report")["observations"][0]["value"] == {
        "rank": 3.4, "sampled": False,
    }
    assert list_analytics(tmp_path, "social")["observations"] == []
    assert not (tmp_path / "oma/campaigns/social/data.sqlite3").exists()


def test_google_analytics_adapters_preserve_daily_grain_and_metric_units(monkeypatch):
    from datetime import date

    calls = []

    def report(url, token, payload):
        calls.append((url, token, payload))
        if "analyticsdata.googleapis.com" in url:
            return {"metadata": {"timeZone": "UTC"}, "rows": [{
                "dimensionValues": [{"value": "20260101"}],
                "metricValues": [{"value": value} for value in ("10", "5", "20", "2")],
            }]}
        return {"rows": [{"keys": ["2026-01-01"], "clicks": 7, "impressions": 20, "ctr": 0.35, "position": 3.2}]}

    monkeypatch.setattr(analytics_sources, "_report", report)
    rows = analytics_sources._ga4("123", "fixture", date(2026, 1, 2))
    rows += analytics_sources._search_console("sc-domain:example.test", "fixture", date(2026, 1, 2))
    assert {row["period_start"] for row in rows} == {"2026-01-01"}
    assert {row["period_end"] for row in rows} == {"2026-01-02"}
    assert {row["metric"]: (row["value"], row["unit"]) for row in rows}["ctr"] == (0.35, "ratio")
    assert {row["account"] for row in rows} == {"123", "sc-domain:example.test"}
    assert "/properties/123:runReport" in calls[0][0]
    assert "/sites/sc-domain%3Aexample.test/searchAnalytics/query" in calls[1][0]
    with pytest.raises(ValueError, match="source binding"):
        analytics_sources.validate_bindings([{ "source": "google-analytics", "account": "123",
                                               "token_env": "OPENROUTER_API_KEY"}])
