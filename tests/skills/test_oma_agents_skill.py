"""The OMA agent-record skill is available without changing profile state."""

import json

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_agents_loads_on_demand_without_creating_agent_records(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert "oma-agents" in sync_skills(quiet=True)["copied"]
    loaded = json.loads(skill_view("oma-agents"))
    assert loaded["success"], loaded
    assert loaded["name"] == "oma-agents"
    assert not (tmp_path / "oma" / "agents").exists()
