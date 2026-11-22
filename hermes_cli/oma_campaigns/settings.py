"""Resolve native Hermes settings shared by a campaign and its agents."""

import re
from pathlib import Path

from agent.secret_scope import _is_global_env
from hermes_cli.config import cfg_get, validate_env_var_name_for_write
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping


SETTINGS = ("model", "mcp_servers")
ENV_REFERENCE = re.compile(r"\$\{\s*(?:env:\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\}")
_OMITTED = object()
_TOOLSET_LISTS = (
    ("agent", "enabled_toolsets"), ("agent", "disabled_toolsets"),
    ("tools", "tool_search", "eager_toolsets"), ("tools", "tool_search", "defer_toolsets"),
)
_TOOL_SEARCH_SWITCHES = (("tools", "tool_search", "enabled"), ("tools", "tool_search", "listing"))


def credential_keys(effective: dict) -> set[str]:
    servers = [server for server in effective.get("mcp_servers", {}).values() if server.get("enabled") is not False]
    pending = [effective.get("model"), *servers]
    seen: set[int] = set()
    refs: set[str] = set()
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            refs.update(ENV_REFERENCE.findall(item))
        elif isinstance(item, (dict, list)) and id(item) not in seen:
            seen.add(id(item))
            pending.extend(item.values() if isinstance(item, dict) else item)
    keys = set()
    for name in refs:
        if _is_global_env(name):
            continue
        try:
            validate_env_var_name_for_write(name)
        except ValueError:
            continue
        keys.add(name)
    return keys


def read_agent_record(home: Path, campaign_id: str, agent_id: str) -> tuple[Path, dict]:
    root = _member(_member(home, "oma"), "agents")
    path = _member(_member(root, agent_id), "config.yaml")
    config = read_mapping(path)
    if config.get("id") != agent_id or config.get("campaign_id") != campaign_id:
        raise ValueError(f"{agent_id}: config id and campaign_id must match the roster")
    validate_record("agent", config, path)
    return path, config


def settings_from(config: dict, context: str) -> dict:
    settings = {key: config[key] for key in SETTINGS if key in config}
    if "model" in settings and not isinstance(settings["model"], (dict, str)):
        raise ValueError(f"{context}: model must be a mapping or model name")
    if "mcp_servers" in settings:
        servers = settings["mcp_servers"]
        if not isinstance(servers, dict) or any(
            not isinstance(name, str) or not name or not isinstance(server, dict)
            for name, server in servers.items()
        ):
            raise ValueError(f"{context}: mcp_servers must map server names to configurations")
    return settings


def _is_toolset_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(name, str) and bool(name.strip()) for name in value)


def _validate_toolset_setting(path: tuple[str, ...], value: object, context: str, *, orchestrator: bool) -> None:
    key = ".".join(path)
    if path in _TOOL_SEARCH_SWITCHES:
        if not (isinstance(value, bool) or value in ("auto", "on", "off")):
            raise ValueError(f"{context}: {key} must be auto, on, off, or a boolean")
        return
    nullable = path[-1] == "eager_toolsets"
    if not (_is_toolset_list(value) or (nullable and value is None)):
        raise ValueError(f"{context}: {key} must be a list of toolset names" + (" or null" if nullable else ""))
    if orchestrator and path[0] == "agent" and isinstance(value, list):
        if (path[-1] == "enabled_toolsets") != ("kanban" in value):
            raise ValueError(f"{context}: {key} must leave kanban enabled for the campaign orchestrator")


def _write_toolset_leaf(config: dict, path: tuple[str, ...], value: object, context: str) -> dict:
    key, *tail = path
    if not tail:
        return {**config, key: value}
    section = config.get(key, {})
    if key == "tool_search" and (section is None or isinstance(section, bool)):
        section = {"enabled": "off" if section is False else "auto"}
    if not isinstance(section, dict):
        raise ValueError(f"{context}: native {key} must be a mapping to sync toolsets")
    return {**config, key: _write_toolset_leaf(section, tuple(tail), value, context)}


def apply_toolset_settings(native: dict, record: dict, context: str, *, orchestrator: bool = False) -> tuple[dict, list[str]]:
    """Apply only the authored role's explicit selection and disclosure settings."""
    updated = []
    for path in (*_TOOLSET_LISTS, *_TOOL_SEARCH_SWITCHES):
        value = cfg_get(record, *path, default=_OMITTED)
        if value is _OMITTED:
            continue
        _validate_toolset_setting(path, value, context, orchestrator=orchestrator)
        if value != cfg_get(native, *path, default=_OMITTED):
            native = _write_toolset_leaf(native, path, value, context)
            updated.append(".".join(path))
    return native, updated


def resolve_settings(defaults: dict, overrides: dict) -> dict:
    effective = {**defaults, **overrides}
    if "mcp_servers" in effective:
        effective["mcp_servers"] = {**defaults.get("mcp_servers", {}), **overrides.get("mcp_servers", {})}
    return effective


def materialize_agent_settings(record: dict, resolved: dict) -> dict:
    """Save the selected model as editable data; only merged MCP remains generated."""
    new = {key: value for key, value in record.items() if key != "effective"}
    if "model" in resolved:
        new["model"] = resolved["model"]
    if "mcp_servers" in resolved:
        new["effective"] = {"mcp_servers": resolved["mcp_servers"]}
    return new
