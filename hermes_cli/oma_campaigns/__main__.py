"""Provision and inspect OMA campaigns from local records."""

import argparse
import json
import sys
from pathlib import Path

from hermes_cli.oma_campaigns.analytics import list_analytics, save_observations
from hermes_cli.oma_campaigns.analytics_cron import analyst_profile, analytics_status
from hermes_cli.oma_campaigns.install import configure, create, default_home, install, installed
from hermes_cli.oma_campaigns.integrations import brand_candidates
from hermes_cli.oma_campaigns.lifecycle import set_lifecycle, set_mode
from hermes_cli.oma_campaigns.schema import KINDS, validate_record
from hermes_cli.oma_campaigns.source import read_mapping
from hermes_constants import get_default_hermes_root, get_hermes_home


def _analytics_home(campaign_id: str, *, write: bool) -> Path:
    profile = get_hermes_home().resolve()
    home = get_default_hermes_root(home=profile).resolve()
    if not write and profile == home:
        return default_home()
    if profile.name != f"{campaign_id}__analyst" or profile.parent != home / "profiles" or not analyst_profile(profile):
        raise ValueError("Use the installed Analyst profile for this campaign.")
    return home


def _save_analytics(home: Path, campaign_id: str) -> dict:
    limit = 256 * 1024
    payload = sys.stdin.read(limit + 1)
    if len(payload.encode("utf-8")) > limit:
        raise ValueError("Analytics input exceeds 256 KiB.")
    try:
        rows = json.loads(payload)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Supply a JSON array of analytics observations on stdin.") from exc
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Supply 1–100 analytics observations on stdin.")
    if any(row.get("source") == "oma-publications" for row in rows):
        raise ValueError("OMA publication counts are managed locally, not written by the Analyst.")
    return {"campaign_id": campaign_id, "saved": save_observations(home, campaign_id, rows)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List installed or incomplete campaigns")
    commands.add_parser("status", help="Inspect a saved campaign and its provisioning status").add_argument("id")
    commands.add_parser("configure", help="Fill missing routing metadata for a verified installed campaign").add_argument("id")
    commands.add_parser("create", help="Create a paused campaign with its team and Kanban board").add_argument("path", type=Path)
    commands.add_parser("install", help="Provision a legacy saved campaign definition without starting it").add_argument("id")
    commands.add_parser("integrations", help="List brand-derived candidate integrations")
    commands.add_parser("analytics-status", help="Read campaign analytics refresh status").add_argument("id")
    commands.add_parser("analytics-save", help="Save observed analytics from a JSON array on stdin").add_argument("id")
    read = commands.add_parser("analytics-read", help="Read saved campaign observations without calling providers")
    read.add_argument("id")
    for flag in ("source", "account", "metric", "start", "end", "breakdown"):
        read.add_argument(f"--{flag}")
    read.add_argument("--before", type=int)
    read.add_argument("--limit", type=int, default=50)
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
        "analytics-status": lambda home, args: analytics_status(home, args.id),
        "analytics-save": lambda home, args: _save_analytics(home, args.id),
        "analytics-read": lambda home, args: list_analytics(
            home, args.id, source=args.source, account=args.account, metric=args.metric, start=args.start,
            end=args.end, breakdown=args.breakdown, before=args.before, limit=args.limit),
        "analytics-breakdown": lambda home, args: list_analytics(
            home, args.id, source=args.source, breakdown=args.breakdown, metric=args.metric,
            before=args.before, limit=args.limit),
        "lifecycle": lambda home, args: set_lifecycle(home, args.id, args.state),
        "mode": lambda home, args: set_mode(home, args.id, args.mode),
    }
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate_record(args.kind, read_mapping(args.path), args.path)
            print(json.dumps({"kind": args.kind, "valid": True}))
            return 0
        home = (_analytics_home(args.id, write=args.command == "analytics-save")
                if args.command.startswith("analytics-") else default_home())
        result = handlers[args.command](home, args)
        print(json.dumps(result, indent=2))
        return 3 if args.command == "lifecycle" and result.get("missing_model") is True else 0
    except (ValueError, OSError) as exc:
        print(f"OMA campaigns: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
