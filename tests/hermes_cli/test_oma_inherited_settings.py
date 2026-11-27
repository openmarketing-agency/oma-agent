"""Exercise workspace defaults through native OMA campaign and agent sync."""

from tests import oma_campaign_fixtures

bundle = oma_campaign_fixtures.bundle


def test_campaign_sync_resolves_mcp_by_name_from_default_campaign_and_agent(bundle, capsys):
    from hermes_cli.config import atomic_config_replace, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    campaign = source / "campaigns/demo/config.yaml"
    worker = source / "agents/demo__worker/config.yaml"
    headers = {"Authorization": "Bearer ${ROOT_MCP_KEY}"}
    root = {"shared": {"url": "https://root.invalid/mcp", "headers": headers},
            "docs": {"url": "https://root-docs.invalid/mcp", "headers": headers}}
    team = {"docs": {"url": "https://team-docs.invalid/mcp"}}
    role = {"docs": {"enabled": False}}
    atomic_config_replace(campaign, {**read_mapping(campaign), "mcp_servers": team})
    atomic_config_replace(worker, {**read_mapping(worker), "mcp_servers": role})
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    atomic_config_replace(home / "config.yaml", {"mcp_servers": root})
    (home / ".env").write_text("ROOT_MCP_KEY=root-only-fixture\n", encoding="utf-8")

    sync_campaign(home, "demo")

    for member, override in [("demo__orchestrator", team), ("demo__worker", role)]:
        expected = {**root, **override}
        native = read_user_config_raw(home / "profiles" / member / "config.yaml")
        authored = read_mapping(source / "agents" / member / "config.yaml")
        assert native["mcp_servers"] == expected
        assert authored["effective"]["mcp_servers"] == expected
        assert "mcp-shared" in native["agent"]["enabled_toolsets"]
        assert ("mcp-docs" in native["agent"]["enabled_toolsets"]) == (member != "demo__worker")
        assert "ROOT_MCP_KEY" in authored["all-keys"]
        assert "ROOT_MCP_KEY" not in authored["available-keys"]
    assert read_mapping(campaign)["mcp_servers"] == team
    assert read_mapping(worker)["mcp_servers"] == role


def test_default_agent_sync_propagates_only_inherited_model_and_mcp(bundle, capsys):
    from hermes_cli.config import atomic_config_replace, read_user_config_raw
    from hermes_cli.oma_campaigns.source import read_mapping
    from hermes_cli.oma_campaigns.standalone import sync_standalone_agent
    from hermes_cli.oma_campaigns.sync import sync_campaign

    home, source, main = bundle
    campaign = source / "campaigns/demo/config.yaml"
    worker = source / "agents/demo__worker/config.yaml"
    owner = source / "agents/demo__orchestrator/config.yaml"
    root_record = source / "agents/default/config.yaml"
    root_record.parent.mkdir()
    new = {"shared": {"url": "https://new.invalid/mcp"}, "docs": {"url": "https://root-docs.invalid/mcp"}}
    team = {"docs": {"url": "https://team-docs.invalid/mcp"}}
    role = {"shared": {"enabled": False}}
    atomic_config_replace(home / "config.yaml", {"model": "old-model", "mcp_servers": {
        "shared": {"url": "https://old.invalid/mcp"}, "removed": {"url": "https://old.invalid/removed"},
    }})
    atomic_config_replace(campaign, {**read_mapping(campaign), "mcp_servers": team})
    atomic_config_replace(worker, {**read_mapping(worker), "model": "worker-model", "mcp_servers": role})
    assert main(["install", "demo"]) == 0
    capsys.readouterr()
    owner_profile = home / "profiles/demo__orchestrator"
    worker_profile = home / "profiles/demo__worker"
    persona = (owner_profile / "SOUL.md").read_bytes()
    assert not (owner_profile / "cron/jobs.json").exists()
    (owner.parent / "SOUL.md").write_text("Pending persona edit\n", encoding="utf-8")
    atomic_config_replace(owner, {**read_mapping(owner), "jobs": [
        {"id": "pending", "schedule": "1d", "prompt": "Pending schedule edit"},
    ]})
    atomic_config_replace(root_record, {"id": "default", "name": "Default", "description": "Default agent",
                                       "campaign_id": None, "model": "new-model", "mcp_servers": new})
    (source / "campaigns/draft").mkdir()
    draft = source / "campaigns/draft/config.yaml"
    draft.write_text("id: draft\n", encoding="utf-8")

    result = sync_standalone_agent(home, "default", env={"ROOT_ONLY_FIXTURE": "default-only-fixture"})

    assert result["updated_campaigns"] == ["demo"]
    owner_native = read_user_config_raw(owner_profile / "config.yaml")
    assert owner_native["model"] == "new-model"
    assert owner_native["mcp_servers"] == {**new, **team}
    assert "mcp-removed" not in owner_native["agent"]["enabled_toolsets"]
    worker_native = read_user_config_raw(worker_profile / "config.yaml")
    assert worker_native["model"] == "worker-model"
    assert worker_native["mcp_servers"] == {**new, **team, **role}
    analyst = read_user_config_raw(home / "profiles/demo__analyst/config.yaml")
    assert analyst["model"] == "new-model"
    assert analyst["mcp_servers"] == {**new, **team}
    assert (owner_profile / "SOUL.md").read_bytes() == persona
    assert not (owner_profile / "cron/jobs.json").exists()
    assert read_mapping(campaign)["lifecycle_state"] == "paused"
    assert "model" not in read_mapping(campaign)
    assert "model" not in read_mapping(owner)
    assert "ROOT_ONLY_FIXTURE" not in read_mapping(owner)["all-keys"]
    assert draft.read_text(encoding="utf-8") == "id: draft\n"
    assert sync_standalone_agent(home, "default")["updated_campaigns"] == []

    atomic_config_replace(campaign, {**read_mapping(campaign), "model": "campaign-model"})
    sync_campaign(home, "demo")
    atomic_config_replace(root_record, {**read_mapping(root_record), "model": "third-root-model"})
    sync_standalone_agent(home, "default")
    assert read_user_config_raw(owner_profile / "config.yaml")["model"] == "campaign-model"
    assert read_user_config_raw(worker_profile / "config.yaml")["model"] == "worker-model"
