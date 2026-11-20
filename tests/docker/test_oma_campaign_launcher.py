"""The OMA campaign helper runs through the sealed Docker launcher, offline."""

import json
import subprocess

import pytest


@pytest.mark.parametrize("user", ["root", "hermes"])
def test_campaign_helper_uses_image_runtime(built_image, user):
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--user", user,
         "--entrypoint", "/bin/sh", built_image, "-ec",
         'python3 /opt/hermes/skills/oma/oma-campaigns/scripts/playbook.py list'],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_prebuilt_image_does_not_require_pnpm_at_runtime(built_image):
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--user", "hermes",
         "--entrypoint", "/bin/sh", built_image, "-ec",
         'if command -v pnpm; then exit 99; fi; hermes config path'],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "pnpm: not installed or outdated" not in result.stderr
