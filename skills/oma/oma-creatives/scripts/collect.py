#!/usr/bin/env python3
"""Collect a target's public posts and ads into the oma-creatives layout.

Usage (run with the Hermes environment's Python):
  collect.py sources <brand_dir> own                     write sources.yaml for the brand from config.yaml
  collect.py organic <brand_dir> <target> [--only P]     collect every platform listed in sources.yaml
  collect.py ads <brand_dir> <target> [--only L] [--countries AT,DE]
  collect.py labels export <brand_dir> <target>          print records that still need labels (JSON)
  collect.py labels apply <brand_dir> <target> <file>    write labels from a JSON list

Inside ``browser_exec`` (no Camofox), load this file with ``runpy.run_path`` and call
``harness_main([...same arguments...], cdp=cdp)`` to run on the Hermes browser.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the oma_collect package sits beside this script

from oma_collect import run
import validate_creatives


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources")
    sources.add_argument("brand", type=Path)
    sources.add_argument("target", choices=["own"])
    for name in ("organic", "ads"):
        command = sub.add_parser(name)
        command.add_argument("brand", type=Path)
        command.add_argument("target")
        command.add_argument("--only")
        if name == "ads":
            command.add_argument("--countries", type=lambda value: [code.strip().upper() for code in value.split(",") if code.strip()])
            command.add_argument("--defer", metavar="REASON",
                                 help="record every library as not_checked with REASON without opening it")
    labels = sub.add_parser("labels")
    labels.add_argument("action", choices=["export", "apply"])
    labels.add_argument("brand", type=Path)
    labels.add_argument("target")
    labels.add_argument("file", nargs="?", type=Path)
    return parser


def _allowed_labels() -> dict[str, set]:
    return {"format": validate_creatives.FORMATS, "hook_type": validate_creatives.HOOKS, "angle": validate_creatives.ANGLES}


def main(argv=None, *, cdp=None) -> int:
    args = _parser().parse_args(argv)
    brand = args.brand.resolve()
    if not (brand / "config.yaml").is_file():
        print(f"ERROR: {brand} is not an OMA brand directory (config.yaml missing)", file=sys.stderr)
        return 2
    if args.command == "sources":
        result = run.plan_own(brand)
    elif args.command == "organic":
        result = run.run_organic(brand, args.target, only=args.only, harness_cdp=cdp)
    elif args.command == "ads":
        result = run.run_ads(brand, args.target, only=args.only, countries=args.countries, defer=args.defer,
                             harness_cdp=cdp)
    elif args.action == "export":
        result = run.export_labels(brand, args.target)
    else:
        if not args.file:
            print("ERROR: labels apply needs a JSON file", file=sys.stderr)
            return 2
        result = run.apply_labels(brand, args.target, json.loads(args.file.read_text(encoding="utf-8")), _allowed_labels())
    print(run.dumps(result))
    return 0


def harness_main(argv, *, cdp) -> int:
    return main(argv, cdp=cdp)


if __name__ == "__main__":
    sys.exit(main())
