"""Exercise local OMA campaign provisioning with native profile operations."""

import json
import os
import subprocess
import sys
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


def test_install_requires_campaign_publisher_before_provisioning(bundle, capsys):
    from hermes_cli import kanban_db
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    path = source / "campaigns/demo/config.yaml"
    config = read_mapping(path)
    atomic_config_write(path, {**config, "agents": [agent for agent in config["agents"] if agent != "demo__publisher"]})
    before = path.read_bytes()

    assert main(["install", "demo"]) == 1
    assert "roster must contain the canonical publisher demo__publisher" in capsys.readouterr().err
    assert path.read_bytes() == before
    assert not kanban_db.board_exists("campaign-demo")
    assert not (home / "profiles/demo__orchestrator").exists()


def test_already_installed_campaign_without_publisher_is_left_unchanged(bundle, capsys):
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    path = source / "campaigns/demo/config.yaml"
    atomic_config_write(path, {**read_mapping(path), "agents": list(DEMO_AGENTS[:2])})
    publisher = home / "profiles/demo__publisher"
    publisher.rename(home / "previous-publisher")
    before = path.read_bytes()

    assert main(["install", "demo"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "installed" and result["present_profiles"] == list(DEMO_AGENTS[:2])
    assert path.read_bytes() == before
    assert not publisher.exists()


def test_campaign_integration_candidates_use_brand_evidence(bundle, capsys):
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.integrations import integration_catalog

    _, source, main = bundle
    brand = source / "brand" / "config.yaml"
    brand.parent.mkdir()
    atomic_config_write(brand, {
        "id": "demo", "name": "Demo", "description": "Example brand",
        "integrations": {"google_analytics": {"status": "observed", "evidence": "research/analytics.md"},
                         "wordpress_com": {"status": "observed", "evidence": "research/cms.md"}},
        "channels": {"social": [{"platform": "twitter", "status": "verified", "url": "https://x.com/demo"},
                                {"platform": "youtube", "status": "not_checked"}]},
    })
    assert main(["integrations"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "candidates": ["google-analytics", "wordpress-com", "x"], "unmapped": [],
    }
    assert integration_catalog()["wordpress-com"]["composio"] == "wordpress_com"
    assert "wordpress" not in integration_catalog()


@pytest.mark.parametrize("model", ["provider/test-model", {"default": "test-model", "provider": "openrouter"}])
def test_campaign_resume_requires_saved_model_but_not_connected_integrations(bundle, capsys, model):
    from hermes_cli import kanban_db
    from hermes_cli.config import atomic_config_replace, atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    config = source / "campaigns" / "demo" / "config.yaml"
    declared = ["google-analytics", "workspace-managed-tool"]
    atomic_config_write(config, {**read_mapping(config), "integrations": declared})
    assert main(["install", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["lifecycle_state"] == "paused"
    assert kanban_db.board_exists("campaign-demo")
    for missing in ({}, {"model": " "}, {"model": {"provider": "openrouter"}}):
        atomic_config_write(config, {**read_mapping(config), **missing})
        assert main(["lifecycle", "demo", "resumed"]) == 3
        assert json.loads(capsys.readouterr().out) == {"id": "demo", "state": "paused", "missing_model": True}
        assert read_mapping(config)["lifecycle_state"] == "paused"

    atomic_config_replace(config, {**read_mapping(config), "model": model})
    assert main(["lifecycle", "demo", "resumed"]) == 0
    assert json.loads(capsys.readouterr().out) == {"id": "demo", "state": "resumed"}
    assert not (home / "profiles" / "demo__orchestrator" / "cron" / "jobs.json").exists()
    assert main(["lifecycle", "demo", "paused"]) == 0
    assert sync_campaign(home, "demo")["id"] == "demo"
    assert read_mapping(config)["integrations"] == declared


def test_campaign_pause_blocks_gateway_cron_and_kanban_without_editing_job_state(bundle, capsys):
    from cron.jobs import create_job, get_due_jobs, list_jobs, trigger_job, use_cron_store
    from hermes_cli import kanban_db, profiles
    from hermes_cli.config import atomic_config_write
    from hermes_cli.kanban_db_connect import connect_closing
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    config = source / "campaigns" / "demo" / "config.yaml"
    atomic_config_write(config, {**read_mapping(config), "model": "provider/test-model"})
    assert main(["install", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["lifecycle_state"] == "paused"
    role = home / "profiles" / "demo__orchestrator"
    assert "demo__orchestrator" not in dict(profiles.profiles_to_serve(True))
    with use_cron_store(role):
        recurring = create_job(prompt="Review progress", schedule="every 1d")
        disabled = create_job(prompt="Stay paused", schedule="every 1d", paused=True)
        assert get_due_jobs() == []
    with connect_closing(board="campaign-demo") as conn:
        task_id = kanban_db.create_task(conn, title="Do work", assignee=role.name)
        assert kanban_db.claim_task(conn, task_id) is None
    assert main(["lifecycle", "demo", "resumed"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "resumed"
    assert "demo__orchestrator" in dict(profiles.profiles_to_serve(True))
    with use_cron_store(role):
        trigger_job(recurring["id"])
        assert [j["id"] for j in get_due_jobs()] == [recurring["id"]]
    with connect_closing(board="campaign-demo") as conn:
        assert kanban_db.claim_task(conn, task_id) is not None
    assert main(["lifecycle", "demo", "paused"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "paused"
    assert "demo__orchestrator" not in dict(profiles.profiles_to_serve(True))
    assert "default" in dict(profiles.profiles_to_serve(True))
    with connect_closing(board="campaign-demo") as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "ready"
        assert kanban_db.claim_task(conn, task_id) is None
    with use_cron_store(role):
        assert get_due_jobs() == []
        assert {j["id"]: j["enabled"] for j in list_jobs(include_disabled=True)} == {
            recurring["id"]: True, disabled["id"]: False,
        }


@pytest.mark.parametrize("mode", [None, "yolo", "approve", "control"])
def test_campaign_publications_handoff(bundle, capsys, mode):
    from hermes_cli import kanban_db
    from hermes_cli.config import atomic_config_write
    from hermes_cli.kanban_db_connect import connect_closing
    from hermes_cli.oma_campaigns.publications import (
        PublicationError, approve_publication, claim_publication, finish_publication, list_publications, save_publication,
    )
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    config_path = source / "campaigns" / "demo" / "config.yaml"
    config = read_mapping(config_path)
    if mode is not None:
        config["mode"] = mode
    atomic_config_write(config_path, {**config, "model": "provider/test-model"})
    role = source / "agents" / "demo__publisher"
    assert main(["install", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == (mode or "approve")
    assert main(["lifecycle", "demo", "resumed"]) == 0
    assert list_publications(home, "demo")["mode"] == (mode or "approve")
    assert list_publications(home, "demo")["publications"] == []
    assert not (config_path.parent / "publications.sqlite3").exists()

    draft = {"platform": "x", "kind": "reply", "account": {"id": "connected-42", "handle": "demo"},
             "content": {"text": "Thanks!\nHere is the detail."}, "target": {"id": "987", "text": "Question?"}}
    saved = save_publication(home, "demo", "demo__worker", draft)
    item = saved["id"]
    if mode == "yolo":
        assert saved["status"] == "approved" and saved["task_id"]
        assert saved["approval"]["source"] == "automatic" and saved["approval"]["by"] is None
    else:
        assert saved["status"] == "pending_approval" and saved["task_id"] is None
        with pytest.raises(PublicationError, match="not available"):
            claim_publication(home, "demo", role.name, item, 1)
        draft["content"]["text"] += " Updated."
        saved = save_publication(home, "demo", "demo__worker", draft, publication_id=item, revision=1)
        with pytest.raises(PublicationError, match="changed"):
            approve_publication(home, "demo", item, 1, "owner")
        saved = approve_publication(home, "demo", item, 2, "owner")
        assert saved["approval"]["source"] == "human" and saved["approval"]["by"] == "owner"
        assert approve_publication(home, "demo", item, 2, "owner")["task_id"] == saved["task_id"]
    with connect_closing(board="campaign-demo") as conn:
        assert len(kanban_db.list_tasks(conn)) == 1
        ordinary = kanban_db.create_task(conn, title="Ordinary work", assignee="demo__worker")
        assert (kanban_db.claim_task(conn, ordinary) is None) == (mode == "control")
        task = kanban_db.claim_task(conn, saved["task_id"])
        assert task is not None and task.assignee == role.name and item in task.body
        assert draft["content"]["text"] not in task.body
    with pytest.raises(PublicationError, match="Only the campaign publisher"):
        claim_publication(home, "demo", "demo__worker", item, saved["revision"])
    claim = claim_publication(home, "demo", role.name, item, saved["revision"])
    assert claim["content"] == draft["content"] and claim["target"] == draft["target"]
    [in_progress] = list_publications(home, "demo")["publications"]
    assert in_progress["status"] == "publishing" and not in_progress.get("needs_verification")
    with pytest.raises(PublicationError, match="not available"):
        claim_publication(home, "demo", role.name, item, saved["revision"])
    with connect_closing(board="campaign-demo") as conn:
        assert kanban_db.complete_task(conn, task.id, result="Worker ended without recording a receipt.",
                                       expected_run_id=task.current_run_id)
    [unconfirmed] = list_publications(home, "demo")["publications"]
    assert unconfirmed["status"] == "publishing" and unconfirmed.get("needs_verification") is True
    assert unconfirmed["result"] is None
    with pytest.raises(PublicationError, match="not available"):
        claim_publication(home, "demo", role.name, item, saved["revision"])

    receipt = {"provider_id": "external-1", "url": "https://x.com/demo/status/1"}
    finish = (home, "demo", role.name, item, saved["revision"])
    result = finish_publication(*finish, claim["claim_token"], receipt)
    assert result["status"] == "published"
    assert not result.get("needs_verification")
    assert finish_publication(*finish, claim["claim_token"], receipt) == result
    with pytest.raises(PublicationError, match="does not own"):
        finish_publication(*finish, "0" * 32, receipt)
    with pytest.raises(PublicationError, match="different result"):
        finish_publication(*finish, claim["claim_token"], {"error": "Definitively rejected"})
    listed = list_publications(home, "demo")["publications"]
    assert listed == [result] and "claim_token" not in listed[0]


def test_campaign_control_removes_registered_cron_and_restores_operator_pause(bundle):
    from cron.jobs import create_job, list_jobs, use_cron_store
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    path = source / "campaigns" / "demo" / "config.yaml"
    atomic_config_write(path, {**read_mapping(path), "model": "provider/test-model"})
    assert main(["install", "demo"]) == 0
    profile = home / "profiles" / "demo__orchestrator"
    with use_cron_store(profile):
        operator = create_job(prompt="Stay paused", schedule="1d", paused=True)
    assert main(["mode", "demo", "control"]) == 0
    sync_campaign(home, "demo")
    assert main(["lifecycle", "demo", "resumed"]) == 0
    with use_cron_store(profile):
        assert list_jobs(include_disabled=True) == []
        with pytest.raises(ValueError, match="control mode"):
            create_job(prompt="Must not run", schedule="1d")
    assert main(["mode", "demo", "approve"]) == 1
    assert main(["lifecycle", "demo", "paused"]) == 0
    assert main(["mode", "demo", "approve"]) == 0
    sync_campaign(home, "demo")
    assert main(["lifecycle", "demo", "resumed"]) == 0
    with use_cron_store(profile):
        jobs = {job["id"]: job for job in list_jobs(include_disabled=True)}
        assert not jobs[operator["id"]]["enabled"]
        assert any(job.get("oma_job_id") == "sample" and job["enabled"] for job in jobs.values())


def test_install_generated_records_without_bundle_campaigns(bundle, capsys):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import read_user_config_raw
    from hermes_cli.oma_campaigns.install import default_home
    from hermes_cli.oma_campaigns.source import read_mapping
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
    assert record["present_profiles"] == list(DEMO_AGENTS)
    assert not (home / "playbooks").exists()
    assert not (source / "installations").exists()
    config_path = source / "campaigns" / "demo" / "config.yaml"
    assert set(config_path.parent.iterdir()) == {config_path}
    saved = config_path.read_bytes()
    assert read_mapping(config_path) == {
        "id": "demo", "name": "Demo", "description": "Test team.",
        "goals": ["Measure demand"], "plans": ["Review evidence"],
        "integrations": [],
        "agents": list(DEMO_AGENTS),
        "orchestrator": "demo__orchestrator", "kanban_board": "campaign-demo",
        "kanban_board_name": "Demo", "installation_state": "installed", "lifecycle_state": "paused",
    }
    assert record["agents"] == list(DEMO_AGENTS)
    for agent_id in record["agents"]:
        profile = home / "profiles" / agent_id
        scratch = source / "agents" / agent_id / "tmp"
        saves = source / "agents" / agent_id / "saves"
        soul = (profile / "SOUL.md").read_text(encoding="utf-8")
        assert soul.startswith(f"I am the {agent_id.split('__')[1]}.\n")
        assert "## Campaign scratch directory" in soul
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


def test_sync_materializes_defaults_and_agent_overrides(bundle, capsys):
    from hermes_cli.config import atomic_config_write, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    campaign = source / "campaigns" / "demo" / "config.yaml"
    worker = source / "agents" / "demo__worker" / "config.yaml"
    orchestrator = source / "agents" / "demo__orchestrator" / "config.yaml"
    campaign_defaults = {
        "model": {"default": "team-model", "provider": "custom", "base_url": "https://model.invalid/v1"},
        "mcp_servers": {
            "docs": {"url": "https://docs.invalid/mcp", "headers": {"X-Test": "shared"}},
            "reports": {"url": "https://reports.invalid/mcp", "timeout": 12},
        },
    }
    override = {"model": "worker-model", "mcp_servers": {"docs": {"enabled": False}}}
    atomic_config_write(campaign, {**read_mapping(campaign), **campaign_defaults})
    atomic_config_write(worker, {**read_mapping(worker), **override})

    assert sync(["demo"]) == 0
    assert json.loads(capsys.readouterr().out)["updated_agents"] == list(DEMO_AGENTS)
    for path, expected in (
        (orchestrator, campaign_defaults),
        (worker, {**override, "mcp_servers": {**campaign_defaults["mcp_servers"], **override["mcp_servers"]}}),
        (source / "agents/demo__publisher/config.yaml", campaign_defaults),
    ):
        authored = read_mapping(path)
        assert authored.get("model") == (override["model"] if path == worker else None)
        assert authored["effective"] == {"mcp_servers": expected["mcp_servers"]}
        assert authored.get("mcp_servers") == (override["mcp_servers"] if path == worker else None)
        native = read_user_config_raw(home / "profiles" / path.parent.name / "config.yaml")
        assert {key: native[key] for key in expected} == expected
        assert native["agent"]["enabled_toolsets"] == ["file", "kanban"]
        assert "effective" not in native and "jobs" not in native

    assert sync(["demo"]) == 0
    assert json.loads(capsys.readouterr().out)["updated_agents"] == []


def test_agent_and_campaign_sync_share_inheritance_and_keep_campaign_persona_context(bundle, capsys):
    from agent.secret_scope import load_env_file
    from hermes_cli.config import atomic_config_replace, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    campaign = source / "campaigns/demo/config.yaml"
    atomic_config_replace(campaign, {**read_mapping(campaign), "model": "initial", "agent": {"reasoning_effort": "low"}})
    assert main(["install", "demo"]) == 0
    owner = home / "profiles/demo__orchestrator"
    worker = home / "profiles/demo__worker"
    owner_record = source / "agents/demo__orchestrator/config.yaml"
    worker_record = source / "agents/demo__worker/config.yaml"
    assert "model" not in read_mapping(owner_record)
    assert read_user_config_raw(owner / "config.yaml")["model"] == "initial"
    assert read_user_config_raw(owner / "config.yaml")["agent"]["reasoning_effort"] == "low"

    atomic_config_replace(campaign, {**read_mapping(campaign), "model": "new-team-model",
                                     "agent": {"reasoning_effort": "high"}})
    saved_worker = read_mapping(worker_record)
    saved_worker["agent"]["reasoning_effort"] = "none"
    atomic_config_replace(worker_record, {**saved_worker, "model": "worker-override"})
    (owner_record.parent / "SOUL.md").write_text("Updated orchestrator persona.\n", encoding="utf-8")
    before_worker = (worker / "config.yaml").read_bytes()
    from hermes_cli.oma_campaigns.sync import sync_agent

    result = sync_agent(home, "demo__orchestrator", env={"PRIVATE_SYNC_FIXTURE": "only-this-agent"})
    assert {"model", "agent.reasoning_effort", "SOUL.md", "env"} <= set(result["updated"])
    assert (worker / "config.yaml").read_bytes() == before_worker
    assert "PRIVATE_SYNC_FIXTURE" not in load_env_file(worker / ".env")
    assert read_mapping(campaign)["available-keys"] == ["PRIVATE_SYNC_FIXTURE"]
    soul = (owner / "SOUL.md").read_text(encoding="utf-8")
    assert soul.startswith("Updated orchestrator persona.")
    assert str(campaign) in soul and "campaign-demo" in soul and str(owner_record.parent / "saves") in soul

    assert sync(["demo"]) == 0
    assert read_user_config_raw(worker / "config.yaml")["model"] == "worker-override"
    assert read_user_config_raw(worker / "config.yaml")["agent"]["reasoning_effort"] == "none"
    assert read_user_config_raw(owner / "config.yaml")["model"] == "new-team-model"
    assert read_mapping(campaign)["lifecycle_state"] == "paused"
    capsys.readouterr()
    assert sync(["demo"]) == 0
    assert json.loads(capsys.readouterr().out)["updated_agents"] == []


def test_campaign_sync_and_resume_resolve_saved_default_without_pinning_it(bundle, capsys):
    from agent.secret_scope import load_env_file
    from hermes_cli.config import atomic_config_replace, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    campaign = source / "campaigns/demo/config.yaml"
    worker_record = source / "agents/demo__worker/config.yaml"
    owner_record = source / "agents/demo__orchestrator/config.yaml"
    owner = home / "profiles/demo__orchestrator"
    worker = home / "profiles/demo__worker"
    default_config = home / "config.yaml"
    initial = {"provider": "openrouter", "default": "first-model", "api_key": "${OPENROUTER_API_KEY}"}
    atomic_config_replace(default_config, {"model": initial, "agent": {"reasoning_effort": "low"}})
    (home / ".env").write_text("OPENROUTER_API_KEY=sk-or-v1-fixture-default\n", encoding="utf-8")
    atomic_config_replace(worker_record, {**read_mapping(worker_record), "model": "worker-override"})
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    assert read_user_config_raw(owner / "config.yaml")["model"] == initial
    assert "model" not in read_mapping(campaign)
    assert read_mapping(campaign)["integrations"] == []

    updated = {**initial, "default": "next-model"}
    atomic_config_replace(default_config, {"model": updated, "agent": {"reasoning_effort": ""}})
    (owner_record.parent / "SOUL.md").unlink()
    native_soul = (owner / "SOUL.md").read_bytes()
    explicit_key = "sk-or-v1-fixture-explicit"
    sync_campaign(home, "demo", env={"OPENROUTER_API_KEY": explicit_key})
    assert read_user_config_raw(owner / "config.yaml")["model"] == updated
    assert read_user_config_raw(owner / "config.yaml")["agent"]["reasoning_effort"] == ""
    assert (owner / "SOUL.md").read_bytes() == native_soul
    assert load_env_file(owner / ".env")["OPENROUTER_API_KEY"] == explicit_key
    assert read_user_config_raw(worker / "config.yaml")["model"] == "worker-override"
    assert "model" not in read_mapping(campaign)
    assert "model" not in read_mapping(owner_record)
    assert main(["lifecycle", "demo", "resumed"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "resumed"
    assert main(["lifecycle", "demo", "paused"]) == 0
    capsys.readouterr()

    atomic_config_replace(default_config, {})
    sync_campaign(home, "demo")
    assert "model" not in read_user_config_raw(owner / "config.yaml")
    assert read_user_config_raw(worker / "config.yaml")["model"] == "worker-override"
    assert main(["lifecycle", "demo", "resumed"]) == 3
    assert json.loads(capsys.readouterr().out)["missing_model"] is True


def test_campaign_sync_reconciles_only_oma_jobs_and_skills(bundle, capsys):
    from cron.jobs import create_job, list_jobs, mark_job_run, resume_job, use_cron_store
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__orchestrator"
    record = source / "agents/demo__orchestrator/config.yaml"
    local_skill = profile / "skills/local"
    local_skill.mkdir()
    (local_skill / "SKILL.md").write_text("---\nname: local\ndescription: Local skill.\n---\n", encoding="utf-8")
    with use_cron_store(profile):
        unrelated = create_job(prompt="Keep this manual job.", schedule="1d")

    capsys.readouterr()
    assert sync(["demo"]) == 0
    with use_cron_store(profile):
        managed, = [job for job in list_jobs(include_disabled=True) if job["id"] != unrelated["id"]]
        assert (managed["state"], managed["enabled"], managed["next_run_at"]) == ("paused", False, None)
        resume_job(managed["id"])
        assert mark_job_run(managed["id"], success=True)

    current = read_mapping(record)
    job = {**current["jobs"][0], "name": "Updated review", "schedule": "0 9 * * *",
           "timezone": "UTC", "prompt": "Check new evidence."}
    second = {**job, "id": "second", "name": "Second review"}
    atomic_config_replace(record, {**current, "jobs": [job, second], "oma_skills": ["unused"]})
    assert sync(["demo"]) == 0
    assert not (profile / "skills/shared").exists()
    assert (profile / "skills/unused/support.txt").is_file() and local_skill.is_dir()
    with use_cron_store(profile):
        by_name = {j["name"]: j for j in list_jobs(include_disabled=True)}
    updated = by_name["Updated review"]
    assert updated["id"] != managed["id"] and managed["name"] not in by_name
    assert (updated["enabled"], updated["timezone"], updated["prompt"], updated["repeat"]["completed"]) == (
        True, "UTC", "Check new evidence.", 0)
    assert updated["next_run_at"] and not updated.get("last_run_at")
    assert not by_name["Second review"]["enabled"]

    atomic_config_replace(record, {**read_mapping(record), "jobs": [], "oma_skills": []})
    assert sync(["demo"]) == 0
    with use_cron_store(profile):
        assert [job["id"] for job in list_jobs(include_disabled=True)] == [unrelated["id"]]
    assert not (profile / "skills/unused").exists() and local_skill.is_dir()


def test_sync_reuses_legacy_oma_schedule_and_preserves_operator_pause(bundle):
    from cron.jobs import create_job, list_jobs, use_cron_store
    from hermes_cli.oma_campaigns.sync import sync_agent, sync_campaign

    home, _, main = bundle
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__orchestrator"
    with use_cron_store(profile):
        legacy = create_job(name="oma:sample", prompt="Review evidence.", schedule="1d",
                            paused=True, paused_reason="Operator paused this")
    assert "jobs" in sync_agent(home, profile.name)["updated"]
    with use_cron_store(profile):
        job, = list_jobs(include_disabled=True)
        assert (job["id"], job["enabled"], job["paused_reason"]) == (legacy["id"], False, "Operator paused this")
    assert sync_campaign(home, "demo")["updated_agents"] == ["demo__worker", "demo__publisher"]


@pytest.mark.parametrize("paused", [False, True], ids=["scheduled", "operator-paused"])
def test_campaign_sync_adopts_identical_local_review_with_api_origin(bundle, paused):
    from cron.jobs import create_job, list_jobs, use_cron_store
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, _, main = bundle
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__orchestrator"
    with use_cron_store(profile):
        original = create_job(name="oma:sample", prompt="Review evidence.", schedule="every 1d",
                              deliver="local", origin={"platform": "api_server", "chat_id": "api"},
                              paused=paused, paused_reason="Operator paused this" if paused else None)
    assert "demo__orchestrator" in sync_campaign(home, "demo")["updated_agents"]
    assert sync_campaign(home, "demo")["updated_agents"] == []
    with use_cron_store(profile):
        job, = list_jobs(include_disabled=True)
    assert job["oma_job_id"] == "sample"
    for key in ("id", "created_at", "enabled", "state", "paused_reason", "next_run_at", "repeat", "deliver", "origin"):
        assert job[key] == original[key]


@pytest.mark.parametrize("override", [
    {"deliver": "origin"}, {"failure_deliver": "origin"}, {"skills": ["shared"]},
], ids=["delivery", "failure-delivery", "skills"])
def test_campaign_sync_leaves_conflicting_api_origin_job_untouched(bundle, override):
    from cron.jobs import create_job, use_cron_store
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, _, main = bundle
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__orchestrator"
    with use_cron_store(profile):
        create_job(**{
            "name": "oma:sample", "prompt": "Review evidence.", "schedule": "1d", "deliver": "local",
            "origin": {"platform": "api_server", "chat_id": "api"}, **override,
        })
    store = profile / "cron/jobs.json"
    before = store.read_bytes()
    with pytest.raises(ValueError, match="reserved OMA name"):
        sync_campaign(home, "demo")
    assert store.read_bytes() == before


@pytest.mark.parametrize("delta", [
    {"name": "Renamed review"}, {"prompt": "Review only new evidence."}, {"schedule": "2d"},
    {"repeat": 3}, {"timezone": "UTC"},
], ids=["name", "prompt", "schedule", "repeat", "timezone"])
def test_campaign_sync_recreates_changed_local_review_with_api_origin(bundle, delta):
    from cron.jobs import create_job, list_jobs, parse_schedule, use_cron_store
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__orchestrator"
    with use_cron_store(profile):
        original = create_job(name="oma:sample", prompt="Review evidence.", schedule="1d", deliver="local",
                              origin={"platform": "api_server", "chat_id": "api"},
                              paused=True, paused_reason="Operator paused this")
    path = source / "agents/demo__orchestrator/config.yaml"
    record = read_mapping(path)
    job = {**record["jobs"][0], **delta}
    atomic_config_replace(path, {**record, "jobs": [job]})

    assert "demo__orchestrator" in sync_campaign(home, "demo")["updated_agents"]
    assert sync_campaign(home, "demo")["updated_agents"] == []
    with use_cron_store(profile):
        replacement, = list_jobs(include_disabled=True)
    assert replacement["id"] != original["id"] and replacement["oma_job_id"] == "sample"
    assert not replacement["enabled"] and replacement["paused_reason"] == "Operator paused this"
    assert replacement["name"] == job.get("name", "oma:sample")
    assert replacement["prompt"] == job["prompt"]
    assert replacement["schedule"] == parse_schedule(job["schedule"])
    assert replacement.get("timezone") == job.get("timezone")
    assert replacement["repeat"] == {"times": job.get("repeat"), "completed": 0}


def test_agent_sync_leaves_unchanged_relative_one_shot_anchored(bundle, capsys):
    from cron.jobs import list_jobs, use_cron_store
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.standalone import main as agent_cli

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    profile = home / "profiles/demo__worker"
    record = source / "agents/demo__worker/config.yaml"
    atomic_config_replace(record, {**read_mapping(record), "jobs": [
        {"id": "one-time-review", "schedule": "in 2h", "prompt": "Review evidence."},
    ]})
    capsys.readouterr()
    assert agent_cli(["sync", profile.name]) == 0
    assert "jobs" in json.loads(capsys.readouterr().out)["updated"]
    with use_cron_store(profile):
        original, = list_jobs(include_disabled=True)
    assert agent_cli(["sync", profile.name]) == 0
    assert json.loads(capsys.readouterr().out)["updated"] == []
    with use_cron_store(profile):
        after, = list_jobs(include_disabled=True)
    assert after["schedule"] == original["schedule"]


@pytest.mark.parametrize("invalid", ["jobs", "oma_skills", "SOUL.md"])
def test_campaign_preflights_every_member_before_applying_settings(bundle, invalid):
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    owner = home / "profiles/demo__orchestrator"
    native = owner / "config.yaml"
    before = native.read_bytes()
    campaign = source / "campaigns/demo/config.yaml"
    atomic_config_replace(campaign, {**read_mapping(campaign), "model": "not-applied"})
    worker = source / "agents/demo__worker"
    if invalid == "SOUL.md":
        (worker / invalid).write_text("\n", encoding="utf-8")
    else:
        value = [{"id": "bad", "prompt": "Sample.", "schedule": "not a schedule"}] if invalid == "jobs" else ["unknown"]
        path = worker / "config.yaml"
        atomic_config_replace(path, {**read_mapping(path), invalid: value})
    with pytest.raises(ValueError):
        sync_campaign(home, "demo", env={"NOT_APPLIED_TOKEN": "fixture-never-written"})
    assert native.read_bytes() == before
    assert not (owner / "cron/jobs.json").exists()
    from agent.secret_scope import load_env_file
    assert "NOT_APPLIED_TOKEN" not in load_env_file(owner / ".env")


def test_campaign_sync_applies_each_roles_toolsets_without_replacing_native_sections(bundle, capsys):
    from hermes_cli.config import atomic_config_replace, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    worker = source / "agents" / "demo__worker" / "config.yaml"
    native = home / "profiles" / "demo__worker" / "config.yaml"
    before = read_user_config_raw(native)
    before["agent"]["max_turns"] = 11
    before["tools"]["tool_search"]["listing"] = "off"
    atomic_config_replace(native, before)
    authored = read_mapping(worker)
    authored["agent"].update(enabled_toolsets=["file", "web"], disabled_toolsets=[], max_turns=99)
    authored["tools"] = {"tool_search": {"eager_toolsets": ["file"], "defer_toolsets": ["web"]}}
    atomic_config_replace(worker, authored)

    owner = home / "profiles" / "demo__orchestrator" / "config.yaml"
    assert sync(["demo"]) == 0
    assert "demo__worker" in json.loads(capsys.readouterr().out)["updated_agents"]
    assert read_user_config_raw(owner)["agent"]["enabled_toolsets"] == ["file", "kanban"]
    applied = read_user_config_raw(native)
    assert applied["agent"]["enabled_toolsets"] == ["file", "web"]
    assert applied["agent"]["disabled_toolsets"] == []
    assert applied["agent"]["max_turns"] == 11
    policy = applied["tools"]["tool_search"]
    assert (policy["eager_toolsets"], policy["defer_toolsets"], policy["listing"]) == (["file"], ["web"], "off")
    assert sync(["demo"]) == 0
    assert json.loads(capsys.readouterr().out)["updated_agents"] == []


@pytest.mark.parametrize(("role", "policy", "error_field"), [
    ("worker", {"enabled_toolsets": "file"}, "agent.enabled_toolsets"),
    ("orchestrator", {"enabled_toolsets": ["file"]}, "kanban"),
    ("orchestrator", {"disabled_toolsets": ["kanban"]}, "kanban"),
])
def test_campaign_sync_rejects_bad_toolsets_before_applying_other_roles(bundle, capsys, role, policy, error_field):
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    owner = source / "agents" / "demo__orchestrator" / "config.yaml"
    worker = source / "agents" / "demo__worker" / "config.yaml"
    invalid, other = (worker, owner) if role == "worker" else (owner, worker)
    atomic_config_replace(other, {**read_mapping(other), "model": "unapplied-model"})
    profiles = tuple(home / "profiles" / name / "config.yaml" for name in DEMO_AGENTS)
    before = [path.read_bytes() for path in profiles]
    atomic_config_replace(invalid, {**read_mapping(invalid), "agent": policy})
    assert sync(["demo"]) == 1
    assert error_field in capsys.readouterr().err
    assert [path.read_bytes() for path in profiles] == before


@pytest.fixture
def run_campaign_script(bundle):
    from hermes_cli._launchers import mint_launcher
    from hermes_cli._startup_fast import project_root_str

    home, _, _ = bundle
    root = Path(project_root_str())
    launcher_dir = home / "bin"
    launcher_dir.mkdir()
    assert mint_launcher("hermes", root, launcher_dir, Path(sys.executable), None)

    def run(script, *args, stdin=None, **values):
        env = {**os.environ, "PATH": os.pathsep.join([str(launcher_dir), os.environ.get("PATH", os.defpath)]),
               **values}
        return subprocess.run([sys.executable, str(root / "scripts" / script), *args],
                              env=env, cwd=home, input=stdin, capture_output=True, text=True, timeout=30, check=False)

    return run


def test_campaign_helper_uses_installed_runtime(bundle, run_campaign_script):
    from hermes_cli._startup_fast import project_root_str

    _, source, _ = bundle
    helper = Path(project_root_str()) / "skills/oma/oma-campaigns/scripts/campaign.py"
    result = run_campaign_script(helper, "status", "demo")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "draft"
    result = run_campaign_script(helper, "validate", "campaign", str(source / "campaigns" / "demo" / "config.yaml"))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"kind": "campaign", "valid": True}


def test_sync_campaign_script_accepts_explicit_env_but_never_imports_ambient_values(bundle, capsys, run_campaign_script):
    from agent.runtime_scope import bind_profile_scope
    from agent.secret_scope import load_env_file
    from hermes_cli.config import atomic_config_write, load_config, save_env_value
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    campaign = source / "campaigns" / "demo" / "config.yaml"
    record = source / "agents" / "demo__worker" / "config.yaml"
    worker = home / "profiles" / "demo__worker"
    with bind_profile_scope(worker, hydrate_secrets=False):
        save_env_value("UNRELATED_OMA_REGRESSION", "leave-alone")
    atomic_config_write(campaign, {**read_mapping(campaign), "model": {
        "provider": "custom", "default": "test-model", "api_key": "${TEAM_SYNC_TOKEN}",
    }})
    atomic_config_write(record, {**read_mapping(record), "mcp_servers": {"worker": {
        "url": "https://worker.invalid/mcp", "headers": {"Authorization": "Bearer ${env:WORKER_SYNC_TOKEN}"},
        "client_cert": ["${HOME}/test-cert", "test-key"],
    }}})
    team_value = 'dummy # with "quotes" and a \\backslash'
    worker_value = "dummy-worker-fixture"
    def run(*args, **values):
        return run_campaign_script("sync-campaign", *args, UNLISTED_OMA_REGRESSION="do-not-copy", **values)

    # Provisioning can seed an empty .env; sync without supplied values must not touch it.
    profiles = [home / "profiles" / role for role in DEMO_AGENTS]
    env_paths = [profile / ".env" for profile in profiles]
    original = [path.read_bytes() if path.exists() else None for path in env_paths]
    first = run("demo", TEAM_SYNC_TOKEN="ambient-same-name", WORKER_SYNC_TOKEN="ambient-worker")
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["updated_agents"] == list(DEMO_AGENTS)
    assert [path.read_bytes() if path.exists() else None for path in env_paths] == original
    assert "${env:WORKER_SYNC_TOKEN}" in (worker / "config.yaml").read_text(encoding="utf-8-sig")

    result = run("demo", "--env-stdin", stdin=json.dumps({"TEAM_SYNC_TOKEN": team_value, "WORKER_SYNC_TOKEN": worker_value}))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["updated_agents"] == list(DEMO_AGENTS)
    assert worker_value not in result.stdout + result.stderr
    for profile in profiles:
        env = load_env_file(profile / ".env")
        assert env["TEAM_SYNC_TOKEN"] == team_value
        assert not {"UNLISTED_OMA_REGRESSION", "HOME"} & env.keys()
        assert env.get("WORKER_SYNC_TOKEN") == worker_value
        assert "${TEAM_SYNC_TOKEN}" in (profile / "config.yaml").read_text(encoding="utf-8-sig")
        with bind_profile_scope(profile, hydrate_secrets=False):
            assert load_config()["model"]["api_key"] == team_value
    assert load_env_file(worker / ".env")["UNRELATED_OMA_REGRESSION"] == "leave-alone"
    assert worker_value not in record.read_text(encoding="utf-8-sig")

    again = run("demo", WORKER_SYNC_TOKEN="")
    assert again.returncode == 0, again.stderr
    assert json.loads(again.stdout)["updated_agents"] == []
    assert load_env_file(worker / ".env")["WORKER_SYNC_TOKEN"] == worker_value
    assert run("demo", "--secret", "TEAM_SYNC_TOKEN").returncode == 2


def test_sync_campaign_saves_explicit_env_without_model_or_mcp_reference(bundle, capsys, monkeypatch):
    from agent.secret_scope import load_env_file
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    monkeypatch.setenv("OMA_AMBIENT_TOKEN", "never-copy")
    expected = {"EXTRA_TOOL_TOKEN": "fixture-explicit-value"}
    roles = DEMO_AGENTS
    assert sync_campaign(home, "demo", env=expected)["updated_agents"] == list(roles)
    assert sync_campaign(home, "demo", env={})["updated_agents"] == []
    for role in roles:
        assert load_env_file(home / "profiles" / role / ".env") == expected
    assert not (home / ".env").exists()
    for directory in [source / "campaigns" / "demo", *(source / "agents" / role for role in roles)]:
        path = directory / "config.yaml"
        saved = read_mapping(path)
        assert saved["all-keys"] == saved["available-keys"] == ["EXTRA_TOOL_TOKEN"]
        assert expected["EXTRA_TOOL_TOKEN"] not in path.read_text()


def test_sync_records_available_keys_in_campaign_and_agent_configs(bundle, capsys, run_campaign_script):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import atomic_config_replace, atomic_config_write, remove_env_value, save_env_value
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    campaign = source / "campaigns" / "demo" / "config.yaml"
    worker_record = source / "agents" / "demo__worker" / "config.yaml"
    atomic_config_write(campaign, {**read_mapping(campaign), "model": {
        "default": "fixture", "api_key": "${TEAM_STATUS_TOKEN}",
    }})
    atomic_config_write(worker_record, {**read_mapping(worker_record), "mcp_servers": {
        "worker": {"url": "https://docs.invalid/mcp", "args": ["${HOME}/cert", "${env:WORKER_STATUS_TOKEN}"]},
        "disabled": {"enabled": False, "headers": {"Authorization": "${DISABLED_STATUS_TOKEN}"}},
    }})
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    owner_record = source / "agents" / "demo__orchestrator" / "config.yaml"
    profile = home / "profiles" / "demo__orchestrator"
    worker = home / "profiles" / "demo__worker"
    with bind_profile_scope(profile, hydrate_secrets=False):
        save_env_value("TEAM_STATUS_TOKEN", "test-stored-value")
        save_env_value("UNRELATED_STATUS_TOKEN", "test-unrelated-value")
    with bind_profile_scope(worker, hydrate_secrets=False):
        for name in ("WORKER_STATUS_TOKEN", "DISABLED_STATUS_TOKEN"):
            save_env_value(name, "test-stored-value")

    owner_names = {"TEAM_STATUS_TOKEN", "UNRELATED_STATUS_TOKEN"}
    worker_names = {"TEAM_STATUS_TOKEN", "WORKER_STATUS_TOKEN", "DISABLED_STATUS_TOKEN"}
    extras = (owner_names | worker_names) - {"TEAM_STATUS_TOKEN"}

    def check(campaign_keys, owner_keys, worker_keys, **env):
        result = run_campaign_script("sync-campaign", "demo", "--env-stdin", stdin=json.dumps(env))
        assert result.returncode == 0, result.stderr
        assert "test-stored-value" not in result.stdout + result.stderr
        assert read_mapping(campaign)["all-keys"] == sorted(owner_names | worker_names)
        assert read_mapping(owner_record)["all-keys"] == sorted(owner_names)
        assert read_mapping(worker_record)["all-keys"] == sorted(worker_names)
        for path, keys in zip((campaign, owner_record, worker_record), (campaign_keys, owner_keys, worker_keys)):
            record = read_mapping(path)
            assert record["available-keys"] == sorted(keys)
            assert "configured-keys" not in record
            assert "test-stored-value" not in path.read_text(encoding="utf-8-sig")
        for directory in (profile, worker):
            assert not {"all-keys", "available-keys"} & read_mapping(directory / "config.yaml").keys()

    check(extras, owner_names, worker_names - {"TEAM_STATUS_TOKEN"})
    check(owner_names | worker_names, owner_names, worker_names, TEAM_STATUS_TOKEN="test-stored-value")

    # An omitted reference still counts while its value is saved in the profile.
    with bind_profile_scope(profile, hydrate_secrets=False):
        remove_env_value("TEAM_STATUS_TOKEN")
    config = read_mapping(worker_record)
    config.pop("mcp_servers")
    atomic_config_replace(worker_record, config)
    check(extras, owner_names - {"TEAM_STATUS_TOKEN"}, worker_names)

    # A model override introduces a campaign-visible key even before the value is supplied.
    config = read_mapping(worker_record)
    atomic_config_write(worker_record, {**config, "model": {
        "default": "other-fixture", "api_key": "${PRIVATE_MODEL_STATUS_TOKEN}",
    }})
    result = run_campaign_script("sync-campaign", "demo")
    assert result.returncode == 0, result.stderr
    new_name = {"PRIVATE_MODEL_STATUS_TOKEN"}
    assert read_mapping(campaign)["all-keys"] == sorted(owner_names | worker_names | new_name)
    assert read_mapping(campaign)["available-keys"] == sorted(extras)
    result = run_campaign_script("sync-campaign", "demo", "--env-stdin",
                                 stdin=json.dumps({"PRIVATE_MODEL_STATUS_TOKEN": "test-stored-value"}))
    assert result.returncode == 0, result.stderr
    assert read_mapping(campaign)["available-keys"] == sorted(extras | new_name)
    assert read_mapping(worker_record)["all-keys"] == sorted(worker_names | new_name)
    assert read_mapping(worker_record)["available-keys"] == sorted(worker_names | new_name)


@pytest.mark.parametrize(("explicit_model", "has_saved_key"), [(False, True), (True, True), (False, False)])
def test_install_snapshots_saved_defaults_without_overriding_role_settings(
    bundle, capsys, monkeypatch, explicit_model, has_saved_key,
):
    from agent.secret_scope import load_env_file
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    campaign = source / "campaigns/demo/config.yaml"
    owner = source / "agents/demo__orchestrator/config.yaml"
    worker = source / "agents/demo__worker/config.yaml"
    base_model = {"default": "root-fixture", "provider": "openrouter"}
    atomic_config_write(home / "config.yaml", {"model": base_model, "agent": {"reasoning_effort": "high"}})
    key = "sk-or-v1-fixture-model-key"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-other-process-key")
    (home / ".env").write_text(
        f"OPENROUTER_API_KEY={key if has_saved_key else ''}\nUNRELATED_API_KEY=unrelated-fixture\n"
        "CAMOFOX_URL=https://browser.invalid\nCAMOFOX_API_KEY=fixture-browser-key\n",
        encoding="utf-8",
    )
    if explicit_model:
        atomic_config_write(campaign, {**read_mapping(campaign), "model": "explicit-team-model"})
    atomic_config_write(owner, {**read_mapping(owner),
                                "agent": {"enabled_toolsets": ["file", "skills", "memory", "kanban", "camofox"]}})
    worker_config = read_mapping(worker)
    atomic_config_write(worker, {**worker_config, "model": "explicit-worker-model",
                                 "agent": {**worker_config["agent"], "reasoning_effort": "low"},
                                 "tools": {"tool_search": {"eager_toolsets": []}}})

    assert main(["install", "demo"]) == 0
    result = capsys.readouterr()
    assert key not in result.out + result.err
    expected = "explicit-team-model" if explicit_model else {**base_model, "api_key": "${OPENROUTER_API_KEY}"}
    saved_campaign = read_mapping(campaign)
    if explicit_model:
        assert saved_campaign["model"] == expected
    else:
        assert "model" not in saved_campaign
    assert "reasoning_effort" not in saved_campaign.get("agent", {})
    assert "model" not in read_mapping(owner)
    assert read_mapping(worker)["model"] == "explicit-worker-model"
    assert "effective" not in read_mapping(owner)
    assert "effective" not in read_mapping(worker)
    for path in (owner, home / "profiles/demo__orchestrator/config.yaml"):
        data = read_mapping(path)
        assert data["agent"].get("reasoning_effort") == (None if path == owner else "high")
        assert data["tools"]["tool_search"] == {"enabled": "on", "eager_toolsets": ["file", "skills", "memory"]}
        assert key not in path.read_text(encoding="utf-8")
    for path in (worker, home / "profiles/demo__worker/config.yaml"):
        data = read_mapping(path)
        assert data["agent"]["reasoning_effort"] == "low"
        assert data["tools"]["tool_search"]["eager_toolsets"] == []
    assert read_mapping(home / "profiles/demo__orchestrator/config.yaml")["model"] == expected
    env = load_env_file(home / "profiles/demo__orchestrator/.env")
    assert env["CAMOFOX_API_KEY"] == "fixture-browser-key"
    assert env.get("OPENROUTER_API_KEY") == (key if has_saved_key and not explicit_model else None)
    assert "UNRELATED_API_KEY" not in env
    assert load_env_file(home / "profiles/demo__worker/.env") == {}
    if not explicit_model:
        for path in (campaign, owner):
            data = read_mapping(path)
            assert data["all-keys"] == ["OPENROUTER_API_KEY"]
            assert data["available-keys"] == (["OPENROUTER_API_KEY"] if has_saved_key else [])


def test_saved_agent_model_persists_and_can_be_edited_independently_of_campaign(bundle, capsys):
    from hermes_cli.config import atomic_config_replace, atomic_config_write, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    campaign = source / "campaigns" / "demo" / "config.yaml"
    defaults = {"model": "team-model", "mcp_servers": {"docs": {"url": "https://docs.invalid/mcp"}}}
    atomic_config_write(campaign, {**read_mapping(campaign), **defaults})
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    native = home / "profiles" / "demo__worker" / "config.yaml"
    agent = source / "agents" / "demo__worker" / "config.yaml"
    assert "model" not in read_mapping(agent)
    assert read_mapping(agent)["effective"] == {"mcp_servers": defaults["mcp_servers"]}
    assert {key: read_user_config_raw(native)[key] for key in defaults} == defaults

    current = read_mapping(campaign)
    atomic_config_replace(campaign, {**{key: value for key, value in current.items() if key not in defaults},
                                     "model": "new-campaign-default"})
    atomic_config_write(agent, {**read_mapping(agent), "model": "edited-worker-model"})
    assert sync(["demo"]) == 0
    assert json.loads(capsys.readouterr().out)["updated_agents"] == list(DEMO_AGENTS)
    assert read_user_config_raw(native)["model"] == "edited-worker-model"
    owner_native = home / "profiles" / "demo__orchestrator" / "config.yaml"
    assert read_user_config_raw(owner_native)["model"] == "new-campaign-default"
    assert "mcp_servers" not in read_user_config_raw(native)
    assert "effective" not in read_mapping(agent)


def test_explicit_sync_refuses_legacy_effective_model_without_changes(bundle, capsys):
    from hermes_cli.config import atomic_config_replace, atomic_config_write, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    campaign = source / "campaigns/demo/config.yaml"
    owner = source / "agents/demo__orchestrator/config.yaml"
    worker = source / "agents/demo__worker/config.yaml"
    atomic_config_write(campaign, {**read_mapping(campaign), "model": "new-campaign-default"})
    atomic_config_replace(owner, {**read_mapping(owner), "effective": {"model": "legacy-owner-model"}})
    atomic_config_replace(worker, {**read_mapping(worker), "model": "authored-worker-model",
                                   "effective": {"model": "stale-worker-model"}})

    assert sync(["demo"]) == 1
    assert "invalid OMA agent effective" in capsys.readouterr().err
    assert read_mapping(owner)["effective"]["model"] == "legacy-owner-model"
    assert "model" not in read_user_config_raw(home / "profiles" / owner.parent.name / "config.yaml")


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
    ("agents/demo__worker/config.yaml", "jobs: []", "jobs: [{id: review, schedule: '1d'}]", "invalid OMA agent jobs.0"),
    ("agents/demo__worker/config.yaml", "enabled_toolsets: [file, kanban]", "enabled_toolsets: null", "explicit list"),
    ("agents/demo__orchestrator/config.yaml", "enabled_toolsets: [file, kanban]", "enabled_toolsets: [file]", "include kanban"),
])
def test_invalid_roster_does_not_publish(bundle, capsys, file, before, after, error):
    home, source, main = bundle
    path = source / file
    path.write_text(path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
    assert main(["install", "demo"]) == 1
    assert error in capsys.readouterr().err
    assert not (home / "profiles").exists()
    assert not (source / "installations" / "demo").exists()


def test_sync_rejects_malformed_campaign_before_writing_profiles(bundle, capsys):
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import main as sync

    home, source, main = bundle
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    campaign = source / "campaigns" / "demo" / "config.yaml"
    profile = home / "profiles" / "demo__orchestrator" / "config.yaml"
    initial = profile.read_bytes()
    atomic_config_write(campaign, {**read_mapping(campaign), "goals": "wrong-shape", "model": "different"})

    assert sync(["demo"]) == 1
    assert "invalid OMA campaign goals" in capsys.readouterr().err
    assert profile.read_bytes() == initial


@pytest.mark.parametrize("saved", [(), ("CAMOFOX_URL",), ("CAMOFOX_API_KEY",), ("CAMOFOX_URL", "CAMOFOX_API_KEY")])
def test_new_campaign_camofox_requires_complete_saved_pair(bundle, capsys, monkeypatch, saved):
    from agent.secret_scope import load_env_file
    from hermes_cli import kanban_db
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    record = source / "agents/demo__orchestrator/config.yaml"
    atomic_config_replace(record, {**read_mapping(record), "agent": {"enabled_toolsets": ["file", "kanban", "camofox"]}})
    pair = {"CAMOFOX_URL": "https://browser.example.invalid", "CAMOFOX_API_KEY": "fixture-browser-token"}
    if saved:
        lines = [f"{key}='{pair[key] if key in saved else '   '}'" for key in pair]
        (home / ".env").write_text("\n".join([*lines, "UNRELATED_API_KEY=fixture-unrelated-token", ""]), encoding="utf-8")
    for key in pair:
        monkeypatch.setenv(key, "process-env-must-not-be-used")

    assert main(["install", "demo"]) == 0
    output = capsys.readouterr()
    assert all(value not in output.out + output.err for value in pair.values())
    assert kanban_db.board_exists("campaign-demo")
    orchestrator = home / "profiles/demo__orchestrator"
    worker = home / "profiles/demo__worker"
    configured = set(saved) == set(pair)
    for path in (record, orchestrator / "config.yaml"):
        assert ("camofox" in read_mapping(path)["agent"]["enabled_toolsets"]) == configured
        assert pair["CAMOFOX_API_KEY"] not in path.read_text(encoding="utf-8")
    assert load_env_file(orchestrator / ".env") == (pair if configured else {})
    assert read_mapping(worker / "config.yaml")["agent"]["enabled_toolsets"] == ["file", "kanban"]
    assert load_env_file(worker / ".env") == {}
    (home / ".env").write_text("", encoding="utf-8")
    assert main(["install", "demo"]) == 0
    assert load_env_file(orchestrator / ".env") == (pair if configured else {})


def test_new_campaign_camofox_respects_opt_out_and_rejects_legacy_selection(bundle, capsys):
    from agent.secret_scope import load_env_file
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.source import read_mapping

    home, source, main = bundle
    records = source / "agents"
    orchestrator = records / "demo__orchestrator/config.yaml"
    spec = read_mapping(orchestrator)
    del spec["agent"]
    atomic_config_replace(orchestrator, {**spec, "platform_toolsets": {"cli": ["file", "camofox"]}})
    assert main(["install", "demo"]) == 1
    assert "explicit list" in capsys.readouterr().err
    assert not (home / "profiles/demo__orchestrator").exists()
    atomic_config_replace(orchestrator, {**spec, "agent": {"enabled_toolsets": ["file", "kanban", "camofox"]}})
    worker = records / "demo__worker/config.yaml"
    atomic_config_replace(worker, {**read_mapping(worker), "agent": {
        "enabled_toolsets": [], "disabled_toolsets": ["camofox"],
    }})
    pair = {"CAMOFOX_URL": "https://browser.example.invalid", "CAMOFOX_API_KEY": "fixture-browser-token"}
    (home / ".env").write_text("".join(f"{key}={value}\n" for key, value in pair.items()), encoding="utf-8")

    assert main(["install", "demo"]) == 0
    profiles = home / "profiles"
    assert load_env_file(profiles / "demo__orchestrator/.env") == pair
    native = read_mapping(profiles / "demo__orchestrator/config.yaml")
    assert native["agent"]["enabled_toolsets"] == ["file", "kanban", "camofox"]
    assert load_env_file(profiles / "demo__worker/.env") == {}
    assert read_mapping(profiles / "demo__worker/config.yaml")["agent"] == {
        "enabled_toolsets": [], "disabled_toolsets": ["camofox"],
    }


def test_generated_cron_belongs_to_the_verified_owner(bundle, capsys):
    from argparse import ArgumentParser

    from agent.runtime_scope import bind_profile_scope
    from cron.jobs import list_jobs
    from hermes_cli.cron import cron_create
    from hermes_cli.oma_campaigns.source import read_mapping
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
    from hermes_cli.oma_campaigns.source import read_mapping

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
    from hermes_cli.oma_campaigns.source import read_mapping

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
    from hermes_cli.oma_campaigns import install as provisioning
    from hermes_cli.oma_campaigns.source import read_mapping

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
