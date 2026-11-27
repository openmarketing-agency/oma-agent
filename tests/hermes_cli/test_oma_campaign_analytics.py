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
                args = request["arguments"]
                dims = args["dimensions"]
                day = args["start_date"]
                keys = [day, *["landing-page" for _ in dims[1:]]]
                data = {"rows": [{"keys": keys, "clicks": 7, "impressions": 20, "ctr": .35, "position": 3.2}]}
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
        assert run_managed_job(profile, job) > 4
        refresh = last_refresh(campaign)
        assert refresh["last_successful_refresh_at"]
        config.write_text(safe_dump({"mcp_servers": {"composio": {**connector, "enabled": False}}}), encoding="utf-8")
        with pytest.raises(AnalyticsError, match="incomplete: google-search-console"):
            run_managed_job(profile, job)
        assert last_refresh(campaign) == refresh
    finally:
        shutdown_mcp_servers(scope=str(profile))
    from datetime import UTC, datetime

    rows = list_analytics(tmp_path, "seo", source="google-search-console", metric="clicks")["observations"]
    assert {(row["account"], row["value"]) for row in rows} == {("sc-domain:example.test", 7)}
    assert (datetime.now(UTC).date() - datetime.fromisoformat(rows[0]["period_start"]).date()).days > 9
    detailed = list_analytics(tmp_path, "seo", source="google-search-console", metric="clicks",
                              breakdown="page")["observations"]
    assert detailed[0]["dimensions"]["page"] == "landing-page"
    calls = [json.loads(line)["tool_slug"] for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls.count("GOOGLE_SEARCH_CONSOLE_LIST_SITES") == 1
    assert set(calls) == {"GOOGLE_SEARCH_CONSOLE_LIST_SITES", "GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY"}


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
    from hermes_cli.oma_campaigns.analytics_mcp import _ga4_property, ga4_page

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
        assert args["offset"] == 0
        return {"rowCount": 2, "metadata": {"timeZone": "UTC"}, "rows": [{
            "dimensionValues": [{"value": "20260101"}],
            "metricValues": [{"value": value} for value in ("10", "5", "20", "2")],
        }]}

    prop = _ga4_property(read, "https://www.example.test/")
    rows, next_offset = ga4_page(read, prop, date(2026, 1, 1), date(2026, 1, 2), (), 0)
    assert next_offset == 1
    assert {row["period_start"] for row in rows} == {"2026-01-01"}
    assert {row["period_end"] for row in rows} == {"2026-01-02"}
    assert {row["metric"]: (row["value"], row["unit"]) for row in rows}["sessions"] == (10, "count")
    assert {row["account"] for row in rows} == {"123"}
    assert calls == ["properties/123"]
    with pytest.raises(ValueError, match="uniquely match"):
        _ga4_property(read, "https://unrelated.test/")
    assert calls == ["properties/123"]


def test_discovered_and_configured_mcp_datasets_resume_and_remain_independent(tmp_path):
    from hermes_cli.oma_campaigns.analytics import AnalyticsError
    from hermes_cli.oma_campaigns.analytics_cron import COLLECTOR, JOB_ID, run_managed_job
    from hermes_cli.oma_campaigns.analytics_sync.data import coverage, list_records
    from hermes_yaml import safe_dump
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers

    campaign = tmp_path / "oma/campaigns/demo"
    campaign.mkdir(parents=True)
    profile = tmp_path / "profiles/demo__analyst"
    profile.mkdir(parents=True)
    contract = {
        "integration": "second-source", "server": "connector", "tool": "list_reports", "account": "team",
        "arguments": {"space": "campaign-team", "limit": 1}, "items": "reports", "record_id": "id",
        "pagination": {"kind": "offset", "parameter": "offset", "size_parameter": "limit"},
    }
    config = {"id": "demo", "name": "Demo", "description": "Campaign fixture",
              "installation_state": "installed", "lifecycle_state": "resumed",
              "orchestrator": "demo__orchestrator", "agents": [profile.name, "demo__orchestrator"],
              "integrations": ["first-source", "second-source", "uncovered-source", "github"],
              "analytics_datasets": {
                  "reports": contract, "unannotated": {**contract, "tool": "unannotated_action"},
              }}
    (campaign / "config.yaml").write_text(safe_dump(config), encoding="utf-8")
    fixture = tmp_path / "connector.py"
    fixture.write_text(dedent('''        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations

        server = MCPServer("campaign fixture")
        read = ToolAnnotations(readOnlyHint=True)

        @server.tool(annotations=read)
        def oma_analytics_list_datasets(campaign_id: str, integrations: list[str]) -> dict:
            assert campaign_id == "demo"
            return {"datasets": [
                {"integration": "first-source", "id": "events", "account_id": "account"},
                {"integration": "other-campaign", "id": "events", "account_id": "private"},
            ]}

        @server.tool(annotations=read)
        def oma_analytics_read_dataset(campaign_id: str, dataset_id: str, integration: str, account_id: str,
                                       limit: int, cursor: str = "", checkpoint: str = "") -> dict:
            assert (campaign_id, dataset_id, integration, account_id) == ("demo", "events", "first-source", "account")
            if checkpoint:
                assert checkpoint == "finished"
                return {"records": [{"id": "4", "data": {"visits": 22}}], "checkpoint": "finished"}
            number = int(cursor or "0") + 1
            page = {"records": [{"id": str(number), "data": {
                "visits": number, "api_key": "synthetic-secret",
                "url": "https://example.test/?api_key=synthetic-url-secret",
            }}]}
            page["next_cursor" if number < 4 else "checkpoint"] = str(number) if number < 4 else "finished"
            return page

        @server.tool(annotations=read)
        def list_reports(space: str, limit: int, offset: int = 0) -> dict:
            assert (space, limit) == ("campaign-team", 1)
            reports = [{"id": 9, "categories": ["search"], "count": 7}]
            return {"reports": reports[offset:offset + limit]}

        @server.tool(annotations=read)
        def COMPOSIO_SEARCH_TOOLS(queries: list[dict], session: dict, search_strategy: str) -> dict:
            assert "github toolkit" in queries[0]["use_case"]
            return {"toolkit_connection_statuses": [{"toolkit": "github", "has_active_connection": True,
                                                     "connection_details": {"connected_account_id": "account-github"}}]}

        @server.tool()
        def unannotated_action(space: str, limit: int, cursor: str = "") -> dict:
            return {"reports": [{"id": 99, "unexpected": True}]}

        server.run("stdio")
    '''), encoding="utf-8")
    mcp = {"mcp_servers": {"connector": {"command": sys.executable, "args": [str(fixture)]}}}
    (profile / "config.yaml").write_text(safe_dump(mcp), encoding="utf-8")
    job = {"id": JOB_ID, "script": COLLECTOR, "no_agent": True, "deliver": "local"}

    try:
        for expected in (3, 4, 4):
            with pytest.raises(AnalyticsError, match="incomplete: github, second-source, uncovered-source"):
                run_managed_job(profile, job)
            records = list_records(campaign, source="first-source", dataset="events")["records"]
            assert len(records) == expected
        assert records[0]["record"] == {"visits": 22}
        assert all("api_key" not in row["record"] for row in records)
        assert "synthetic-url-secret" not in json.dumps(records)
        assert not list_records(campaign, source="other-campaign", dataset="events")["records"]
        [summary] = list_records(campaign, source="second-source", dataset="reports")["records"]
        assert summary["record"] == {"id": 9, "categories": ["search"], "count": 7}
        states = {(row["source"], row["dataset"]): row["state"] for row in coverage(campaign)}
        assert states["first-source", "events"] == "current"
        assert states["uncovered-source", "integration"] == "unavailable"
        assert states["github", "integration"] == "no_readable_tools"
        assert states["second-source", "unannotated"] == "unavailable"
        assert not list_records(campaign, source="second-source", dataset="unannotated")["records"]
        page = list_records(campaign, source="first-source", dataset="events", limit=2)
        remainder = list_records(campaign, source="first-source", dataset="events", before=page["next_cursor"])
        assert [item["record_id"] for item in remainder["records"]] == ["2", "1"]
    finally:
        shutdown_mcp_servers(scope=str(profile))


def test_managed_analyst_collects_from_campaign_composio_without_dataset_configuration(tmp_path):
    from hermes_cli.oma_campaigns.analytics import AnalyticsError
    from hermes_cli.oma_campaigns.analytics_cron import COLLECTOR, JOB_ID, run_managed_job
    from hermes_cli.oma_campaigns.analytics_sync.data import coverage, list_records
    from hermes_yaml import safe_dump
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers

    campaign = tmp_path / "oma/campaigns/demo"
    campaign.mkdir(parents=True)
    profile = tmp_path / "profiles/demo__analyst"
    profile.mkdir(parents=True)
    brand = tmp_path / "oma/brand"
    brand.mkdir()
    (brand / "config.yaml").write_text("website: {status: verified, url: 'https://example.test/'}")
    fixture = tmp_path / "router.py"
    fixture.write_text(dedent('''\
        from mcp.server import MCPServer
        server = MCPServer("campaign Composio")

        def tool(toolkit, slug, properties=None, required=(), tags=()):
            result = {"toolkit": toolkit.upper(), "tool_slug": slug, "tags": list(tags)}
            if properties is not None:
                result["input_schema"] = {"type": "object", "properties": properties,
                                          "required": list(required), "additionalProperties": False}
            return result

        @server.tool()
        def COMPOSIO_SEARCH_TOOLS(queries: list[dict], session: dict, search_strategy: str) -> dict:
            assert session == {"generate_id": True}
            assert search_strategy == "tool_search" and len(queries) == 3
            github = "the github toolkit" in queries[0]["use_case"]
            toolkit = "github" if github else "stripe"
            github_tools = [
                {**tool("github", "GITHUB_LIST_REPOSITORIES"), "hasFullSchema": False,
                 "schemaRef": {"tool": "made_up_execute"}},
                tool("github", "GITHUB_GET_SITE_REPORT", {"site_url": {"type": "string"}},
                     ("site_url",), ("readOnlyHint",)),
                tool("github", "GITHUB_GET_REPO_REPORT", {"repository_id": {"type": "string"}},
                     ("repository_id",), ("readOnlyHint",)),
                tool("github", "GITHUB_DELETE_REPO", {}, tags=("readOnlyHint", "destructiveHint")),
                tool("github", "GITHUB_LIST_UNVERIFIED", {}),
                tool("stripe", "STRIPE_LIST_CHARGES", {}),
            ]
            stripe_tools = [tool("stripe", "STRIPE_LIST_CHARGES", {
                "limit": {"type": "integer"}, "starting_after": {"type": "string"},
            })]
            selected = github_tools if github else stripe_tools
            return {
                "session": {"id": f"session-{toolkit}"},
                "toolkit_connection_statuses": [{"toolkit": toolkit, "has_active_connection": True,
                                                 "accounts": [{"id": f"account-{toolkit}", "status": "ACTIVE"}]}],
                "tool_schemas": {item["tool_slug"]: item for item in selected},
            }

        @server.tool()
        def COMPOSIO_GET_TOOL_SCHEMAS(tool_slugs: list[str], session_id: str, include: list[str]) -> dict:
            assert (tool_slugs, session_id, include) == (
                ["GITHUB_LIST_REPOSITORIES"], "session-github", ["input_schema"],
            )
            entry = tool("github", "GITHUB_LIST_REPOSITORIES", {
                "page": {"type": "integer", "minimum": 1}, "per_page": {"type": "integer", "maximum": 100},
            })
            return {"tool_schemas": {entry["tool_slug"]: entry}}

        @server.tool()
        def COMPOSIO_MULTI_EXECUTE_TOOL(tools: list[dict], session_id: str,
                                        sync_response_to_workbench: bool, current_step: str) -> dict:
            assert not sync_response_to_workbench
            assert current_step == "READING_ANALYTICS"
            [request] = tools
            slug = request["tool_slug"]
            args = request["arguments"]
            toolkit = slug.split("_")[0].lower()
            assert (session_id, request["account"]) == (f"session-{toolkit}", f"account-{toolkit}")
            if slug == "GITHUB_LIST_REPOSITORIES":
                assert args["per_page"] == 20
                start = (args["page"] - 1) * args["per_page"]
                data = [{"id": i, "name": f"repository-{i}"} for i in range(start, min(start + 20, 61))]
            elif slug == "STRIPE_LIST_CHARGES":
                assert args["limit"] == 20
                item = "charge-2" if args.get("starting_after") == "charge-1" else "charge-1"
                data = {"data": [{"id": item, "amount": 55}], "has_more": item == "charge-1"}
            else:
                assert slug == "GITHUB_GET_SITE_REPORT" and args == {"site_url": "https://example.test/"}
                data = {"rows": [{"id": "observed", "clicks": 12}], "breakdown": {"desktop": 9, "mobile": 3},
                        "totals": {"clicks": 12}}
            return {"results": [{"tool_slug": slug, "response": {"successful": True, "data": data}}]}

        server.run("stdio")
    '''), encoding="utf-8")
    servers = {"composio": {"command": sys.executable, "args": [str(fixture)]}}
    config = {"id": "demo", "installation_state": "installed", "lifecycle_state": "resumed",
              "agents": [profile.name], "integrations": ["github", "stripe"], "mcp_servers": servers}
    (campaign / "config.yaml").write_text(safe_dump(config), encoding="utf-8")
    (profile / "config.yaml").write_text(safe_dump({"mcp_servers": servers}), encoding="utf-8")
    job = {"id": JOB_ID, "script": COLLECTOR, "no_agent": True, "deliver": "local"}

    try:
        assert run_managed_job(profile, job) == 64
        repos = list_records(campaign, source="github", dataset="github-list-repositories", limit=100)["records"]
        assert len(repos) == 60
        assert run_managed_job(profile, job) == 5
        repos = list_records(campaign, source="github", dataset="github-list-repositories", limit=100)["records"]
        assert len(repos) == 61 and repos[0]["record"]["name"] == "repository-60"
        charges = list_records(campaign, source="stripe", dataset="stripe-list-charges")["records"]
        assert [item["record_id"] for item in charges] == ["charge-2", "charge-1"]
        report_rows = list_records(campaign, source="github", dataset="github-get-site-report")["records"]
        report = {row["record_id"]: row["record"] for row in report_rows}
        assert report["observed"]["clicks"] == 12
        assert report["@oma-report-summary"] == {"breakdown": {"desktop": 9, "mobile": 3}, "totals": {"clicks": 12}}
        states = {row["dataset"]: row["state"] for row in coverage(campaign)}
        assert states["github-get-repo-report"] == "read_inputs_required"
        assert "github-delete-repo" not in states
        assert "github-list-unverified" not in states
        assert states["github-list-repositories"] == "current"

        shutdown_mcp_servers(scope=str(profile))
        overridden = {"composio": {**servers["composio"], "env": {"ACCOUNT_SCOPE": "different-session"}}}
        (profile / "config.yaml").write_text(safe_dump({"mcp_servers": overridden}), encoding="utf-8")
        with pytest.raises(AnalyticsError, match="incomplete: github, stripe"):
            run_managed_job(profile, job)
        integrations = {row["source"]: row["state"] for row in coverage(campaign) if row["dataset"] == "integration"}
        assert integrations == {"github": "connection_sync_required", "stripe": "connection_sync_required"}
    finally:
        shutdown_mcp_servers(scope=str(profile))
