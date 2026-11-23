"""Standalone OMA records adopt existing profiles without taking over their runtime."""

from hashlib import sha256
from pathlib import Path

import pytest

from hermes_cli.config import atomic_config_replace, read_user_config_raw
from hermes_cli.oma_campaigns.source import read_mapping


def _profile(path: Path, model, soul: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    atomic_config_replace(path / "config.yaml", {
        "model": model, "agent": {"enabled_toolsets": ["file"]},
        "mcp_servers": {"legacy": {"headers": {"Authorization": "fixture-private-value"}}},
    })
    (path / "SOUL.md").write_text(soul, encoding="utf-8")
    return path


def test_startup_adopts_existing_profiles_and_bundles_default_only_skills(tmp_path, monkeypatch):
    from agent.runtime_scope import bind_profile_scope
    from agent.skill_selection import OMA_DEFAULT_ONLY_SKILLS, OMA_RETIRED_SKILLS
    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents
    from tools import skills_tool
    import json

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "openrouter/test-model", "Custom default persona")
    maintenance = _profile(tmp_path / "profiles" / "maintenance", {"api_key": "fixture-private-value"}, "Custom ops persona")
    source = Path(__file__).resolve().parents[2]
    seed_standalone_agents(tmp_path, install_dir=source)
    records = tmp_path / "oma" / "agents"
    default, ops = (records / role for role in ("default", "maintenance"))
    refs = OMA_DEFAULT_ONLY_SKILLS - OMA_RETIRED_SKILLS
    saved = read_mapping(default / "config.yaml")
    assert saved["model"] == "openrouter/test-model" and saved["campaign_id"] is None
    assert "oma_skills" not in saved
    assert "oma_skills" not in read_mapping(ops / "config.yaml")
    assert "model" not in read_mapping(ops / "config.yaml") and "mcp_servers" not in saved
    assert (default / "SOUL.md").read_bytes() == b"Custom default persona"
    assert (ops / "SOUL.md").read_bytes() == b"Custom ops persona"
    assert {row["name"] for row in json.loads(skills_tool.skills_search("oma"))["skills"]} >= refs
    assert not json.loads(skills_tool.skill_view("oma/omactl", preprocess=False))["success"]
    with bind_profile_scope(maintenance, hydrate_secrets=False):
        assert not json.loads(skills_tool.skill_view("oma/oma-campaigns", preprocess=False))["success"]
        assert json.loads(skills_tool.skill_view("oma/omactl", preprocess=False))["success"]

    atomic_config_replace(default / "config.yaml", {**saved, "model": "operator-edit", "agent": {"enabled_toolsets": []}})
    (default / "SOUL.md").write_text("Operator edit", encoding="utf-8")
    edited = (default / "config.yaml").read_bytes()
    seed_standalone_agents(tmp_path, install_dir=source)
    assert (default / "config.yaml").read_bytes() == edited
    assert (default / "SOUL.md").read_bytes() == b"Operator edit"
    assert read_user_config_raw(tmp_path / "config.yaml")["model"] == "openrouter/test-model"


def test_startup_seeds_each_standalone_record_from_its_native_starter(tmp_path, monkeypatch):
    from hermes_cli.config_home import seed_install_config
    from hermes_cli.oma_campaigns.standalone import main, sync_standalone_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_DISABLE_LAZY_INSTALLS", "1")
    seed_install_config()
    paths = {
        "default": tmp_path / "config.yaml",
        "maintenance": tmp_path / "profiles" / "maintenance" / "config.yaml",
    }
    before = {role: path.read_bytes() for role, path in paths.items()}

    assert main(["seed", "--ensure-maintenance"]) == 0

    for role, path in paths.items():
        native = read_user_config_raw(path)
        saved = read_mapping(tmp_path / "oma" / "agents" / role / "config.yaml")
        keys = ["agent", "tools", "skills", "approvals", "_config_version"]
        if role == "default":
            keys.append("kanban")
        else:
            assert "kanban" not in saved
        assert {key: saved[key] for key in keys} == {key: native[key] for key in keys}
        assert "_default_plugins_installed" not in saved
        assert sync_standalone_agent(tmp_path, role)["updated"] == []
        assert path.read_bytes() == before[role]


def test_startup_adopts_saved_plugin_state_without_copying_other_native_settings(tmp_path, monkeypatch):
    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    plugins = {"enabled": ["camofox"], "disabled": []}
    atomic_config_replace(tmp_path / "config.yaml", {
        "agent": {"enabled_toolsets": [], "max_turns": 99},
        "tools": {"tool_search": {"enabled": "off", "eager_toolsets": None, "listing": "off"}},
        "skills": {"disabled": [], "extra_dirs": ["/private/local-skills"]},
        "plugins": {**plugins, "settings": {"example": {"api_key": "fixture-private-value"}}},
        "_default_plugins_installed": ["camofox"],
    })
    assert seed_standalone_agents(tmp_path)["seeded"] == ["default"]
    saved = read_mapping(tmp_path / "oma" / "agents" / "default" / "config.yaml")
    assert saved["plugins"] == plugins
    assert saved["_default_plugins_installed"] == ["camofox"]
    assert saved["agent"] == {"enabled_toolsets": []}
    assert saved["skills"] == {"disabled": []}
    assert saved["tools"]["tool_search"]["eager_toolsets"] is None


@pytest.mark.parametrize("role", ["default", "maintenance"])
def test_sync_applies_only_saved_settings_to_the_owning_profile(tmp_path, monkeypatch, role):
    from hermes_cli.oma_campaigns.standalone import StaleRecord, seed_standalone_agents, sync_standalone_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    root = _profile(tmp_path, "root-model", "Default persona")
    ops = _profile(tmp_path / "profiles" / "maintenance", "ops-model", "Maintenance persona")
    native, untouched = (root, ops) if role == "default" else (ops, root)
    untouched_bytes = (untouched / "config.yaml").read_bytes()
    seed_standalone_agents(tmp_path, install_dir=Path(__file__).resolve().parents[2])
    source = tmp_path / "oma" / "agents" / role
    record = source / "config.yaml"
    old_revision = sha256(record.read_bytes()).hexdigest()
    settings = {"model": {"default": "new-model", "api_key": "${MODEL_KEY}"},
                "mcp_servers": {"example": {"url": "https://example.invalid/mcp"}}}
    atomic_config_replace(record, {**read_mapping(record), **settings,
                                   "agent": {"enabled_toolsets": [], "disabled_toolsets": ["terminal"],
                                             "reasoning_effort": "high", "max_turns": 99},
                                   "tools": {"tool_search": {"enabled": "off", "eager_toolsets": None}}})
    (source / "SOUL.md").write_text("Updated persona.\n", encoding="utf-8")
    with pytest.raises(StaleRecord):
        sync_standalone_agent(tmp_path, role, revision=old_revision)
    assert read_user_config_raw(native / "config.yaml")["model"] != settings["model"]

    assert set(sync_standalone_agent(tmp_path, role)["updated"]) == {
        "model", "mcp_servers", "agent.enabled_toolsets", "agent.disabled_toolsets",
        "tools.tool_search.eager_toolsets", "tools.tool_search.enabled", "agent.reasoning_effort", "SOUL.md",
    }
    applied = read_user_config_raw(native / "config.yaml")
    assert {key: applied[key] for key in settings} == settings
    assert applied["agent"] == {"enabled_toolsets": [], "disabled_toolsets": ["terminal"], "reasoning_effort": "high"}
    assert applied["tools"]["tool_search"] == {"enabled": "off", "eager_toolsets": None}
    assert (native / "SOUL.md").read_bytes() == b"Updated persona.\n"
    assert (untouched / "config.yaml").read_bytes() == untouched_bytes
    assert sync_standalone_agent(tmp_path, role)["updated"] == []


def test_standalone_sync_saves_explicit_env_and_tracks_names(tmp_path, monkeypatch):
    from agent.secret_scope import load_env_file
    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents, sync_standalone_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    ops = _profile(tmp_path / "profiles" / "maintenance", "ops-model", "Maintenance persona")
    seed_standalone_agents(tmp_path)
    target = tmp_path / "oma" / "agents" / "maintenance" / "config.yaml"
    values = {"EXTRA_TOOL_TOKEN": "fixture-explicit-value"}
    assert sync_standalone_agent(tmp_path, "maintenance", env=values)["updated"] == ["env"]
    assert sync_standalone_agent(tmp_path, "maintenance", env={})["updated"] == []
    assert load_env_file(ops / ".env") == values
    assert not (tmp_path / ".env").exists()
    saved = read_mapping(target)
    assert saved["all-keys"] == saved["available-keys"] == ["EXTRA_TOOL_TOKEN"]
    assert values["EXTRA_TOOL_TOKEN"] not in target.read_text()


def test_sync_updates_and_prunes_managed_packages_without_touching_unrelated_skills(tmp_path, monkeypatch):
    import json
    import shutil

    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents, sync_standalone_agent
    from tools import skills_tool

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    source = Path(__file__).resolve().parents[2]
    seed_standalone_agents(tmp_path, install_dir=source)
    record = tmp_path / "oma" / "agents" / "default" / "config.yaml"
    config = read_mapping(record)
    shared = tmp_path / "oma-bundle" / "skills"
    bundle = shared / "social-media-skills" / "social-strategy"
    starter = tmp_path / "skills" / "oma-brand"
    shutil.copytree(shared / "oma" / "oma-brand", starter)
    starter_bytes = (starter / "SKILL.md").read_bytes()
    local = tmp_path / "skills" / "personal"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text("---\nname: personal\n---\nKeep me", encoding="utf-8")
    atomic_config_replace(record, {**config, "oma_skills": ["social-strategy"]})
    assert sync_standalone_agent(tmp_path, "default")["updated"] == ["oma_skills"]
    installed = tmp_path / "skills" / "social-strategy"
    assert (starter / "SKILL.md").read_bytes() == starter_bytes
    assert (installed / "SKILL.md").read_bytes() == (bundle / "SKILL.md").read_bytes()
    (bundle / "extra.md").write_text("Edited source package", encoding="utf-8")
    sync_standalone_agent(tmp_path, "default")
    assert (installed / "extra.md").read_text(encoding="utf-8") == "Edited source package"

    atomic_config_replace(record, config)
    assert sync_standalone_agent(tmp_path, "default")["updated"] == []
    assert installed.is_dir()

    atomic_config_replace(record, {**config, "model": "don't-apply", "oma_skills": ["omactl", "unavailable"]})
    with pytest.raises(ValueError, match="eligible OMA package"):
        sync_standalone_agent(tmp_path, "default")
    assert installed.is_dir() and read_mapping(tmp_path / "config.yaml")["model"] == "root-model"

    atomic_config_replace(record, {**config, "oma_skills": []})
    assert sync_standalone_agent(tmp_path, "default")["updated"] == ["oma_skills"]
    assert not installed.exists() and bundle.exists() and local.exists()
    assert not json.loads(skills_tool.skill_view("social-strategy", preprocess=False))["success"]
    assert (starter / "SKILL.md").read_bytes() == starter_bytes
    atomic_config_replace(record, {**config, "oma_skills": ["social-strategy"]})
    sync_standalone_agent(tmp_path, "default")
    assert json.loads(skills_tool.skill_view("social-strategy", preprocess=False))["skill_dir"] == str(installed)


def test_legacy_inventory_does_not_own_or_hide_starters(tmp_path, monkeypatch):
    import json

    from agent.skill_selection import OMA_SKILL_INVENTORY
    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents, sync_standalone_agent
    from tools import skills_tool

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    seed_standalone_agents(tmp_path, install_dir=Path(__file__).resolve().parents[2])
    record = tmp_path / "oma" / "agents" / "default" / "config.yaml"
    atomic_config_replace(record, {**read_mapping(record), "oma_skills": []})
    starter = tmp_path / "skills" / "oma-brand" / "SKILL.md"
    starter.parent.mkdir(parents=True)
    starter.write_text("---\nname: oma-brand\n---\nKeep my edits", encoding="utf-8")
    inventory = tmp_path / "skills" / OMA_SKILL_INVENTORY
    inventory.write_text(json.dumps({"owned": {"oma-brand": "oma-brand"}, "pruned": ["oma-agents"]}), encoding="utf-8")

    assert json.loads(skills_tool.skill_view("oma-agents", preprocess=False))["success"]
    assert sync_standalone_agent(tmp_path, "default")["updated"] == ["oma_skills"]
    assert json.loads(inventory.read_text(encoding="utf-8")) == {"owned": {}, "pruned": []}
    assert starter.read_text(encoding="utf-8").endswith("Keep my edits")


def test_sync_rejects_non_standalone_or_missing_profiles(tmp_path, monkeypatch):
    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents, sync_standalone_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    seed_standalone_agents(tmp_path)
    with pytest.raises(FileNotFoundError):
        sync_standalone_agent(tmp_path, "maintenance")
    record = tmp_path / "oma" / "agents" / "default" / "config.yaml"
    atomic_config_replace(record, {**read_mapping(record), "campaign_id": "demo"})
    with pytest.raises(ValueError, match="standalone"):
        sync_standalone_agent(tmp_path, "default")
    with pytest.raises(ValueError):
        sync_standalone_agent(tmp_path, "demo__publisher")


def test_docker_seed_command_keeps_omactl_outside_extra_skill_sync(tmp_path, monkeypatch):
    from hermes_cli.oma_campaigns.standalone import main, sync_standalone_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    source = Path(__file__).resolve().parents[2]
    assert main(["seed", "--install-dir", str(source), "--ensure-maintenance"]) == 0
    installed = tmp_path / "profiles" / "maintenance" / "skills" / "omactl" / "SKILL.md"
    assert installed.is_file()
    record = tmp_path / "oma" / "agents" / "maintenance" / "config.yaml"
    config = read_mapping(record)
    atomic_config_replace(record, {**config, "oma_skills": ["omactl"]})
    assert sync_standalone_agent(tmp_path, "maintenance")["updated"] == []
    atomic_config_replace(record, {**config, "oma_skills": []})
    assert sync_standalone_agent(tmp_path, "maintenance")["updated"] == []
    assert installed.is_file()
    assert main(["seed", "--install-dir", str(source), "--ensure-maintenance"]) == 0
    assert installed.is_file() and read_mapping(record)["oma_skills"] == []
