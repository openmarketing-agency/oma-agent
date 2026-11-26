#!/usr/bin/env python3
"""Run OMA onboarding as a Kanban card graph on the default profile.

Usage (with the Hermes environment's Python):
  board.py start <home> --url URL [--repo URL] [--synthesis-model MODEL]
  board.py repository <home> URL         the brand-core card adds the analysis of a repository it verified
  board.py fanout <home>                 the discovery card adds competitor and creatives cards
  board.py campaigns <home> ID [ID ...]  the playbook card adds one design card per campaign and provisioning
  board.py merge-config <home> <file>    merge a YAML fragment into oma/brand/config.yaml under a lock
  board.py status <home>

Every card is a fresh worker of the default profile that does one stage and finishes with that stage's
validator. A card starts only when the cards it depends on are done. Cards are created with idempotency
keys, so running ``start`` again resumes the same board instead of duplicating it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from ruamel.yaml import YAML

BOARD = "oma-onboarding"
SKILLS = Path(__file__).resolve().parents[2]
CARDS = Path(__file__).resolve().parents[1] / "references" / "cards"
JUDGMENT = {"design-system", "landscape", "playbook", "campaign"}  # cards that may use --synthesis-model
CREATOR = "oma-onboarding"
# Cards other cards look up later; the Kanban list does not return idempotency keys, so titles identify them.
TITLES = {"brand-core": "Brand: website, channels, integrations, docs",
          "discovery": "Competitors: discover, score and tier",
          "landscape": "Competitors: patterns, landscape and validation",
          "playbook": "Strategy: playbook and campaign choice",
          "provision": "Campaigns: provision paused teams"}


@dataclass
class Graph:
    home: Path
    model: str | None = None
    created: list[dict] = field(default_factory=list)

    @property
    def values(self) -> dict:
        return {"home": str(self.home), "brand": str(self.home / "oma" / "brand"),
                "board": str(Path(__file__).resolve()), "python": sys.executable,
                "collect": str(SKILLS / "oma-creatives" / "scripts" / "collect.py"),
                "sources_template": str(SKILLS / "oma-creatives" / "references" / "sources.md"),
                "validate_creatives": str(SKILLS / "oma-creatives" / "scripts" / "validate_creatives.py"),
                "validate_competitors": str(SKILLS / "oma-competitors" / "scripts" / "validate_competitors.py"),
                "campaign": str(SKILLS / "oma-campaigns" / "scripts" / "campaign.py")}


def _hermes() -> str:
    found = shutil.which("hermes")
    if not found:
        raise SystemExit("ERROR: the hermes command is not on PATH; run this with the Hermes environment active")
    return found


def kanban(*args: str) -> str:
    done = subprocess.run([_hermes(), "kanban", "--board", BOARD, *args], capture_output=True, text=True, check=False,
                          timeout=120)
    if done.returncode != 0:
        raise RuntimeError(f"hermes kanban {' '.join(args[:2])} failed: {(done.stderr or done.stdout).strip()[:400]}")
    return done.stdout


def ensure_board() -> None:
    listing = subprocess.run([_hermes(), "kanban", "boards", "list"], capture_output=True, text=True, check=False,
                             timeout=60).stdout
    if f" {BOARD} " not in f" {listing} ":
        subprocess.run([_hermes(), "kanban", "boards", "create", BOARD, "--name", "Onboarding",
                        "--description", "Brand research, strategy and campaign setup, one stage per card"],
                       capture_output=True, text=True, check=True, timeout=60)


def render(template: str, values: dict) -> str:
    text = (CARDS / f"{template}.md").read_text(encoding="utf-8") + (CARDS / "_rules.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def card(graph: Graph, key: str, title: str, template: str, *, parents=(), skills=(), runtime="60m", **values) -> str:
    """Create (or, by idempotency key, find) one card; returns its id."""
    body = render(template, {**graph.values, **values})
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(body)
    args = ["create", title, "--assignee", "default", "--body-file", handle.name, "--idempotency-key", f"onboarding:{key}",
            "--max-runtime", runtime, "--max-retries", "2", "--created-by", CREATOR, "--json"]
    for parent in parents:
        args += ["--parent", parent]
    for skill in skills:
        args += ["--skill", skill]
    if graph.model and template in JUDGMENT:
        args += ["--model", graph.model]
    try:
        created = json.loads(kanban(*args))
    finally:
        os.unlink(handle.name)
    graph.created.append({"key": key, "id": created["id"], "title": title})
    return created["id"]


def _ours() -> list[dict]:
    return [task for task in json.loads(kanban("list", "--json") or "[]") if task.get("created_by") == CREATOR]


def find(key: str) -> str | None:
    return next((task["id"] for task in _ours() if task.get("title") == TITLES[key]), None)


def link(parent: str, child: str) -> None:
    try:
        kanban("link", parent, child)
    except RuntimeError as exc:
        if "already" not in str(exc).lower() and "exists" not in str(exc).lower():
            raise


def start(graph: Graph, url: str, repo: str | None) -> None:
    ensure_board()
    core = card(graph, "brand-core", TITLES["brand-core"], "brand-core",
                skills=["oma-brand"], url=url)
    stage = [core]
    if repo:
        stage.append(card(graph, "repository", "Brand: repository analysis", "repository", parents=[core],
                          skills=["oma-brand"], repo=repo, runtime="90m"))
    visuals = card(graph, "visuals", "Brand: screenshots and visual assets", "visuals", parents=[core], skills=["oma-brand"])
    market = card(graph, "market", "Brand: market research", "market", parents=[core], skills=["oma-brand"])
    own_organic = card(graph, "creatives-own-organic", "Creatives: the brand's own posts", "creatives-organic",
                       parents=[core], skills=["oma-creatives"], target="own", name="the brand", runtime="120m")
    own_ads = card(graph, "creatives-own-ads", "Creatives: the brand's own ads and summary", "creatives-ads",
                   parents=[own_organic], skills=["oma-creatives"], target="own", name="the brand", runtime="120m")
    discovery = card(graph, "discovery", TITLES["discovery"], "discovery", parents=[core],
                     skills=["oma-competitors"])
    landscape = card(graph, "landscape", TITLES["landscape"], "landscape",
                     parents=[discovery, own_ads], skills=["oma-competitors"])
    design = card(graph, "design-system", "Brand: design system", "design-system", parents=[visuals, own_ads],
                  skills=["oma-brand"])
    card(graph, "playbook", TITLES["playbook"], "playbook",
         parents=stage + [market, landscape, design], skills=["oma-playbook"])


def repository(graph: Graph, url: str) -> None:
    """A repository found during brand research gets its own card; the playbook waits for it."""
    core, playbook = find("brand-core"), find("playbook")
    if not core or not playbook:
        raise SystemExit("ERROR: run board.py start first; the brand-core and playbook cards are missing")
    repo_card = card(graph, "repository", "Brand: repository analysis", "repository", parents=[core],
                     skills=["oma-brand"], repo=url, runtime="90m")
    link(repo_card, playbook)


def fanout(graph: Graph) -> None:
    """Called by the discovery card once research/competitors/index.yaml validates."""
    index = YAML(typ="safe").load((graph.home / "oma/brand/research/competitors/index.yaml").read_text()) or {}
    discovery, landscape = find("discovery"), find("landscape")
    if not discovery or not landscape:
        raise SystemExit("ERROR: run board.py start first; the discovery and landscape cards are missing")
    competitors = index.get("competitors") or []
    direct = [c for c in competitors if c.get("tier") == "direct" and c.get("depth") == "full"]
    indirect = [c for c in competitors if c.get("tier") == "indirect" and c.get("depth") == "light"]
    finals = []
    for c in direct:
        profile = card(graph, f"competitor-{c['id']}", f"Competitor: {c['name']} profile and teardown", "competitor",
                       parents=[discovery], skills=["oma-competitors"], target=c["id"], name=c["name"], depth="full")
        finals += [profile, _creatives(graph, c["id"], c["name"], profile)]
    if indirect:
        names = ", ".join(f"{c['name']} ({c['id']})" for c in indirect)
        finals.append(card(graph, "competitors-indirect", "Competitors: indirect profiles", "competitor-indirect",
                           parents=[discovery], skills=["oma-competitors"], targets=names))
    for r in index.get("references") or []:
        finals.append(_creatives(graph, r["id"], r.get("name", r["id"]), discovery, reference=True))
    for final in finals:
        link(final, landscape)


def _creatives(graph: Graph, target: str, name: str, parent: str, *, reference: bool = False) -> str:
    plan = "reference" if reference else "competitor"
    organic = card(graph, f"creatives-{target}-organic", f"Creatives: {name} posts", "creatives-organic",
                   parents=[parent], skills=["oma-creatives"], target=target, name=name, plan=plan, runtime="120m")
    return card(graph, f"creatives-{target}-ads", f"Creatives: {name} ads and summary", "creatives-ads",
                parents=[organic], skills=["oma-creatives"], target=target, name=name, runtime="120m")


def campaigns(graph: Graph, ids: list[str]) -> None:
    """Called by the playbook card with the campaigns it recommends, in priority order."""
    task = next((t for t in _ours() if t.get("title") == TITLES["playbook"]), None)
    if not task:
        raise SystemExit("ERROR: the playbook card is missing; run board.py start first")
    playbook = task["id"]
    graph.model = graph.model or task.get("model_override")  # the strategy model chosen at start
    designs = [card(graph, f"campaign-{cid}", f"Campaign: design {cid}", "campaign", parents=[playbook],
                    skills=["oma-campaigns", "oma-agents"], campaign=cid) for cid in ids]
    existing = find("provision")
    provision = card(graph, "provision", TITLES["provision"], "provision", parents=designs,
                     skills=["oma-campaigns"], ids=" ".join(ids), runtime="45m")
    if existing:
        for design in designs:
            link(design, provision)


def merge_config(home: Path, fragment: Path) -> dict:
    """Parallel cards each own some config keys; merge them one at a time so no card overwrites another."""
    config_path = home / "oma" / "brand" / "config.yaml"
    lock = config_path.with_name(".config.lock")
    deadline = time.monotonic() + 300
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise SystemExit(f"ERROR: {lock} is held by another card; retry shortly")
            time.sleep(1)
    try:
        yaml = YAML(typ="safe", pure=True)
        yaml.default_flow_style = False
        config = yaml.load(config_path.read_text(encoding="utf-8")) or {}
        update = yaml.load(fragment.read_text(encoding="utf-8")) or {}
        for key, value in update.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        temp = config_path.with_suffix(".yaml.part")
        with temp.open("w", encoding="utf-8") as stream:
            yaml.dump(config, stream)
        temp.replace(config_path)
        return {"merged": sorted(update)}
    finally:
        lock.unlink(missing_ok=True)


def status() -> dict:
    cards = [{"id": t["id"], "status": t.get("status"), "title": t.get("title"),
              "failure": t.get("last_failure_error")} for t in _ours()]
    counts: dict[str, int] = {}
    for item in cards:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"board": BOARD, "counts": counts, "cards": cards}


def _graph_result(action):
    def run(graph: Graph, args) -> dict:
        action(graph, args)
        return {"board": BOARD, "cards": graph.created}
    return run


# command -> (extra arguments, handler)
COMMANDS = {
    "start": ((("--url", {"required": True}), ("--repo", {}), ("--synthesis-model", {})),
              _graph_result(lambda graph, args: start(graph, args.url, args.repo))),
    "repository": ((("url", {}),), _graph_result(lambda graph, args: repository(graph, args.url))),
    "fanout": ((), _graph_result(lambda graph, args: fanout(graph))),
    "campaigns": ((("ids", {"nargs": "+"}),), _graph_result(lambda graph, args: campaigns(graph, args.ids))),
    "merge-config": ((("file", {"type": Path}),), lambda graph, args: merge_config(graph.home, args.file)),
    "status": ((), lambda graph, args: status()),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (extra, _) in COMMANDS.items():
        command = sub.add_parser(name)
        command.add_argument("home", type=Path)
        for flag, options in extra:
            command.add_argument(flag, **options)
    args = parser.parse_args(argv)
    graph = Graph(args.home.resolve(), getattr(args, "synthesis_model", None))
    print(json.dumps(COMMANDS[args.command][1](graph, args), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
