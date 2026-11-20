"""Install validated definitions and keep an installation-local YAML ledger."""

from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
import shutil
import sqlite3
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from agent.skill_selection import OMA_DEFAULT_ONLY_SKILLS
from agent.skill_utils import parse_config_string_list
from hermes_cli import kanban_db
from hermes_cli.config import atomic_config_replace, atomic_config_write
from hermes_cli.config_backend import FileBackend, require_file_tooling
from hermes_cli.config_defaults import DEFAULT_CONFIG
from hermes_cli.config_home import OMA_PLAYBOOK_SKILL
from hermes_cli.oma_playbooks.source import Agent, Playbook, checked_id, read_mapping
from hermes_cli.profile_provision import ProfileCreateRequest, provision_profile
from hermes_cli.profiles import get_profile_dir, profile_exists
from hermes_constants import get_hermes_home
from toolsets import resolve_toolset
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


def _campaign_config_path(home: Path, campaign_id: str) -> Path:
    oma = _real_path(home / "oma")
    campaigns = _real_path(oma / "campaigns")
    directory = _real_path(campaigns / checked_id(campaign_id))
    path = _real_path(directory / "config.yaml")
    if FileBackend().exists(directory) and read_mapping(path).get("id") != campaign_id:
        raise ValueError(f"Campaign config ID does not match its installation: {path}")
    return path


def _ensure_campaign_config(path: Path, record: dict) -> Path:
    routing = {key: record[key] for key in ("orchestrator", "kanban_board", "kanban_board_name") if record.get(key)}
    if FileBackend().exists(path.parent):
        config = read_mapping(path)
        missing = {key: value for key, value in routing.items() if key not in config}
        if missing:
            atomic_config_write(path, {**config, **missing})
        return path
    config = {key: record.get(key) for key in ("id", "name", "description", "version")}
    config.update(goals=[], plans=[], **routing)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_yaml_write(path, config, create_mode=0o600)  # config-writer: ok — campaign data, not Hermes settings
    return path


def configure(home: Path, campaign_id: str) -> dict:
    """Seed config or missing routing metadata without reading source files."""
    require_file_tooling("OMA campaign configuration")
    registry = _registry(home)
    with _install_lock(registry):
        record = installed(home, campaign_id)[0]
        if record.get("state") != "installed":
            raise ValueError(f"Campaign {campaign_id!r} is not fully installed")
        path = _ensure_campaign_config(_campaign_config_path(home, campaign_id), record)
        return {"id": campaign_id, "config_path": str(path)}


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
    unavailable = (needed & (disabled | OMA_DEFAULT_ONLY_SKILLS)) | (needed - (bundled | set(agent.skills)))
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


def _with_kanban(config: dict, board: str, orchestrator: str, agent_id: str) -> dict:
    agent_config = config.get("agent", {})
    kanban = config.get("kanban", {})
    if not isinstance(agent_config, dict) or not isinstance(kanban, dict):
        raise ValueError(f"{agent_id}: agent and kanban must be mappings")
    disabled = parse_config_string_list(agent_config.get("disabled_toolsets"))
    if any(set(resolve_toolset(name)) & set(resolve_toolset("kanban")) for name in disabled):
        raise ValueError(f"{agent_id}: agent.disabled_toolsets conflicts with campaign Kanban tools")
    config = {**config, "kanban": {**kanban, "profile_board": board, "orchestrator_profile": orchestrator}}
    enabled = agent_config.get("enabled_toolsets")
    if enabled is not None:
        if not isinstance(enabled, list) or any(not isinstance(name, str) or not name for name in enabled):
            raise ValueError(f"{agent_id}: agent.enabled_toolsets must be a list of toolset names or null")
        config["agent"] = {**agent_config, "enabled_toolsets": list(dict.fromkeys([*enabled, "kanban"]))}
    else:
        config["toolsets"] = list(dict.fromkeys([*parse_config_string_list(config.get("toolsets")), "kanban"]))
        if isinstance(platforms := config.get("platform_toolsets"), dict):
            config["platform_toolsets"] = {
                platform: list(dict.fromkeys([*selected, "kanban"])) if isinstance(selected, list) else selected
                for platform, selected in platforms.items()
            }
    return config


def _initialize(agent: Agent, config: dict, staging: Path) -> None:
    atomic_config_replace(staging / "config.yaml", config)
    with bind_profile_scope(staging, hydrate_secrets=False):
        result = sync_skills(quiet=True)
    bundled_needed = set(config["skills"].get("auto_load", [])) - set(agent.skills)
    if not bundled_needed.issubset(result["copied"]):
        raise ValueError(f"{agent.id}: a bundled preload could not be installed")
    for name, source in agent.skills.items():
        shutil.copytree(source, staging / "skills" / name)


def _scratch_path(agent_id: str) -> Path:
    return Path("agents", agent_id, "tmp")


def _agent_saves_path(home: Path, agent_id: str) -> Path:
    path = home
    for part in ("oma", "agents", agent_id, "saves"):
        path = _real_path(path / part)
        if path.exists() and not path.is_dir():
            raise ValueError(f"Expected an agent saves directory, found a non-directory: {path}")
    return path


def _new_record(playbook: Playbook, board: str) -> dict:
    return {
        "id": playbook.id,
        "name": playbook.name,
        "version": playbook.version,
        "description": playbook.description,
        "source_manifest": str(playbook.source_manifest),
        "orchestrator": playbook.orchestrator,
        "kanban_board": board,
        "state": "installing",
        "started_at": datetime.now(UTC).isoformat(),
        "agents": {agent.id: {"version": agent.version, "profile": agent.id,
                              "oma_skills": sorted(agent.skills), "declared_jobs": agent.jobs,
                              "scratch_dir": _scratch_path(agent.id).as_posix(),
                              "state": "pending"} for agent in playbook.agents},
    }


def _campaign_context_soul(config_path: Path) -> str:
    oma = config_path.parents[2]
    playbook = oma / "playbook" / "config.yaml"
    brand = oma / "brand" / "config.yaml"
    return (
        "## Your campaign context\n\n"
        f"- Campaign: read `{config_path}` for your campaign's goals and plans.\n"
        f"- Playbook: read `{playbook}` for the shared strategy.\n"
        f"- Brand: read `{brand}` for the shared brand context.\n\n"
        "No record links are required; use only these fixed paths. "
        "Don't follow symlinks outside those record directories. "
        "If a record needed for the work is missing, report the gap rather than guessing. "
        "Do not scan other records or change these records as part of loading context.\n"
    )


def _publish_profiles(playbook: Playbook, configs: dict[str, dict], saves_paths: dict[str, Path],
                      record: dict, path: Path, campaign_config: Path) -> None:
    campaign_context = _campaign_context_soul(campaign_config)
    board = record["kanban_board"]
    roster = ", ".join(f"`{agent.id}`" for agent in playbook.agents)
    for agent in playbook.agents:
        scratch = path.parent / _scratch_path(agent.id)
        scratch.mkdir(mode=0o700, parents=True)
        saves = saves_paths[agent.id]
        saves.mkdir(mode=0o700, parents=True, exist_ok=True)
        if agent.id == playbook.orchestrator:
            board_role = f"Coordinate the team's work here. Assign tasks only within your campaign roster: {roster}."
        else:
            board_role = f"Your orchestrator is `{playbook.orchestrator}`. Return handoffs on your assigned task."
        soul = (f"{agent.soul.rstrip()}\n\n{campaign_context}\n## Campaign Kanban board\n\n"
                f"Use only `{board}` for this campaign's Kanban work. {board_role}\n\n"
                "## Playbook scratch directory\n\n"
                f"Use `{scratch}` for this profile's temporary playbook files.\n\n"
                "## Saved context\n\n"
                f"Use `{saves}` to remember context for future sessions. Save useful decisions, "
                "preferences, findings, blockers, and next steps as concise Markdown (`.md`) "
                "notes only. When resuming work, read the relevant notes if needed and update "
                "them when the context changes. Do not store credentials or raw transcripts.\n")
        request = ProfileCreateRequest(name=agent.id, alias=False, mirror_credentials=False,
                                       description=agent.description, soul=soul)
        provision_profile(request, initialize=partial(_initialize, agent, configs[agent.id]))
        record["agents"][agent.id]["state"] = "installed"
        atomic_yaml_write(path, record)


def install(home: Path, playbook: Playbook) -> dict:
    require_file_tooling("OMA playbook installation")
    registry = _registry(home)
    path = _record_path(registry, playbook.id)
    with _install_lock(registry):
        config_path = _campaign_config_path(home, playbook.id)
        if path.exists():
            record = installed(home, playbook.id)[0]
            if record.get("state") == "installed":
                _ensure_campaign_config(config_path, record)
                return record
            raise ValueError(f"An installation record already exists at {path}; no profiles were changed")
        policies = _check_profiles(home, playbook)
        saves_paths = {agent.id: _agent_saves_path(home, agent.id) for agent in playbook.agents}
        board = f"campaign-{playbook.id}"
        record = _new_record(playbook, board)
        if FileBackend().exists(config_path.parent):
            existing = read_mapping(config_path)
            for key in ("orchestrator", "kanban_board"):
                if key in existing and existing[key] != record[key]:
                    raise ValueError(f"Campaign config {key} conflicts with the installation: {config_path}")
        configs = {
            agent.id: _with_kanban({**agent.config, "skills": policies[agent.id],
                                   "_config_version": DEFAULT_CONFIG["_config_version"]},
                                  board, playbook.orchestrator, agent.id)
            for agent in playbook.agents
        }
        if (board_dir := kanban_db.board_dir(board)).exists() or board_dir.is_symlink():
            raise ValueError(f"Kanban board {board!r} already exists; refusing to reuse an unrelated board")
        path.parent.mkdir(mode=0o700)
        atomic_yaml_write(path, record)
        try:
            board_metadata = kanban_db.create_board(board, name=playbook.name, description=playbook.description)
        except sqlite3.Error as exc:
            raise ValueError(f"Could not initialize campaign Kanban board {board!r}: {exc}") from exc
        record["kanban_board_name"] = board_metadata["name"]
        _ensure_campaign_config(config_path, record)
        _publish_profiles(playbook, configs, saves_paths, record, path, config_path)
        record["state"] = "installed"
        record["installed_at"] = datetime.now(UTC).isoformat()
        atomic_yaml_write(path, record)
        return installed(home, playbook.id)[0]
