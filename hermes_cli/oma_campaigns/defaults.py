"""Creation-time defaults for OMA campaign records and native profiles."""

import re
from pathlib import Path

from agent.secret_scope import _is_global_env, load_env_file
from hermes_cli.auth import PROVIDER_REGISTRY, _IMPLICIT_ENV_VARS, _usable_declared_secret
from hermes_cli.config import read_user_config_raw, validate_env_var_name_for_write
from hermes_cli.config_credential_values import refuse_redacted_env_value
from hermes_cli.models import normalize_provider
from hermes_cli.oma_campaigns.settings import ENV_REFERENCE

_EAGER = ("file", "skills", "memory")


def _provider_keys(provider: str) -> tuple[str, ...]:
    if provider == "openrouter":  # intentionally outside the native auth registry
        return ("OPENROUTER_API_KEY",)
    config = PROVIDER_REGISTRY.get(provider)
    return config.api_key_env_vars if config and config.auth_type == "api_key" else ()


def _saved_credential(provider: str, names: tuple[str, ...], saved: dict) -> dict[str, str]:
    for name in names:
        if _is_global_env(name) or name in _IMPLICIT_ENV_VARS or name in {"CAMOFOX_URL", "CAMOFOX_API_KEY"}:
            continue
        value = saved.get(name, "").strip()
        if not value or not value.isascii() or "\n" in value or "\r" in value:
            continue
        try:
            validate_env_var_name_for_write(name)
            refuse_redacted_env_value(name, value)
        except ValueError:
            continue
        if _usable_declared_secret(provider, value, name):
            return {name: value}
    return {}


def _inherited_model(model: object, env_path: Path) -> tuple[object, dict[str, str]]:
    if isinstance(model, str):
        return (model if model.strip() else None), {}
    if not isinstance(model, dict) or not isinstance(model.get("default"), str) or not model["default"].strip():
        return None, {}
    model = dict(model)
    provider = normalize_provider(model.get("provider"))
    api_key = model.pop("api_key", "")
    reference = ENV_REFERENCE.fullmatch(api_key.strip()) if isinstance(api_key, str) else None
    pointer = model.get("key_env") or model.get("api_key_env")
    if reference:
        model["api_key"] = reference.group(0)
        names = (reference.group(1),)
    elif isinstance(pointer, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", pointer):
        names = (pointer,)
    else:
        names = _provider_keys(provider)
    if names and env_path.is_symlink():
        raise ValueError("Refusing symlinked default profile .env")
    credential = _saved_credential(provider, names, load_env_file(env_path)) if names else {}
    if not reference and (credential or len(names) == 1):
        name = next(iter(credential), names[0])
        model["api_key"] = "${" + name + "}"
    return model, credential


def snapshot(home: Path, campaign: dict) -> tuple[dict, object, dict[str, str]]:
    """Read saved settings, not the current turn or the merged runtime defaults."""
    saved = read_user_config_raw(home / "config.yaml")
    agent = saved.get("agent")
    effort = agent.get("reasoning_effort") if isinstance(agent, dict) else None
    if "model" in campaign:
        return campaign, effort, {}
    model, credential = _inherited_model(saved.get("model"), home / ".env")
    return ({**campaign, "model": model} if model is not None else campaign), effort, credential


def agent_defaults(config: dict, effort: object, agent_id: str, *, orchestrator: bool) -> dict:
    raw_agent = config.get("agent")
    agent = dict(raw_agent) if isinstance(raw_agent, dict) else {}
    enabled = agent.get("enabled_toolsets")
    if not isinstance(enabled, list) or any(not isinstance(name, str) or not name.strip() for name in enabled):
        raise ValueError(f"{agent_id}: agent.enabled_toolsets must be an explicit list of toolset names")
    if orchestrator and "kanban" not in enabled:
        raise ValueError(f"{agent_id}: include kanban in the orchestrator's agent.enabled_toolsets")

    if effort is not None:
        agent.setdefault("reasoning_effort", effort)
    tools = config.get("tools", {})
    if not isinstance(tools, dict) or not isinstance(tools.get("tool_search", {}), dict):
        raise ValueError(f"{agent_id}: tools and tools.tool_search must be mappings")
    return {**config, "agent": agent, "tools": {**tools, "tool_search": {
        "enabled": "on", "eager_toolsets": list(_EAGER), **tools.get("tool_search", {}),
    }}}
