"""Saved workspace defaults for OMA campaign records and native profiles."""

from dataclasses import dataclass, field
import re
from pathlib import Path

from agent.secret_scope import _is_global_env, load_env_file
from hermes_cli.auth import PROVIDER_REGISTRY, _IMPLICIT_ENV_VARS, _usable_declared_secret
from hermes_cli.config import read_user_config_raw, validate_env_var_name_for_write
from hermes_cli.config_credential_values import refuse_redacted_env_value
from hermes_cli.models import normalize_provider
from hermes_cli.oma_campaigns.credentials import retired_analytics_keys
from hermes_cli.oma_campaigns.settings import (
    ENV_REFERENCE, credential_keys, enforce_toolset_baseline, resolve_settings, settings_from,
)
from hermes_cli.oma_campaigns.source import _member


def _provider_keys(provider: str) -> tuple[str, ...]:
    if provider == "openrouter":  # intentionally outside the native auth registry
        return ("OPENROUTER_API_KEY",)
    config = PROVIDER_REGISTRY.get(provider)
    return config.api_key_env_vars if config and config.auth_type == "api_key" else ()


def _saved_values(names: set[str], saved: dict[str, str], *, provider: str = "") -> dict[str, str]:
    values = {}
    for name in names - retired_analytics_keys(names):
        if _is_global_env(name) or name in _IMPLICIT_ENV_VARS or name in {"CAMOFOX_URL", "CAMOFOX_API_KEY"}:
            continue
        value = saved.get(name, "").strip()
        if not value or not value.isascii() or not value.isprintable():
            continue
        try:
            validate_env_var_name_for_write(name)
            refuse_redacted_env_value(name, value)
        except ValueError:
            continue
        if _usable_declared_secret(provider, value, name):
            values[name] = value
    return values


def _model_key_names(model: dict) -> tuple[str, ...]:
    api_key = model.get("api_key")
    if isinstance(api_key, str) and (reference := ENV_REFERENCE.fullmatch(api_key.strip())):
        return (reference[1],)
    pointer = model.get("key_env") or model.get("api_key_env")
    if isinstance(pointer, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", pointer):
        return (pointer,)
    return _provider_keys(normalize_provider(model.get("provider")))


def _inherited_model(model: object, saved: dict[str, str]) -> tuple[object, dict[str, str]]:
    if isinstance(model, str):
        return (model if model.strip() else None), {}
    if not isinstance(model, dict) or not isinstance(model.get("default"), str) or not model["default"].strip():
        return None, {}
    model = dict(model)
    provider = normalize_provider(model.get("provider"))
    names = _model_key_names(model)
    api_key = model.pop("api_key", "")
    reference = ENV_REFERENCE.fullmatch(api_key.strip()) if isinstance(api_key, str) else None
    if reference:
        model["api_key"] = reference.group(0)
    eligible = _saved_values(set(names), saved, provider=provider)
    credential = next(({name: eligible[name]} for name in names if name in eligible), {})
    if not reference and (credential or len(names) == 1):
        name = next(iter(credential), names[0])
        model["api_key"] = "${" + name + "}"
    return model, credential


@dataclass(frozen=True)
class InheritedCredentials:
    model: dict[str, str] = field(repr=False)
    mcp: dict[str, dict[str, str]] = field(repr=False)

    def for_agent(self, campaign: dict, agent: dict, *, native: dict | None = None) -> dict[str, str]:
        overrides = resolve_settings(campaign, agent)
        servers = overrides.get("mcp_servers", {})
        native = native or {}
        # A profile has one .env value per name. Don't change the value for a live
        # local definition or an authored override that uses the same name.
        native_servers = {name: server for name, server in native.get("mcp_servers", {}).items()
                          if name in servers or name not in self.mcp}
        protected = credential_keys({"mcp_servers": servers}) | credential_keys({"mcp_servers": native_servers})
        values = {key: value for name, keys in self.mcp.items() if name not in servers for key, value in keys.items()}
        if "model" in overrides:
            protected.update(self.model)
            for model in (overrides["model"], native.get("model")):
                protected.update(credential_keys({"model": model}))
                if isinstance(model, dict):
                    protected.update(_model_key_names(model))
        else:
            values.update(self.model)
        return {key: value for key, value in values.items() if key not in protected}


def snapshot(home: Path, campaign: dict) -> tuple[dict, InheritedCredentials]:
    """Read saved settings, not the current turn or the merged runtime defaults."""
    saved = read_user_config_raw(home / "config.yaml")
    # Transfer definitions and credential values separately; YAML retains references.
    mcp = {}
    if "mcp_servers" in saved:
        defaults = settings_from({"mcp_servers": saved["mcp_servers"]}, "default profile")
        mcp = {name: credential_keys({"mcp_servers": {name: server}})
               for name, server in defaults["mcp_servers"].items() if name not in campaign.get("mcp_servers", {})}
        campaign = resolve_settings(defaults, campaign)
    agent = saved.get("agent")
    campaign_agent = campaign.get("agent", {})
    if isinstance(agent, dict) and agent.get("reasoning_effort") is not None and "reasoning_effort" not in campaign_agent:
        campaign = {**campaign, "agent": {**campaign_agent, "reasoning_effort": agent["reasoning_effort"]}}
    model = saved.get("model") if "model" not in campaign else None
    needed = any(mcp.values()) or (isinstance(model, dict) and bool(_model_key_names(model)))
    dotenv = load_env_file(_member(home, ".env")) if needed else {}
    model, credential = _inherited_model(model, dotenv)
    return ({**campaign, "model": model} if model is not None else campaign), InheritedCredentials(
        credential, {name: _saved_values(keys, dotenv) for name, keys in mcp.items()},
    )


def agent_defaults(config: dict, agent_id: str, *, orchestrator: bool, campaign_id: str) -> dict:
    agent = config.get("agent")
    enabled = agent.get("enabled_toolsets") if isinstance(agent, dict) else None
    if not isinstance(enabled, list) or any(not isinstance(name, str) or not name.strip() for name in enabled):
        raise ValueError(f"{agent_id}: agent.enabled_toolsets must be an explicit list of toolset names")

    tools = config.get("tools", {})
    if not isinstance(tools, dict) or not isinstance(tools.get("tool_search", {}), dict):
        raise ValueError(f"{agent_id}: tools and tools.tool_search must be mappings")
    return enforce_toolset_baseline(config, agent_id, orchestrator=orchestrator, campaign_id=campaign_id)
