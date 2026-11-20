"""OMA playbook authoring is available on demand without creating user data."""

import json

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_playbooks_loads_alongside_campaign_management(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = sync_skills(quiet=True)
    assert {"oma-playbooks", "oma-campaigns"} <= set(result["copied"])
    for name in ("oma-playbooks", "oma-campaigns"):
        loaded = json.loads(skill_view(name))
        assert loaded["success"], loaded
        assert loaded["name"] == name
    assert not (tmp_path / "oma" / "playbooks").exists()
