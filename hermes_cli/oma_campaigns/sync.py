"""Materialize a campaign's model and MCP settings in its installed profiles."""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from agent.secret_scope import load_env_file
from hermes_cli.config import (
    atomic_config_replace, atomic_config_write, require_env_writable, require_readable_config_before_write,
    save_env_value,
)
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.config_credential_values import refuse_redacted_env_value
from hermes_cli.oma_campaigns.install import _campaign_config_path, _campaigns_dir, _install_lock, _real_path, _status, default_home
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.settings import (
    SETTINGS, credential_keys, read_agent_record, record_with_effective, resolve_settings, settings_from,
)
from hermes_cli.oma_campaigns.source import read_mapping

@dataclass(frozen=True)
class _AgentUpdate:
    agent_id: str
    record_path: Path
    native_path: Path
    record: dict | None
    native: dict | None
    required_keys: set[str]
    available_keys: set[str]
    credentials: dict[str, str] = field(repr=False)


def _credential_updates(profile: Path, keys: set[str], stored: dict[str, str]) -> dict[str, str]:
    updates = {}
    for name in sorted(keys):
        value = os.environ.get(name)
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


def _plan_agent(home: Path, campaign_id: str, agent_id: str, defaults: dict) -> _AgentUpdate:
    record_path, record = read_agent_record(home, campaign_id, agent_id)
    effective = resolve_settings(defaults, settings_from(record, agent_id))
    previous = record.get("effective", {})
    if not isinstance(previous, dict):
        raise ValueError(f"{agent_id}: effective must be a mapping")
    native_path = home / "profiles" / agent_id / "config.yaml"
    native = require_readable_config_before_write(native_path)
    removed = (previous.keys() & set(SETTINGS)) - effective.keys()
    next_native = {**{k: v for k, v in native.items() if k not in removed}, **effective}
    profile = native_path.parent
    required = credential_keys(effective)
    stored = load_env_file(_real_path(profile / ".env")) if required else {}
    credentials = _credential_updates(profile, required, stored)
    available = {key for key in required if credentials.get(key, stored.get(key, "")).strip()}
    next_record = record_with_effective(record, effective)
    next_record["all-keys"] = sorted(required)
    next_record["available-keys"] = sorted(available)
    return _AgentUpdate(agent_id, record_path, native_path, next_record if next_record != record else None,
                        next_native if next_native != native else None, required, available, credentials)


def _apply(update: _AgentUpdate) -> None:
    # When values are supplied, publish them before the YAML that uses them.
    if update.credentials:
        profile = update.native_path.parent
        with bind_profile_scope(profile, hydrate_secrets=False):
            for name, value in update.credentials.items():
                save_env_value(name, value)
        saved = load_env_file(profile / ".env")
        if any(saved.get(name) != value for name, value in update.credentials.items()):
            raise ValueError(f"{update.agent_id}: could not verify the saved .env values")
    if update.native is not None:
        atomic_config_replace(update.native_path, update.native)
    if update.record is not None:
        atomic_config_replace(update.record_path, update.record)


def sync_campaign(home: Path, campaign_id: str) -> dict:
    require_file_tooling("OMA campaign settings sync")
    campaign_path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(campaign_path):
        print(f"OMA sync: validating {campaign_id}", file=sys.stderr)
        campaign = read_mapping(campaign_path)
        status = _status(home, campaign_id, campaign)
        if status["state"] != "installed":
            raise ValueError(f"Campaign {campaign_id!r} is not fully installed; no settings were synced")
        validate_record("campaign", campaign, campaign_path)
        defaults = settings_from(campaign, campaign_id)
        plans = [_plan_agent(home, campaign_id, agent_id, defaults) for agent_id in status["agents"]]
        updates = [plan for plan in plans if plan.native is not None or plan.record is not None or plan.credentials]
        missing = {key for plan in plans for key in plan.required_keys - plan.available_keys}
        required = {key for plan in plans for key in plan.required_keys}
        key_status = {"all-keys": sorted(required), "available-keys": sorted(required - missing)}
        if updates:
            print(f"OMA sync: updating {len(updates)} profile(s)", file=sys.stderr)
            for update in updates:
                _apply(update)
        # Only publish the campaign summary after every profile update succeeded.
        latest = read_mapping(campaign_path)
        if latest != campaign:
            raise ValueError(f"{campaign_id}: campaign changed during sync; rerun sync-campaign")
        if any(campaign.get(key) != value for key, value in key_status.items()):
            atomic_config_write(campaign_path, {**campaign, **key_status})
        elif not updates:
            print("OMA sync: nothing to change", file=sys.stderr)
    return {"id": campaign_id, "agents": status["agents"], "updated_agents": [plan.agent_id for plan in updates]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sync-campaign", description=__doc__)
    parser.add_argument("campaign_id", metavar="CAMPAIGN_ID")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(sync_campaign(default_home(), args.campaign_id), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"OMA sync: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
