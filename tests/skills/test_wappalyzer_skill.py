"""Research reports preserve evidence and fail visibly without installing tools."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "optional-skills/research/wappalyzer/scripts"
SPEC = importlib.util.spec_from_file_location("wappalyzer_research", SCRIPTS / "research.py")
research = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
    SPEC.loader.exec_module(research)
installation = sys.modules["wappalyzer_installation"]


@pytest.mark.parametrize("prepared", [False, True])
def test_preflight_checks_the_cache_without_launching_a_detector(tmp_path, capsys, monkeypatch, prepared):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    upstream = installation.cache_path()
    if prepared:
        files = {
            installation.DRIVER / "package.json": '{"version": "6.10.62"}',
            Path("src/wappalyzer.js"): "",
            Path("src/categories.json"): "{}",
            Path("src/technologies/_.json"): "{}",
        }
        for path, content in files.items():
            asset = upstream / path
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text(content, encoding="utf-8")
    with patch("sys.argv", ["research.py", "--check"]), \
         patch.object(research, "command", return_value="node"), \
         patch.object(research.subprocess, "run") as run:
        assert research.main() == (0 if prepared else 1)
    run.assert_not_called()
    captured = capsys.readouterr()
    if prepared:
        assert json.loads(captured.out) == {"status": "ready", "upstream": str(upstream), "version": "6.10.62"}
    else:
        error = json.loads(captured.err)
        assert error["status"] == "error"
        assert "Check container startup logs or run wappalyzer_installation.py" in error["error"]
        assert not upstream.exists()


def test_capture_report_preserves_detection_evidence_and_discloses_coverage(tmp_path, capsys, monkeypatch):
    url = "https://example.com/"
    capture = {"url": url, "html": '<meta name="generator" content="WordPress 6.0">'}
    capture_path = tmp_path / "capture.json"
    capture_path.write_text(json.dumps(capture))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home" / "profiles" / "research"))
    package = tmp_path / "home/cache/research/wappalyzer" / installation.REVISION / installation.DRIVER / "package.json"
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"version": "fixture-version"}))
    tech = {"name": "WordPress", "version": "6.0", "confidence": 100,
            "categories": [{"id": 1, "name": "CMS"}]}
    completed = subprocess.CompletedProcess([], 0, json.dumps({"technologies": [tech]}), "")
    output = tmp_path / "report.json"
    argv = ["research.py", url, "--capture", str(capture_path), "--browser", "camofox", "--output", str(output)]
    with patch.object(research, "command", return_value="node"), \
         patch.object(research, "chromium_executable", side_effect=AssertionError("No Chromium needed")), \
         patch.object(research.subprocess, "run", return_value=completed) as run, \
         patch("sys.argv", argv):
        assert research.main() == 0
    result = json.loads(output.read_text())
    assert result == json.loads(capsys.readouterr().out)
    assert result["technologies"] == [tech]
    assert result["browser"] == "camofox" and result["mode"] == "browser-capture"
    assert result["detector"]["version"] == "fixture-version"
    assert result["limitations"] and result["scanned_at"]
    assert json.loads(run.call_args.kwargs["input"]) == capture


def test_failed_install_can_retry_and_completed_install_is_reused(tmp_path):
    destination = tmp_path / "wappalyzer" / installation.REVISION
    with patch.object(installation, "_prepare", side_effect=subprocess.CalledProcessError(1, "npm")):
        with pytest.raises(subprocess.CalledProcessError):
            installation.install(destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".install-*"))

    def prepare(checkout):
        (checkout / "LICENSE").write_text("upstream license", encoding="utf-8")

    with patch.object(installation, "_prepare", side_effect=prepare) as run:
        assert installation.install(destination) == destination
        assert installation.install(destination) == destination
    run.assert_called_once()
    assert (destination / "LICENSE").read_text(encoding="utf-8") == "upstream license"


def test_cli_fallback_uses_prepared_browser_and_keeps_navigation_failures_visible(tmp_path, monkeypatch):
    url = "https://example.com/"
    payload = {"technologies": [], "urls": {url: {"status": 0, "error": "Navigation timed out"}}}
    completed = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
    monkeypatch.setenv("CHROMIUM_WEBSOCKET", "ws://unrelated-browser")
    with patch.object(research, "command", return_value="node"), \
         patch.object(research, "chromium_executable", return_value="/prepared/chromium"), \
         patch.object(research.subprocess, "run", return_value=completed) as run:
        raw = research.detect(tmp_path, url, None, 60)
    call = run.call_args
    assert call.args[0][1] == str(tmp_path / "src/drivers/npm/cli.js")
    assert "--max-urls=1" in call.args[0]
    assert call.kwargs["env"]["CHROMIUM_BIN"] == "/prepared/chromium"
    assert "CHROMIUM_WEBSOCKET" not in call.kwargs["env"]
    assert "--no-sandbox" not in call.kwargs["env"]["CHROMIUM_ARGS"]
    report = research.report(url, raw, "chromium-cli", "fixture")
    assert report["status"] == "partial"
    assert report["urls"][url]["error"] == "Navigation timed out"


@pytest.mark.parametrize("url", ["example.com", "file:///etc/passwd", "https://user:pass@example.com"])
def test_invalid_urls_do_not_start_a_detector(tmp_path, url):
    with patch.object(research, "command", return_value="node"), \
         patch.object(research.subprocess, "run") as run:
        with pytest.raises(ValueError):
            research.detect(tmp_path, url, None, 60)
    run.assert_not_called()


def test_missing_fallback_browser_never_installs_at_research_time(tmp_path):
    with patch.object(research, "command", return_value="node"), \
         patch.object(research, "chromium_executable", return_value=None), \
         patch.object(research.subprocess, "run") as run:
        with pytest.raises(ValueError, match="Prepare it during build/setup"):
            research.detect(tmp_path, "https://example.com", None, 60)
    run.assert_not_called()


def test_capture_for_another_page_is_rejected(tmp_path, capsys):
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps({"url": "https://other.example/"}))
    argv = ["research.py", "https://example.com/", "--capture", str(capture),
            "--upstream", str(tmp_path), "--browser", "camofox"]
    with patch("sys.argv", argv), patch.object(research, "detect") as detect:
        assert research.main() == 1
    detect.assert_not_called()
    assert json.loads(capsys.readouterr().err)["status"] == "error"
