"""Provision campaigns using the existing campaign and agent records."""

from contextlib import contextmanager
from functools import partial
import shutil
import sqlite3
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from agent.skill_selection import OMA_DEFAULT_ONLY_SKILLS
from agent.skill_utils import parse_config_string_list
from hermes_cli import kanban_db
from hermes_cli.config import atomic_config_replace, atomic_config_write, read_user_config_raw
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.config_defaults import DEFAULT_CONFIG
from hermes_cli.config_home import OMA_PLAYBOOK_SKILL
from hermes_cli.oma_playbooks.source import Agent, Playbook, campaign_fields, checked_id, read_mapping, resolve
from hermes_cli.profile_provision import ProfileCreateRequest, provision_profile
from hermes_cli.profiles import get_profile_dir, profile_exists
from hermes_constants import get_hermes_home
from toolsets import resolve_toolset
from tools.skills_sync import bundled_skill_names, sync_skills

def default_home() -> Path:
    home = get_hermes_home().resolve()
    if home != get_profile_dir("default").resolve():
        raise ValueError("Playbook management must run from the default OMA Agent profile")
    return home


def _real_path(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked playbook state: {path}")
    return path


def _campaigns_dir(home: Path) -> Path:
    return _real_path(_real_path(home / "oma") / "campaigns")


def _campaign_config_path(campaigns: Path, campaign_id: str) -> Path:
    directory = _real_path(campaigns / checked_id(campaign_id))
    return _real_path(directory / "config.yaml")


def _profile_matches(home: Path, agent_id: str, board: str, orchestrator: str) -> bool:
    profile = get_profile_dir(agent_id)
    expected = home / "profiles" / agent_id
    config = profile / "config.yaml"
    if profile.resolve() != expected or profile.is_symlink() or config.is_symlink() or not profile_exists(agent_id):
        return False
    routing = read_user_config_raw(config).get("kanban")
    return (isinstance(routing, dict) and routing.get("profile_board") == board
            and routing.get("orchestrator_profile") == orchestrator)


def _status(home: Path, campaign_id: str, config: dict) -> dict:
    record = campaign_fields(config, campaign_id)
    board = f"campaign-{campaign_id}"
    marker = config.get("installation_state")
    if marker not in (None, "installing", "installed"):
        raise ValueError(f"{campaign_id}: invalid installation_state")
    if "kanban_board" in config and config["kanban_board"] != board:
        raise ValueError(f"{campaign_id}: campaign config kanban_board conflicts with {board!r}")
    recorded = marker is not None or config.get("kanban_board") == board
    present = [agent for agent in record["agents"]
               if recorded and _profile_matches(home, agent, board, record["orchestrator"])]
    metadata = kanban_db.read_board_metadata(board) if recorded and kanban_db.board_exists(board) else None
    ready = (metadata is not None and not metadata.get("archived") and present == record["agents"])
    if marker == "installing" or (marker == "installed" and not ready):
        state = "incomplete"
    else:
        state = "installed" if ready else "draft"
    return {**record, "state": state, "present_profiles": present,
            "kanban_board": board if recorded else None,
            "kanban_board_name": metadata["name"] if metadata else None}


def installed(home: Path, campaign_id: str | None = None) -> list[dict]:
    campaigns = _campaigns_dir(home)
    if campaign_id is not None:
        return [_status(home, campaign_id, read_mapping(_campaign_config_path(campaigns, campaign_id)))]
    if not campaigns.is_dir():
        return []
    records = []
    for directory in sorted(campaigns.iterdir()):
        if directory.name.startswith(".") or not directory.is_dir():
            continue
        path = _campaign_config_path(campaigns, directory.name)
        if not path.is_file():
            continue
        config = read_mapping(path)
        if config.get("installation_state") is None and "kanban_board" not in config:
            continue
        record = _status(home, directory.name, config)
        if record["state"] != "draft":
            records.append(record)
    return records


def configure(home: Path, campaign_id: str) -> dict:
    """Backfill missing routing metadata from a verified board and roster."""
    require_file_tooling("OMA campaign configuration")
    campaigns = _campaigns_dir(home)
    path = _campaign_config_path(campaigns, campaign_id)
    with _install_lock(path):
        config = read_mapping(path)
        record = _status(home, campaign_id, config)
        if record["state"] != "installed":
            raise ValueError(f"Campaign {campaign_id!r} is not fully installed")
        missing = {key: record[key] for key in ("kanban_board", "kanban_board_name") if key not in config}
        if missing:
            atomic_config_write(path, {**config, **missing})
        return {"id": campaign_id, "config_path": str(path)}


@contextmanager
def _install_lock(config_path: Path):
    campaigns = config_path.parent.parent
    if not campaigns.is_dir():
        raise FileNotFoundError(f"Missing campaign config: {config_path}")
    lock = campaigns / ".install-lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError(f"A campaign operation is running or was interrupted; inspect {lock}") from None
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


def _agent_data_dir(home: Path, agent_id: str, name: str) -> Path:
    path = home
    for part in ("oma", "agents", agent_id, name):
        path = _real_path(path / part)
        if path.exists() and not path.is_dir():
            raise ValueError(f"Expected an agent {name} directory, found a non-directory: {path}")
    return path


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


def _publish_profiles(playbook: Playbook, configs: dict[str, dict], paths: dict[str, tuple[Path, Path]],
                      board: str, campaign_config: Path) -> None:
    campaign_context = _campaign_context_soul(campaign_config)
    roster = ", ".join(f"`{agent.id}`" for agent in playbook.agents)
    for agent in playbook.agents:
        saves, scratch = paths[agent.id]
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
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

def install(home: Path, campaign_id: str) -> dict:
    require_file_tooling("OMA campaign installation")
    campaigns = _campaigns_dir(home)
    config_path = _campaign_config_path(campaigns, campaign_id)
    with _install_lock(config_path):
        config = read_mapping(config_path)
        record = _status(home, campaign_id, config)
        if record["state"] == "installed":
            return record
        if record["state"] == "incomplete":
            raise ValueError(f"Campaign {campaign_id!r} has an incomplete installation; no profiles were changed")
        playbook = resolve(home, campaign_id)
        policies = _check_profiles(home, playbook)
        paths = {agent.id: (_agent_data_dir(home, agent.id, "saves"), _agent_data_dir(home, agent.id, "tmp"))
                 for agent in playbook.agents}
        board = f"campaign-{playbook.id}"
        configs = {
            agent.id: _with_kanban({**agent.config, "skills": policies[agent.id],
                                   "_config_version": DEFAULT_CONFIG["_config_version"]},
                                  board, playbook.orchestrator, agent.id)
            for agent in playbook.agents
        }
        if (board_dir := kanban_db.board_dir(board)).exists() or board_dir.is_symlink():
            raise ValueError(f"Kanban board {board!r} already exists; refusing to reuse an unrelated board")
        atomic_config_write(config_path, {**config, "kanban_board": board, "installation_state": "installing"})
        try:
            board_metadata = kanban_db.create_board(board, name=playbook.name, description=playbook.description)
        except sqlite3.Error as exc:
            raise ValueError(f"Could not initialize campaign Kanban board {board!r}: {exc}") from exc
        _publish_profiles(playbook, configs, paths, board, config_path)
        current = read_mapping(config_path)
        current.setdefault("kanban_board_name", board_metadata["name"])
        current["installation_state"] = "installed"
        atomic_config_write(config_path, current)
        return _status(home, campaign_id, current)
