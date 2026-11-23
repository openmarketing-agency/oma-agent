"""Materialize campaign model, MCP, and role toolset settings in installed profiles."""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from agent.secret_scope import load_env_file
from hermes_cli.config import (
    atomic_config_replace, atomic_config_write, require_readable_config_before_write,
)
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.oma_campaigns.credentials import (
    apply_credential_updates, key_status, plan_credential_updates, read_sync_env, validate_sync_env,
)
from hermes_cli.oma_campaigns.install import _campaign_config_path, _campaigns_dir, _install_lock, _real_path, _status, default_home
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.settings import (
    apply_toolset_settings, credential_keys, materialize_agent_settings, read_agent_record, resolve_settings, settings_from,
)
from hermes_cli.oma_campaigns.source import read_mapping

@dataclass(frozen=True)
class _AgentUpdate:
    agent_id: str
    record_path: Path
    native_path: Path
    record: dict | None
    native: dict | None
    all_keys: set[str]
    available_keys: set[str]
    credentials: dict[str, str] = field(repr=False)


def _plan_agent(
    home: Path, campaign_id: str, agent_id: str, defaults: dict, *, orchestrator: bool, env: dict[str, str] | None,
) -> _AgentUpdate:
    record_path, record = read_agent_record(home, campaign_id, agent_id)
    previous = record.get("effective", {})
    resolved = resolve_settings(defaults, settings_from(record, agent_id))
    native_path = home / "profiles" / agent_id / "config.yaml"
    native = require_readable_config_before_write(native_path)
    if "mcp_servers" in previous and "mcp_servers" not in resolved:
        next_native = {key: value for key, value in native.items() if key != "mcp_servers"}
    else:
        next_native = dict(native)
    next_native.update(resolved)
    next_native, _ = apply_toolset_settings(next_native, record, agent_id, orchestrator=orchestrator)
    profile = native_path.parent
    required = credential_keys(resolved)
    stored = load_env_file(_real_path(profile / ".env"))
    # The legacy CLI can still read named references from the process environment.
    # Explicit sync payloads never harvest ambient variables.
    credentials = (plan_credential_updates(profile, required, stored, os.environ) if env is None
                   else plan_credential_updates(profile, set(env), stored, env))
    names, available = key_status(required, {**stored, **credentials})
    next_record = materialize_agent_settings(record, resolved)
    next_record["all-keys"] = sorted(names)
    next_record["available-keys"] = sorted(available)
    return _AgentUpdate(agent_id, record_path, native_path, next_record if next_record != record else None,
                        next_native if next_native != native else None, names, available, credentials)


def _apply(update: _AgentUpdate) -> None:
    # When values are supplied, publish them before the YAML that uses them.
    apply_credential_updates(update.native_path.parent, update.credentials)
    if update.native is not None:
        atomic_config_replace(update.native_path, update.native)
    if update.record is not None:
        atomic_config_replace(update.record_path, update.record)


def sync_campaign(home: Path, campaign_id: str, *, env: dict[str, str] | None = None) -> dict:
    require_file_tooling("OMA campaign settings sync")
    if env is not None:
        env = validate_sync_env(env)
    campaign_path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(campaign_path):
        print(f"OMA sync: validating {campaign_id}", file=sys.stderr)
        campaign = read_mapping(campaign_path)
        status = _status(home, campaign_id, campaign)
        if status["state"] != "installed":
            raise ValueError(f"Campaign {campaign_id!r} is not fully installed; no settings were synced")
        validate_record("campaign", campaign, campaign_path)
        defaults = settings_from(campaign, campaign_id)
        plans = [_plan_agent(home, campaign_id, agent_id, defaults, orchestrator=agent_id == status["orchestrator"], env=env)
                 for agent_id in status["agents"]]
        updates = [plan for plan in plans if plan.native is not None or plan.record is not None or plan.credentials]
        missing = {key for plan in plans for key in plan.all_keys - plan.available_keys}
        names = {key for plan in plans for key in plan.all_keys}
        summary = {"all-keys": sorted(names), "available-keys": sorted(names - missing)}
        if updates:
            print(f"OMA sync: updating {len(updates)} profile(s)", file=sys.stderr)
            for update in updates:
                _apply(update)
        # Only publish the campaign summary after every profile update succeeded.
        latest = read_mapping(campaign_path)
        if latest != campaign:
            raise ValueError(f"{campaign_id}: campaign changed during sync; rerun sync-campaign")
        if any(campaign.get(key) != value for key, value in summary.items()):
            atomic_config_write(campaign_path, {**campaign, **summary})
        elif not updates:
            print("OMA sync: nothing to change", file=sys.stderr)
    return {"id": campaign_id, "agents": status["agents"], "updated_agents": [plan.agent_id for plan in updates]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sync-campaign", description=__doc__)
    parser.add_argument("campaign_id", metavar="CAMPAIGN_ID")
    parser.add_argument("--env-stdin", action="store_true", help="Read a JSON map of profile environment values from stdin")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(sync_campaign(default_home(), args.campaign_id,
                                       env=read_sync_env() if args.env_stdin else None), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"OMA sync: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
