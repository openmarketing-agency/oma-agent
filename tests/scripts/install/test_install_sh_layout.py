"""Direct POSIX installs resolve their paths against the invocation directory."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / "scripts/install.sh"
pytestmark = pytest.mark.platforms("posix")


@pytest.fixture
def layout(tmp_path):
    parent = tmp_path / "install parent"
    home = tmp_path / "user"
    parent.mkdir()
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    for key in ("HERMES_HOME", "HERMES_INSTALL_DIR", "HERMES_REPO_URL"):
        env.pop(key, None)
    return parent, home, env


def _resolve(parent, env, *args):
    result = subprocess.run(
        ["bash", "-c", 'source "$1" --manifest "${@:2}"; printf "%s\\n" "$INSTALL_DIR" "$HERMES_HOME"',
         "layout", str(INSTALLER), *args],
        cwd=parent, env=env, capture_output=True, text=True, check=True, timeout=20,
    )
    return result.stdout.splitlines()


def test_fresh_install_uses_sibling_directories(layout):
    parent, _, env = layout
    assert _resolve(parent, env) == [str(parent / "oma-agent"), str(parent / "oma-agent-data")]
    assert not any(parent.iterdir())  # The manifest does not create anything.


def test_installer_preserves_legacy_home_and_honors_explicit_flags(layout):
    parent, home, env = layout
    legacy = home / ".hermes"
    legacy.mkdir()
    (legacy / "config.yaml").write_text("{}\n", encoding="utf-8")
    assert _resolve(parent, env) == [str(legacy / "hermes-agent"), str(legacy)]
    env.update(HERMES_HOME="ignored-data", HERMES_INSTALL_DIR="ignored-app")
    assert _resolve(parent, env, "--dir", "custom app", "--hermes-home", "custom data") == [
        str(parent / "custom app"), str(parent / "custom data"),
    ]


def test_rerun_keeps_data_bound_to_checkout(layout):
    parent, _, env = layout
    checkout = parent / "oma-agent"
    data = parent / "custom state"
    marker = checkout / ".hermes/install-home"
    marker.parent.mkdir(parents=True)
    marker.write_text(str(data) + "\n", encoding="utf-8")
    assert _resolve(parent, env) == [str(checkout), str(data)]


def test_install_home_is_saved_and_used_from_another_directory(layout):
    parent, _, env = layout
    checkout = parent / "oma-agent"
    data = parent / "oma-agent-data"
    checkout.mkdir()
    data.mkdir()
    # Import the real resolver from a staged source checkout, not the test runner's checkout.
    shutil.copy2(ROOT / "hermes_constants.py", checkout)
    subprocess.run(
        ["bash", "-c", 'source "$1" --manifest; remember_install_home', "layout", str(INSTALLER)],
        cwd=parent, env=env, capture_output=True, text=True, check=True, timeout=20,
    )
    probe = "import sys; sys.path.insert(0, sys.argv[1]); from hermes_constants import get_hermes_home; print(get_hermes_home())"
    command = [sys.executable, "-I", "-c", probe, str(checkout)]
    result = subprocess.run(command, cwd=parent.parent, env=env, capture_output=True, text=True, check=True, timeout=20)
    assert result.stdout.strip() == str(data)
    env["HERMES_HOME"] = str(parent / "override")
    result = subprocess.run(command, cwd=parent.parent, env=env, capture_output=True, text=True, check=True, timeout=20)
    assert result.stdout.strip() == env["HERMES_HOME"]
