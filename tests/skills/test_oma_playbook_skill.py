"""OMA playbook authoring is available on demand without creating user data."""

import json

import hermes_yaml as yaml

from hermes_cli.oma_campaigns.schema import validate_record
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


def test_bundled_playbook_example_uses_existing_inline_strategy(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    loaded = json.loads(skill_view("oma-playbook", file_path="references/examples.md"))
    assert loaded["success"], loaded
    raw = loaded["content"].split("```yaml\n", 1)[1].split("```", 1)[0]
    record = yaml.safe_load(raw)
    validate_record("playbook", record, "references/examples.md")
    assert set(record) == {"id", "name", "description", "strategy"}
    assert isinstance(record["strategy"], str) and record["strategy"].strip()
