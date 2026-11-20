"""OMA brand management is available on demand without creating user data."""

import json

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_brands_loads_in_a_fresh_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = sync_skills(quiet=True)
    assert "oma-brands" in result["copied"]
    loaded = json.loads(skill_view("oma-brands"))
    assert loaded["success"], loaded
    assert loaded["name"] == "oma-brands"
    assert not (tmp_path / "oma" / "brands").exists()
