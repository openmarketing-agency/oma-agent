"""Exercise local OMA campaign provisioning with native profile operations."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    from hermes_cli.oma_playbooks import __main__ as cli

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
        "agents: [demo__orchestrator, demo__worker]\ngoals: [Measure demand]\nplans: [Review evidence]\n",
        encoding="utf-8",
    )
    for role, dependencies in (("orchestrator", "[shared]"), ("worker", "[]")):
        candidate = source / "agents" / f"demo__{role}"
        candidate.mkdir(parents=True)
        jobs = "[{id: sample, schedule: '1d', prompt: Review evidence.}]" if role == "orchestrator" else "[]"
        (candidate / "config.yaml").write_text(
            f"id: demo__{role}\nname: {role.title()}\ndescription: Test role.\ncampaign_id: demo\noma_skills: {dependencies}\n"
            f"agent: {{enabled_toolsets: [file]}}\njobs: {jobs}\n", encoding="utf-8",
        )
        (candidate / "SOUL.md").write_text(f"I am the {role}.\n", encoding="utf-8")
    for name in ("shared", "unused"):
        skill = skills / "category" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\nContents.\n",
                                       encoding="utf-8")
        (skill / "support.txt").write_text("Support file.", encoding="utf-8")
    return home, source, cli.main


def test_install_generated_records_without_bundle_campaigns(bundle, capsys):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import read_user_config_raw
    from hermes_cli.oma_playbooks.install import default_home
    from hermes_cli.oma_playbooks.source import read_mapping
    from tools.file_tools import read_file_tool, write_file_tool

    home, source, main = bundle
    assert main(["list"]) == 0
    assert not (home / "oma-bundle" / "campaigns").exists()
    assert json.loads(capsys.readouterr().out) == []
    assert main(["status", "demo"]) == 0
    draft = json.loads(capsys.readouterr().out)
    assert draft["state"] == "draft" and draft["present_profiles"] == []
    existing = home / "oma" / "agents" / "demo__worker" / "saves" / "handoff.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("Keep this handoff.", encoding="utf-8")
    assert main(["install", "demo"]) == 0
    assert existing.read_text(encoding="utf-8") == "Keep this handoff."
    record = json.loads(capsys.readouterr().out)
    assert record["description"] == "Test team."
    assert "version" not in record
    assert record["state"] == "installed"
    assert record["present_profiles"] == ["demo__orchestrator", "demo__worker"]
    assert not (home / "playbooks").exists()
    assert not (source / "installations").exists()
    config_path = source / "campaigns" / "demo" / "config.yaml"
    assert set(config_path.parent.iterdir()) == {config_path}
    saved = config_path.read_bytes()
    assert read_mapping(config_path) == {
        "id": "demo", "name": "Demo", "description": "Test team.",
        "goals": ["Measure demand"], "plans": ["Review evidence"],
        "agents": ["demo__orchestrator", "demo__worker"],
        "orchestrator": "demo__orchestrator", "kanban_board": "campaign-demo",
        "kanban_board_name": "Demo", "installation_state": "installed",
    }
    assert record["agents"] == ["demo__orchestrator", "demo__worker"]
    for agent_id in record["agents"]:
        profile = home / "profiles" / agent_id
        scratch = source / "agents" / agent_id / "tmp"
        saves = source / "agents" / agent_id / "saves"
        soul = (profile / "SOUL.md").read_text(encoding="utf-8")
        assert soul.startswith(f"I am the {agent_id.split('__')[1]}.\n")
        assert scratch.is_dir() and str(scratch.resolve()) in soul
        assert saves.is_dir() and f"`{saves.resolve()}`" in soul
        assert "Markdown (`.md`)" in soul and "read the relevant notes" in soul
        assert f"`{config_path.resolve()}`" in soul
        oma = home.resolve() / "oma"
        assert f"`{oma / 'playbook' / 'config.yaml'}`" in soul
        assert f"`{oma / 'brand' / 'config.yaml'}`" in soul
        assert "`brand_id`" not in soul and "`playbook`" not in soul
        assert "Do not scan other records" in soul
        agent_record = read_mapping(source / "agents" / agent_id / "config.yaml")
        assert agent_record["campaign_id"] == "demo"
        assert not (profile / "cron" / "jobs.json").exists()
        assert not (profile / "skills" / "unused").exists()
        raw = read_user_config_raw(profile / "config.yaml")
        assert not {"id", "name", "description", "campaign_id", "version", "jobs", "oma_skills"} & raw.keys()
        assert "oma-campaigns" in raw["skills"]["disabled"]
        with bind_profile_scope(profile, hydrate_secrets=False):
            marker = str(scratch / "marker.txt")
            assert not json.loads(write_file_tool(marker, "Scratch check.")).get("error")
            assert "Scratch check." in read_file_tool(marker)
            assert "id: demo" in read_file_tool(str(config_path), task_id=agent_id)
            note = str(saves / "context.md")
            assert not json.loads(write_file_tool(note, f"Remember {agent_id}.")).get("error")
            assert f"Remember {agent_id}." in read_file_tool(note)
            with pytest.raises(ValueError, match="default OMA Agent"):
                default_home()
    orchestrator_skills = home / "profiles" / "demo__orchestrator" / "skills"
    assert (orchestrator_skills / "shared" / "support.txt").read_text(encoding="utf-8") == "Support file."
    assert not (home / "profiles" / "demo__worker" / "skills" / "shared").exists()

    assert main(["install", "demo"]) == 0
    assert json.loads(capsys.readouterr().out) == record
    assert config_path.read_bytes() == saved
    for agent_id in record["agents"]:
        note = home / "oma" / "agents" / agent_id / "saves" / "context.md"
        assert note.read_text(encoding="utf-8") == f"Remember {agent_id}."
    assert main(["status", "demo"]) == 0
    assert json.loads(capsys.readouterr().out) == record


def test_bundle_templates_are_ignored_and_profile_conflicts_do_not_publish(bundle, capsys):
    home, source, main = bundle
    campaigns = source / "campaigns"
    old_source = home / "oma-bundle" / "campaigns"
    campaigns.rename(old_source)
    assert main(["install", "demo"]) == 1
    assert str(campaigns / "demo" / "config.yaml") in capsys.readouterr().err
    old_source.rename(campaigns)
    missing = home / "oma-bundle" / "skills" / "category" / "shared" / "SKILL.md"
    missing.rename(missing.with_suffix(".disabled"))
    assert main(["install", "demo"]) == 1
    assert "skill 'shared' must resolve" in capsys.readouterr().err
    assert not (home / "profiles").exists()
    missing.with_suffix(".disabled").rename(missing)
    collision = home / "profiles" / "demo__worker"
    collision.mkdir(parents=True)
    assert main(["install", "demo"]) == 1
    assert "already exists" in capsys.readouterr().err
    assert not (home / "profiles" / "demo__orchestrator").exists()
    assert not (source / "installations" / "demo").exists()


@pytest.mark.parametrize(("file", "before", "after", "error"), [
    ("campaigns/demo/config.yaml", "demo__orchestrator, demo__worker", "demo__worker", "canonical orchestrator"),
    ("campaigns/demo/config.yaml", "demo__orchestrator, demo__worker", "demo__orchestrator, demo__orchestrator", "duplicate names"),
    ("agents/demo__worker/config.yaml", "campaign_id: demo", "campaign_id: other", "campaign_id"),
])
def test_invalid_roster_does_not_publish(bundle, capsys, file, before, after, error):
    home, source, main = bundle
    path = source / file
    path.write_text(path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
    assert main(["install", "demo"]) == 1
    assert error in capsys.readouterr().err
    assert not (home / "profiles").exists()
    assert not (source / "installations" / "demo").exists()


def test_generated_cron_belongs_to_the_verified_owner(bundle, capsys):
    from argparse import ArgumentParser

    from agent.runtime_scope import bind_profile_scope
    from cron.jobs import list_jobs
    from hermes_cli.cron import cron_create
    from hermes_cli.oma_playbooks.source import read_mapping
    from hermes_cli.subcommands.cron import build_cron_parser

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    team = json.loads(capsys.readouterr().out)
    owner = team["orchestrator"]
    job, = read_mapping(source / "agents" / owner / "config.yaml")["jobs"]
    assert owner in team["present_profiles"]
    parser = ArgumentParser()
    build_cron_parser(parser.add_subparsers(), cmd_cron=cron_create)
    args = parser.parse_args(["cron", "create", "--name", f"oma:{job['id']}", "--deliver", "local",
                              "--", job["schedule"], job["prompt"]])
    with bind_profile_scope(home / "profiles" / owner, hydrate_secrets=False):
        assert list_jobs(include_disabled=True) == []
        assert cron_create(args) == 0
        saved, = list_jobs(include_disabled=True)
        assert saved["name"] == f"oma:{job['id']}" and saved["enabled"]
        assert saved["prompt"] == job["prompt"]
    with bind_profile_scope(home / "profiles" / "demo__worker", hydrate_secrets=False):
        assert list_jobs(include_disabled=True) == []
    assert list_jobs(include_disabled=True) == []


def test_campaign_agents_share_their_own_kanban_board(bundle, capsys):
    from contextlib import closing
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli import kanban_db as kb
    from hermes_cli.config import read_user_config_raw
    from hermes_cli.kanban_db_connect import connect
    from model_tools import get_tool_definitions
    from tools.kanban_tools import _handle_create, _handle_list

    home, _, main = bundle
    kb.create_board("unrelated")
    kb.set_current_board("unrelated")
    assert main(["install", "demo"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    board = receipt["kanban_board"]
    assert board == "campaign-demo" and kb.board_exists(board)
    assert receipt["kanban_board_name"] == kb.read_board_metadata(board)["name"] == "Demo"
    assert kb.get_current_board() == "unrelated"
    task_id = None
    for agent_id in receipt["present_profiles"]:
        profile = home / "profiles" / agent_id
        raw = read_user_config_raw(profile / "config.yaml")
        assert raw["kanban"]["profile_board"] == board
        with bind_profile_scope(profile, hydrate_secrets=False):
            tools = get_tool_definitions(enabled_toolsets=raw["agent"]["enabled_toolsets"],
                                         skip_tool_search_assembly=True, quiet_mode=True)
            assert "kanban_list" in {tool["function"]["name"] for tool in tools}
            tasks = json.loads(_handle_list({}))
            assert [row["id"] for row in tasks["tasks"]] == ([task_id] if task_id else [])
            assert "error" in json.loads(_handle_list({"board": "unrelated"}))
            if agent_id == receipt["orchestrator"]:
                assert raw["kanban"]["orchestrator_profile"] == agent_id
                result = json.loads(_handle_create({"title": "Plan work", "assignee": "demo__worker"}))
                assert result["ok"], result
                task_id = result["task_id"]
    assert task_id
    with closing(connect(board=board)) as conn:
        task = kb.get_task(conn, task_id)
        assert task and task.assignee == "demo__worker"
    with closing(connect(board="unrelated")) as conn:
        assert kb.get_task(conn, task_id) is None
    assert main(["install", "demo"]) == 0
    assert json.loads(capsys.readouterr().out) == receipt
    assert kb.get_current_board() == "unrelated"


def test_saves_path_conflict_does_not_publish_profiles(bundle, capsys):
    home, source, main = bundle
    conflict = home / "oma" / "agents" / "demo__worker" / "saves"
    conflict.write_text("Keep this file.", encoding="utf-8")

    assert main(["install", "demo"]) == 1
    assert "Expected an agent saves directory" in capsys.readouterr().err
    assert conflict.read_text(encoding="utf-8") == "Keep this file."
    assert not (home / "profiles").exists()
    assert not (source / "installations" / "demo").exists()


def test_configure_recovers_routing_without_reinstalling_unversioned_campaign(bundle, capsys):
    from hermes_cli.oma_playbooks.source import read_mapping

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    config_path = source / "campaigns" / "demo" / "config.yaml"
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = "".join(line for line in lines if not line.startswith(("installation_state:", "kanban_board_name:")))
    config_path.write_text("# Keep my comment\n" + kept, encoding="utf-8")
    profile = home / "profiles" / "demo__orchestrator" / "SOUL.md"
    original_soul = profile.read_bytes()
    assert main(["status", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "installed"
    assert main(["configure", "demo"]) == 0
    assert Path(json.loads(capsys.readouterr().out)["config_path"]).resolve() == config_path.resolve()
    updated = config_path.read_bytes()
    assert updated.startswith(b"# Keep my comment")
    assert read_mapping(config_path)["kanban_board_name"] == "Demo"
    assert read_mapping(config_path)["goals"] == ["Measure demand"]
    assert main(["configure", "demo"]) == 0
    assert config_path.read_bytes() == updated
    assert profile.read_bytes() == original_soul


def test_legacy_versions_do_not_affect_provisioning(bundle, capsys):
    from hermes_cli.oma_playbooks.source import read_mapping

    home, source, main = bundle
    campaign = source / "campaigns" / "demo" / "config.yaml"
    agent = source / "agents" / "demo__worker" / "config.yaml"
    for path in (campaign, agent):
        with path.open("a", encoding="utf-8") as stream:
            stream.write("version: 9.9.9\n")
    assert main(["install", "demo"]) == 0
    assert "version" not in json.loads(capsys.readouterr().out)
    assert "version" not in read_mapping(home / "profiles" / "demo__worker" / "config.yaml")
    assert all(read_mapping(path)["version"] == "9.9.9" for path in (campaign, agent))


def test_interrupted_provisioning_is_recorded_in_campaign_config(bundle, capsys, monkeypatch):
    from hermes_cli.oma_playbooks import install as provisioning
    from hermes_cli.oma_playbooks.source import read_mapping

    home, source, main = bundle
    provision = provisioning.provision_profile

    def fail_worker(request, **kwargs):
        if request.name == "demo__worker":
            raise OSError("Worker could not be provisioned")
        return provision(request, **kwargs)

    monkeypatch.setattr(provisioning, "provision_profile", fail_worker)
    assert main(["install", "demo"]) == 1
    assert "Worker could not be provisioned" in capsys.readouterr().err
    config = source / "campaigns" / "demo" / "config.yaml"
    original = config.read_bytes()
    assert read_mapping(config)["installation_state"] == "installing"
    assert set(config.parent.iterdir()) == {config}
    assert main(["status", "demo"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["state"] == "incomplete"
    assert status["present_profiles"] == ["demo__orchestrator"]
    assert main(["install", "demo"]) == 1
    assert "incomplete installation" in capsys.readouterr().err
    assert config.read_bytes() == original
    assert not (home / "profiles" / "demo__worker").exists()


def test_list_ignores_legacy_installation_state(bundle, capsys):
    home, _, main = bundle
    legacy = home / "playbooks" / "demo" / "installation.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("id: demo\nstate: installed\nagents: {demo__orchestrator: {}}\n", encoding="utf-8")
    original = legacy.read_bytes()
    assert main(["list"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert legacy.read_bytes() == original


@pytest.mark.parametrize("argv", [["catalog"], ["check"], ["fetch"], ["plan", "demo"],
                                  ["install", "demo", "--version", "0.1.0"]])
def test_helper_rejects_old_discovery_and_version_commands(bundle, argv):
    with pytest.raises(SystemExit, match="2"):
        bundle[2](argv)
