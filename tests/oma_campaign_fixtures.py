"""Native campaign provisioning fixture shared by campaign integration tests."""

from pathlib import Path

import pytest


DEMO_AGENTS = ("demo__orchestrator", "demo__worker", "demo__publisher")


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    from hermes_cli import default_plugins
    from hermes_cli.oma_campaigns import __main__ as cli

    monkeypatch.setattr(default_plugins, "spawn_install", lambda _path: True)
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    source = home / "oma"
    campaigns = source / "campaigns"
    skills = home / "oma-bundle" / "skills"
    team = campaigns / "demo"
    team.mkdir(parents=True)
    (team / "config.yaml").write_text(
        "id: demo\nname: Demo\ndescription: Test team.\norchestrator: demo__orchestrator\n"
        f"agents: [{', '.join(DEMO_AGENTS)}]\ngoals: [Measure demand]\nplans: [Review evidence]\n",
        encoding="utf-8",
    )
    for agent_id in DEMO_AGENTS:
        role = agent_id.removeprefix("demo__")
        dependencies = "[shared]" if role == "orchestrator" else "[]"
        candidate = source / "agents" / agent_id
        candidate.mkdir(parents=True)
        jobs = "[{id: sample, schedule: '1d', prompt: Review evidence.}]" if role == "orchestrator" else "[]"
        (candidate / "config.yaml").write_text(
            f"id: demo__{role}\nname: {role.title()}\ndescription: Test role.\ncampaign_id: demo\noma_skills: {dependencies}\n"
            f"agent: {{enabled_toolsets: [file, kanban]}}\njobs: {jobs}\n", encoding="utf-8",
        )
        (candidate / "SOUL.md").write_text(f"I am the {role}.\n", encoding="utf-8")
    for name in ("shared", "unused"):
        skill = skills / "category" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\nContents.\n",
                                       encoding="utf-8")
        (skill / "support.txt").write_text("Support file.", encoding="utf-8")
    return home, source, cli.main
