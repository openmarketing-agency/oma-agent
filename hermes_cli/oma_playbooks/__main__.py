"""Command adapter launched by the bundled OMA playbook skill."""

import argparse
import json
import sys
from pathlib import Path

from hermes_cli.oma_playbooks.install import default_home, install, installed
from hermes_cli.oma_playbooks.releases import cached_path, fetch_release, resolve_release
from hermes_cli.oma_playbooks.source import catalog, checked_id, resolve


def _plan(playbook) -> dict:
    return {"id": playbook.id, "version": playbook.version, "orchestrator": playbook.orchestrator,
            "agents": {agent.id: {"version": agent.version, "oma_skills": sorted(agent.skills),
                                  "declared_jobs": agent.jobs} for agent in playbook.agents}}


def _run(home: Path, args: argparse.Namespace):
    command = args.command
    if command == "list":
        return installed(home)
    if command == "status":
        return installed(home, args.id)[0]
    if command in {"plan", "install"}:
        checked_id(args.id)

    release = None
    if getattr(args, "repo", None) is not None:
        repo = args.repo.resolve()
    else:
        release = resolve_release(args.tag)
        cached = cached_path(home, release)
        if command == "check":
            return {"source": release.provenance(), "cached": cached is not None,
                    "cache_path": str(cached) if cached is not None else None}
        repo = cached if cached is not None else fetch_release(home, release)
        if command == "fetch":
            return {"source": release.provenance(), "cache_path": str(repo), "downloaded": cached is None}

    source = {"source": release.provenance()} if release else {}
    if command == "catalog":
        return [{**entry, **source} for entry in catalog(repo)]
    playbook = resolve(repo, args.id, args.version)
    if command == "plan":
        return {**_plan(playbook), **source}
    return install(home, playbook, release=release)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List local installation records")
    commands.add_parser("status", help="Inspect a local installation record").add_argument("id")
    for name, help_text in {
        "check": "Look up the R2 release and its cache status without downloading ZIPs",
        "fetch": "Cache public OMA playbooks and skills from R2 without installing profiles",
        "catalog": "List available OMA playbooks",
        "plan": "Validate a playbook and show what would be installed",
        "install": "Provision a playbook from the public OMA release",
    }.items():
        command = commands.add_parser(name, help=help_text)
        options = command.add_mutually_exclusive_group()
        options.add_argument("--tag", help="Use this stable R2 release tag instead of the latest release")
        if name in {"catalog", "plan", "install"}:
            options.add_argument("--repo", type=Path, help="Use an explicit trusted local checkout instead of the public source")
        if name in {"plan", "install"}:
            command.add_argument("id")
            command.add_argument("--version", help="Require this exact source manifest version")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(_run(default_home(), args), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"OMA playbooks: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
