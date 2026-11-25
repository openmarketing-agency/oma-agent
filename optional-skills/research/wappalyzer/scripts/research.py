# SPDX-License-Identifier: Apache-2.0
"""Run a separately installed upstream detector; never provision it here."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from hermes_cli.browser_runtime import chromium_executable
from wappalyzer_installation import DRIVER, cache_path, command


def detector_version(upstream: Path) -> str:
    manifest = upstream / DRIVER / "package.json"
    if not manifest.is_file():
        raise ValueError(
            f"Wappalyzer is missing at {upstream}. Check container startup logs "
            "or run wappalyzer_installation.py."
        )
    package = json.loads(manifest.read_text(encoding="utf-8"))
    version = package.get("version") if isinstance(package, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError(f"Wappalyzer has an invalid package version at {manifest}.")
    return version


def check_detector(upstream: Path) -> dict:
    version = detector_version(upstream)
    command("node")
    for asset in ("src/wappalyzer.js", "src/categories.json", "src/technologies/_.json"):
        if not (upstream / asset).is_file():
            raise ValueError(f"Wappalyzer is incomplete at {upstream}. Missing {asset}.")
    return {"status": "ready", "upstream": str(upstream), "version": version}


def web_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Expected an absolute HTTP or HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not supported.")
    return value


def detect(upstream: Path, url: str, capture: dict | None, timeout: int) -> dict:
    node = command("node")
    url = web_url(url)
    if capture is not None:
        completed = subprocess.run(
            [node, str(Path(__file__).with_name("analyze.cjs")), str(upstream)],
            input=json.dumps({**capture, "url": url}), text=True,
            capture_output=True, timeout=timeout, check=True,
        )
    else:
        browser = chromium_executable()
        if not browser:
            raise ValueError("No fallback Chromium is installed. Prepare it during build/setup.")
        # The upstream defaults disable browser security and share a fixed profile.
        # Supply normal headless flags and a disposable profile instead.
        env = {**os.environ, "CHROMIUM_BIN": browser,
               "CHROMIUM_ARGS": "--headless --disable-gpu"}
        env.pop("CHROMIUM_WEBSOCKET", None)
        completed = subprocess.run(
            [node, str(upstream / DRIVER / "cli.js"), url,
             "--max-urls=1", "--max-depth=0", "--max-wait=15000"],
            env=env, text=True, capture_output=True, timeout=timeout, check=True,
        )
    result = json.loads(completed.stdout)
    if not isinstance(result, dict) or not isinstance(result.get("technologies"), list):
        raise ValueError("Detector returned an invalid result; expected a technologies array.")
    return result


def report(url: str, result: dict, browser: str, version: str) -> dict:
    urls = result.get("urls", {})
    failures = {key: value for key, value in urls.items()
                if value.get("error") or not 0 < value.get("status", 200) < 400}
    return {
        "url": url,
        "scanned_at": datetime.now(UTC).isoformat(),
        "browser": browser,
        "mode": "upstream-cli" if browser == "chromium-cli" else "browser-capture",
        "detector": {"repository": "https://github.com/tomnomnom/wappalyzer", "version": version},
        "status": "partial" if failures else "ok",
        "urls": urls,
        "technologies": sorted(result["technologies"], key=lambda item: item["name"].casefold()),
        "limitations": ([] if browser == "chromium-cli" else [
            "Capture detection covers rendered HTML, meta tags, text, inline scripts and script URLs.",
            "No response headers, cookies, JavaScript globals, DOM rules or DNS probes were collected.",
        ]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?")
    parser.add_argument("--check", action="store_true", help="Check the detector before opening a page")
    parser.add_argument("--upstream", type=Path, help="Use an alternate preinstalled checkout")
    parser.add_argument("--capture", type=Path, help="JSON returned by collect.js in a browser tool")
    parser.add_argument("--browser", choices=("camofox", "browser-exec", "chromium-cli"))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        upstream = args.upstream or cache_path()
        if args.check:
            print(json.dumps(check_detector(upstream)))
            return 0
        if args.url is None or args.browser is None:
            raise ValueError("Provide a URL and --browser, or use --check.")
        if (args.capture is None) != (args.browser == "chromium-cli"):
            raise ValueError("Browser captures require --capture; chromium-cli runs without it.")
        if args.timeout <= 0:
            raise ValueError("Timeout must be positive.")
        url = web_url(args.url)
        capture = json.loads(args.capture.read_text(encoding="utf-8")) if args.capture else None
        if capture is not None and (not isinstance(capture, dict) or capture.get("url") != url):
            raise ValueError("Capture URL must match the final browser URL supplied to this command.")
        version = detector_version(upstream)
        result = report(url, detect(upstream, url, capture, args.timeout), args.browser, version)
        output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        print(output, end="")
        return 0 if result["status"] == "ok" else 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
