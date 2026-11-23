"""Resolve a campaign and exactly the OMA skills its agents declare."""

import re
from dataclasses import dataclass
from pathlib import Path

import hermes_yaml as yaml
from agent.skill_selection import OMA_DEFAULT_ONLY_SKILLS, OMA_MAINTENANCE_ONLY_SKILLS
from hermes_constants import PROFILE_ID_RE
from hermes_cli.oma_campaigns.bundle import bundle_dir
from hermes_cli.oma_campaigns.schema import validate_record
from tools.skill_usage import read_skill_name

DEFAULT_CAMPAIGN_MODE = "approve"
_SOURCE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class Agent:
    id: str
    description: str
    config: dict
    soul: str
    skills: dict[str, Path]


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    description: str
    orchestrator: str
    agents: tuple[Agent, ...]


def checked_id(value: str) -> str:
    if not isinstance(value, str) or not _SOURCE_SLUG.fullmatch(value):
        raise ValueError("Expected a lowercase campaign ID, e.g. social-media")
    return value


def _member(parent: Path, name: str) -> Path:
    path = parent / name
    if path.is_symlink():
        raise ValueError(f"Symlinked source is not supported: {path}")
    return path


def read_mapping(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError:
        raise ValueError(f"Invalid YAML in {path}") from None
    if not isinstance(data, dict) or any(not isinstance(key, str) for key in data):
        raise ValueError(f"Expected a YAML mapping with string keys in {path}")
    return data


def _text(data: dict, key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: {key} must be a nonempty string")
    return value


def _names(value: object, context: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(n, str) or not n.strip() for n in value):
        raise ValueError(f"{context}: expected a list of names")
    if len(set(value)) != len(value):
        raise ValueError(f"{context}: duplicate names")
    return value


def campaign_fields(data: dict, campaign_id: str) -> dict:
    if data.get("id") != campaign_id:
        raise ValueError(f"{campaign_id}: manifest id does not match its directory")
    fields = {key: _text(data, key, campaign_id) for key in ("id", "name", "description", "orchestrator")}
    ids = _names(data.get("agents"), f"{campaign_id}.agents")
    orchestrator = f"{campaign_id}__orchestrator"
    if fields["orchestrator"] != orchestrator or orchestrator not in ids:
        raise ValueError(f"{campaign_id}: roster must contain the canonical orchestrator {orchestrator}")
    prefix = f"{campaign_id}__"
    if any(not agent.startswith(prefix) or not _SOURCE_SLUG.fullmatch(agent[len(prefix):])
           or not PROFILE_ID_RE.fullmatch(agent) for agent in ids):
        raise ValueError(f"{campaign_id}: roster must use canonical campaign-prefixed IDs")
    return {**fields, "agents": ids}


def _skill_index(*roots: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for root in roots:
        for path in sorted(root.rglob("SKILL.md")):
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if path.resolve() != path.absolute():
                raise ValueError(f"Symlinked skill source is not supported: {path}")
            name = read_skill_name(path, "")
            if name and path.is_file():
                index.setdefault(name, []).append(path.parent)
    return index


def resolve_skills(names: object, context: str, index: dict[str, list[Path]],
                   *, excluded: frozenset[str]) -> dict[str, Path]:
    selected = {}
    for name in _names(names, f"{context}.oma_skills"):
        paths = index.get(name, [])
        if len(paths) != 1 or not PROFILE_ID_RE.fullmatch(name) or name in excluded:
            raise ValueError(f"{context}: skill {name!r} must resolve to one eligible OMA package (found {len(paths)})")
        if any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in paths[0].rglob("*")):
            raise ValueError(f"{context}: skill {name!r} contains unsupported files or symlinks")
        selected[name] = paths[0]
    return selected


def _job_ids(value: object, context: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(job, dict) for job in value):
        raise ValueError(f"{context}.jobs: expected a list of job mappings")
    return _names([job.get("id") for job in value], f"{context}.jobs")


def _read_agent(root: Path, campaign_id: str, agent_id: str, index: dict[str, list[Path]]) -> Agent:
    path = _member(root, agent_id)
    config_path = _member(path, "config.yaml")
    data = read_mapping(config_path)
    if data.get("id") != agent_id:
        raise ValueError(f"{agent_id}: config id does not match the roster")
    if data.get("campaign_id") != campaign_id:
        raise ValueError(f"{agent_id}: campaign_id must match {campaign_id}")
    validate_record("agent", data, config_path)
    del data["id"], data["campaign_id"], data["name"]
    data.pop("version", None)  # Legacy template metadata is not a native setting.
    data.pop("effective", None)  # Materialized OMA view, not an authored override.
    # OMA credential metadata stays in the record, not the native profile.
    data.pop("all-keys", None)
    data.pop("available-keys", None)
    description = data.pop("description")
    soul = _member(path, "SOUL.md").read_text(encoding="utf-8-sig")
    if not soul.strip():
        raise ValueError(f"{agent_id}: SOUL.md is empty")
    skills = resolve_skills(data.pop("oma_skills", []), agent_id, index,
                            excluded=OMA_DEFAULT_ONLY_SKILLS | OMA_MAINTENANCE_ONLY_SKILLS)
    _job_ids(data.pop("jobs", []), agent_id)
    return Agent(agent_id, description, data, soul, skills)


def resolve(home: Path, campaign_id: str) -> Campaign:
    """Resolve authored campaign and agent records, not shipped templates."""
    oma = _member(home.resolve(), "oma")
    campaigns_dir = _member(oma, "campaigns")
    directory = _member(campaigns_dir, checked_id(campaign_id))
    manifest = _member(directory, "config.yaml")
    data = campaign_fields(read_mapping(manifest), campaign_id)
    ids = data.pop("agents")
    index = _skill_index(_member(bundle_dir(home.resolve()), "skills"))
    agents_root = _member(oma, "agents")
    agents = tuple(_read_agent(agents_root, campaign_id, agent, index) for agent in ids)
    return Campaign(**data, agents=agents)
