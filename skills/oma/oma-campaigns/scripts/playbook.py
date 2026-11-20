#!/usr/bin/env python3
"""Invoke the installed Hermes runtime without evaluating shell output."""

import json
import subprocess
import sys


def main() -> int:
    try:
        result = subprocess.run(
            ["hermes", "--print-runtime-command", "--module", "hermes_cli.oma_playbooks"],
            check=True, capture_output=True, text=True, timeout=15,
        )
        argv = json.loads(result.stdout)
        if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
            raise ValueError("Invalid Hermes runtime command")
        return subprocess.run([*argv, *sys.argv[1:]], check=False, timeout=600).returncode
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"Cannot launch the OMA campaign manager: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
