"""Locate the shared OMA skill bundle and seed packages during setup."""

import shutil
import tempfile
from pathlib import Path

from agent.skill_selection import OMA_DEFAULT_STARTER_SKILLS, OMA_MAINTENANCE_ONLY_SKILLS
from hermes_constants import get_default_hermes_root, get_hermes_home
from tools.skill_usage import read_skill_name

HUMANIZER_SKILL = "humanizer"


def shared_skill_dir() -> Path | None:
    """Read-only discovery root shared by profiles of the same Hermes home."""
    root = get_default_hermes_root(home=get_hermes_home()).resolve()
    bundle = root / "oma-bundle"
    skills = bundle / "skills"
    if not bundle.is_symlink() and not skills.is_symlink() and skills.is_dir():
        return skills
    return None


def bundle_dir(home: Path) -> Path:
    path = home / "oma-bundle"
    if path.is_symlink():
        raise ValueError(f"Symlinked OMA bundle is not supported: {path}")
    return path


def _seed_package(source: Path, package: Path) -> None:
    if package.exists() or package.is_symlink():
        return
    package.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".role-skill-", dir=package.parent) as staging:
        staged = Path(staging) / package.name
        shutil.copytree(source, staged)
        if not package.exists() and not package.is_symlink():
            staged.rename(package)


def _seed_humanizer(source: Path, bundle: Path) -> None:
    package = source / "write" / HUMANIZER_SKILL
    if not (package / "SKILL.md").is_file():
        return
    skills = bundle / "skills"
    write = skills / "write"
    if skills.is_symlink() or write.is_symlink():
        return  # Keep operator-managed directories outside this additive seed.
    destination = write / HUMANIZER_SKILL
    if destination.exists() or destination.is_symlink():
        return
    # An operator may already have supplied this exact skill ID in another category.
    for skill in skills.rglob("SKILL.md"):
        if skill.is_symlink() or any(part.startswith(".") for part in skill.relative_to(skills).parts):
            continue
        if read_skill_name(skill, "") == HUMANIZER_SKILL:
            return
    _seed_package(package, destination)


def seed_bundle(source: Path, home: Path) -> None:
    """Publish shared skill packages without replacing operator-owned data."""
    destination = bundle_dir(home)
    if destination.exists():
        _seed_humanizer(source, destination)
        return
    # Stage on the home filesystem so a failed copy never leaves a partial bundle.
    with tempfile.TemporaryDirectory(prefix=".oma-bundle-", dir=home) as staging:
        staged = Path(staging) / destination.name
        shutil.copytree(source / "skills", staged / "skills", symlinks=True)
        _seed_humanizer(source, staged)
        for filename in ("LICENSE", "README.md"):
            if (source / filename).is_file():
                shutil.copy2(source / filename, staged / filename)
        if not bundle_dir(home).exists():
            staged.rename(destination)
        else:
            _seed_humanizer(source, destination)


def seed_role_skills(install_dir: Path, home: Path) -> None:
    """Publish missing role-only packages from their canonical shipped sources."""
    roots = {
        install_dir / "skills" / "oma": OMA_DEFAULT_STARTER_SKILLS,
        install_dir / "hermes_cli" / "data" / "profiles" / "maintenance" / "skills": OMA_MAINTENANCE_ONLY_SKILLS,
    }
    destination = bundle_dir(home) / "skills" / "oma"
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("Refusing a symlinked OMA skill destination")
    destination.mkdir(parents=True, exist_ok=True)
    for root, names in roots.items():
        for name in sorted(names):
            _seed_package(root / name, destination / name)
