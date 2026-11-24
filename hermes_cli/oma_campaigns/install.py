"""Provision campaigns using the existing campaign and agent records."""

from contextlib import contextmanager
from functools import partial
import shutil
import sqlite3
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from agent.secret_scope import load_env_file
from agent.skill_selection import OMA_DEFAULT_ONLY_SKILLS
from agent.skill_utils import parse_config_string_list
from hermes_cli import kanban_db
from hermes_cli.config import (
    atomic_config_replace, atomic_config_write, read_user_config_raw, require_env_writable, save_env_value,
)
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.config_credential_values import refuse_redacted_env_value
from hermes_cli.config_defaults import DEFAULT_CONFIG
from hermes_cli.config_home import OMA_CAMPAIGN_SKILL
from hermes_cli.oma_campaigns.defaults import agent_defaults, snapshot
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.role_skills import write_skill_inventory
from hermes_cli.oma_campaigns.settings import (
    apply_profile_settings,
    credential_keys, materialize_agent_settings, read_agent_record, resolve_settings, settings_from,
)
from hermes_cli.oma_campaigns.source import (
    DEFAULT_CAMPAIGN_MODE, Agent, Campaign, campaign_fields, checked_id, read_mapping, resolve,
)
from hermes_cli.profile_provision import ProfileCreateRequest, provision_profile
from hermes_cli.profiles import get_profile_dir, profile_exists
from hermes_constants import get_hermes_home
from toolsets import resolve_toolset
from tools.skills_sync import bundled_skill_names, sync_skills

def default_home() -> Path:
    home = get_hermes_home().resolve()
    if home != get_profile_dir("default").resolve():
        raise ValueError("Campaign management must run from the default OMA Agent profile")
    return home


def _real_path(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked campaign state: {path}")
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
    lifecycle = config.get("lifecycle_state", "resumed" if state == "installed" else "paused")
    return {**record, "state": state, "present_profiles": present,
            "lifecycle_state": lifecycle, "mode": config.get("mode", DEFAULT_CAMPAIGN_MODE),
            "integrations": config.get("integrations", []),
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
        validate_record("campaign", config, path)
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
    disabled = set(skills.get("disabled", [])) | {OMA_CAMPAIGN_SKILL}
    needed = set(agent.skills) | set(skills.get("auto_load", []))
    unavailable = (needed & (disabled | OMA_DEFAULT_ONLY_SKILLS)) | (needed - (bundled | set(agent.skills)))
    if skills.get("enabled") is not None:
        unavailable |= needed - set(skills["enabled"])
    if unavailable:
        raise ValueError(f"{agent.id}: configured skills would not be available: {', '.join(sorted(unavailable))}")
    return {**skills, "disabled": sorted(disabled)}


def _check_profiles(home: Path, campaign: Campaign) -> dict[str, dict]:
    policies = {}
    root = home / "profiles"
    if root.is_symlink():
        raise ValueError(f"Refusing symlinked profiles directory: {root}")
    bundled = set(bundled_skill_names())
    for agent in campaign.agents:
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
    if "kanban" in agent_config["enabled_toolsets"] and any(
        set(resolve_toolset(name)) & set(resolve_toolset("kanban")) for name in disabled
    ):
        raise ValueError(f"{agent_id}: agent.disabled_toolsets conflicts with campaign Kanban tools")
    return {**config, "kanban": {**kanban, "profile_board": board, "orchestrator_profile": orchestrator}}


def _camofox_requested(config: dict) -> bool:
    agent = config.get("agent", {})
    if "camofox" in parse_config_string_list(agent.get("disabled_toolsets")):
        return False
    return "camofox" in agent["enabled_toolsets"]


def _without_camofox(config: dict) -> dict:
    agent = config["agent"]
    return {**config, "agent": {**agent, "enabled_toolsets": [
        name for name in agent["enabled_toolsets"] if name != "camofox"
    ]}}


def _camofox_credentials(home: Path) -> dict[str, str]:
    saved = load_env_file(_real_path(home / ".env"))
    pair = {name: saved.get(name, "").strip() for name in ("CAMOFOX_URL", "CAMOFOX_API_KEY")}
    if not all(pair.values()):
        return {}
    for name, value in pair.items():
        if not value.isascii() or "\n" in value or "\r" in value:
            raise ValueError(f"{name} must be a single-line ASCII value in the default profile's .env")
        refuse_redacted_env_value(name, value)
        require_env_writable(name, "set")
    return pair


def _configure_camofox(home: Path, configs: dict[str, dict]) -> tuple[dict[str, dict[str, str]], set[str]]:
    requested = {agent_id for agent_id, config in configs.items() if _camofox_requested(config)}
    pair = _camofox_credentials(home) if requested else {}
    skipped = set()
    if not pair:
        for agent_id, config in configs.items():
            if "camofox" in config["agent"]["enabled_toolsets"]:
                configs[agent_id] = _without_camofox(config)
                skipped.add(agent_id)
    return ({agent_id: pair for agent_id in requested} if pair else {}), skipped


def _initialize(agent: Agent, config: dict, credentials: dict[str, str], staging: Path) -> None:
    atomic_config_replace(staging / "config.yaml", config)
    with bind_profile_scope(staging, hydrate_secrets=False):
        for name, value in credentials.items():
            save_env_value(name, value)
        if credentials:
            saved = load_env_file(staging / ".env")
            if any(saved.get(name) != value for name, value in credentials.items()):
                raise ValueError(f"{agent.id}: could not verify the new profile's saved settings")
        result = sync_skills(quiet=True)
    bundled_needed = set(config["skills"].get("auto_load", [])) - set(agent.skills)
    if not bundled_needed.issubset(result["copied"]):
        raise ValueError(f"{agent.id}: a bundled preload could not be installed")
    for name, source in agent.skills.items():
        shutil.copytree(source, staging / "skills" / name)
    if agent.skills:
        write_skill_inventory(staging / "skills", {name: name for name in agent.skills})


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


def campaign_soul(soul: str, agent_id: str, orchestrator: str, agents: tuple[str, ...], board: str,
                  campaign_config: Path, saves: Path, scratch: Path) -> str:
    campaign_context = _campaign_context_soul(campaign_config)
    if agent_id == orchestrator:
        roster = ", ".join(f"`{name}`" for name in agents)
        board_role = f"Coordinate the team's work here. Assign tasks only within your campaign roster: {roster}."
    else:
        board_role = f"Your orchestrator is `{orchestrator}`. Return handoffs on your assigned task."
    return (
        f"{soul.rstrip()}\n\n{campaign_context}\n## Campaign Kanban board\n\n"
        f"Use only `{board}` for this campaign's Kanban work. {board_role}\n\n"
        "## Campaign publications\n\n"
        "Save each intended post or reply as a publication, in every campaign mode. Submit the exact platform, "
        "account, kind, content and reply target as JSON on stdin to "
        "`python -m hermes_cli.oma_campaigns.publications save`. Do not send it directly. The runtime handles "
        "automatic or human approval according to the campaign mode and queues the campaign publisher. "
        "Only the publisher posts, after claiming the saved revision, then records the provider receipt. "
        "If the required tool or approved claim is unavailable, report the blocker without posting.\n\n"
        "## Campaign scratch directory\n\n"
        f"Use `{scratch}` for this profile's temporary campaign files.\n\n"
        "## Saved context\n\n"
        f"Use `{saves}` to remember context for future sessions. Save useful decisions, "
        "preferences, findings, blockers, and next steps as concise Markdown (`.md`) "
        "notes only. When resuming work, read the relevant notes if needed and update "
        "them when the context changes. Do not store credentials or raw transcripts.\n"
    )


def _publish_profiles(campaign: Campaign, configs: dict[str, dict], paths: dict[str, tuple[Path, Path]],
                      board: str, campaign_config: Path, credentials: dict[str, dict[str, str]]) -> None:
    roster = tuple(agent.id for agent in campaign.agents)
    for agent in campaign.agents:
        saves, scratch = paths[agent.id]
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        saves.mkdir(mode=0o700, parents=True, exist_ok=True)
        soul = campaign_soul(agent.soul, agent.id, campaign.orchestrator, roster, board, campaign_config, saves, scratch)
        request = ProfileCreateRequest(name=agent.id, alias=False, mirror_credentials=False,
                                       description=agent.description, soul=soul)
        provision_profile(request, initialize=partial(_initialize, agent, configs[agent.id], credentials[agent.id]))

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
        validate_record("campaign", config, config_path)
        publisher = f"{campaign_id}__publisher"
        if publisher not in record["agents"]:
            raise ValueError(f"{campaign_id}: roster must contain the canonical publisher {publisher}")
        campaign = resolve(home, campaign_id)
        policies = _check_profiles(home, campaign)
        paths = {agent.id: (_agent_data_dir(home, agent.id, "saves"), _agent_data_dir(home, agent.id, "tmp"))
                 for agent in campaign.agents}
        inherited = "model" not in config
        resolved_campaign, model_credential = snapshot(home, config)
        inherited = inherited and "model" in resolved_campaign
        for name in model_credential:
            require_env_writable(name, "set")
        defaults = settings_from(resolved_campaign, campaign_id)
        effective = {agent.id: resolve_settings(defaults, settings_from(agent.config, agent.id))
                     for agent in campaign.agents}
        board = f"campaign-{campaign.id}"
        authored = {agent.id: agent_defaults(agent.config, agent.id, orchestrator=agent.id == campaign.orchestrator)
                    for agent in campaign.agents}
        configs = {
            agent.id: _with_kanban({**authored[agent.id], **effective[agent.id], "skills": policies[agent.id],
                                   "_config_version": DEFAULT_CONFIG["_config_version"]},
                                  board, campaign.orchestrator, agent.id)
            for agent in campaign.agents
        }
        for agent in campaign.agents:
            configs[agent.id], _ = apply_profile_settings(
                configs[agent.id], authored[agent.id], resolved_campaign, agent.id,
                orchestrator=agent.id == campaign.orchestrator, campaign=True,
            )
        camofox, skipped_camofox = _configure_camofox(home, configs)
        credentials = {agent.id: {**(model_credential if "model" not in agent.config else {}),
                                  **camofox.get(agent.id, {})} for agent in campaign.agents}
        if (board_dir := kanban_db.board_dir(board)).exists() or board_dir.is_symlink():
            raise ValueError(f"Kanban board {board!r} already exists; refusing to reuse an unrelated board")
        config.setdefault("integrations", [])
        atomic_config_write(config_path, {**config, "kanban_board": board, "installation_state": "installing",
                                          "lifecycle_state": "paused"})
        try:
            board_metadata = kanban_db.create_board(board, name=campaign.name, description=campaign.description)
        except sqlite3.Error as exc:
            raise ValueError(f"Could not initialize campaign Kanban board {board!r}: {exc}") from exc
        _publish_profiles(campaign, configs, paths, board, config_path, credentials)
        all_keys, missing_keys = set(), set()
        for agent_id, settings in effective.items():
            path, agent_record = read_agent_record(home, campaign_id, agent_id)
            policy = {key: authored[agent_id][key] for key in ("agent", "tools")}
            updated = materialize_agent_settings({**agent_record, **policy}, settings)
            if agent_id in skipped_camofox:
                updated = _without_camofox(updated)
            if inherited:
                required = credential_keys(settings)
                available = required & credentials[agent_id].keys()
                updated.update({"all-keys": sorted(required), "available-keys": sorted(available)})
                all_keys.update(required)
                missing_keys.update(required - available)
            if updated != agent_record:
                atomic_config_replace(path, updated)
        current = read_mapping(config_path)
        if inherited:
            current.update({"all-keys": sorted(all_keys), "available-keys": sorted(all_keys - missing_keys)})
        current.setdefault("kanban_board_name", board_metadata["name"])
        current["installation_state"] = "installed"
        atomic_config_write(config_path, current)
        return _status(home, campaign_id, current)
