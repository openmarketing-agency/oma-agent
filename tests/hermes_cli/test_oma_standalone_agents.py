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
    assert set(saved["oma_skills"]) == refs
    assert read_mapping(ops / "config.yaml")["oma_skills"] == ["omactl"]
    assert "model" not in read_mapping(ops / "config.yaml") and "mcp_servers" not in saved
    assert (default / "SOUL.md").read_bytes() == b"Custom default persona"
    assert (ops / "SOUL.md").read_bytes() == b"Custom ops persona"
    assert {row["name"] for row in json.loads(skills_tool.skills_search("oma"))["skills"]} >= refs
    assert not json.loads(skills_tool.skill_view("oma/omactl", preprocess=False))["success"]
    with bind_profile_scope(maintenance, hydrate_secrets=False):
        assert not json.loads(skills_tool.skill_view("oma/oma-campaigns", preprocess=False))["success"]
        assert json.loads(skills_tool.skill_view("oma/omactl", preprocess=False))["success"]

    atomic_config_replace(default / "config.yaml", {**saved, "model": "operator-edit"})
    (default / "SOUL.md").write_text("Operator edit", encoding="utf-8")
    seed_standalone_agents(tmp_path, install_dir=source)
    assert read_mapping(default / "config.yaml")["model"] == "operator-edit"
    assert (default / "SOUL.md").read_bytes() == b"Operator edit"
    assert read_user_config_raw(tmp_path / "config.yaml")["model"] == "openrouter/test-model"


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
                                   "agent": {"enabled_toolsets": [], "disabled_toolsets": ["terminal"], "max_turns": 99},
                                   "tools": {"tool_search": {"enabled": "off", "eager_toolsets": None}}})
    (source / "SOUL.md").write_text("Do not apply me", encoding="utf-8")
    with pytest.raises(StaleRecord):
        sync_standalone_agent(tmp_path, role, revision=old_revision)
    assert read_user_config_raw(native / "config.yaml")["model"] != settings["model"]

    assert sync_standalone_agent(tmp_path, role)["updated"] == [
        "model", "mcp_servers", "agent.enabled_toolsets", "agent.disabled_toolsets",
        "tools.tool_search.eager_toolsets", "tools.tool_search.enabled", "oma_skills",
    ]
    applied = read_user_config_raw(native / "config.yaml")
    assert {key: applied[key] for key in settings} == settings
    assert applied["agent"] == {"enabled_toolsets": [], "disabled_toolsets": ["terminal"]}
    assert applied["tools"]["tool_search"] == {"enabled": "off", "eager_toolsets": None}
    assert (native / "SOUL.md").read_bytes() != b"Do not apply me"
    assert (untouched / "config.yaml").read_bytes() == untouched_bytes
    assert sync_standalone_agent(tmp_path, role)["updated"] == []


def test_sync_updates_and_prunes_managed_packages_without_touching_unrelated_skills(tmp_path, monkeypatch):
    import json

    from hermes_cli.oma_campaigns.standalone import seed_standalone_agents, sync_standalone_agent
    from tools import skills_tool

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    source = Path(__file__).resolve().parents[2]
    seed_standalone_agents(tmp_path, install_dir=source)
    record = tmp_path / "oma" / "agents" / "default" / "config.yaml"
    config = read_mapping(record)
    bundle = tmp_path / "oma-bundle" / "skills" / "oma" / "oma-brand"
    local = tmp_path / "skills" / "personal"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text("---\nname: personal\n---\nKeep me", encoding="utf-8")
    atomic_config_replace(record, {**config, "oma_skills": ["oma-brand"]})
    assert sync_standalone_agent(tmp_path, "default")["updated"] == ["oma_skills"]
    installed = tmp_path / "skills" / "oma-brand"
    assert (installed / "SKILL.md").read_bytes() == (bundle / "SKILL.md").read_bytes()
    (bundle / "extra.md").write_text("Edited source package", encoding="utf-8")
    sync_standalone_agent(tmp_path, "default")
    assert (installed / "extra.md").read_text(encoding="utf-8") == "Edited source package"

    atomic_config_replace(record, {**config, "model": "don't-apply", "oma_skills": ["omactl", "unavailable"]})
    with pytest.raises(ValueError, match="eligible OMA package"):
        sync_standalone_agent(tmp_path, "default")
    assert installed.is_dir() and read_mapping(tmp_path / "config.yaml")["model"] == "root-model"

    atomic_config_replace(record, {**config, "oma_skills": []})
    assert sync_standalone_agent(tmp_path, "default")["updated"] == ["oma_skills"]
    assert not installed.exists() and bundle.exists() and local.exists()
    assert not json.loads(skills_tool.skill_view("oma-brand", preprocess=False))["success"]
    atomic_config_replace(record, {**config, "oma_skills": ["oma-brand"]})
    sync_standalone_agent(tmp_path, "default")
    assert json.loads(skills_tool.skill_view("oma-brand", preprocess=False))["skill_dir"] == str(installed)


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


def test_docker_seed_command_adopts_missing_maintenance_and_first_sync_can_remove_omactl(tmp_path, monkeypatch):
    from hermes_cli.oma_campaigns.standalone import main, sync_standalone_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _profile(tmp_path, "root-model", "Default persona")
    source = Path(__file__).resolve().parents[2]
    assert main(["seed", "--install-dir", str(source), "--ensure-maintenance"]) == 0
    installed = tmp_path / "profiles" / "maintenance" / "skills" / "omactl" / "SKILL.md"
    assert installed.is_file()
    record = tmp_path / "oma" / "agents" / "maintenance" / "config.yaml"
    atomic_config_replace(record, {**read_mapping(record), "oma_skills": []})
    assert sync_standalone_agent(tmp_path, "maintenance")["updated"] == ["oma_skills"]
    assert not installed.exists()
    assert main(["seed", "--install-dir", str(source), "--ensure-maintenance"]) == 0
    assert not installed.exists() and read_mapping(record)["oma_skills"] == []
