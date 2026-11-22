"""Canonical OMA integrations and read-only Composio readiness checks."""

import asyncio
from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path
from urllib.parse import urlsplit

from agent.runtime_scope import bind_profile_scope
from hermes_cli.config_effective import load_user_config_effective
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping

_COMPOSIO_HOSTS = {"connect.composio.dev", "mcp.composio.dev", "backend.composio.dev"}


@lru_cache(maxsize=1)
def integration_catalog() -> dict:
    resource = files("hermes_cli.oma_campaigns").joinpath("schemas", "integrations.json")
    return json.loads(resource.read_text(encoding="utf-8-sig"))


def brand_candidates(home: Path) -> dict:
    path = _member(_member(_member(home, "oma"), "brand"), "config.yaml")
    try:
        record = read_mapping(path)
    except FileNotFoundError:
        return {"candidates": [], "unmapped": []}
    validate_record("brand", record, path)
    catalog = integration_catalog()
    aliases = {
        alias: key for key, row in catalog.items()
        for alias in (key, key.replace("-", "_"), row["composio"], *row.get("aliases", ()))
        if alias
    }
    observed = {key for key, row in record.get("integrations", {}).items() if row["status"] == "observed"}
    observed.update(row["platform"] for row in record.get("channels", {}).get("social", ())
                    if row["status"] == "verified")
    canonical = {aliases.get(key, key.replace("_", "-")) for key in observed}
    supported = {key for key in canonical if catalog.get(key, {}).get("composio")}
    return {"candidates": sorted(supported), "unmapped": sorted(canonical - supported)}


def missing_integrations(home: Path, required: list[str], *, connection_home: Path | None = None) -> list[str]:
    if not required:
        return []
    catalog = integration_catalog()
    candidates = set(brand_candidates(home)["candidates"])
    slugs = {key: catalog[key]["composio"] for key in required if key in candidates}
    active = active_composio_toolkits(connection_home or home, {
        slug: catalog[key]["name"] for key, slug in slugs.items()
    }) if slugs else set()
    return [key for key in required if slugs.get(key) not in active]


def _active_connections(payload: object) -> set[str]:
    if not isinstance(payload, dict) or payload.get("successful") is False or payload.get("error"):
        return set()
    data = payload.get("data", payload)
    rows = data.get("toolkit_connection_statuses") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return set()
    slugs = [row["toolkit"] for row in rows if isinstance(row, dict) and isinstance(row.get("toolkit"), str)]
    return {row["toolkit"] for row in rows if isinstance(row, dict)
            and isinstance(row.get("toolkit"), str) and slugs.count(row["toolkit"]) == 1
            and row.get("has_active_connection") is True}


async def _search_composio(url: str, headers: dict, queries: dict[str, str]) -> set[str]:
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    # The router provides account status; never call MANAGE_CONNECTIONS (which can start OAuth).
    async with asyncio.timeout(15), httpx2.AsyncClient(headers=headers, follow_redirects=False) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool("COMPOSIO_SEARCH_TOOLS", {
                    "queries": [{"use_case": f"Read the current account or property in {name} ({slug})."}
                                for slug, name in queries.items()],
                    "session": {"generate_id": True},
                })
                if result.isError:
                    return set()
                payload = result.structuredContent
                if payload is None and len(result.content) == 1 and result.content[0].type == "text":
                    payload = json.loads(result.content[0].text)
                return _active_connections(payload) & queries.keys()


def active_composio_toolkits(home: Path, queries: dict[str, str]) -> set[str]:
    try:
        with bind_profile_scope(home):
            config = load_user_config_effective(home / "config.yaml", fail_closed=True)
        server = config.get("mcp_servers", {}).get("composio", {})
        if not server or server.get("enabled", True) is not True or server.get("command"):
            return set()
        url = server.get("url", "")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in _COMPOSIO_HOSTS or parsed.username is not None
                or parsed.port not in (None, 443) or "${" in url):
            return set()
        headers = server.get("headers", {})
        if not isinstance(headers, dict) or any(not isinstance(value, str) or "${" in value for value in headers.values()):
            return set()
        return asyncio.run(_search_composio(url, headers, queries))
    except Exception:  # health: allow BLE001 -- fail closed without emitting sensitive URL/header diagnostics
        return set()
