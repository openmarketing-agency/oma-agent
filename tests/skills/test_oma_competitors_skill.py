"""The competitor validator runs in the Hermes environment and reads the saved index."""

import json
from pathlib import Path
import subprocess
import sys

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
