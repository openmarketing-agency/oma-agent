"""The creatives validator accepts the brand's own collection on every supported platform."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


@pytest.fixture
def validator(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = json.loads(skill_view("oma/oma-creatives"))
    assert skill["success"], skill
    return Path(skill["skill_dir"]) / "scripts" / "validate_creatives.py"


def _own_platform(brand: Path, platform: str) -> None:
    folder = brand / "research" / "own" / "socials" / platform
    (folder / "p1").mkdir(parents=True)
    (folder / "p1" / "media-1.jpg").write_bytes(b"jpeg")
    folder.joinpath("index.yaml").write_text(json.dumps({
        "account": {"handle": "@brand", "profile_url": f"https://{platform}.example/brand"},
        "coverage": {"status": "checked", "note": ""},
        "posts": [{
            "id": "p1", "url": f"https://{platform}.example/brand/p1",
            "posted_at": "2026-01-01T10:00:00Z", "captured_at": "2026-01-15T10:00:00Z",
            "selected_by": ["latest"], "caption": "Launch day", "format": "image",
            "hook_type": "bold_claim", "angle": "outcome", "structure": "Headline, product, CTA",
            "media": [f"research/own/socials/{platform}/p1/media-1.jpg"], "reuse": "not_permitted",
        }],
    }))


def _validate(validator: Path, brand: Path) -> subprocess.CompletedProcess:
    (brand / "research" / "own" / "creatives.md").write_text("# Creatives: Brand\n")
    return subprocess.run([sys.executable, str(validator), str(brand), "own"],
                          capture_output=True, text=True, check=False)


def test_own_collection_passes_on_pinterest_and_bluesky(validator, tmp_path):
    brand = tmp_path / "oma" / "brand"
    for platform in ("instagram", "tiktok", "facebook", "pinterest", "bluesky"):
        _own_platform(brand, platform)

    result = _validate(validator, brand)

    assert result.returncode == 0, result.stdout
    assert "PASS" in result.stdout


def test_unsupported_platform_folder_is_rejected(validator, tmp_path):
    brand = tmp_path / "oma" / "brand"
    _own_platform(brand, "myspace")

    result = _validate(validator, brand)

    assert result.returncode == 1
    assert "socials/myspace: unknown platform folder" in result.stdout
