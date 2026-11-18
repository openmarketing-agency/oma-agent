"""Every writer that seeds or first-configures config.yaml must leave each messaging platform's display defaults
alone (#121230). The gateway loader merges no DEFAULT_CONFIG, so any written global ``display.<key>`` beats every
platform tier (e.g. Telegram/Slack tool_progress ``off`` -> ``all``, QQBot show_reasoning ``False`` -> ``True``)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.gateway.test_display_config import assert_keeps_platform_display_defaults


def _config_edit(tmp_path, monkeypatch, cfg):
    """`hermes config edit` on a home with no config.yaml (seeds via seed_config_file, like `doctor --fix`)."""
    monkeypatch.setenv("EDITOR", "true")
    monkeypatch.setattr(cfg.subprocess, "run", lambda *a, **k: None)
    cfg.edit_config()


def _setup_agent_enter(tmp_path, monkeypatch, cfg):
    """`hermes setup agent` on a fresh home, pressing Enter (the offered default) on every prompt."""
    from hermes_cli import setup

    monkeypatch.setattr(setup, "prompt", lambda question, default=None, *a, **k: default or "")
    monkeypatch.setattr(setup, "prompt_yes_no", lambda *a, **k: False)
    setup.setup_agent_settings(cfg.load_config())


def _apply_default_agent_settings(tmp_path, monkeypatch, cfg):
    """Quick and full first-time setup."""
    from hermes_cli.setup import _apply_default_agent_settings

    _apply_default_agent_settings(cfg.load_config())


def _blank_slate(tmp_path, monkeypatch, cfg):
    from hermes_cli.setup_quick import _blank_slate_minimize_config

    config = cfg.load_config()
    _blank_slate_minimize_config(config)
    cfg.save_config(config)


def _doctor_fix(tmp_path, monkeypatch, cfg):
    """`hermes doctor --fix` on a home with no config.yaml: the real config-file check, fix enabled."""
    from hermes_cli import doctor
    from hermes_cli.doctor_config import _check_config_file

    home = cfg.get_hermes_home()
    monkeypatch.setattr(doctor, "HERMES_HOME", home)
    assert _check_config_file(True).fixed == 1
    if os.name == "posix":
        assert (home / "config.yaml").stat().st_mode & 0o777 == 0o600


SEEDERS = {
    "config-edit": _config_edit,
    "setup-agent-enter": _setup_agent_enter,
    "apply-default-agent-settings": _apply_default_agent_settings,
    "blank-slate": _blank_slate,
    "doctor-fix": _doctor_fix,
}


@pytest.mark.parametrize("seeder", list(SEEDERS))
def test_every_seeder_keeps_every_platform_display_default(tmp_path, monkeypatch, seeder):
    import hermes_cli.config as cfg
    from gateway.run import _load_gateway_config

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    SEEDERS[seeder](tmp_path, monkeypatch, cfg)

    config_path = home / "config.yaml"
    assert config_path.exists()  # the resolution checks below would pass on a missing file
    assert_keeps_platform_display_defaults(_load_gateway_config(config_path))


def test_config_edit_refusal_without_a_config_file_exits_nonzero(tmp_path, monkeypatch, capsys):
    """A backend with no local file (Remote Config) refuses `config edit` with rc 1, so a script
    cannot read the refusal as a successful edit (teknium1 P3 on #122509)."""
    import hermes_cli.config as cfg

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(cfg, "is_managed", lambda: False)
    monkeypatch.setattr(cfg, "supports_file_tooling", lambda: False)
    monkeypatch.setattr(cfg.subprocess, "run", lambda *a, **k: pytest.fail("no editor may open"))
    with pytest.raises(SystemExit) as exc:
        cfg.edit_config()
    assert exc.value.code == 1
    assert "hermes config set" in capsys.readouterr().err
    assert not (tmp_path / "config.yaml").exists()


def test_seeded_config_keeps_the_update_backup_default(tmp_path, monkeypatch):
    from argparse import Namespace

    from hermes_cli.config_defaults import DEFAULT_CONFIG
    from hermes_cli.config_home import seed_config_file
    from hermes_cli.update_cmd_maint import _resolve_pre_update_backup_mode

    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    assert seed_config_file(home / "config.yaml")

    assert _resolve_pre_update_backup_mode(Namespace(no_backup=False, backup=False)) == \
        DEFAULT_CONFIG["updates"]["pre_update_backup"]


@pytest.mark.parametrize("entry", ["install", "profile"])
def test_starter_config_applies_oma_policy(tmp_path, monkeypatch, entry):
    import hermes_yaml as yaml
    from agent.skill_utils import get_disabled_skill_names
    from agent.skill_commands import build_auto_load_prompt
    from hermes_cli.config_defaults import DEFAULT_CONFIG
    from hermes_cli.config_effective import load_user_config_effective
    from hermes_cli.profiles import create_profile
    from hermes_cli.tools_config import _get_platform_tools
    from tools import approval_context
    from tools.tool_search import BRIDGE_TOOL_NAMES, assemble_tool_defs

    root = tmp_path / ".hermes"
    root.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(root))
    bundled = Path(__file__).resolve().parents[2] / "skills"
    monkeypatch.setenv("HERMES_BUNDLED_SKILLS", str(bundled))

    if entry == "install":
        source = bundled.parent
        subprocess.run(
            [sys.executable, "-I", "-B", str(source / "hermes_cli/source_completion.py"),
             "--source", str(source), "--seed-config", "--prepared"],
            env={**os.environ, "HOME": str(tmp_path)}, check=True, timeout=20,
        )
        home = root
    else:
        home = create_profile("fresh", no_alias=True, seed_model=False)
    path = home / "config.yaml"
    content = path.read_text(encoding="utf-8")
    assert "#" not in content
    assert yaml.safe_load(content) == {
        "agent": {"enabled_toolsets": ["file", "terminal", "browser", "web"]},
        "tools": {"tool_search": {"enabled": "on", "eager_toolsets": [], "listing": "off"}},
        "skills": {"disabled": []},
        "approvals": {
            "mode": "off",
            "timeout": 300,
            "cron_mode": "approve",
            "single_query_mode": "approve",
            "unattended_mode": "approve",
            "approvers": ["*"],
            "mcp_reload_confirm": False,
            "destructive_slash_confirm": False,
        },
        "_config_version": DEFAULT_CONFIG["_config_version"],
    }

    monkeypatch.setenv("HERMES_HOME", str(home))
    config = load_user_config_effective(path)
    assert build_auto_load_prompt(user_config=config) == ("", [], [])
    for surface in ("cli", "tui", "telegram"):
        assert _get_platform_tools(config, surface) == {"file", "terminal", "browser", "web"}
    assert not get_disabled_skill_names()
    assert approval_context._get_approval_mode() == "off"
    assert approval_context._get_approval_timeout() == 300
    assert approval_context._get_cron_approval_mode() == "approve"
    assert approval_context._get_single_query_approval_mode() == "approve"
    assert approval_context._get_unattended_approval_mode() == "approve"
    available = [{"type": "function", "function": {"name": "read_file"}}]
    result = assemble_tool_defs(available)
    assert result.activated and result.deferred_count == len(available)
    assert result.listing_form == "none"
    assert {tool["function"]["name"] for tool in result.tool_defs} == BRIDGE_TOOL_NAMES


def test_installer_leaves_existing_config_bytes_untouched(tmp_path, monkeypatch):
    from hermes_cli.config_home import seed_install_config

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "config.yaml"
    existing = b"# local settings\nagent:\n  enabled_toolsets: [kanban]\n"
    path.write_bytes(existing)
    seed_install_config()
    assert path.read_bytes() == existing

