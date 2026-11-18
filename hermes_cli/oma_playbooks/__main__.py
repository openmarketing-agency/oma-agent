"""Command adapter launched by the bundled OMA playbook skill."""

import argparse
import json
import sys
from pathlib import Path

from hermes_cli.oma_playbooks.install import default_home, install, installed
from hermes_cli.oma_playbooks.source import catalog, resolve


def _plan(playbook) -> dict:
    return {"id": playbook.id, "version": playbook.version, "orchestrator": playbook.orchestrator,
            "agents": {agent.id: {"version": agent.version, "oma_skills": sorted(agent.skills),
                                  "declared_jobs": agent.jobs} for agent in playbook.agents}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List local installation records")
    commands.add_parser("status", help="Inspect a local installation record").add_argument("id")
    for name in ("catalog", "plan", "install"):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True, type=Path, help="Local openmarketing.agency checkout")
        if name != "catalog":
            command.add_argument("id")
            command.add_argument("--version", help="Require this exact source manifest version")
    args = parser.parse_args(argv)
    try:
        home = default_home()
        handlers = {
            "list": lambda: installed(home),
            "status": lambda: installed(home, args.id)[0],
            "catalog": lambda: catalog(args.repo.resolve()),
            "plan": lambda: _plan(resolve(args.repo, args.id, args.version)),
            "install": lambda: install(home, resolve(args.repo, args.id, args.version)),
        }
        print(json.dumps(handlers[args.command](), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"OMA playbooks: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
