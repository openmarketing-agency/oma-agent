"""Resolve native Hermes settings shared by a campaign and its agents."""

from pathlib import Path

from hermes_cli.oma_playbooks.source import _member, read_mapping


SETTINGS = ("model", "mcp_servers")


def read_agent_record(home: Path, campaign_id: str, agent_id: str) -> tuple[Path, dict]:
    root = _member(_member(home, "oma"), "agents")
    path = _member(_member(root, agent_id), "config.yaml")
    config = read_mapping(path)
    if config.get("id") != agent_id or config.get("campaign_id") != campaign_id:
        raise ValueError(f"{agent_id}: config id and campaign_id must match the roster")
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
