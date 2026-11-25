# SPDX-License-Identifier: Apache-2.0
"""Locate Wappalyzer's runtime cache and prepare it when explicitly invoked."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from hermes_constants import get_default_hermes_root, get_hermes_home
from hermes_platform.resolver import locate_command
from pm.filesystem import lock_path

REPOSITORY = "https://github.com/tomnomnom/wappalyzer.git"
REVISION = "30450a0841b28b5e89091110774d15867dd265c3"
DRIVER = Path("src/drivers/npm")


def cache_path() -> Path:
    # The detector is public and shared by profiles on the same data volume.
    return get_default_hermes_root(home=get_hermes_home()) / "cache" / "research" / "wappalyzer" / REVISION


def command(name: str) -> str:
    resolved = locate_command(name).command
    if not resolved:
        raise ValueError(f"Required command is unavailable: {name}. Prepare it during setup.")
    return resolved[0]


def _prepare(checkout: Path) -> None:
    git, node, npm = (command(name) for name in ("git", "node", "npm"))
    # Git and npm need network configuration, not the container's application secrets.
    allowed = {
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "HTTPS_PROXY",
        "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env["HOME"] = str(checkout.parent)
    env["GIT_TERMINAL_PROMPT"] = "0"
    for args in (
        ["init", "-q"],
        ["fetch", "-q", "--depth=1", REPOSITORY, REVISION],
        ["checkout", "-q", "--detach", REVISION],
    ):
        subprocess.run([git, *args], cwd=checkout, env=env, check=True, timeout=45)

    # The pinned checkout includes the driver's yarn.lock. npm uses it
    # when resolving the tree. Skip Puppeteer's browser download.
    subprocess.run(
        [npm, "install", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund",
         "--fetch-retries=0", "--cache", str(checkout.parent / "npm-cache")],
        cwd=checkout / DRIVER, env=env, check=True, timeout=90,
    )
    subprocess.run([node, "bin/link.js"], cwd=checkout, env=env, check=True, timeout=15)
    subprocess.run(
        [node, str(DRIVER / "cli.js"), "--help"],
        cwd=checkout, env=env, check=True, stdout=subprocess.DEVNULL, timeout=15,
    )


def install(destination: Path) -> Path:
    # A restart with a complete cache needs neither internet nor the lock.
    if destination.is_dir():
        return destination
    lock = lock_path(destination.with_suffix(".lock"), timeout=150, create_dir=True)
    if lock is None:
        raise TimeoutError("Another container is preparing Wappalyzer")
    try:
        if destination.is_dir():
            return destination
        with TemporaryDirectory(prefix=".install-", dir=destination.parent) as staging:
            checkout = Path(staging) / "checkout"
            checkout.mkdir()
            _prepare(checkout)
            # Publish only after all steps work so a failed boot can retry.
            checkout.rename(destination)
        return destination
    finally:
        os.close(lock)


def main() -> int:
    try:
        print(f"Wappalyzer ready at {install(cache_path())}", flush=True)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Wappalyzer setup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
