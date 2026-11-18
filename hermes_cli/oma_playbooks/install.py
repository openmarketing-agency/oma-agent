"""Install validated definitions and keep an installation-local YAML ledger."""

from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
import shutil
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from hermes_cli.config import atomic_config_replace
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.config_defaults import DEFAULT_CONFIG
from hermes_cli.config_home import OMA_PLAYBOOK_SKILL
from hermes_cli.oma_playbooks.releases import Release
from hermes_cli.oma_playbooks.source import Agent, Playbook, checked_id, read_mapping
from hermes_cli.profile_provision import ProfileCreateRequest, provision_profile
from hermes_cli.profiles import get_profile_dir, profile_exists
from hermes_constants import get_hermes_home
from tools.skills_sync import bundled_skill_names, sync_skills
from utils import atomic_yaml_write


def default_home() -> Path:
    home = get_hermes_home().resolve()
    if home != get_profile_dir("default").resolve():
        raise ValueError("Playbook management must run from the default OMA Agent profile")
    return home


def _real_path(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked playbook state: {path}")
    return path


def _registry(home: Path) -> Path:
    return _real_path(home / "playbooks")


def _record_path(registry: Path, playbook_id: str) -> Path:
    directory = _real_path(registry / checked_id(playbook_id))
    return _real_path(directory / "installation.yaml")


def installed(home: Path, playbook_id: str | None = None) -> list[dict]:
    registry = _registry(home)
    ids = ([checked_id(playbook_id)] if playbook_id else
           sorted(item.name for item in registry.iterdir() if item.is_dir() and not item.name.startswith("."))
           if registry.is_dir() else [])
    records = []
    for name in ids:
        path = _record_path(registry, name)
        if not path.is_file() and not playbook_id:
            continue
        record = read_mapping(path)
        agents = record.get("agents")
        if record.get("id") != name or not isinstance(agents, dict):
            raise ValueError(f"Invalid installation record: {path}")
        record["present_profiles"] = [agent for agent in agents if profile_exists(agent)]
        records.append(record)
    return records


@contextmanager
def _install_lock(registry: Path):
    registry.mkdir(mode=0o700, exist_ok=True)
    lock = registry / ".install-lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError(f"An installation is running or was interrupted; inspect {lock}") from None
    try:
        yield
    finally:
        lock.rmdir()


def _readiness(agent: Agent, bundled: set[str]) -> dict:
    skills = agent.config.get("skills", {})
    if not isinstance(skills, dict):
        raise ValueError(f"{agent.id}: skills must be a mapping")
    for field in ("disabled", "auto_load", "enabled"):
        if field in skills and not (field == "enabled" and skills[field] is None):
            if not isinstance(skills[field], list) or any(not isinstance(n, str) for n in skills[field]):
                raise ValueError(f"{agent.id}: skills.{field} must be a list of names")
    disabled = set(skills.get("disabled", [])) | {OMA_PLAYBOOK_SKILL}
    needed = set(agent.skills) | set(skills.get("auto_load", []))
    unavailable = (needed & disabled) | (needed - (bundled | set(agent.skills)))
    if skills.get("enabled") is not None:
        unavailable |= needed - set(skills["enabled"])
    if unavailable:
        raise ValueError(f"{agent.id}: configured skills would not be available: {', '.join(sorted(unavailable))}")
    return {**skills, "disabled": sorted(disabled)}


def _check_profiles(home: Path, playbook: Playbook) -> dict[str, dict]:
    policies = {}
    root = home / "profiles"
    if root.is_symlink():
        raise ValueError(f"Refusing symlinked profiles directory: {root}")
    bundled = set(bundled_skill_names())
    for agent in playbook.agents:
        path = get_profile_dir(agent.id)
        if path.resolve() != root / agent.id or path.is_symlink() or path.exists():
            raise ValueError(f"Profile {agent.id} already exists or does not resolve under this OMA home")
        if set(agent.skills) & bundled:
            raise ValueError(f"{agent.id}: an OMA dependency collides with a bundled skill")
        policies[agent.id] = _readiness(agent, bundled)
    return policies


def _initialize(agent: Agent, skills: dict, staging: Path) -> None:
    config = {**agent.config, "skills": skills, "_config_version": DEFAULT_CONFIG["_config_version"]}
    atomic_config_replace(staging / "config.yaml", config)
    with bind_profile_scope(staging, hydrate_secrets=False):
        result = sync_skills(quiet=True)
    bundled_needed = set(skills.get("auto_load", [])) - set(agent.skills)
    if not bundled_needed.issubset(result["copied"]):
        raise ValueError(f"{agent.id}: a bundled preload could not be installed")
    for name, source in agent.skills.items():
        shutil.copytree(source, staging / "skills" / name)


def _scratch_path(agent_id: str) -> Path:
    return Path("agents", agent_id, "tmp")


def _new_record(playbook: Playbook) -> dict:
    return {
        "id": playbook.id,
        "name": playbook.name,
        "version": playbook.version,
        "description": playbook.description,
        "source_manifest": f"playbooks/{playbook.id}/config.yaml",
        "orchestrator": playbook.orchestrator,
        "state": "installing",
        "started_at": datetime.now(UTC).isoformat(),
        "agents": {agent.id: {"version": agent.version, "profile": agent.id,
                              "oma_skills": sorted(agent.skills), "declared_jobs": agent.jobs,
                              "scratch_dir": _scratch_path(agent.id).as_posix(),
                              "state": "pending"} for agent in playbook.agents},
    }


def _publish_profiles(playbook: Playbook, policies: dict[str, dict], record: dict, path: Path) -> None:
    for agent in playbook.agents:
        scratch = path.parent / _scratch_path(agent.id)
        scratch.mkdir(mode=0o700, parents=True)
        soul = (f"{agent.soul.rstrip()}\n\n## Playbook scratch directory\n\n"
                f"Use `{scratch}` for this profile's temporary playbook files.\n")
        request = ProfileCreateRequest(name=agent.id, alias=False, mirror_credentials=False,
                                       description=agent.description, soul=soul)
        provision_profile(request, initialize=partial(_initialize, agent, policies[agent.id]))
        record["agents"][agent.id]["state"] = "installed"
        atomic_yaml_write(path, record)


def install(home: Path, playbook: Playbook, *, release: Release | None = None) -> dict:
    require_file_tooling("OMA playbook installation")
    registry = _registry(home)
    path = _record_path(registry, playbook.id)
    with _install_lock(registry):
        if path.exists():
            record = read_mapping(path)
            if record.get("state") == "installed" and record.get("version") == playbook.version:
                return installed(home, playbook.id)[0]
            raise ValueError(f"An installation record already exists at {path}; no profiles were changed")
        policies = _check_profiles(home, playbook)
        path.parent.mkdir(mode=0o700)
        record = _new_record(playbook)
        if release is not None:
            record["source"] = release.provenance()
        atomic_yaml_write(path, record)
        _publish_profiles(playbook, policies, record, path)
        record["state"] = "installed"
        record["installed_at"] = datetime.now(UTC).isoformat()
        atomic_yaml_write(path, record)
        return installed(home, playbook.id)[0]
