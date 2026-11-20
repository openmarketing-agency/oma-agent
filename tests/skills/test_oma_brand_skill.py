"""OMA brand management is available on demand without creating user data."""

import json

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_brand_loads_in_a_fresh_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = sync_skills(quiet=True)
    assert "oma-brand" in result["copied"]
    loaded = json.loads(skill_view("oma-brand"))
    assert loaded["success"], loaded
    assert loaded["name"] == "oma-brand"
    assert "`oma/brand/config.yaml`" in loaded["content"]
    assert not (tmp_path / "oma").exists()
