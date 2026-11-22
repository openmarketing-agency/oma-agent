"""Locate the local OMA source bundle and seed it on Docker first use."""

import shutil
import tempfile
from pathlib import Path

from agent.skill_selection import OMA_DEFAULT_ONLY_SKILLS, OMA_MAINTENANCE_ONLY_SKILLS, OMA_RETIRED_SKILLS
from hermes_constants import get_default_hermes_root, get_hermes_home


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


def seed_bundle(source: Path, home: Path) -> None:
    """Publish shared skill packages without replacing operator-owned data."""
    destination = bundle_dir(home)
    if destination.exists():
        return
    # Stage on the home filesystem so a failed copy never leaves a partial bundle.
    with tempfile.TemporaryDirectory(prefix=".oma-bundle-", dir=home) as staging:
        staged = Path(staging) / destination.name
        shutil.copytree(source / "skills", staged / "skills", symlinks=True)
        for filename in ("LICENSE", "README.md"):
            if (source / filename).is_file():
                shutil.copy2(source / filename, staged / filename)
        if not bundle_dir(home).exists():
            staged.rename(destination)


def seed_role_skills(install_dir: Path, home: Path) -> None:
    """Publish missing role-only packages from their canonical shipped sources."""
    roots = {
        install_dir / "skills" / "oma": OMA_DEFAULT_ONLY_SKILLS - OMA_RETIRED_SKILLS,
        install_dir / "hermes_cli" / "data" / "profiles" / "maintenance" / "skills": OMA_MAINTENANCE_ONLY_SKILLS,
    }
    destination = bundle_dir(home) / "skills" / "oma"
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("Refusing a symlinked OMA skill destination")
    destination.mkdir(parents=True, exist_ok=True)
    for root, names in roots.items():
        for name in sorted(names):
            package = destination / name
            if package.exists() or package.is_symlink():
                continue
            with tempfile.TemporaryDirectory(prefix=".role-skill-", dir=destination) as staging:
                staged = Path(staging) / name
                shutil.copytree(root / name, staged)
                if not package.exists() and not package.is_symlink():
                    staged.rename(package)
