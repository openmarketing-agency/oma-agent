"""The OMA agent-record skill is available without changing profile state."""

import json

from hermes_yaml import safe_load
from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_agents_loads_on_demand_without_creating_agent_records(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert "oma-agents" in sync_skills(quiet=True)["copied"]
    loaded = json.loads(skill_view("oma-agents"))
    assert loaded["success"], loaded
    assert loaded["name"] == "oma-agents"
    assert not (tmp_path / "oma" / "agents").exists()


def test_only_campaign_orchestrator_templates_grant_standing_kanban_access(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = json.loads(skill_view("oma-agents"))
    assert skill["success"], skill
    for path in skill["linked_files"]["references"]:
        if not path.endswith("-template.md"):
            continue
        item = json.loads(skill_view("oma-agents", file_path=path))
        assert item["success"], item
        _, _, code = item["content"].partition("```yaml\n")
        record = safe_load(code.split("```", 1)[0])
        role = record["id"].split("__", 1)[1]
        toolsets = record["agent"]
        assert ("kanban" in toolsets["enabled_toolsets"]) == (role == "orchestrator"), path
        assert "kanban" not in toolsets.get("disabled_toolsets", []), path
