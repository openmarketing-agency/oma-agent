"""Skill allowlist policy, shared by discovery, prompts and explicit activation."""

from functools import lru_cache
import json
import logging
import os
from pathlib import Path
from typing import Any

from hermes_constants import get_default_hermes_root, get_hermes_home, PROFILE_ID_RE

logger = logging.getLogger(__name__)

# Old bundled copies can remain on disk after sync; never offer the retired workflow.
OMA_RETIRED_SKILLS = frozenset({"oma-brands", "oma-playbooks"})
OMA_DEFAULT_ONLY_SKILLS = OMA_RETIRED_SKILLS | {
    "oma-agents", "oma-brand", "oma-campaigns", "oma-onboarding", "oma-playbook",
}
OMA_MAINTENANCE_ONLY_SKILLS = frozenset({"omactl"})
OMA_SKILL_INVENTORY = ".oma-managed.json"


@lru_cache(maxsize=16)
def _pruned_skills(path: Path, _version: tuple) -> frozenset[str]:
    try:
        pruned = json.loads(path.read_text(encoding="utf-8-sig")).get("pruned", [])
        if isinstance(pruned, list):
            return frozenset(name for name in pruned if isinstance(name, str) and PROFILE_ID_RE.fullmatch(name))
    except (AttributeError, OSError, ValueError, RecursionError):
        pass
    return frozenset()


def _profile_pruned_skills(home: Path) -> frozenset[str]:
    inventory = home / "skills" / OMA_SKILL_INVENTORY
    try:
        info = inventory.lstat()
    except OSError:
        return frozenset()
    if inventory.is_symlink() or not inventory.is_file() or info.st_size > 256 * 1024:
        return frozenset()
    return _pruned_skills(inventory, (info.st_ino, info.st_mtime_ns, info.st_size))


def profile_excluded_skills(home: Path | None = None, *, include_pruned: bool = True) -> frozenset[str]:
    """Reserve the built-in skills for their owning profiles."""
    home = get_hermes_home() if home is None else home
    root = get_default_hermes_root(home=home).resolve()
    resolved = home.resolve()
    if resolved == root:
        excluded = OMA_RETIRED_SKILLS | OMA_MAINTENANCE_ONLY_SKILLS
    elif resolved == root / "profiles" / "maintenance":
        excluded = OMA_DEFAULT_ONLY_SKILLS
    else:
        return OMA_DEFAULT_ONLY_SKILLS | OMA_MAINTENANCE_ONLY_SKILLS
    return excluded | _profile_pruned_skills(home) if include_pruned else excluded


def _allowlist(value: Any, key: str) -> frozenset[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(name, str) for name in value):
        logger.warning("%s must be a list of skill names or null; excluding nonessential skills", key)
        return frozenset()
    # Names are exact identifiers, not patterns or values to repair/normalize.
    return frozenset(value)


def enabled_skill_names(skills_config: dict, platform: str | None = None) -> frozenset[str] | None:
    """Profile ceiling intersected with the platform allowlist; None means unrestricted.

    Empty or malformed lists select only the essential operating manual. Disabled lists,
    compatibility, plugin enablement and project trust remain separate, authoritative gates.
    """
    from agent.skill_utils import ESSENTIAL_SKILLS

    enabled = _allowlist(skills_config.get("enabled"), "skills.enabled")
    platforms = skills_config.get("platform_enabled")
    if platforms is not None and not isinstance(platforms, dict):
        logger.warning("skills.platform_enabled must be a mapping; excluding nonessential skills")
        return ESSENTIAL_SKILLS
    per_platform = _allowlist(
        platforms.get(platform), f"skills.platform_enabled.{platform}",
    ) if isinstance(platforms, dict) and platform else None
    if per_platform is not None:
        enabled = per_platform if enabled is None else enabled & per_platform
    return None if enabled is None else enabled | ESSENTIAL_SKILLS


def get_enabled_skill_names(platform: str | None = None) -> frozenset[str] | None:
    """Resolve the active profile and platform at call time, never at process import."""
    from agent.skill_utils import _skills_cfg
    from gateway.session_context import get_session_env

    platform = platform or os.getenv("HERMES_PLATFORM") or get_session_env("HERMES_SESSION_PLATFORM")
    return enabled_skill_names(_skills_cfg() or {}, platform)


def skill_is_selected(enabled: frozenset[str] | None, *names: str | None) -> bool:
    """Match the canonical skill name (or a duplicate's exact advertised load name)."""
    return enabled is None or not enabled.isdisjoint(names)


def is_enabled_entry(entry: dict, enabled: frozenset[str] | None) -> bool:
    return skill_is_selected(enabled, str(entry["name"]), entry.get("load_name"))
