"""Read-only reports through the campaign analyst's native MCP servers."""

from datetime import date, datetime, timedelta
import json
from math import isfinite
import re
from urllib.parse import SplitResult, urlsplit

from hermes_cli.oma_campaigns.analytics import AnalyticsError

_MULTI_EXECUTE = "COMPOSIO_MULTI_EXECUTE_TOOL"
_COMPOSIO_METADATA = {"COMPOSIO_SEARCH_TOOLS", "COMPOSIO_GET_TOOL_SCHEMAS"}
_GSC = "google-search-console"
_GA4 = "google-analytics"
_GSC_TOOLS = ("GOOGLE_SEARCH_CONSOLE_LIST_SITES", "GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY")
_GA4_TOOLS = ("GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES", "GOOGLE_ANALYTICS_LIST_DATA_STREAMS",
              "GOOGLE_ANALYTICS_RUN_REPORT")
_MAX_PROPERTIES = 12


def observation(source: str, account: str, metric: str, day: date, value, unit: str, **dimensions) -> dict:
    return dict(source=source, account=account, metric=metric, period_start=day.isoformat(),
                period_end=(day + timedelta(days=1)).isoformat(), value=value, unit=unit, dimensions=dimensions)


def _object(value) -> dict:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Expected an MCP report object.")
    return value


def _payload(value: dict) -> dict:
    if value.get("error") or value.get("successful") is False or value.get("success") is False:
        raise ValueError("Read-only MCP tool returned an error.")
    return _object(value.get("data", value))


class _Reports:
    def __init__(self, configs: dict[str, dict], check_active, *, pinned_composio: bool,
                 composio_needs_sync: bool):
        from tools.mcp_tool_discovery import discover_mcp_tools
        from tools.registry import registry

        check_active()
        servers = list(configs)
        discovered = set(discover_mcp_tools(servers)) if servers else set()
        self.tools = {server: discovered.intersection(registry.get_tool_names_for_toolset(f"mcp-{server}"))
                      for server in servers}
        self.check_active = check_active
        self.pinned_composio = pinned_composio
        self.composio_needs_sync = composio_needs_sync
        self.scoped_url = configs.get("composio", {}).get("url") if pinned_composio else None

    def direct_reader(self, server: str, slugs: tuple[str, ...]):
        from tools.mcp_tool_handlers import _tool_is_read_only
        from tools.mcp_tool_schema import mcp_prefixed_tool_name

        names = {slug: mcp_prefixed_tool_name(server, slug) for slug in slugs}
        if not all(name in self.tools.get(server, ()) and _tool_is_read_only(server, slug)
                   for slug, name in names.items()):
            return None
        def read(slug, args):
            if not _tool_is_read_only(server, slug):
                raise ValueError("MCP tool is no longer declared read-only.")
            return self._call(names[slug], args)

        return read

    def reader(self, slugs: tuple[str, ...]):
        from tools.mcp_tool_schema import mcp_prefixed_tool_name

        direct, routers = [], []
        for server, tools in self.tools.items():
            names = {slug: mcp_prefixed_tool_name(server, slug) for slug in slugs}
            if set(names.values()) <= tools:
                direct.append(names)
            multi = mcp_prefixed_tool_name(server, _MULTI_EXECUTE)
            if multi in tools and (not self.pinned_composio or server == "composio"):
                routers.append(multi)
        if len(direct) == 1:
            return lambda slug, args: self._call(direct[0][slug], args)
        if not direct and len(routers) == 1:
            return lambda slug, args: self._call_composio(routers[0], slug, args)
        raise ValueError("No unique MCP connection exposes the required read tools.")

    def composio_metadata(self, server: str, slug: str):
        """Only the fixed metadata actions can use the documented Composio fallback."""
        from tools.mcp_tool_schema import mcp_prefixed_tool_name

        name = mcp_prefixed_tool_name(server, slug)
        if slug in _COMPOSIO_METADATA and name in self.tools.get(server, ()):
            return lambda _slug, args: self._call(name, args)
        return None

    def composio_reader(self, server: str, slugs: frozenset[str], session: str, account: str | None):
        """Route only the independently verified read actions in this discovery pass."""
        from tools.mcp_tool_schema import mcp_prefixed_tool_name

        multi = mcp_prefixed_tool_name(server, _MULTI_EXECUTE)
        if multi not in self.tools.get(server, ()):
            return None

        def read(slug, args):
            if slug not in slugs:
                raise ValueError("Composio action is outside the analytics read set.")
            return self._call_composio(multi, slug, args, session=session, account=account)

        return read

    def _call(self, name: str, args: dict) -> dict:
        from tools.registry import registry

        self.check_active()
        result = _object(registry.dispatch(name, args))
        if result.get("error") or result.get("truncated"):
            raise ValueError("MCP read failed or returned a truncated result.")
        return _payload(_object(result.get("structuredContent", result.get("result", result))))

    def _call_composio(self, name: str, slug: str, args: dict, *, session: str | None = None,
                       account: str | None = None) -> dict:
        tool = {"tool_slug": slug, "arguments": args}
        if account is not None:
            tool["account"] = account
        request = {"tools": [tool], "sync_response_to_workbench": False, "current_step": "READING_ANALYTICS"}
        if session is not None:
            request["session_id"] = session
        data = self._call(name, request)
        if data.get("remote_file_info"):
            raise ValueError("Composio did not return the complete analytics page inline.")
        [result] = data["results"]
        if result.get("error") or result.get("tool_slug") != slug:
            raise ValueError("MCP response did not match the requested tool.")
        response = _object(result["response"])
        value = response.get("data", response)
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, list) and not (response.get("error") or response.get("successful") is False
                                              or response.get("success") is False):
            page = {key: response[key] for key in ("next_cursor", "next_page_token", "nextPageToken", "has_more")
                    if key in response}
            return {**page, "items": value}
        return _payload(response)


def _site(url: str) -> tuple[SplitResult, str]:
    parsed = urlsplit(url)
    host = parsed.hostname
    if parsed.scheme not in ("https", "http") or not host or parsed.username is not None:
        raise ValueError("Expected a verified website URL.")
    return parsed, host


def _number(value) -> float:
    if isinstance(value, bool):
        raise ValueError("Expected a numeric metric.")
    number = float(value)
    if not isfinite(number):
        raise ValueError("Invalid numeric metric.")
    return number


def _search_property(read, website: str) -> str:
    parsed, host = _site(website)
    domain = f"sc-domain:{host.removeprefix('www.')}"
    prefix = parsed._replace(query="", fragment="").geturl().rstrip("/") + "/"
    candidates = (domain, f"sc-domain:{host}", prefix)
    sites = {site["siteUrl"] for site in read(_GSC_TOOLS[0], {}).get("siteEntry", [])
             if site.get("permissionLevel") in {"siteOwner", "siteFullUser", "siteRestrictedUser"}
             and site["siteUrl"] in candidates}
    account = next((candidate for candidate in candidates if candidate in sites), None)
    if account is None:
        raise ValueError("No verified Search Console property matches the campaign website.")
    return account


def _report_day(day: date, start: date, end: date) -> date:
    if not start <= day <= end:
        raise ValueError("Analytics provider returned a date outside the requested window.")
    return day


def search_page(read, account: str, start: date, end: date, dimensions: tuple[str, ...], offset: int,
                limit: int = 100) -> tuple[list[dict], int | None]:
    data = read(_GSC_TOOLS[1], {
        "site_url": account, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "dimensions": ["date", *dimensions], "row_limit": limit, "start_row": offset, "data_state": "all",
    })
    rows = data.get("rows", [])
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError("Invalid analytics report page.")
    observations = []
    for row in rows:
        day, *values = row["keys"]
        tags = dict(zip(dimensions, values, strict=True))
        if dimensions:
            tags["breakdown"] = ",".join(dimensions)
        report_day = _report_day(date.fromisoformat(day), start, end)
        observations.extend(observation(_GSC, account, name, report_day, _number(row[name]), unit,
                                        timezone="America/Los_Angeles", **tags)
                            for name, unit in (("clicks", "count"), ("impressions", "count"),
                                               ("ctr", "ratio"), ("position", "position")))
    return observations, offset + len(rows) if len(rows) == limit else None


def _ga4_property(read, website: str) -> str:
    hostname = _site(website)[1].removeprefix("www.")
    data = read(_GA4_TOOLS[0], {"pageSize": 200})
    properties = {prop["property"] for account in data.get("accountSummaries", [])
                  for prop in account.get("propertySummaries", [])
                  if re.fullmatch(r"properties/[0-9]{1,20}", prop["property"])}
    if data.get("nextPageToken") or len(properties) > _MAX_PROPERTIES:
        raise ValueError("GA4 property discovery exceeded the collector budget.")
    matches = []
    for prop in sorted(properties):
        streams = read(_GA4_TOOLS[1], {"parent": prop, "pageSize": 200})
        if streams.get("nextPageToken"):
            raise ValueError("GA4 stream discovery exceeded the collector budget.")
        urls = [s.get("webStreamData", {}).get("defaultUri") for s in streams.get("dataStreams", [])]
        if any(_site(url)[1].removeprefix("www.") == hostname for url in urls if url):
            matches.append(prop)
    if len(matches) != 1:
        raise ValueError("Could not uniquely match the campaign website to a GA4 property.")
    return matches[0]


def ga4_page(read, prop: str, start: date, end: date, dimensions: tuple[str, ...], offset: int,
             limit: int = 100) -> tuple[list[dict], int | None]:
    metrics = ("eventCount", "keyEvents") if dimensions == ("eventName",) else (
        "sessions", "activeUsers", "screenPageViews", "keyEvents")
    groups = ("date", *dimensions)
    data = read(_GA4_TOOLS[2], {
        "property": prop, "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": name} for name in groups], "metrics": [{"name": name} for name in metrics],
        "orderBys": [{"dimension": {"dimensionName": name}} for name in groups],
        "offset": offset, "limit": limit,
    })
    rows = data.get("rows", [])
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError("Invalid analytics report page.")
    observations = []
    for row in rows:
        day, *values = [part["value"] for part in row["dimensionValues"]]
        tags = dict(zip(dimensions, values, strict=True))
        if dimensions:
            tags["breakdown"] = ",".join(dimensions)
        report_day = _report_day(datetime.strptime(day, "%Y%m%d").date(), start, end)
        observations.extend(observation(_GA4, prop.split("/")[1], name, report_day, _number(value["value"]), "count",
                                        timezone=data.get("metadata", {}).get("timeZone"), **tags)
                            for name, value in zip(metrics, row["metricValues"], strict=True))
    following = offset + len(rows)
    return observations, following if following < int(data.get("rowCount", following)) else None


def _same_campaign_connection(saved: dict, active: dict) -> bool:
    from hermes_cli.config import _expand_env_vars
    from tools.mcp_tool_registration import _connection_identity

    # Compare the campaign's saved routing and credentials in the Analyst scope.
    # Working directory and identity headers also affect the actual transport.
    saved = _expand_env_vars(saved)
    return _connection_identity(saved) == _connection_identity(active) and all(
        saved.get(key) == active.get(key) for key in ("cwd", "identity_header")
    )


def discover_reports(check_active, campaign_servers: dict) -> _Reports:
    from hermes_cli.config import load_config
    from tools.mcp_tool_common import mcp_server_enabled

    configured = load_config().get("mcp_servers")
    servers = {name: server for name, server in configured.items()
               if isinstance(server, dict) and mcp_server_enabled(server)} if isinstance(configured, dict) else {}
    pinned = "composio" in campaign_servers
    needs_sync = pinned and not (
        "composio" in servers and _same_campaign_connection(campaign_servers["composio"], servers["composio"])
    )
    if needs_sync:
        servers.pop("composio", None)
    return _Reports(servers, check_active, pinned_composio=pinned, composio_needs_sync=needs_sync)
