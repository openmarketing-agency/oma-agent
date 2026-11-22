"""Resolve native Hermes settings shared by a campaign and its agents."""

import re
from pathlib import Path

from agent.secret_scope import _is_global_env
from hermes_cli.config import validate_env_var_name_for_write
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping


SETTINGS = ("model", "mcp_servers")
ENV_REFERENCE = re.compile(r"\$\{\s*(?:env:\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\}")


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


def resolve_settings(defaults: dict, overrides: dict) -> dict:
    effective = {**defaults, **overrides}
    if "mcp_servers" in effective:
        effective["mcp_servers"] = {**defaults.get("mcp_servers", {}), **overrides.get("mcp_servers", {})}
    return effective


def record_with_effective(record: dict, effective: dict) -> dict:
    new = {key: value for key, value in record.items() if key != "effective"}
    if effective:
        new["effective"] = effective
    return new
