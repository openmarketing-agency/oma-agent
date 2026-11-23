"""Seed and apply the OMA records for the workspace's built-in profiles."""

import argparse
from contextlib import suppress
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from agent.runtime_scope import bind_profile_scope
from agent.secret_scope import load_env_file
from hermes_cli.active_sessions import _FileLock
from hermes_cli.config import atomic_config_replace, cfg_get, require_readable_config_before_write
from hermes_cli.config_backend import config_version, require_file_tooling, supports_file_tooling
from hermes_cli.oma_campaigns.bundle import seed_bundle, seed_role_skills
from hermes_cli.oma_campaigns.credentials import (
    apply_credential_updates, key_status, plan_credential_updates, read_sync_env, validate_sync_env,
)
from hermes_cli.oma_campaigns.install import default_home
from hermes_cli.oma_campaigns.role_skills import apply_role_skills
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.settings import ENV_REFERENCE, apply_toolset_settings, credential_keys, settings_from
from hermes_cli.oma_campaigns.source import _member
from hermes_constants import named_profile_is_live
from hermes_yaml import YAMLError, safe_load

_AGENTS = {
    "default": ("Default", "Set up the brand, strategy, and campaigns."),
    "maintenance": ("Maintenance", "Diagnose and maintain this OMA workspace."),
}
_IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_./:@+\-]{0,199}")
_MAX_RECORD_BYTES = 256 * 1024

_MISSING = object()
# Copy only the requested settings, not entire native sections that may contain
# credentials, plugin-specific options, or machine-local data.
_SEED_FIELDS = (
    ("agent", "enabled_toolsets"),
    ("agent", "disabled_toolsets"),
    ("tools", "tool_search", "enabled"),
    ("tools", "tool_search", "eager_toolsets"),
    ("tools", "tool_search", "defer_toolsets"),
    ("tools", "tool_search", "listing"),
    ("skills", "disabled"),
    ("approvals", "mode"),
    ("approvals", "timeout"),
    ("approvals", "cron_mode"),
    ("approvals", "single_query_mode"),
    ("approvals", "unattended_mode"),
    ("approvals", "approvers"),
    ("approvals", "mcp_reload_confirm"),
    ("approvals", "destructive_slash_confirm"),
    ("_config_version",),
    ("kanban", "orchestrator_profile"),
    ("plugins", "enabled"),
    ("plugins", "disabled"),
    ("_default_plugins_installed",),
)


class StaleRecord(ValueError):
    """The requested source revision is no longer current."""


def _record_dir(home: Path, agent_id: str) -> Path:
    if agent_id not in _AGENTS:
        raise ValueError("Only default and maintenance are standalone OMA agents")
    return _member(_member(_member(home, "oma"), "agents"), agent_id)


def _profile(home: Path, agent_id: str) -> Path:
    if agent_id == "default":
        return home
    profile = _member(_member(home, "profiles"), agent_id)
    if not named_profile_is_live(profile):
        raise FileNotFoundError(f"The {agent_id} profile is not installed")
    return profile


def _existing_model(value):
    # Only adopt a complete, recognizable selection. Copying partial native blocks
    # would change routing on first sync; arbitrary URLs/options can contain secrets.
    if isinstance(value, str) and _IDENTIFIER.fullmatch(value):
        return value
    if not isinstance(value, dict) or not value or set(value) - {"default", "provider", "context_length", "api_key"}:
        return None
    if not all(isinstance(value[key], str) and _IDENTIFIER.fullmatch(value[key]) for key in value.keys() & {"default", "provider"}):
        return None
    if "context_length" in value and type(value["context_length"]) is not int:
        return None
    if "api_key" in value and not (isinstance(value["api_key"], str) and ENV_REFERENCE.fullmatch(value["api_key"])):
        return None
    return dict(value)


def _seed_settings(native: dict) -> dict:
    settings: dict = {}
    for path in _SEED_FIELDS:
        value = cfg_get(native, *path, default=_MISSING)
        if value is _MISSING:
            continue
        node = settings
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value
    return settings


def _seed_record(home: Path, agent_id: str) -> bool:
    directory = _record_dir(home, agent_id)
    target = _member(directory, "config.yaml")
    persona = _member(directory, "SOUL.md")
    if target.exists() and persona.exists():  # config-reader: ok — authored OMA record, not native config
        return False
    profile = _profile(home, agent_id)
    name, description = _AGENTS[agent_id]
    native = _member(profile, "config.yaml")
    with bind_profile_scope(profile, hydrate_secrets=False):
        config_version(native)  # Do not adopt an absent profile configuration.
        saved = require_readable_config_before_write(native)
    record = {"id": agent_id, "name": name, "description": description, "campaign_id": None}
    model = _existing_model(saved.get("model"))
    if model is not None:
        record["model"] = model
    record.update(_seed_settings(saved))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    seeded = False
    # Publish missing files atomically and never replace an editor's concurrent save.
    with TemporaryDirectory(prefix=".seed-", dir=directory) as tmp:
        staging = Path(tmp)
        if not target.exists():  # config-reader: ok — authored OMA record, not native config
            atomic_config_replace(staging / target.name, record)
        if not persona.exists():
            with suppress(FileNotFoundError):
                (staging / persona.name).write_bytes(_member(profile, persona.name).read_bytes())
        for source in staging.iterdir():
            with suppress(FileExistsError):
                os.link(source, directory / source.name)
                seeded = True
    return seeded


def seed_standalone_agents(home: Path, *, install_dir: Path | None = None) -> dict:
    if not supports_file_tooling():
        return {"seeded": []}
    records = _member(_member(home, "oma"), "agents")
    records.mkdir(mode=0o700, parents=True, exist_ok=True)
    if install_dir is not None:
        seed_bundle(install_dir / "oma-bundle", home)
        seed_role_skills(install_dir, home)
    seeded = []
    for agent_id in _AGENTS:
        with suppress(FileNotFoundError):  # Do not recreate an absent or deleted native profile.
            if _seed_record(home, agent_id):
                seeded.append(agent_id)
    return {"seeded": seeded}


def _read_saved(path: Path, agent_id: str, revision: str | None) -> tuple[dict, str]:
    with path.open("rb") as stream:
        data = stream.read(_MAX_RECORD_BYTES + 1)
    if len(data) > _MAX_RECORD_BYTES:
        raise ValueError("The saved OMA agent config is too large")
    digest = sha256(data).hexdigest()
    if revision is not None and revision != digest:
        raise StaleRecord("The standalone agent record changed before sync")
    try:
        record = safe_load(data.decode("utf-8-sig"))
    except (UnicodeError, YAMLError, RecursionError):
        raise ValueError("Invalid standalone agent YAML") from None
    if not isinstance(record, dict) or record.get("id") != agent_id or record.get("campaign_id") is not None:
        raise ValueError("The saved record must match this standalone agent")
    validate_record("agent", record, path)
    return record, digest


def sync_standalone_agent(
    home: Path, agent_id: str, *, revision: str | None = None, env: dict[str, str] | None = None,
) -> dict:
    require_file_tooling("OMA standalone agent sync")
    supplied = validate_sync_env(env) if env is not None else {}
    directory = _record_dir(home, agent_id)
    path = _member(directory, "config.yaml")
    if not path.is_file():  # config-reader: ok — authored OMA record, not native config
        raise FileNotFoundError(path)
    profile = _profile(home, agent_id)
    native = _member(profile, "config.yaml")
    lock = _member(directory, ".sync.lock")
    with _FileLock(lock, timeout=10), bind_profile_scope(profile, hydrate_secrets=False):
        record, digest = _read_saved(path, agent_id, revision)
        settings = settings_from(record, agent_id)
        before = config_version(native)
        current = require_readable_config_before_write(native)
        updated = [key for key, value in settings.items() if current.get(key) != value]
        next_native, toolset_updates = apply_toolset_settings({**current, **settings}, record, agent_id)
        updated.extend(toolset_updates)
        stored = load_env_file(_member(profile, ".env"))
        credentials = plan_credential_updates(profile, set(supplied), stored, supplied)
        names, available = key_status(credential_keys(settings), {**stored, **credentials})
        summary = {"all-keys": sorted(names), "available-keys": sorted(available)}
        with apply_role_skills(home, profile, record.get("oma_skills")) as skills_changed:
            if config_version(native) != before:
                raise StaleRecord("The native profile changed during sync")
            _read_saved(path, agent_id, digest)
            apply_credential_updates(profile, credentials)
            if updated:
                atomic_config_replace(native, next_native)
            if any(record.get(key) != value for key, value in summary.items()):
                _read_saved(path, agent_id, digest)
                atomic_config_replace(path, {**record, **summary})
                _, digest = _read_saved(path, agent_id, None)
        if credentials:
            updated.append("env")
        if skills_changed:
            updated.append("oma_skills")
    return {"id": agent_id, "revision": digest, "updated": updated}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    seed = commands.add_parser("seed", help="Create missing standalone records without applying them")
    seed.add_argument("--install-dir", type=Path)
    seed.add_argument("--ensure-maintenance", action="store_true", help="Seed the native starter if missing")
    sync = commands.add_parser("sync", help="Apply saved model, MCP configuration, toolsets, and bundle skills to one profile")
    sync.add_argument("id", choices=_AGENTS)
    sync.add_argument("--revision")
    sync.add_argument("--env-stdin", action="store_true", help="Read a JSON map of credential values from stdin")
    args = parser.parse_args(argv)
    try:
        home = default_home()
        if args.action == "seed" and args.ensure_maintenance and supports_file_tooling():
            from hermes_cli.config_home import _seed_maintenance_profile

            with bind_profile_scope(home, hydrate_secrets=False):
                _seed_maintenance_profile(home)
        result = (seed_standalone_agents(home, install_dir=args.install_dir) if args.action == "seed"
                  else sync_standalone_agent(home, args.id, revision=args.revision,
                                             env=read_sync_env() if args.env_stdin else None))
        print(json.dumps(result))
        return 0
    except StaleRecord:
        print("OMA standalone agent: source or native profile changed; reload and retry", file=sys.stderr)
        return 3
    except FileNotFoundError:
        print("OMA standalone agent: record or profile is missing", file=sys.stderr)
        return 4
    except (OSError, ValueError, RuntimeError):
        print("OMA standalone agent: could not read or apply settings; check the saved record and profile", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
