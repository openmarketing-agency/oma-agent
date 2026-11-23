"""Plan and persist credentials for explicit OMA profile settings sync."""

from collections.abc import Mapping
import json
from pathlib import Path
import re
import sys

from agent.runtime_scope import bind_profile_scope
from agent.secret_scope import _is_global_env, load_env_file
from hermes_cli.config import require_env_writable, save_env_value, validate_env_var_name_for_write
from hermes_cli.config_credential_values import refuse_redacted_env_value
from hermes_cli.oma_campaigns.install import _real_path

_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MAX_SYNC_ENV_BYTES = 256 * 1024


def validate_sync_env(env: object) -> dict[str, str]:
    if not isinstance(env, dict) or any(
        not isinstance(key, str) or not _ENV_NAME.fullmatch(key)
        or not isinstance(value, str) or not 0 < len(value) <= 4096
        or not value.strip() or not value.isascii() or not value.isprintable()
        for key, value in env.items()
    ):
        raise ValueError("Invalid sync env object")
    for key in env:
        if _is_global_env(key):
            raise ValueError(f"{key} is not a profile environment variable")
        validate_env_var_name_for_write(key)
    return env


def read_sync_env() -> dict[str, str]:
    data = sys.stdin.buffer.read(_MAX_SYNC_ENV_BYTES + 1)
    if len(data) > _MAX_SYNC_ENV_BYTES:
        raise ValueError("The sync env object is too large")
    try:
        return validate_sync_env(json.loads(data))
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid sync env object") from exc


def key_status(referenced: set[str], stored: dict[str, str]) -> tuple[set[str], set[str]]:
    names = referenced | {name for name in stored if _ENV_NAME.fullmatch(name) and not _is_global_env(name)}
    return names, {name for name in names if stored.get(name, "").strip()}


def plan_credential_updates(
    profile: Path, keys: set[str], stored: dict[str, str], supplied: Mapping[str, str],
) -> dict[str, str]:
    updates = {}
    for name in sorted(keys):
        value = supplied.get(name)
        if not value or not value.strip():
            continue
        if not value.isascii() or "\n" in value or "\r" in value:
            raise ValueError(f"{profile.name}: secret {name} must be a single-line ASCII credential")
        if value != stored.get(name):
            updates[name] = value
    if updates:
        _real_path(profile / ".env.lock")
        with bind_profile_scope(profile, hydrate_secrets=False):
            for name, value in updates.items():
                require_env_writable(name, "set")
                refuse_redacted_env_value(name, value)
    return updates


def apply_credential_updates(profile: Path, updates: dict[str, str]) -> None:
    if not updates:
        return
    with bind_profile_scope(profile, hydrate_secrets=False):
        for name, value in updates.items():
            save_env_value(name, value)
    saved = load_env_file(profile / ".env")
    if any(saved.get(name) != value for name, value in updates.items()):
        raise ValueError(f"{profile.name}: could not verify the saved .env values")
