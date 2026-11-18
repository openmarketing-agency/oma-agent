"""Exercise OMA playbook provisioning with native profile operations in an isolated home."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    repo = tmp_path / "openmarketing.agency"
    team = repo / "playbooks" / "demo"
    team.mkdir(parents=True)
    (team / "config.yaml").write_text(
        "id: demo\nname: Demo\nversion: 0.2.0\ndescription: >-\n  Test team.\n\n"
        "# Keep canonical IDs unchanged.\norchestrator: demo__orchestrator\n"
        "agents:\n  - demo__orchestrator\n  - demo__worker\n", encoding="utf-8")
    for role, version, dependencies in (("orchestrator", "0.1.2", "[shared, local]"), ("worker", "0.2.1", "[]")):
        candidate = team / "agents" / f"demo__{role}"
        candidate.mkdir(parents=True)
        (candidate / "config.yaml").write_text(
            f"id: demo__{role}\nversion: {version}\ndescription: Test role.\noma_skills: {dependencies}\n"
            "agent: {enabled_toolsets: [file]}\njobs: [{id: sample}]\n", encoding="utf-8")
        (candidate / "SOUL.md").write_text(f"I am the {role}.\n", encoding="utf-8")
    for root, name in ((repo, "shared"), (team, "local"), (repo, "unused")):
        skill = root / "skills" / "category" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\nContents.\n",
                                       encoding="utf-8")
        (skill / "support.txt").write_text("Support file.", encoding="utf-8")
    return home, repo


def test_install_saves_playbook_metadata_in_the_ledger_only(checkout):
    from hermes_cli.oma_playbooks.install import install, installed
    from hermes_cli.oma_playbooks.source import read_mapping, resolve

    home, repo = checkout
    plan = resolve(repo, "demo")
    install(home, plan)

    directory = home / "playbooks" / "demo"
    assert not (directory / "config.yaml").exists()
    record = read_mapping(directory / "installation.yaml")
    assert record["description"] == "Test team."
    assert record["source_manifest"] == "playbooks/demo/config.yaml"
    assert installed(home, "demo")[0]["description"] == "Test team."


def test_install_records_agent_versions_and_configures_agent_scratch(checkout):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import read_user_config_raw
    from hermes_cli.oma_playbooks.install import default_home, install, installed
    from hermes_cli.oma_playbooks.source import catalog, read_mapping, resolve
    from tools.file_tools import read_file_tool, write_file_tool

    home, repo = checkout
    assert default_home() == home.resolve()
    assert [row["id"] for row in catalog(repo)] == ["demo"]
    assert installed(home) == []
    plan = resolve(repo, "demo", "0.2.0")
    record = install(home, plan)
    registry = home / "playbooks" / "demo"
    saved = read_mapping(registry / "installation.yaml")
    assert saved["state"] == "installed" and saved["version"] == "0.2.0"
    assert saved["agents"]["demo__worker"]["version"] == "0.2.1"
    assert record == install(home, plan) == installed(home, "demo")[0]
    for agent in plan.agents:
        profile = home / "profiles" / agent.id
        row = saved["agents"][agent.id]
        scratch = registry / row["scratch_dir"]
        assert scratch.is_dir() and str(scratch.resolve()) in (profile / "SOUL.md").read_text(encoding="utf-8")
        assert row["state"] == "installed" and row["declared_jobs"] == ["sample"]
        assert not (profile / "cron" / "jobs.json").exists()
        assert not (profile / "skills" / "unused").exists()
        raw = read_user_config_raw(profile / "config.yaml")
        assert not {"id", "description", "version", "jobs", "oma_skills"} & raw.keys()
        assert "oma-playbooks" in raw["skills"]["disabled"]
        for name in agent.skills:
            assert (profile / "skills" / name / "support.txt").read_text(encoding="utf-8") == "Support file."
        with bind_profile_scope(profile, hydrate_secrets=False):
            marker = str(scratch / "marker.txt")
            assert not json.loads(write_file_tool(marker, "Scratch check.")).get("error")
            assert "Scratch check." in read_file_tool(marker)
            with pytest.raises(ValueError, match="default OMA Agent"):
                default_home()


def test_missing_skill_and_profile_collision_do_not_publish(checkout):
    from hermes_cli.oma_playbooks.install import install
    from hermes_cli.oma_playbooks.source import resolve

    home, repo = checkout
    with pytest.raises(ValueError, match="expected version"):
        resolve(repo, "demo", "1.0.0")
    missing = repo / "skills" / "category" / "shared" / "SKILL.md"
    missing.rename(missing.with_suffix(".disabled"))
    with pytest.raises(ValueError, match="one eligible OMA package"):
        resolve(repo, "demo")
    assert not (home / "profiles").exists()
    missing.with_suffix(".disabled").rename(missing)
    collision = home / "profiles" / "demo__worker"
    collision.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        install(home, resolve(repo, "demo"))
    assert not (home / "profiles" / "demo__orchestrator").exists()
    assert not (home / "playbooks" / "demo").exists()
