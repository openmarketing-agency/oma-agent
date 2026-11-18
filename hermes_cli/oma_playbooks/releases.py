"""Resolve public OMA release tags and cache their playbook and skill trees."""

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from hermes_cli.archive_safe import normalize_archive_parts
from hermes_cli.boot_bootstrap import _git_binary
from hermes_cli.source_check import source_git_env
from hermes_cli.update_channel import STABLE_TAG_RE

REPOSITORY = "openmarketing-agency/openmarketing.agency"
_CACHE_NAME = "openmarketing.agency"
_TREES = ("playbooks", "skills")
_SHA = re.compile(r"[0-9a-f]{40}")
_LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


@dataclass(frozen=True)
class Release:
    tag: str
    commit: str

    def provenance(self) -> dict[str, str]:
        return {"repository": REPOSITORY, "tag": self.tag, "commit": self.commit}


def _download(url: str, limit: int, *, accept: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "oma-playbooks", "Accept": accept})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Public OMA download exceeds the size limit")
    return data


def _published_tag() -> str | None:
    try:
        data = json.loads(_download(_LATEST_URL, 1024 * 1024, accept="application/vnd.github+json"))
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 429) or (exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0"):
            return None
        raise
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not isinstance(tag, str) or not STABLE_TAG_RE.fullmatch(tag) or data.get("draft") or data.get("prerelease"):
        raise ValueError("The latest public OMA release must use a stable tag such as v1.2.3")
    return tag


def _tag_refs() -> dict[str, str]:
    git = _git_binary()
    if git is None:
        raise ValueError("Git is needed to look up public OMA release tags")
    env = source_git_env()
    for key in ("GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"):
        env.pop(key, None)
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    try:
        result = subprocess.run(
            [git, "ls-remote", "--tags", f"https://github.com/{REPOSITORY}.git", "refs/tags/v*"],
            cwd=os.path.abspath(os.sep), env=env, text=True, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Timed out looking up public OMA release tags") from exc
    if result.returncode:
        raise ValueError("Could not look up public OMA release tags on GitHub")
    refs = {}
    for line in result.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/tags/") and _SHA.fullmatch(sha):
            refs[ref.removeprefix("refs/tags/")] = sha
    return refs


def resolve_release(tag: str | None = None) -> Release:
    """Prefer the published release; otherwise choose the highest stable version tag."""
    if tag is not None and not STABLE_TAG_RE.fullmatch(tag):
        raise ValueError("Expected a stable OMA release tag such as v1.2.3")
    selected = tag if tag is not None else _published_tag()
    refs = _tag_refs()
    if selected is None:
        versions = [ref for ref in refs if STABLE_TAG_RE.fullmatch(ref)]
        if not versions:
            raise ValueError(f"No stable v* tags found in {REPOSITORY}")
        selected = max(versions, key=lambda value: tuple(map(int, value[1:].split("."))))
    if selected not in refs:
        raise ValueError(f"Release tag {selected} not found in {REPOSITORY}")
    return Release(selected, refs.get(f"{selected}^{{}}", refs[selected]))


def _cache_path(home: Path, release: Release) -> Path:
    path = home / "cache" / _CACHE_NAME / release.commit
    if any(part.is_symlink() for part in (path.parent.parent, path.parent, path)):
        raise ValueError(f"Refusing symlinked OMA release cache: {path}")
    return path


def cached_path(home: Path, release: Release) -> Path | None:
    path = _cache_path(home, release)
    if not path.exists():
        return None
    if not path.is_dir() or not all((path / tree).is_dir() and not (path / tree).is_symlink() for tree in _TREES):
        raise ValueError(f"Invalid OMA release cache entry: {path}")
    return path


def _extract_sources(content: bytes, destination: Path, release: Release) -> None:
    archive_root = f"{_CACHE_NAME}-{release.commit}"
    total_size = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
            for member in archive:
                total_size += member.size
                if total_size > 64 * 1024 * 1024:
                    raise ValueError("Public OMA archive exceeds the unpacked size limit")
                parts = normalize_archive_parts(member.name)
                if parts[0] != archive_root:
                    raise ValueError(f"Public OMA archive does not match commit {release.commit}")
                if len(parts) < 2 or parts[1] not in _TREES:
                    continue
                if any(":" in part or part.endswith((".", " ")) for part in parts[1:]):
                    raise ValueError(f"Unsafe archive member path: {member.name}")
                target = destination.joinpath(*parts[1:])
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile() and (source := archive.extractfile(member)) is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    if member.mode & 0o111:
                        target.chmod(0o700)
                else:
                    raise ValueError(f"Unsupported OMA archive member: {member.name}")
    except (tarfile.TarError, EOFError) as exc:
        raise ValueError("Could not read the public OMA release archive") from exc
    if not all((destination / tree).is_dir() for tree in _TREES):
        raise ValueError("Public OMA release must contain both playbooks/ and skills/")


def fetch_release(home: Path, release: Release) -> Path:
    """Cache only the source trees by commit; never replace a usable snapshot."""
    cached = cached_path(home, release)
    if cached is not None:
        return cached
    path = _cache_path(home, release)
    content = _download(f"https://codeload.github.com/{REPOSITORY}/tar.gz/{release.commit}",
                        16 * 1024 * 1024, accept="application/gzip")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".fetch-") as temp:
        stage = Path(temp) / "source"
        stage.mkdir(mode=0o700)
        _extract_sources(content, stage, release)
        try:
            stage.rename(path)
        except OSError:
            if cached_path(home, release) is None:
                raise
    return path
