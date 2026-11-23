"""Apply saved OMA settings to one agent or an installed campaign roster."""

import argparse
import json
import sys
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from agent.secret_scope import load_env_file
from hermes_cli.active_sessions import _FileLock
from hermes_cli.config import (
    atomic_config_replace, atomic_config_write, require_readable_config_before_write,
)
from hermes_cli.config_backend import config_version, require_file_tooling
from hermes_cli.oma_campaigns.credentials import (
    apply_credential_updates, key_status, plan_credential_updates, read_sync_env, validate_sync_env,
)
from hermes_cli.oma_campaigns.install import (
    _agent_data_dir, _campaign_config_path, _campaigns_dir, _install_lock, _status, campaign_soul, default_home,
)
from hermes_cli.oma_campaigns.role_jobs import apply_role_jobs, plan_role_jobs
from hermes_cli.oma_campaigns.role_skills import apply_role_skills, plan_role_skills
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.settings import (
    apply_profile_settings, credential_keys, materialize_agent_settings, resolve_settings, settings_from,
)
from hermes_cli.oma_campaigns.source import _member, read_mapping
from hermes_constants import PROFILE_ID_RE, named_profile_is_live
from hermes_yaml import YAMLError, safe_load
from utils import atomic_write_text

STANDALONE_IDS = ("default", "maintenance")
_MAX_RECORD_BYTES = 256 * 1024


class StaleRecord(ValueError):
    """A saved record or native config changed during sync."""


@dataclass(frozen=True)
class _Campaign:
    path: Path
    saved: dict = field(repr=False)
    status: dict

    def render_soul(self, home: Path, agent_id: str, soul: str) -> str:
        return campaign_soul(
            soul, agent_id, self.status["orchestrator"], tuple(self.status["agents"]),
            self.status["kanban_board"], self.path,
            _agent_data_dir(home, agent_id, "saves"), _agent_data_dir(home, agent_id, "tmp"),
        )


@dataclass(frozen=True)
class _AgentUpdate:
    agent_id: str
    record_path: Path
    revision: str
    native_path: Path
    native_version: object
    record: dict | None = field(repr=False)
    native: dict = field(repr=False)
    source_soul: str | None = field(repr=False)
    native_soul: str | None = field(repr=False)
    rendered_soul: str | None = field(repr=False)
    updated: tuple[str, ...]
    all_keys: set[str]
    available_keys: set[str]
    credentials: dict[str, str] = field(repr=False)
    skills: tuple | None = field(repr=False)
    jobs: dict | None = field(repr=False)


def record_dir(home: Path, agent_id: str) -> Path:
    return _member(_member(_member(home, "oma"), "agents"), agent_id)


def profile_dir(home: Path, agent_id: str) -> Path:
    profile = home if agent_id == "default" else _member(_member(home, "profiles"), agent_id)
    if agent_id != "default" and not named_profile_is_live(profile):
        raise FileNotFoundError(f"The {agent_id} profile is not installed")
    return profile


def _read_saved(path: Path, agent_id: str, campaign_id: str | None, revision: str | None = None) -> tuple[dict, str]:
    with path.open("rb") as stream:
        data = stream.read(_MAX_RECORD_BYTES + 1)
    if len(data) > _MAX_RECORD_BYTES:
        raise ValueError(f"{agent_id}: the saved OMA config is too large")
    digest = sha256(data).hexdigest()
    if revision is not None and revision != digest:
        raise StaleRecord(f"{agent_id}: the saved agent record changed during sync")
    try:
        record = safe_load(data.decode("utf-8-sig"))
    except (UnicodeError, YAMLError, RecursionError):
        raise ValueError(f"{agent_id}: invalid agent YAML") from None
    if not isinstance(record, dict) or record.get("id") != agent_id or record.get("campaign_id") != campaign_id:
        owner = "standalone agent" if campaign_id is None else f"member of {campaign_id}"
        raise ValueError(f"{agent_id}: the saved record must match this {owner}")
    validate_record("agent", record, path)
    return record, digest


def _read_soul(path: Path) -> str | None:
    return path.read_text(encoding="utf-8-sig") if path.exists() else None


def _plan_agent(home: Path, agent_id: str, env: dict[str, str], *, campaign: _Campaign | None = None,
                revision: str | None = None) -> _AgentUpdate:
    directory = record_dir(home, agent_id)
    record_path = _member(directory, "config.yaml")
    campaign_id = campaign.status["id"] if campaign else None
    record, digest = _read_saved(record_path, agent_id, campaign_id, revision)
    source_soul = _read_soul(_member(directory, "SOUL.md"))
    if (source_soul is not None or campaign is not None) and not (source_soul or "").strip():
        raise ValueError(f"{agent_id}: SOUL.md is missing or empty")
    rendered = campaign.render_soul(home, agent_id, source_soul) if campaign and source_soul is not None else source_soul
    profile = profile_dir(home, agent_id)
    native_path = _member(profile, "config.yaml")
    before = config_version(native_path)
    native = require_readable_config_before_write(native_path)
    native_soul = _read_soul(_member(profile, "SOUL.md"))
    defaults = campaign.saved if campaign else {}
    resolved = resolve_settings(settings_from(defaults, campaign_id or agent_id), settings_from(record, agent_id))
    next_native = {**native, **resolved}
    updated = [key for key, value in resolved.items() if native.get(key) != value]
    if (campaign and "mcp_servers" in record.get("effective", {}) and "mcp_servers" not in resolved
            and "mcp_servers" in next_native):
        del next_native["mcp_servers"]
        updated.append("mcp_servers")
    next_native, profile_changes = apply_profile_settings(
        next_native, record, defaults, agent_id, campaign=campaign is not None,
        orchestrator=bool(campaign and agent_id == campaign.status["orchestrator"]),
    )
    stored = load_env_file(_member(profile, ".env"))
    credentials = plan_credential_updates(profile, set(env), stored, env)
    required = credential_keys(settings_from(next_native, agent_id))
    names, available = key_status(required, {**stored, **credentials})
    next_record = materialize_agent_settings(record, resolved) if campaign else dict(record)
    next_record["all-keys"] = sorted(names)
    next_record["available-keys"] = sorted(available)
    return _AgentUpdate(agent_id, record_path, digest, native_path, before, next_record if next_record != record else None,
                        next_native, source_soul, native_soul, rendered, tuple(updated + profile_changes),
                        names, available, credentials, plan_role_skills(home, profile, record.get("oma_skills")),
                        plan_role_jobs(profile, record.get("jobs")) if defaults.get("mode") != "control" else None)


def _verify_record(update: _AgentUpdate) -> None:
    authored_path = _member(update.record_path.parent, "config.yaml")
    with authored_path.open("rb") as stream:  # config-reader: ok — authored OMA record, not native config
        digest = sha256(stream.read(_MAX_RECORD_BYTES + 1)).hexdigest()
    if (digest != update.revision
            or _read_soul(_member(update.record_path.parent, "SOUL.md")) != update.source_soul):
        raise StaleRecord(f"{update.agent_id}: the saved agent record changed during sync")


def _verify_plan(update: _AgentUpdate) -> None:
    _verify_record(update)
    if (config_version(update.native_path) != update.native_version
            or _read_soul(_member(update.native_path.parent, "SOUL.md")) != update.native_soul):
        raise StaleRecord(f"{update.agent_id}: the native profile changed during sync")


def _apply(update: _AgentUpdate) -> tuple[list[str], str]:
    profile = update.native_path.parent
    changed = list(update.updated)
    revision = update.revision
    with bind_profile_scope(profile, hydrate_secrets=False):
        _verify_plan(update)
        with apply_role_skills(update.skills) as skills_changed:
            if update.credentials:
                apply_credential_updates(profile, update.credentials)
                changed.append("env")
            if update.updated:
                atomic_config_replace(update.native_path, update.native)
            if update.rendered_soul is not None and update.rendered_soul != update.native_soul:
                atomic_write_text(_member(profile, "SOUL.md"), update.rendered_soul, preserve_mode=True, create_mode=0o644)
                changed.append("SOUL.md")
            if apply_role_jobs(profile, update.jobs):
                changed.append("jobs")
            if skills_changed:
                changed.append("oma_skills")
        if update.record is not None:
            _verify_record(update)
            atomic_config_replace(update.record_path, update.record)
            revision = sha256(update.record_path.read_bytes()).hexdigest()
    return changed, revision


def _load_installed(home: Path, path: Path, campaign_id: str) -> _Campaign:
    saved = read_mapping(path)
    status = _status(home, campaign_id, saved)
    if status["state"] != "installed":
        raise ValueError(f"Campaign {campaign_id!r} is not fully installed; no settings were synced")
    validate_record("campaign", saved, path)
    return _Campaign(path, saved, status)


def _verify_campaign(campaign: _Campaign) -> None:
    if read_mapping(campaign.path) != campaign.saved:
        raise StaleRecord(f"{campaign.status['id']}: campaign changed during sync; retry")


def _publish_campaign_keys(campaign: _Campaign, pairs: list[tuple[set[str], set[str]]]) -> None:
    _verify_campaign(campaign)
    names = {key for listed, _ in pairs for key in listed}
    missing = {key for listed, available in pairs for key in listed - available}
    summary = {"all-keys": sorted(names), "available-keys": sorted(names - missing)}
    if any(campaign.saved.get(key) != value for key, value in summary.items()):
        atomic_config_write(campaign.path, {**campaign.saved, **summary})


def sync_campaign(home: Path, campaign_id: str, *, env: dict[str, str] | None = None) -> dict:
    require_file_tooling("OMA campaign settings sync")
    supplied = validate_sync_env(env) if env is not None else {}
    campaign_path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(campaign_path):
        print(f"OMA sync: validating {campaign_id}", file=sys.stderr)
        campaign = _load_installed(home, campaign_path, campaign_id)
        agents = campaign.status["agents"]
        plans = [_plan_agent(home, agent_id, supplied, campaign=campaign) for agent_id in agents]
        for plan in plans:
            _verify_plan(plan)
        _verify_campaign(campaign)
        updates = []
        for plan in plans:
            changed, _ = _apply(plan)
            if changed or plan.record is not None:
                updates.append(plan.agent_id)
        _publish_campaign_keys(campaign, [(plan.all_keys, plan.available_keys) for plan in plans])
        message = f"updated {len(updates)} profile(s)" if updates else "no agent changes"
        print(f"OMA sync: {message}", file=sys.stderr)
    return {"id": campaign_id, "agents": agents, "updated_agents": updates}


def _sync_campaign_agent(home: Path, agent_id: str, supplied: dict[str, str], revision: str | None) -> dict:
    campaign_id = agent_id.partition("__")[0]
    path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(path):
        campaign = _load_installed(home, path, campaign_id)
        if agent_id not in campaign.status["agents"]:
            raise ValueError(f"{agent_id}: not on the installed campaign roster")
        plan = _plan_agent(home, agent_id, supplied, campaign=campaign, revision=revision)
        pairs = [(plan.all_keys, plan.available_keys)]
        for member in campaign.status["agents"]:
            if member != agent_id:
                profile = profile_dir(home, member)
                native = require_readable_config_before_write(_member(profile, "config.yaml"))
                pairs.append(key_status(credential_keys(settings_from(native, member)), load_env_file(_member(profile, ".env"))))
        _verify_campaign(campaign)
        changed, digest = _apply(plan)
        _publish_campaign_keys(campaign, pairs)
    return {"id": agent_id, "revision": digest, "updated": changed}


def sync_agent(home: Path, agent_id: str, *, revision: str | None = None, env: dict[str, str] | None = None) -> dict:
    require_file_tooling("OMA agent sync")
    supplied = validate_sync_env(env) if env is not None else {}
    if agent_id in STANDALONE_IDS:
        directory = record_dir(home, agent_id)
        if not directory.is_dir():
            raise FileNotFoundError(f"The {agent_id} agent record is missing")
        with _FileLock(_member(directory, ".sync.lock"), timeout=10):
            plan = _plan_agent(home, agent_id, supplied, revision=revision)
            changed, digest = _apply(plan)
        return {"id": agent_id, "revision": digest, "updated": changed}
    if not PROFILE_ID_RE.fullmatch(agent_id) or "__" not in agent_id:
        raise ValueError("Expected default, maintenance, or a canonical campaign agent ID")
    return _sync_campaign_agent(home, agent_id, supplied, revision)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sync-campaign", description=__doc__)
    parser.add_argument("campaign_id", metavar="CAMPAIGN_ID")
    parser.add_argument("--env-stdin", action="store_true", help="Read a JSON map of profile environment values from stdin")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(sync_campaign(default_home(), args.campaign_id,
                                       env=read_sync_env() if args.env_stdin else None), indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"OMA sync: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
