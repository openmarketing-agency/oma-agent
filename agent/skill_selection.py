"""Skill allowlist policy, shared by discovery, prompts and explicit activation."""

import logging
import os
from pathlib import Path
from typing import Any

from hermes_constants import get_default_hermes_root, get_hermes_home

logger = logging.getLogger(__name__)

OMA_DEFAULT_ONLY_SKILLS = frozenset({
    "oma-agents", "oma-brands", "oma-campaigns", "oma-onboarding", "oma-playbooks",
})


def profile_excluded_skills(home: Path | None = None) -> frozenset[str]:
    """Reserve the OMA management skills for the default profile."""
    home = get_hermes_home() if home is None else home
    if home.resolve() == get_default_hermes_root(home=home).resolve():
        return frozenset()
    return OMA_DEFAULT_ONLY_SKILLS


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
