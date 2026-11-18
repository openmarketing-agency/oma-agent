"""Resolve a playbook and exactly the OMA skills its agents declare."""

import re
from dataclasses import dataclass
from pathlib import Path

import hermes_yaml as yaml
from hermes_constants import PROFILE_ID_RE
from tools.skill_usage import read_skill_name

PLAYBOOK_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class Agent:
    id: str
    version: str
    description: str
    config: dict
    soul: str
    skills: dict[str, Path]
    jobs: list[str]


@dataclass(frozen=True)
class Playbook:
    id: str
    name: str
    version: str
    description: str
    orchestrator: str
    agents: tuple[Agent, ...]


def checked_id(value: str) -> str:
    if not isinstance(value, str) or not PLAYBOOK_ID.fullmatch(value):
        raise ValueError("Expected a lowercase playbook ID, e.g. social-media")
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


def _source_manifest(directory: Path) -> dict:
    data = read_mapping(_member(directory, "config.yaml"))
    if data.get("id") != checked_id(directory.name):
        raise ValueError(f"{directory.name}: manifest id does not match its directory")
    return {key: _text(data, key, directory.name) for key in ("id", "name", "version", "description", "orchestrator")} | {
        "agents": _names(data.get("agents"), f"{directory.name}.agents"),
    }


def catalog(repo: Path) -> list[dict]:
    root = _member(repo, "playbooks")
    return [_source_manifest(_member(root, path.name)) for path in sorted(root.iterdir())
            if path.is_dir() and not path.name.startswith(".") and (path / "config.yaml").is_file()]  # config-reader: ok — source definitions, not runtime config


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


def _resolve_skills(data: dict, context: str, index: dict[str, list[Path]]) -> dict[str, Path]:
    selected = {}
    for name in _names(data.pop("oma_skills", []), f"{context}.oma_skills"):
        paths = index.get(name, [])
        if len(paths) != 1 or not PROFILE_ID_RE.fullmatch(name) or name == "oma-playbooks":
            raise ValueError(f"{context}: skill {name!r} must resolve to one eligible OMA package (found {len(paths)})")
        if any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in paths[0].rglob("*")):
            raise ValueError(f"{context}: skill {name!r} contains unsupported files or symlinks")
        selected[name] = paths[0]
    return selected


def _job_ids(value: object, context: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(job, dict) for job in value):
        raise ValueError(f"{context}.jobs: expected a list of job mappings")
    return _names([job.get("id") for job in value], f"{context}.jobs")


def _read_agent(root: Path, agent_id: str, index: dict[str, list[Path]]) -> Agent:
    path = _member(root, agent_id)
    data = read_mapping(_member(path, "config.yaml"))
    if data.pop("id", None) != agent_id:
        raise ValueError(f"{agent_id}: config id does not match the roster")
    version = _text(data, "version", agent_id)
    description = _text(data, "description", agent_id)
    del data["version"], data["description"]
    soul = _member(path, "SOUL.md").read_text(encoding="utf-8-sig")
    if not soul.strip():
        raise ValueError(f"{agent_id}: SOUL.md is empty")
    skills = _resolve_skills(data, agent_id, index)
    jobs = _job_ids(data.pop("jobs", []), agent_id)
    return Agent(agent_id, version, description, data, soul, skills, jobs)


def resolve(repo: Path, playbook_id: str, version: str | None = None) -> Playbook:
    directory = _member(_member(repo.resolve(), "playbooks"), checked_id(playbook_id))
    data = _source_manifest(directory)
    if version is not None and data["version"] != version:
        raise ValueError(f"{playbook_id}: expected version {version}, found {data['version']}")
    ids = data.pop("agents")
    orchestrator = f"{playbook_id}__orchestrator"
    if data["orchestrator"] != orchestrator or orchestrator not in ids:
        raise ValueError(f"{playbook_id}: roster must contain the canonical orchestrator {orchestrator}")
    prefix = f"{playbook_id}__"
    if any(not agent.startswith(prefix) or not PLAYBOOK_ID.fullmatch(agent[len(prefix):])
           or not PROFILE_ID_RE.fullmatch(agent) for agent in ids):
        raise ValueError(f"{playbook_id}: roster must use canonical playbook-prefixed IDs")
    index = _skill_index(_member(repo.resolve(), "skills"), _member(directory, "skills"))
    agents_root = _member(directory, "agents")
    agents = tuple(_read_agent(agents_root, agent, index) for agent in ids)
    return Playbook(**data, agents=agents)
