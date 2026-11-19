"""OMA Agent does not offer, collect or transmit Nous shared metrics."""

import argparse
import subprocess
from pathlib import Path

import pytest


def test_setup_does_not_offer_telemetry(capsys):
    from hermes_cli.subcommands.setup import build_setup_parser

    parser = argparse.ArgumentParser(prog="hermes")
    build_setup_parser(parser.add_subparsers(), cmd_setup=lambda args: None)
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["setup", "telemetry"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("profile", ["default", "named"])
def test_legacy_opt_in_cannot_collect_or_send(monkeypatch, tmp_path, profile):
    from hermes_cli.config import get_config_path, read_user_config_raw
    from hermes_cli.observability import relay_shared_metrics as metrics
    from hermes_cli.observability.shared_metrics_consent import consent_state
    from hermes_cli.observability.shared_metrics_engagement import _collects
    from hermes_cli.observability.shared_metrics_process import begin_process
    from hermes_cli.observability.shared_metrics_send_config import resolve_send_config
    from hermes_cli.observability.shared_metrics_sender import _post
    from hermes_cli.update_receipt import _publish_shared_metrics

    home = tmp_path if profile == "default" else tmp_path / "profiles" / profile
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    path = get_config_path()
    contents = ("telemetry:\n  shared_metrics:\n    enabled: true\n    send: true\n"
                "    endpoint: 'https://example.invalid/metrics'\n")
    path.write_text(contents, encoding="utf-8")  # config-writer: ok — legacy user fixture
    config = read_user_config_raw(path)
    assert not metrics.enabled()
    assert not _collects(path.parent)
    send = resolve_send_config(config)
    assert (send.enabled, send.send, send.endpoint) == (False, False, "")
    assert consent_state(config) == {"enabled": False, "send": False, "decided": True, "reask": False}
    monkeypatch.setattr(metrics, "_RUNTIMES", {})
    assert metrics._get_runtime(retry_failed=True) is None
    begin_process("cli")
    metrics.observe_lifecycle("post_auxiliary_call")
    _publish_shared_metrics({"update_id": "a" * 32})
    assert not (path.parent / "telemetry").exists()
    assert path.read_text(encoding="utf-8") == contents
    with pytest.raises(RuntimeError, match="does not send"):
        _post("https://example.invalid/metrics", b"{}", timeout=1)


@pytest.mark.asyncio
async def test_dashboard_cannot_enable_shared_metrics():
    from hermes_cli.web_routers.shared_metrics import ConsentAnswer, get_shared_metrics_consent, put_shared_metrics_consent

    disabled = {"enabled": False, "send": False, "decided": True, "reask": False, "managed": True}
    assert await get_shared_metrics_consent() == disabled
    assert await put_shared_metrics_consent(ConsentAnswer(enabled=True, send=True)) == disabled


def test_legacy_clients_cannot_enable_shared_metrics():
    from tui_gateway import server

    for action, params in [("status", {}), ("set", {"enabled": True, "send": True, "first_run": True})]:
        response = server._methods[f"shared_metrics.{action}"]("legacy", params)
        assert response["result"] == {"enabled": False, "send": False, "decided": True, "reask": False}


@pytest.mark.platforms("posix")
def test_failed_shell_install_does_not_leave_shared_metrics(tmp_path):
    import shutil

    installer = Path(__file__).resolve().parents[2] / "scripts" / "install.sh"
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("bash", "uname", "mkdir", "id", "cat", "dirname", "curl"):
        if path := shutil.which(name):
            (bin_dir / name).symlink_to(path)
    result = subprocess.run(
        [str(bin_dir / "bash"), str(installer), "--non-interactive", "--hermes-home", str(home),
         "--dir", str(tmp_path / "checkout")],
        env={"PATH": str(bin_dir), "HOME": str(tmp_path)}, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode != 0
    assert "git" in result.stdout + result.stderr
    assert not (home / "telemetry").exists()
