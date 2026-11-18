"""Resolve public OMA release tags and cache their playbook and skill ZIPs from R2."""

import io
import re
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

import hermes_yaml as yaml
from hermes_cli.archive_safe import normalize_archive_parts
from hermes_cli.update_channel import STABLE_TAG_RE

REPOSITORY = "openmarketing-agency/openmarketing.agency"
_R2_BASE_URL = "https://pub-d3419a6b761b48b38897cf50a5056136.r2.dev"
_CACHE_NAME = "oma-playbooks-r2"
_TREES = ("playbooks", "skills")
_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Release:
    tag: str
    commit: str

    def provenance(self) -> dict[str, str]:
        return {"repository": REPOSITORY, "tag": self.tag, "commit": self.commit,
                "base_url": _R2_BASE_URL}


# This already-published snapshot predates the R2 release manifests.
_BOOTSTRAP_RELEASE = Release("v0.1.1", "80be8c56d59d0680efbe5a72e1baffd45caa55ae")


def _download(url: str, limit: int, *, accept: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "oma-playbooks", "Accept": accept})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Public OMA download exceeds the size limit")
    return data


def resolve_release(tag: str | None = None) -> Release:
    """Resolve an R2 release without downloading either ZIP."""
    if tag is not None and not STABLE_TAG_RE.fullmatch(tag):
        raise ValueError("Expected a stable OMA release tag such as v1.2.3")
    if tag == _BOOTSTRAP_RELEASE.tag:
        return _BOOTSTRAP_RELEASE
    key = "latest.yaml" if tag is None else f"{tag}/release.yaml"
    url = f"{_R2_BASE_URL}/{key}"
    try:
        payload = _download(url, 16 * 1024, accept="application/yaml")
    except urllib.error.HTTPError as exc:
        if tag is None and exc.code == 404:
            return _BOOTSTRAP_RELEASE
        raise ValueError(f"Could not download {url} (HTTP {exc.code})") from exc
    try:
        data = yaml.safe_load(payload)
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        raise ValueError(f"Invalid OMA release manifest: {url}") from exc
    selected = data.get("tag") if isinstance(data, dict) else None
    commit = data.get("commit") if isinstance(data, dict) else None
    if (not isinstance(selected, str) or not STABLE_TAG_RE.fullmatch(selected)
            or (tag is not None and selected != tag)
            or not isinstance(commit, str) or not _SHA.fullmatch(commit)):
        raise ValueError(f"Invalid OMA release manifest: {url}")
    return Release(selected, commit)


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


def _extract_zip(content: bytes, destination: Path, tree: str, release: Release) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            # git archive writes the source commit into the ZIP comment.
            if archive.comment != release.commit.encode("ascii"):
                raise ValueError(f"Public OMA {tree}.zip does not match commit {release.commit}")
            if sum(member.file_size for member in archive.infolist()) > 64 * 1024 * 1024:
                raise ValueError(f"Public OMA {tree}.zip exceeds the unpacked size limit")
            for member in archive.infolist():
                parts = normalize_archive_parts(member.orig_filename)
                if any(":" in part or "\0" in part or part.endswith((".", " ")) for part in parts):
                    raise ValueError(f"Unsafe archive member path: {member.orig_filename}")
                if parts[0] != tree or (len(parts) == 1 and not member.is_dir()):
                    raise ValueError(f"Public OMA {tree}.zip must contain only the {tree}/ tree")
                mode = member.external_attr >> 16
                expected_type = stat.S_IFDIR if member.is_dir() else stat.S_IFREG
                if (stat.S_IFMT(mode) not in (0, expected_type) or member.flag_bits & 1
                        or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError(f"Unsupported OMA archive member: {member.filename}")
                target = destination.joinpath(*parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    if mode & 0o111:
                        target.chmod(0o700)
    except (zipfile.BadZipFile, EOFError, zlib.error) as exc:
        raise ValueError(f"Could not read public OMA {tree}.zip") from exc
    if not (destination / tree).is_dir():
        raise ValueError(f"Public OMA {tree}.zip is missing the {tree}/ tree")


def fetch_release(home: Path, release: Release) -> Path:
    """Cache both R2 trees together by commit; never replace a usable snapshot."""
    cached = cached_path(home, release)
    if cached is not None:
        return cached
    path = _cache_path(home, release)

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".fetch-") as temp:
        stage = Path(temp) / "source"
        stage.mkdir(mode=0o700)
        for tree in _TREES:
            url = f"{_R2_BASE_URL}/{release.tag}/{tree}.zip"
            try:
                content = _download(url, 16 * 1024 * 1024, accept="application/zip")
            except urllib.error.HTTPError as exc:
                raise ValueError(f"Could not download {url} (HTTP {exc.code})") from exc
            _extract_zip(content, stage, tree, release)
        try:
            stage.rename(path)
        except OSError:
            if cached_path(home, release) is None:
                raise
    return path
