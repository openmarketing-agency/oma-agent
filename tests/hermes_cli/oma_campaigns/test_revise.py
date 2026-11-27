"""Revising an installed campaign keeps plans in step with its tools."""

import json
from pathlib import Path

import pytest

AGENTS = ("demo__orchestrator", "demo__writer", "demo__publisher")
PLANS = ["Publish one Reddit answer a week."]


@pytest.fixture
def campaign(tmp_path, monkeypatch, capsys):
    from hermes_cli import default_plugins
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns import __main__ as cli

    monkeypatch.setattr(default_plugins, "spawn_install", lambda _path: True)
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for agent_id in AGENTS:
        record = home / "oma" / "agents" / agent_id
        record.mkdir(parents=True)
        atomic_config_write(record / "config.yaml", {
            "id": agent_id, "name": agent_id, "description": "Test role.", "campaign_id": "demo",
            "agent": {"enabled_toolsets": ["file"]}, "jobs": [],
        })
        (record / "SOUL.md").write_text("I am a test role.\n", encoding="utf-8")
    definition = tmp_path / "demo.yaml"
    atomic_config_write(definition, {
        "id": "demo", "name": "Demo", "description": "Test team.", "orchestrator": "demo__orchestrator",
        "agents": list(AGENTS), "goals": ["Grow trials."], "plans": PLANS, "integrations": ["reddit"],
        "mode": "yolo",
    })
    assert cli.main(["create", str(definition)]) == 0
    capsys.readouterr()
    return home, home / "oma" / "campaigns" / "demo" / "config.yaml", tmp_path / "revised.yaml", cli.main


def _revise(main, capsys, revised, **fields):
    from hermes_cli.config import atomic_config_replace

    atomic_config_replace(revised, {"id": "demo", **fields})
    code = main(["revise", "demo", str(revised)])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if code == 0 else captured.err


def test_revise_refuses_a_tool_change_the_plans_do_not_cover(campaign, capsys):
    from hermes_cli.oma_campaigns.source import read_mapping

    _, config, revised, main = campaign
    before = read_mapping(config)
    code, error = _revise(main, capsys, revised, integrations=["reddit", "instagram"])
    assert code == 1 and "instagram was added but no plan uses it" in error
    code, error = _revise(main, capsys, revised, integrations=[])
    assert code == 1 and "reddit was removed but a plan still uses it" in error
    assert read_mapping(config) == before


def test_revise_saves_covered_tools_and_wakes_a_running_orchestrator_once(campaign, capsys):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli import kanban_db
    from hermes_cli.config import atomic_config_write
    from hermes_cli.kanban_db_connect import connect_closing
    from hermes_cli.oma_campaigns.source import read_mapping

    home, config, revised, main = campaign
    plans = [*PLANS, "Post three Instagram carousels a week with images made in Replicate."]
    code, result = _revise(main, capsys, revised, integrations=["reddit", "instagram", "replicate"], plans=plans)
    assert code == 0, result
    assert result["added"] == ["instagram", "replicate"] and result["replan_task"] is None
    saved = read_mapping(config)
    assert saved["plans"] == plans and saved["mode"] == "yolo" and "demo__analyst" in saved["agents"]

    atomic_config_write(config, {**read_mapping(config), "lifecycle_state": "resumed"})
    code, result = _revise(main, capsys, revised, integrations=["instagram", "replicate"], plans=plans[1:])
    assert code == 0, result
    assert result["removed"] == ["reddit"] and result["replan_task"]
    code, again = _revise(main, capsys, revised, integrations=["instagram", "replicate"], plans=plans[1:])
    assert code == 0 and again["replan_task"] is None
    with bind_profile_scope(home, hydrate_secrets=False), connect_closing(board="campaign-demo") as conn:
        [task] = kanban_db.list_tasks(conn)
    assert task.assignee == "demo__orchestrator" and "removed reddit" in task.body


def test_revise_keeps_the_installed_roster_and_mode(campaign, capsys):
    _, _, revised, main = campaign
    code, error = _revise(main, capsys, revised, agents=["demo__orchestrator", "demo__publisher"])
    assert code == 1 and "keeps the installed roster" in error
    code, error = _revise(main, capsys, revised, mode="control")
    assert code == 1 and "change the mode" in error


def test_validate_warns_about_integrations_no_plan_uses(tmp_path, monkeypatch, capsys):
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns import __main__ as cli

    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    definition = tmp_path / "demo.yaml"
    record = {"id": "demo", "name": "Demo", "description": "Test team.", "orchestrator": "demo__orchestrator",
              "agents": ["demo__orchestrator", "demo__publisher"], "integrations": ["reddit", "google-analytics"]}
    for plans, warned in ((["Answer Reddit threads and track signups in Google Analytics."], []),
                          (["Answer Reddit threads."], ["google-analytics"])):
        atomic_config_write(definition, {**record, "plans": plans})
        assert cli.main(["validate", "campaign", str(definition)]) == 0
        warnings = json.loads(capsys.readouterr().out)["warnings"]
        assert [text.split(" ", 1)[0] for text in warnings] == warned
