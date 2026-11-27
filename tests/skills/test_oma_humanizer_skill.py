"""Exercise Humanizer delivery guidance and on-demand loading through OMA campaign profiles."""

import json
from pathlib import Path

import pytest

from tests.skills.test_oma_campaigns_skill import bundle as bundle  # noqa: PLC0414 -- register the shared campaign fixture


@pytest.mark.parametrize("setup", ["install", "sync", "sync-native-persona"])
def test_campaign_writer_loads_humanizer_before_delivering_copy(bundle, capsys, setup):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import atomic_config_replace, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents
    from hermes_cli.oma_campaigns.sync import sync_agent
    from tools.skills_tool import skill_view

    home, source, main = bundle
    seed_standalone_agents(home, install_dir=Path(__file__).resolve().parents[2])
    record = source / "agents/demo__worker/config.yaml"
    writer = home / "profiles/demo__worker"
    publisher = home / "profiles/demo__publisher"
    local_skill = writer / "skills/editorial-notes/SKILL.md"
    local_text = "---\nname: editorial-notes\n---\nKeep the team's editorial notes.\n"

    if setup != "install":
        assert main(["install", "demo"]) == 0, capsys.readouterr().err
        assert not (writer / "skills/humanizer").exists()
        assert "humanizer" not in (writer / "SOUL.md").read_text(encoding="utf-8")
        local_skill.parent.mkdir(parents=True)
        local_skill.write_text(local_text, encoding="utf-8")
        if setup == "sync-native-persona":
            (record.parent / "SOUL.md").unlink()

    saved = read_mapping(record)
    atomic_config_replace(record, {
        **saved, "oma_skills": ["humanizer"],
        "agent": {"enabled_toolsets": ["file", "skills"]},
    })
    if setup != "install":
        assert {"SOUL.md", "oma_skills"} <= set(sync_agent(home, "demo__worker")["updated"])
        assert local_skill.read_text(encoding="utf-8") == local_text
    else:
        assert main(["install", "demo"]) == 0, capsys.readouterr().err

    with bind_profile_scope(writer, hydrate_secrets=False):
        loaded = json.loads(skill_view("humanizer", preprocess=False))
    assert loaded["success"], loaded
    assert loaded["name"] == "humanizer"
    assert Path(loaded["skill_dir"]) == writer / "skills/humanizer"
    config = read_user_config_raw(writer / "config.yaml")
    assert "humanizer" not in config.get("skills", {}).get("auto_load", [])

    writer_soul = (writer / "SOUL.md").read_text(encoding="utf-8")
    assert "I am the worker." in writer_soul
    assert "`skill_view`" in writer_soul and "`humanizer`" in writer_soul
    assert "before saving" in writer_soul and "handing off" in writer_soul
    publisher_soul = (publisher / "SOUL.md").read_text(encoding="utf-8")
    assert "humanizer" not in publisher_soul
    assert "publish the saved content immediately and unchanged" in publisher_soul

    if setup == "sync-native-persona":
        assert sync_agent(home, "demo__worker")["updated"] == []
        atomic_config_replace(record, {**read_mapping(record), "oma_skills": []})
        assert {"SOUL.md", "oma_skills"} <= set(sync_agent(home, "demo__worker")["updated"])
        restored = (writer / "SOUL.md").read_text(encoding="utf-8")
        assert "I am the worker." in restored and "`humanizer`" not in restored
