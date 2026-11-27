"""Provision and inspect OMA campaigns from local records."""

import argparse
import json
import sys
from pathlib import Path

from hermes_cli.oma_campaigns.analytics import campaign_dir, list_analytics
from hermes_cli.oma_campaigns.analytics_cron import analytics_status
from hermes_cli.oma_campaigns.analytics_sync.data import list_records
from hermes_cli.oma_campaigns.install import configure, create, default_home, install, installed
from hermes_cli.oma_campaigns.integrations import brand_candidates, needs_warnings, recommend
from hermes_cli.oma_campaigns.lifecycle import set_lifecycle, set_mode
from hermes_cli.oma_campaigns.schema import KINDS, validate_record
from hermes_cli.oma_campaigns.source import read_mapping


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List installed or incomplete campaigns")
    commands.add_parser("status", help="Inspect a saved campaign and its provisioning status").add_argument("id")
    commands.add_parser("configure", help="Fill missing routing metadata for a verified installed campaign").add_argument("id")
    commands.add_parser("create", help="Create a paused campaign with its team and Kanban board").add_argument("path", type=Path)
    commands.add_parser("install", help="Provision a legacy saved campaign definition without starting it").add_argument("id")
    commands.add_parser("integrations", help="List brand-derived candidate integrations")
    recommendation = commands.add_parser(
        "recommend", help="Suggest integrations, what they need, and complementary tools for a campaign")
    recommendation.add_argument("--for", dest="ids", type=_csv, default=[], help="Comma-separated integration IDs")
    recommendation.add_argument("--channels", type=_csv, default=[], help="Comma-separated play channel IDs")
    commands.add_parser("analytics-status", help="Read campaign analytics progress and coverage").add_argument("id")
    records = commands.add_parser("analytics-records", help="Read saved detailed campaign analytics records")
    records.add_argument("id")
    records.add_argument("source")
    records.add_argument("dataset")
    records.add_argument("--before", type=int)
    records.add_argument("--limit", type=int, default=50)
    breakdown = commands.add_parser("analytics-breakdown", help="Read a saved campaign analytics breakdown")
    breakdown.add_argument("id")
    breakdown.add_argument("source")
    breakdown.add_argument("breakdown")
    breakdown.add_argument("--metric")
    breakdown.add_argument("--before", type=int)
    breakdown.add_argument("--limit", type=int, default=50)
    lifecycle = commands.add_parser("lifecycle", help="Pause or resume an installed campaign")
    lifecycle.add_argument("id")
    lifecycle.add_argument("state", choices=("paused", "resumed"))
    mode = commands.add_parser("mode", help="Change the automation policy of a stopped campaign")
    mode.add_argument("id")
    mode.add_argument("mode", choices=("yolo", "approve", "control"))
    validate = commands.add_parser("validate", help="Check an OMA YAML record without applying it")
    validate.add_argument("kind", choices=KINDS)
    validate.add_argument("path", type=Path)

    handlers = {
        "list": lambda home, args: installed(home),
        "status": lambda home, args: installed(home, args.id)[0],
        "configure": lambda home, args: configure(home, args.id),
        "create": lambda home, args: create(home, args.path),
        "install": lambda home, args: install(home, args.id),
        "integrations": lambda home, args: brand_candidates(home),
        "recommend": lambda home, args: recommend(home, args.ids, args.channels),
        "analytics-status": lambda home, args: analytics_status(home, args.id),
        "analytics-records": lambda home, args: list_records(campaign_dir(home, args.id), source=args.source,
                                                              dataset=args.dataset, before=args.before,
                                                              limit=args.limit),
        "analytics-breakdown": lambda home, args: list_analytics(
            home, args.id, source=args.source, breakdown=args.breakdown, metric=args.metric,
            before=args.before, limit=args.limit),
        "lifecycle": lambda home, args: set_lifecycle(home, args.id, args.state),
        "mode": lambda home, args: set_mode(home, args.id, args.mode),
    }
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            record = read_mapping(args.path)
            validate_record(args.kind, record, args.path)
            warnings = needs_warnings(record) if args.kind == "campaign" else []
            print(json.dumps({"kind": args.kind, "valid": True, "warnings": warnings}))
            return 0
        result = handlers[args.command](default_home(), args)
        print(json.dumps(result, indent=2))
        return 3 if args.command == "lifecycle" and result.get("missing_model") is True else 0
    except (ValueError, OSError) as exc:
        print(f"OMA campaigns: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
