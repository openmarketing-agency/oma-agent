"""OMA playbook authoring is available on demand without creating user data."""

import json

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_playbook_loads_alongside_campaign_management(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = sync_skills(quiet=True)
    assert {"oma-playbook", "oma-campaigns"} <= set(result["copied"])
    for name in ("oma-playbook", "oma-campaigns"):
        loaded = json.loads(skill_view(name))
        assert loaded["success"], loaded
        assert loaded["name"] == name
        assert "`oma/playbook/config.yaml`" in loaded["content"]
    assert not (tmp_path / "oma").exists()
