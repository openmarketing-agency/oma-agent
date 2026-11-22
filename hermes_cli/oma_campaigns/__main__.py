"""Provision and inspect OMA campaigns from local records."""

import argparse
import json
import sys
from pathlib import Path

from hermes_cli.oma_campaigns.install import configure, default_home, install, installed
from hermes_cli.oma_campaigns.integrations import brand_candidates
from hermes_cli.oma_campaigns.lifecycle import set_lifecycle
from hermes_cli.oma_campaigns.schema import KINDS, validate_record
from hermes_cli.oma_campaigns.source import read_mapping


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List installed or incomplete campaigns")
    commands.add_parser("status", help="Inspect a saved campaign and its provisioning status").add_argument("id")
    commands.add_parser("configure", help="Fill missing routing metadata for a verified installed campaign").add_argument("id")
    commands.add_parser("install", help="Provision a campaign from saved OMA campaign and agent records").add_argument("id")
    commands.add_parser("integrations", help="List brand-derived candidate integrations")
    lifecycle = commands.add_parser("lifecycle", help="Pause or resume an installed campaign")
    lifecycle.add_argument("id")
    lifecycle.add_argument("state", choices=("paused", "resumed"))
    validate = commands.add_parser("validate", help="Check an OMA YAML record without applying it")
    validate.add_argument("kind", choices=KINDS)
    validate.add_argument("path", type=Path)

    handlers = {
        "list": lambda home, args: installed(home),
        "status": lambda home, args: installed(home, args.id)[0],
        "configure": lambda home, args: configure(home, args.id),
        "install": lambda home, args: install(home, args.id),
        "integrations": lambda home, args: brand_candidates(home),
        "lifecycle": lambda home, args: set_lifecycle(home, args.id, args.state),
    }
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate_record(args.kind, read_mapping(args.path), args.path)
            print(json.dumps({"kind": args.kind, "valid": True}))
            return 0
        result = handlers[args.command](default_home(), args)
        print(json.dumps(result, indent=2))
        return 3 if args.command == "lifecycle" and "missing_integrations" in result else 0
    except (ValueError, OSError) as exc:
        print(f"OMA campaigns: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
