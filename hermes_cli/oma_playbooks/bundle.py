"""Locate the local OMA source bundle and seed it on Docker first use."""

import shutil
import tempfile
from pathlib import Path

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
    """Publish a complete starter bundle without replacing operator-owned data."""
    destination = bundle_dir(home)
    if destination.exists():
        return
    # Stage on the home filesystem so a failed copy never leaves a partial bundle.
    with tempfile.TemporaryDirectory(prefix=".oma-bundle-", dir=home) as staging:
        staged = Path(staging) / destination.name
        shutil.copytree(source, staged, symlinks=True)
        if not bundle_dir(home).exists():
            staged.rename(destination)
