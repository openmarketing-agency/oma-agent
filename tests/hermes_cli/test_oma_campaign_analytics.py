"""Campaign analytics must retain typed observations and never splice campaign datasets."""

import json
from pathlib import Path
import sys
from textwrap import dedent

import pytest

from hermes_cli.oma_campaigns.analytics import list_analytics, save_observations


def test_managed_analytics_reads_search_console_via_analyst_mcp(tmp_path):
    from hermes_cli.oma_campaigns.analytics import AnalyticsError, last_refresh
    from hermes_cli.oma_campaigns.analytics_cron import COLLECTOR, JOB_ID, run_managed_job
    from hermes_yaml import safe_dump
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers

    campaign = tmp_path / "oma/campaigns/seo"
    campaign.mkdir(parents=True)
    (campaign / "config.yaml").write_text(
        "id: seo\ninstallation_state: installed\nlifecycle_state: resumed\n"
        "agents: [seo__analyst]\nintegrations: [google-search-console]\n",
        encoding="utf-8",
    )
    brand = tmp_path / "oma/brand"
    brand.mkdir()
    (brand / "config.yaml").write_text("website: {status: verified, url: 'https://example.test/'}\n")
    profile = tmp_path / "profiles/seo__analyst"
    profile.mkdir(parents=True)
    config = profile / "config.yaml"
    fixture = tmp_path / "reports_server.py"
    fixture.write_text(dedent('''\
        import json, sys
        from pathlib import Path
        from mcp.server import MCPServer

        server = MCPServer("reports fixture")

        @server.tool()
        def COMPOSIO_MULTI_EXECUTE_TOOL(tools: list[dict], sync_response_to_workbench: bool, current_step: str) -> dict:
            assert not sync_response_to_workbench
            [request] = tools
            slug = request["tool_slug"]
            with Path(sys.argv[1]).open("a", encoding="utf-8") as receipt:
                receipt.write(json.dumps(request) + "\\n")
            if slug == "GOOGLE_SEARCH_CONSOLE_LIST_SITES":
                data = {"siteEntry": [{"siteUrl": "sc-domain:other.test", "permissionLevel": "siteOwner"},
                                      {"siteUrl": "sc-domain:example.test", "permissionLevel": "siteRestrictedUser"}]}
            else:
                assert slug == "GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY"
                assert request["arguments"]["site_url"] == "sc-domain:example.test"
                day = request["arguments"]["start_date"]
                data = {"rows": [{"keys": [day], "clicks": 7, "impressions": 20, "ctr": .35, "position": 3.2}]}
            return {"successful": True, "data": {"results": [
                {"index": 0, "tool_slug": slug, "response": {"successful": True, "data": data}},
            ]}}

        server.run("stdio")
    '''), encoding="utf-8")
    log = tmp_path / "mcp-calls.jsonl"
    connector = {"command": sys.executable, "args": [str(fixture), str(log)]}
    config.write_text(safe_dump({"mcp_servers": {"composio": connector}}), encoding="utf-8")
    (profile / ".env").write_text("OMA_ANALYTICS_GOOGLE_LEGACY=not-usable\n")
    record = tmp_path / "oma/agents/seo__analyst"
    record.mkdir(parents=True)
    (record / "config.yaml").write_text("analytics_sources: ignored\n")
    job = {"id": JOB_ID, "script": COLLECTOR, "no_agent": True, "deliver": "local"}
    try:
        assert run_managed_job(profile, job) == 4
        refresh = last_refresh(campaign)
        assert refresh["last_successful_refresh_at"]
        config.write_text(safe_dump({"mcp_servers": {"composio": {**connector, "enabled": False}}}), encoding="utf-8")
        with pytest.raises(AnalyticsError, match="incomplete: google-search-console"):
            run_managed_job(profile, job)
        assert last_refresh(campaign) == refresh
    finally:
        shutdown_mcp_servers(scope=str(profile))
    [row] = list_analytics(tmp_path, "seo", source="google-search-console", metric="clicks")["observations"]
    assert (row["account"], row["value"]) == ("sc-domain:example.test", 7)
    calls = [json.loads(line)["tool_slug"] for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls == ["GOOGLE_SEARCH_CONSOLE_LIST_SITES", "GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY"]


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


def test_ga4_reads_only_the_property_matching_the_verified_stream():
    from datetime import date
    from hermes_cli.oma_campaigns.analytics_mcp import _ga4

    calls = []
    def read(slug, args):
        if slug == "GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES":
            return {"accountSummaries": [{"propertySummaries": [{"property": f"properties/{p}"} for p in (123, 456)]}]}
        if slug == "GOOGLE_ANALYTICS_LIST_DATA_STREAMS":
            return {"dataStreams": [{"webStreamData": {"defaultUri": {
                "properties/123": "https://example.test", "properties/456": "https://other.test",
            }[args["parent"]]}}]}
        assert slug == "GOOGLE_ANALYTICS_RUN_REPORT"
        calls.append(args["property"])
        return {"metadata": {"timeZone": "UTC"}, "rows": [{
            "dimensionValues": [{"value": "20260101"}],
            "metricValues": [{"value": value} for value in ("10", "5", "20", "2")],
        }]}

    rows = _ga4(read, "https://www.example.test/", date(2026, 1, 2))
    assert {row["period_start"] for row in rows} == {"2026-01-01"}
    assert {row["period_end"] for row in rows} == {"2026-01-02"}
    assert {row["metric"]: (row["value"], row["unit"]) for row in rows}["sessions"] == (10, "count")
    assert {row["account"] for row in rows} == {"123"}
    assert calls == ["properties/123"]
    with pytest.raises(ValueError, match="uniquely match"):
        _ga4(read, "https://unrelated.test/", date(2026, 1, 2))
    assert calls == ["properties/123"]
