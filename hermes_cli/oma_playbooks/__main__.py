"""Install and inspect OMA campaigns from the local runtime bundle."""

import argparse
import json
import sys

from hermes_cli.oma_playbooks.bundle import bundle_dir
from hermes_cli.oma_playbooks.install import configure, default_home, install, installed
from hermes_cli.oma_playbooks.source import resolve


def _install_from_bundle(home, args):
    bundle = bundle_dir(home)
    return install(home, resolve(bundle / "campaigns", bundle / "skills", args.id))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List installed campaigns")
    commands.add_parser("status", help="Inspect an installed campaign").add_argument("id")
    commands.add_parser("configure", help="Seed an installed campaign config or missing routing metadata").add_argument("id")
    commands.add_parser("install", help="Install a campaign from $HERMES_HOME/oma-bundle").add_argument("id")
    handlers = {
        "list": lambda home, args: installed(home),
        "status": lambda home, args: installed(home, args.id)[0],
        "configure": lambda home, args: configure(home, args.id),
        "install": _install_from_bundle,
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
