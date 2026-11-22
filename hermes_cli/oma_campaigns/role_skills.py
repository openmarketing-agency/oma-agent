"""Materialize and prune standalone profiles' optional OMA skill packages."""

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from agent.skill_selection import (
    OMA_DEFAULT_STARTER_SKILLS, OMA_MAINTENANCE_ONLY_SKILLS,
    OMA_SKILL_INVENTORY, profile_excluded_skills,
)
from hermes_cli.oma_campaigns.bundle import bundle_dir
from hermes_cli.oma_campaigns.source import _member, _skill_index, resolve_skills
from hermes_constants import PROFILE_ID_RE


def _read_inventory(path: Path) -> tuple[dict[str, str], set[str]]:
    if not path.exists():
        return {}, set()
    inventory = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(inventory, dict):
        raise ValueError("Invalid OMA managed skill inventory")
    data, pruned = inventory.get("owned"), inventory.get("pruned")
    if (not isinstance(data, dict) or not isinstance(pruned, list)
            or not all(isinstance(name, str) and PROFILE_ID_RE.fullmatch(name) for name in pruned)):
        raise ValueError("Invalid OMA managed skill inventory")
    for name, relative in data.items():
        if (not PROFILE_ID_RE.fullmatch(name) or not isinstance(relative, str)
                or any(not PROFILE_ID_RE.fullmatch(p) for p in relative.split("/"))):
            raise ValueError("Invalid OMA managed skill inventory")
    if len(set(data.values())) != len(data):
        raise ValueError("Duplicate OMA managed skill paths")
    return data, set(pruned)


def _destination(root: Path, relative: str) -> Path:
    current = root
    for part in relative.split("/"):
        current = _member(current, part)
    if current.exists() and not current.is_dir():
        raise ValueError("An OMA skill destination is not a package directory")
    return current


def _same_package(source: Path, target: Path) -> bool:
    if not target.is_dir():
        return False
    files = {item.relative_to(source) for item in source.rglob("*")}
    if files != {item.relative_to(target) for item in target.rglob("*")}:
        return False
    for relative in files:
        a, b = source / relative, target / relative
        if a.is_symlink() or b.is_symlink() or (a.is_dir() and not b.is_dir()):
            return False
        if a.is_file() and (not b.is_file() or a.read_bytes() != b.read_bytes()):
            return False
    return True


def _plan(home: Path, profile: Path, root: Path, names: list[str], owned: dict[str, str]) -> tuple[dict, dict]:
    bundled = _skill_index(_member(bundle_dir(home), "skills")) if names else {}
    selected = resolve_skills(names, profile.name, bundled,
                              excluded=profile_excluded_skills(profile, include_pruned=False))
    local = _skill_index(root) if selected or owned else {}
    installs = {}
    next_owned = {}
    for name, package in selected.items():
        copies = local.get(name, [])
        if len(copies) > 1:
            raise ValueError(f"Ambiguous local skill: {name}")
        relative = owned.get(name, copies[0].relative_to(root).as_posix() if copies else name)
        # Validate adopted paths before saving them as removal targets.
        if not all(PROFILE_ID_RE.fullmatch(part) for part in relative.split("/")):
            raise ValueError(f"Unsupported local skill path: {name}")
        target = _destination(root, relative)
        if target.exists() and target not in copies:
            raise ValueError(f"OMA skill destination conflicts with local files: {name}")
        next_owned[name] = relative
        if not _same_package(package, target):
            installs[target] = package
    removals = {}
    for name in owned.keys() - selected.keys():
        target = _destination(root, owned[name])
        if target.exists() and target not in local.get(name, ()):
            raise ValueError(f"Managed skill {name} no longer matches its package")
        if target.exists():
            removals[target] = None
    for target in (*removals, *installs):
        if any(target in path.parents for copies in local.values() for path in copies):
            raise ValueError("OMA skill package overlaps another local skill")
    return next_owned, {**removals, **installs}


@contextmanager
def apply_role_skills(home: Path, profile: Path, names: list[str] | None):
    """Stage all copies before mutating the profile; roll back on a failed config write."""
    if names is None:
        yield False
        return
    root = _member(profile, "skills")
    inventory = _member(root, OMA_SKILL_INVENTORY)
    owned, pruned = _read_inventory(inventory)
    starters = OMA_DEFAULT_STARTER_SKILLS if profile == home else OMA_MAINTENANCE_ONLY_SKILLS
    # Accept legacy record lists and release old claims without touching starter copies.
    names = [name for name in names if name not in starters]
    extras_owned = {name: path for name, path in owned.items() if name not in starters}
    next_owned, changes = _plan(home, profile, root, names, extras_owned)
    next_pruned = (pruned | extras_owned.keys()) - next_owned.keys() - starters
    if not changes and owned == next_owned and pruned == next_pruned:
        yield False
        return
    root.mkdir(mode=0o700, exist_ok=True)
    with TemporaryDirectory(prefix=".oma-sync-", dir=root) as staging:
        stage = Path(staging)
        prepared = {}
        for index, (target, package) in enumerate(changes.items()):
            prepared[target] = (stage / f"before-{index}", stage / f"after-{index}")
            if package is not None:
                shutil.copytree(package, prepared[target][1])
        prepared[inventory] = (stage / "old-inventory", stage / "new-inventory")
        data = {"owned": next_owned, "pruned": sorted(next_pruned)}
        prepared[inventory][1].write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        touched = []
        try:
            for target, (backup, replacement) in prepared.items():
                if target.exists():
                    target.rename(backup)
                touched.append((target, backup, replacement))
                if replacement.exists():
                    replacement.rename(target)
            yield True
        except BaseException:
            for target, backup, replacement in reversed(touched):
                if target.exists():
                    target.rename(replacement)
                if backup.exists():
                    backup.rename(target)
            raise
