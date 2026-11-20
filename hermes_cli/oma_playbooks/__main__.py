"""Install and inspect OMA campaigns from the local runtime bundle."""

import argparse
import json
import sys
from pathlib import Path

from hermes_cli.oma_playbooks.install import configure, default_home, install, installed
from hermes_cli.oma_playbooks.source import resolve


_CAMPAIGNS_DIR = Path("/opt/oma/campaigns")
_SKILLS_DIR = Path("/opt/oma/skills")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List installed campaigns")
    commands.add_parser("status", help="Inspect an installed campaign").add_argument("id")
    commands.add_parser("configure", help="Seed an installed campaign config or missing routing metadata").add_argument("id")
    commands.add_parser("install", help=f"Install a campaign from {_CAMPAIGNS_DIR}").add_argument("id")
    handlers = {
        "list": lambda home, args: installed(home),
        "status": lambda home, args: installed(home, args.id)[0],
        "configure": lambda home, args: configure(home, args.id),
        "install": lambda home, args: install(home, resolve(_CAMPAIGNS_DIR, _SKILLS_DIR, args.id)),
    }
    args = parser.parse_args(argv)
    try:
        print(json.dumps(handlers[args.command](default_home(), args), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"OMA campaigns: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
