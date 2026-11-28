"""The competitor validator runs in the Hermes environment and reads the saved index."""

import json
from pathlib import Path
import subprocess
import sys

from ruamel.yaml import YAML

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_validator_reports_index_errors_instead_of_a_missing_parser(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = json.loads(skill_view("oma/oma-competitors"))
    assert skill["success"], skill
    brand = tmp_path / "oma" / "brand"
    (brand / "research" / "competitors").mkdir(parents=True)
    (brand / "research" / "competitors" / "index.yaml").write_text("frame: {}\n")

    result = subprocess.run(
        [sys.executable, str(Path(skill["skill_dir"]) / "scripts" / "validate_competitors.py"), str(brand)],
        capture_output=True, text=True, check=False)

    assert result.returncode == 1, result.stdout
    assert "index.yaml: missing" in result.stdout


def test_a_summary_only_creatives_file_fails_competitor_validation(tmp_path, monkeypatch):
    """A placeholder creatives.md once passed because only its existence was checked."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = Path(json.loads(skill_view("oma/oma-competitors"))["skill_dir"])
    brand = tmp_path / "oma" / "brand"
    index_path = brand / "research" / "competitors" / "index.yaml"
    index_path.parent.mkdir(parents=True)
    index_path.write_text((skill / "references" / "index-example.yaml").read_text())
    index = YAML(typ="safe").load(index_path.read_text())
    for entry in (index.get("competitors") or []) + (index.get("references") or []):
        for key in ("profile", "gtm", "creatives"):
            if entry.get(key):
                (brand / entry[key]).parent.mkdir(parents=True, exist_ok=True)
                (brand / entry[key]).write_text("# Placeholder\nAd libraries: blocked (not attempted).\n")

    result = subprocess.run([sys.executable, str(skill / "scripts" / "validate_competitors.py"), str(brand)],
                            capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert "competitor 'deckly': creatives collection fails oma-creatives validation" in result.stdout
    assert "not a collection" in result.stdout


def test_depth_caps_keep_all_but_the_top_competitors_index_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = Path(json.loads(skill_view("oma/oma-competitors"))["skill_dir"])
    brand = tmp_path / "oma" / "brand"
    index_path = brand / "research" / "competitors" / "index.yaml"
    index_path.parent.mkdir(parents=True)
    index = YAML(typ="safe").load((skill / "references" / "index-example.yaml").read_text())
    indirect = next(c for c in index["competitors"] if c["tier"] == "indirect")
    indirect["depth"] = "index_only"
    for key in ("profile", "gtm"):
        indirect.pop(key, None)
    with index_path.open("w") as stream:
        YAML().dump(index, stream)
    validate = lambda *flags: subprocess.run(
        [sys.executable, str(skill / "scripts" / "validate_competitors.py"), str(brand), *flags],
        capture_output=True, text=True, check=False).stdout

    onboarding, full = validate("--full", "1", "--light", "0"), validate()
    assert "depth must be" not in onboarding
    assert f"competitor '{indirect['id']}': ranks in top 5 indirect, depth must be 'light'" in full
