"""Read-only reports through the campaign analyst's native MCP servers."""

from datetime import date, datetime, timedelta
import json
from math import isfinite
import re
from urllib.parse import SplitResult, urlsplit

from hermes_cli.oma_campaigns.analytics import AnalyticsError

_MULTI_EXECUTE = "COMPOSIO_MULTI_EXECUTE_TOOL"
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
    def __init__(self, servers: list[str], check_active):
        from tools.mcp_tool_discovery import discover_mcp_tools
        from tools.registry import registry

        check_active()
        discovered = set(discover_mcp_tools(servers))
        self.tools = {server: discovered.intersection(registry.get_tool_names_for_toolset(f"mcp-{server}"))
                      for server in servers}
        self.check_active = check_active

    def reader(self, slugs: tuple[str, ...]):
        from tools.mcp_tool_schema import mcp_prefixed_tool_name

        direct, routers = [], []
        for server, tools in self.tools.items():
            names = {slug: mcp_prefixed_tool_name(server, slug) for slug in slugs}
            if set(names.values()) <= tools:
                direct.append(names)
            multi = mcp_prefixed_tool_name(server, _MULTI_EXECUTE)
            if multi in tools:
                routers.append(multi)
        if len(direct) == 1:
            return lambda slug, args: self._call(direct[0][slug], args)
        if not direct and len(routers) == 1:
            return lambda slug, args: self._call_composio(routers[0], slug, args)
        raise ValueError("No unique MCP connection exposes the required read tools.")

    def _call(self, name: str, args: dict) -> dict:
        from tools.registry import registry

        self.check_active()
        result = _object(registry.dispatch(name, args))
        if result.get("error") or result.get("truncated"):
            raise ValueError("MCP read failed or returned a truncated result.")
        return _payload(_object(result.get("structuredContent", result.get("result", result))))

    def _call_composio(self, name: str, slug: str, args: dict) -> dict:
        # Never execute a tool advertised by provider output. These are the fixed read slugs from _ADAPTERS.
        data = self._call(name, {"tools": [{"tool_slug": slug, "arguments": args}],
                                 "sync_response_to_workbench": False, "current_step": "READING_ANALYTICS"})
        [result] = data["results"]
        if result.get("error") or result.get("tool_slug") != slug:
            raise ValueError("MCP response did not match the requested tool.")
        return _payload(_object(result["response"]))


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


def _search_console(read, website: str, today: date) -> list[dict]:
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
    data = read(_GSC_TOOLS[1], {
        "site_url": account, "start_date": (today - timedelta(days=9)).isoformat(), "end_date": today.isoformat(),
        "dimensions": ["date"], "row_limit": 10, "data_state": "all",
    })
    return [observation(_GSC, account, name, date.fromisoformat(row["keys"][0]), _number(row[name]), unit,
                        timezone="America/Los_Angeles")
            for row in data.get("rows", []) for name, unit in (
                ("clicks", "count"), ("impressions", "count"), ("ctr", "ratio"), ("position", "position"),
            )]


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


def _ga4(read, website: str, today: date) -> list[dict]:
    prop = _ga4_property(read, website)
    metrics = ("sessions", "activeUsers", "screenPageViews", "keyEvents")
    data = read(_GA4_TOOLS[2], {
        "property": prop, "dateRanges": [{"startDate": (today - timedelta(days=7)).isoformat(), "endDate": today.isoformat()}],
        "dimensions": [{"name": "date"}], "metrics": [{"name": name} for name in metrics], "limit": 10,
    })
    return [observation(_GA4, prop.split("/")[1], name,
                        datetime.strptime(row["dimensionValues"][0]["value"], "%Y%m%d").date(),
                        _number(value["value"]), "count", timezone=data.get("metadata", {}).get("timeZone"))
            for row in data.get("rows", []) for name, value in zip(metrics, row["metricValues"], strict=True)]


_ADAPTERS = {_GSC: (_GSC_TOOLS, _search_console), _GA4: (_GA4_TOOLS, _ga4)}


def collect_mcp(integrations: list[str], website: str, today: date, check_active) -> tuple[list[dict], list[str]]:
    from hermes_cli.config import load_config
    from tools.mcp_tool_common import mcp_server_enabled

    sources = [source for source in _ADAPTERS if source in integrations]
    if not sources or not website:
        return [], sources
    configured = load_config().get("mcp_servers")
    if not isinstance(configured, dict):
        return [], sources
    servers = [name for name, server in configured.items()
               if isinstance(server, dict) and mcp_server_enabled(server)]
    if not servers:
        return [], sources
    reports = _Reports(servers, check_active)
    rows, failed = [], []
    for source in sources:
        slugs, adapter = _ADAPTERS[source]
        try:
            rows.extend(adapter(reports.reader(slugs), website, today))
        except AnalyticsError:
            raise  # Stop/cancellation is not an ordinary source error.
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
            failed.append(source)
    return rows, failed
