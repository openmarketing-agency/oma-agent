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
    opt = tmp_path / "opt"
    campaigns = opt / "oma" / "campaigns"
    skills = opt / "oma" / "skills"
    monkeypatch.setattr(cli, "_CAMPAIGNS_DIR", tmp_path.joinpath(*cli._CAMPAIGNS_DIR.parts[1:]))
    monkeypatch.setattr(cli, "_SKILLS_DIR", tmp_path.joinpath(*cli._SKILLS_DIR.parts[1:]))
    team = campaigns / "demo"
    team.mkdir(parents=True)
    (team / "config.yaml").write_text(
        "id: demo\nname: Demo\ndescription: Test team.\norchestrator: demo__orchestrator\n"
        "agents: [demo__orchestrator, demo__worker]\n", encoding="utf-8",
    )
    for role, dependencies in (("orchestrator", "[shared, local]"), ("worker", "[]")):
        candidate = team / "agents" / f"demo__{role}"
        candidate.mkdir(parents=True)
        (candidate / "config.yaml").write_text(
            f"id: demo__{role}\ndescription: Test role.\noma_skills: {dependencies}\n"
            "agent: {enabled_toolsets: [file]}\njobs: [{id: sample}]\n", encoding="utf-8",
        )
        (candidate / "SOUL.md").write_text(f"I am the {role}.\n", encoding="utf-8")
    for parent, name in ((skills, "shared"), (team / "skills", "local"), (skills, "unused")):
        skill = parent / "category" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\nContents.\n",
                                       encoding="utf-8")
        (skill / "support.txt").write_text("Support file.", encoding="utf-8")
    return home, opt, cli.main


def test_install_local_campaign_without_versions_and_inspect_it(bundle, capsys):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import read_user_config_raw
    from hermes_cli.oma_playbooks.install import default_home
    from hermes_cli.oma_playbooks.source import read_mapping
    from tools.file_tools import read_file_tool, write_file_tool

    home, opt, main = bundle
    assert main(["list"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    existing = home / "oma" / "agents" / "demo__worker" / "saves" / "handoff.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("Keep this handoff.", encoding="utf-8")
    assert main(["install", "demo"]) == 0
    assert existing.read_text(encoding="utf-8") == "Keep this handoff."
    record = json.loads(capsys.readouterr().out)
    assert record["description"] == "Test team."
    assert record["state"] == "installed"
    assert record["present_profiles"] == ["demo__orchestrator", "demo__worker"]
    directory = home / "playbooks" / "demo"
    ledger = directory / "installation.yaml"
    saved = read_mapping(ledger)
    config_path = home / "oma" / "campaigns" / "demo" / "config.yaml"
    assert read_mapping(config_path) == {
        "id": "demo", "name": "Demo", "description": "Test team.", "version": None,
        "goals": [], "plans": [], "playbook": None,
        "orchestrator": "demo__orchestrator", "kanban_board": "campaign-demo",
        "kanban_board_name": "Demo",
    }
    manifest = (opt / "oma" / "campaigns" / "demo" / "config.yaml").resolve()
    assert saved["source_manifest"] == str(manifest)
    assert not (directory / "config.yaml").exists()
    for agent_id, row in saved["agents"].items():
        profile = home / "profiles" / agent_id
        scratch = directory / row["scratch_dir"]
        saves = home / "oma" / "agents" / agent_id / "saves"
        soul = (profile / "SOUL.md").read_text(encoding="utf-8")
        assert soul.startswith(f"I am the {agent_id.split('__')[1]}.\n")
        assert scratch.is_dir() and str(scratch.resolve()) in soul
        assert saves.is_dir() and f"`{saves.resolve()}`" in soul
        assert "Markdown (`.md`)" in soul and "read the relevant notes" in soul
        assert f"`{config_path.resolve()}`" in soul
        oma = home.resolve() / "oma"
        assert f"`{oma / 'playbooks' / '<playbook-id>' / 'config.yaml'}`" in soul
        assert f"`{oma / 'brands' / '<brand-id>' / 'config.yaml'}`" in soul
        assert "`brand_id`" in soul and "`playbook`" in soul
        assert "Do not scan other records" in soul
        assert row["state"] == "installed" and row["declared_jobs"] == ["sample"]
        assert not (profile / "cron" / "jobs.json").exists()
        assert not (profile / "skills" / "unused").exists()
        raw = read_user_config_raw(profile / "config.yaml")
        assert not {"id", "description", "version", "jobs", "oma_skills"} & raw.keys()
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
    for name in ("shared", "local"):
        assert (orchestrator_skills / name / "support.txt").read_text(encoding="utf-8") == "Support file."
    assert not (home / "profiles" / "demo__worker" / "skills" / "shared").exists()

    with manifest.open("a", encoding="utf-8") as stream:
        stream.write("version: 9.9.9\n")
    assert main(["install", "demo"]) == 0
    assert json.loads(capsys.readouterr().out) == record
    assert read_mapping(ledger) == saved
    for agent_id in saved["agents"]:
        note = home / "oma" / "agents" / agent_id / "saves" / "context.md"
        assert note.read_text(encoding="utf-8") == f"Remember {agent_id}."
    assert main(["status", "demo"]) == 0
    assert json.loads(capsys.readouterr().out) == record


def test_missing_local_sources_and_profile_collision_do_not_publish(bundle, capsys):
    home, opt, main = bundle
    campaigns = opt / "oma" / "campaigns"
    old_source = opt / "oma" / "playbooks"
    campaigns.rename(old_source)
    assert main(["install", "demo"]) == 1
    assert str(campaigns / "demo" / "config.yaml") in capsys.readouterr().err
    old_source.rename(campaigns)
    missing = opt / "oma" / "skills" / "category" / "shared" / "SKILL.md"
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
    assert not (home / "playbooks" / "demo").exists()


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
    home, _, main = bundle
    conflict = home / "oma" / "agents" / "demo__worker" / "saves"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("Keep this file.", encoding="utf-8")

    assert main(["install", "demo"]) == 1
    assert "Expected an agent saves directory" in capsys.readouterr().err
    assert conflict.read_text(encoding="utf-8") == "Keep this file."
    assert not (home / "profiles").exists()
    assert not (home / "playbooks" / "demo").exists()


def test_configure_backfills_from_installed_campaign_without_reinstalling(bundle, capsys):
    from hermes_cli.oma_playbooks.source import read_mapping

    home, opt, main = bundle
    (opt / "oma" / "campaigns").rename(opt / "oma" / "unavailable")
    ledger = home / "playbooks" / "demo" / "installation.yaml"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        "id: demo\nname: Installed Demo\ndescription: Existing campaign.\nversion: 1.2.3\n"
        "state: installed\norchestrator: demo__orchestrator\nagents: {demo__orchestrator: {}}\n", encoding="utf-8",
    )
    original = ledger.read_bytes()
    config_path = home / "oma" / "campaigns" / "demo" / "config.yaml"
    assert main(["status", "demo"]) == 0
    capsys.readouterr()
    assert not config_path.exists()
    assert main(["configure", "demo"]) == 0
    assert Path(json.loads(capsys.readouterr().out)["config_path"]).resolve() == config_path.resolve()
    assert read_mapping(config_path) == {
        "id": "demo", "name": "Installed Demo", "description": "Existing campaign.",
        "version": "1.2.3", "goals": [], "plans": [], "playbook": None,
        "orchestrator": "demo__orchestrator",
    }
    custom = "# Keep my comment\nid: demo\ngoals: [Measure sign-ups]\nplans: [Review weekly]\nplaybook: product-launch\n"
    config_path.write_text(custom, encoding="utf-8")
    assert main(["configure", "demo"]) == 0
    updated = config_path.read_bytes()
    assert updated.startswith(b"# Keep my comment")
    assert read_mapping(config_path) == {
        "id": "demo", "goals": ["Measure sign-ups"], "plans": ["Review weekly"],
        "playbook": "product-launch", "orchestrator": "demo__orchestrator",
    }
    assert main(["configure", "demo"]) == 0
    assert config_path.read_bytes() == updated
    assert ledger.read_bytes() == original
    assert not (home / "profiles").exists()
    assert not (home / "kanban").exists()


@pytest.mark.parametrize("argv", [["catalog"], ["check"], ["fetch"], ["plan", "demo"],
                                  ["install", "demo", "--version", "0.1.0"]])
def test_helper_rejects_old_discovery_and_version_commands(bundle, argv):
    with pytest.raises(SystemExit, match="2"):
        bundle[2](argv)
