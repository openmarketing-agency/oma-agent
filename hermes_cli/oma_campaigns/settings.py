"""Resolve native Hermes settings shared by a campaign and its agents."""

import re
from pathlib import Path

from agent.secret_scope import _is_global_env
from agent.skill_utils import parse_config_string_list
from hermes_cli.config import cfg_get, validate_env_var_name_for_write
from hermes_cli.config_home import OMA_BASE_TOOLSETS, OMA_CAMPAIGN_SKILL, OMA_EAGER_TOOLSETS
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping
from hermes_constants import VALID_REASONING_EFFORTS
from toolsets import resolve_toolset


SETTINGS = ("model", "mcp_servers")
ENV_REFERENCE = re.compile(r"\$\{\s*(?:env:\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\}")
_OMITTED = object()
_TOOLSET_LISTS = (
    ("agent", "enabled_toolsets"), ("agent", "disabled_toolsets"),
    ("tools", "tool_search", "eager_toolsets"), ("tools", "tool_search", "defer_toolsets"),
)
_TOOL_SEARCH_SWITCHES = (("tools", "tool_search", "enabled"), ("tools", "tool_search", "listing"))
_TOOLSET_SETTINGS = (*_TOOLSET_LISTS, *_TOOL_SEARCH_SWITCHES)


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


def _validate_toolset_setting(path: tuple[str, ...], value: object, context: str) -> None:
    key = ".".join(path)
    if path in _TOOL_SEARCH_SWITCHES:
        if not (isinstance(value, bool) or value in ("auto", "on", "off")):
            raise ValueError(f"{context}: {key} must be auto, on, off, or a boolean")
        return
    nullable = path[-1] == "eager_toolsets"
    if not (_is_toolset_list(value) or (nullable and value is None)):
        raise ValueError(f"{context}: {key} must be a list of toolset names" + (" or null" if nullable else ""))



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


def mcp_toolset_names(config: dict) -> list[str]:
    """``mcp-<server>`` for every enabled server in the resolved MCP map.

    An explicit profile allowlist is authoritative, so a server it does not name is
    unreachable even when its definition is configured and enabled.
    """
    servers = config.get("mcp_servers")
    if not isinstance(servers, dict):
        return []
    return [f"mcp-{name}" for name, server in servers.items()
            if isinstance(name, str) and name.strip() and isinstance(server, dict)
            and server.get("enabled") is not False]


def enforce_toolset_baseline(
    config: dict, context: str, *, orchestrator: bool = False, campaign_id: str | None = None,
) -> dict:
    """Keep the OMA floor without broadening an explicit tool exclusion."""
    enabled = cfg_get(config, "agent", "enabled_toolsets", default=[])
    if enabled is None:
        enabled = []
    _validate_toolset_setting(("agent", "enabled_toolsets"), enabled, context)
    floor = (*OMA_BASE_TOOLSETS, "kanban") if orchestrator else OMA_BASE_TOOLSETS
    required = (*floor, *mcp_toolset_names(config))
    if campaign_id is not None and context == f"{campaign_id}__publisher":
        # Remove standing selection, including bundles, without disabling the
        # task tools granted by the dispatcher on a claimed publication.
        kanban_tools = set(resolve_toolset("kanban"))
        enabled = [name for name in enabled if not kanban_tools.intersection(resolve_toolset(name))]
    # Append only what is missing, in a fixed order: a list that already satisfies the
    # floor keeps its authored order, so an unchanged profile reports no change.
    missing = [name for name in required if name not in enabled]
    disabled = parse_config_string_list(cfg_get(config, "agent", "disabled_toolsets", default=[]))
    if disabled:
        required_tools = {tool for name in required for tool in resolve_toolset(name)}
        conflicts = [name for name in disabled if name in required or required_tools.intersection(resolve_toolset(name))]
        if conflicts:
            raise ValueError(f"{context}: agent.disabled_toolsets excludes required OMA tools: {', '.join(conflicts)}")
    policy = {
        ("agent", "enabled_toolsets"): [*enabled, *missing],
        ("tools", "tool_search", "enabled"): "on",
        ("tools", "tool_search", "eager_toolsets"): list(OMA_EAGER_TOOLSETS),
    }
    for path, value in policy.items():
        config = _write_toolset_leaf(config, path, value, context)
    return config


def apply_toolset_settings(
    native: dict, record: dict, context: str, *, orchestrator: bool = False, campaign_id: str | None = None,
) -> tuple[dict, list[str]]:
    """Apply authored role settings above the required OMA baseline."""
    before = native
    for path in _TOOLSET_SETTINGS:
        value = cfg_get(record, *path, default=_OMITTED)
        if value is _OMITTED:
            continue
        _validate_toolset_setting(path, value, context)
        if value != cfg_get(native, *path, default=_OMITTED):
            native = _write_toolset_leaf(native, path, value, context)
    native = enforce_toolset_baseline(native, context, orchestrator=orchestrator, campaign_id=campaign_id)
    updated = [".".join(path) for path in _TOOLSET_SETTINGS
               if cfg_get(native, *path, default=_OMITTED) != cfg_get(before, *path, default=_OMITTED)]
    return native, updated


def reasoning_effort(record: dict, context: str):
    value = cfg_get(record, "agent", "reasoning_effort", default=_OMITTED)
    if value is not _OMITTED and value is not None and value is not False and value not in ("", *VALID_REASONING_EFFORTS, "none"):
        raise ValueError(f"{context}: invalid agent.reasoning_effort")
    return value


def apply_profile_settings(native: dict, record: dict, defaults: dict, context: str, *,
                           orchestrator: bool = False, campaign: bool = False) -> tuple[dict, list[str]]:
    changed = []
    for path in (("agent", "reasoning_effort"), ("skills", "enabled"), ("skills", "disabled"), ("skills", "auto_load")):
        if path[0] == "agent":
            value = reasoning_effort(record, context)
            if value is _OMITTED:
                value = reasoning_effort(defaults, context)
        else:
            value = cfg_get(record, *path, default=_OMITTED)
            if value is _OMITTED:
                continue
            if not (_is_toolset_list(value) or (path[-1] == "enabled" and value is None)):
                raise ValueError(f"{context}: {'.'.join(path)} must be a list of skill names")
            if campaign and path[-1] == "disabled":
                # The campaign management skill stays unavailable to campaign profiles.
                value = sorted(set(value or ()) | {OMA_CAMPAIGN_SKILL})
        if value is not _OMITTED and value != cfg_get(native, *path, default=_OMITTED):
            native = _write_toolset_leaf(native, path, value, context)
            changed.append(".".join(path))
    native, toolsets = apply_toolset_settings(
        native, record, context, orchestrator=orchestrator, campaign_id=record.get("campaign_id") if campaign else None,
    )
    return native, changed + toolsets


def resolve_settings(defaults: dict, overrides: dict) -> dict:
    effective = {**defaults, **overrides}
    if "mcp_servers" in effective:
        effective["mcp_servers"] = {**defaults.get("mcp_servers", {}), **overrides.get("mcp_servers", {})}
    return effective


def materialize_agent_settings(record: dict, resolved: dict) -> dict:
    """Keep model overrides authored; never turn an inherited model into an override."""
    new = {key: value for key, value in record.items() if key != "effective"}
    if "mcp_servers" in resolved:
        new["effective"] = {"mcp_servers": resolved["mcp_servers"]}
    return new
