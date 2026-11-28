#!/usr/bin/env python3
"""Run OMA onboarding as a Kanban card graph on the default profile, in stages.

Usage (with the Hermes environment's Python):
  board.py start <home> --url URL [--synthesis-model MODEL]
  board.py confirm <home>                the user confirmed: add the deferred stage
  board.py competitors <home>            the user asked for competitor research: add that stage
  board.py ads <home>                    the user asked for ads: the brand's, and the researched competitors'
  board.py status <home>
Run by the cards:
  board.py brief <home> <card-key>       a slot card prints its instructions once its target is known
  board.py slots <home>                  the discovery card checks the index and records each slot's target
  board.py campaigns <home> <plan.yaml>  the playbook card saves its campaigns, with their agents, as drafts
  board.py merge-config <home> <file>    merge a YAML fragment into oma/brand/config.yaml under a lock
  board.py provision <home> [--when-ready]  install and start the enriched campaigns (run by the cron job)

``start`` creates the first stage: brand core, market, the brand's own posts (its ad libraries
recorded as deferred), and the playbook, which also names the campaigns and their agents and saves them
as drafts. Onboarding then waits for the user's confirmation. ``confirm``, run from the onboarding
session, adds screenshots and assets, the design system, a playbook refresh, and one card per campaign
that enriches the draft with full agent definitions; the campaigns are then installed and started. Two
stages run only when the user asks: ``competitors`` adds discovery, profiles of the top five direct
competitors, their posts, and the landscape; ``ads`` collects the brand's ads and, when competitor
research is on the board, the five competitors' ads and a landscape update with them.

Card workers cannot change the board (Kanban fences the commands a worker runs), so a card whose
target comes from an earlier card is a fixed slot: its body tells the worker to run ``brief``, which
renders the instructions from what the earlier cards saved, or says the slot is empty so the worker
completes it at once. Installing a campaign creates its board, so ``confirm`` also registers a
script-only cron job that runs ``provision --when-ready`` every ten minutes; once every campaign card is
done it installs and starts the campaigns and removes itself. Every card is a fresh worker that finishes with its
stage's check; cards carry idempotency keys, so each command is safe to run again.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from ruamel.yaml import YAML

BOARD = "oma-onboarding"
SKILLS = Path(__file__).resolve().parents[2]
CARDS = Path(__file__).resolve().parents[1] / "references" / "cards"
JUDGMENT = {"design-system", "landscape", "landscape-ads", "playbook", "playbook-refresh", "campaign"}
CREATOR = "oma-onboarding"
CAMPAIGN_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CAMPAIGN_HELPER = SKILLS / "oma-campaigns" / "scripts" / "campaign.py"
CRON_NAME, CRON_SCRIPT = "OMA onboarding: install campaigns", "oma-onboarding-provision.py"
CRON_WRAPPER = '''"""Written by oma-onboarding board.py confirm: install the designed campaigns once their cards are done."""
import runpy
import sys

sys.exit(runpy.run_path({board!r})["main"](["provision", {home!r}, "--when-ready"]))
'''


MAX_CANDIDATES, COMPETITORS = 30, 5  # the competitor stage; its landscape card validates with --full 5 --light 0
CAMPAIGN_SLOTS = 5


@dataclass(frozen=True)
class Spec:
    """One card of the graph. ``slot`` names the resolver that fills it when the card starts."""
    key: str
    title: str
    template: str
    parents: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    runtime: str = "60m"
    values: dict = field(default_factory=dict)
    slot: tuple[str, int] | None = None


@dataclass
class Graph:
    home: Path
    model: str | None = None
    created: list[dict] = field(default_factory=list)

    @property
    def brand(self) -> Path:
        return self.home / "oma" / "brand"

    @property
    def state_path(self) -> Path:
        return self.brand / ".onboarding.yaml"

    @property
    def values(self) -> dict:
        return {"home": str(self.home), "brand": str(self.brand),
                "board": str(Path(__file__).resolve()), "python": sys.executable,
                "collect": str(SKILLS / "oma-creatives" / "scripts" / "collect.py"),
                "sources_template": str(SKILLS / "oma-creatives" / "references" / "sources.md"),
                "validate_creatives": str(SKILLS / "oma-creatives" / "scripts" / "validate_creatives.py"),
                "validate_competitors": str(SKILLS / "oma-competitors" / "scripts" / "validate_competitors.py"),
                "campaign": str(SKILLS / "oma-campaigns" / "scripts" / "campaign.py")}


def _yaml() -> YAML:
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    return yaml


def _load(path: Path) -> dict:
    return (_yaml().load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}


def _dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".part")
    with temp.open("w", encoding="utf-8") as stream:
        _yaml().dump(data, stream)
    temp.replace(path)


def first_stage(url: str) -> list[Spec]:
    """The first stage, which ``start`` creates; parents first."""
    return [
        Spec("brand-core", "Brand: website, channels, integrations, docs", "brand-core", skills=("oma-brand",),
             values={"url": url}),
        Spec("market", "Brand: market research", "market", ("brand-core",), ("oma-brand",)),
        Spec("creatives-own", "Creatives: the brand's own posts and summary", "creatives-posts", ("brand-core",),
             ("oma-creatives",), "120m", {"target": "own", "name": "the brand"}),
        Spec("playbook", "Strategy: playbook and campaigns", "playbook",
             ("brand-core", "market", "creatives-own"), ("oma-playbook",)),
    ]


def confirmed_stage() -> list[Spec]:
    """The stage ``confirm`` adds; its parents include cards of the first stage."""
    return [
        Spec("visuals", "Brand: screenshots and visual assets", "visuals", ("brand-core",), ("oma-brand",)),
        Spec("design-system", "Brand: design system", "design-system", ("visuals", "creatives-own"), ("oma-brand",)),
        Spec("playbook-refresh", "Strategy: playbook refresh", "playbook-refresh", ("playbook", "design-system"),
             ("oma-playbook",)),
        *(Spec(f"campaign-{n}", f"Campaign {n}: agents and plan", "campaign", ("playbook-refresh",),
               ("oma-campaigns", "oma-agents"), slot=("campaign", n)) for n in range(1, CAMPAIGN_SLOTS + 1)),
    ]


PROFILES = tuple(f"competitor-{n}" for n in range(1, COMPETITORS + 1))


def competitor_research() -> list[Spec]:
    """On request: discovery, five profiles, their posts (ads deferred), and the landscape."""
    specs = [Spec("discovery", "Competitors: discover, score and tier", "discovery", ("brand-core",),
                  ("oma-competitors",)),
             *(Spec(key, f"Competitor {n}: profile and teardown", "competitor", ("discovery",), ("oma-competitors",),
                    slot=("profile", n)) for n, key in enumerate(PROFILES, 1))]
    specs += [Spec(f"creatives-competitor-{n}-posts", f"Creatives: competitor {n} posts and summary", "creatives-posts",
                   (profile,), ("oma-creatives",), "120m", slot=("creatives", n)) for n, profile in enumerate(PROFILES, 1)]
    specs.append(Spec("landscape", "Competitors: landscape", "landscape",
                      ("creatives-own", *PROFILES, *(f"creatives-competitor-{n}-posts" for n in range(1, COMPETITORS + 1))),
                      ("oma-competitors",)))
    return specs


def own_ads() -> list[Spec]:
    """On request: the brand's ad libraries, replacing the deferred records."""
    return [Spec("creatives-own-ads", "Creatives: the brand's own ads", "creatives-ads", ("creatives-own",),
                 ("oma-creatives",), "120m", {"target": "own", "name": "the brand"})]


def competitor_ads() -> list[Spec]:
    """Part of the ads stage once competitor research is on the board: five competitors' ads, a landscape update."""
    ads = [Spec(f"creatives-competitor-{n}-ads", f"Creatives: competitor {n} ads", "creatives-ads",
                (f"creatives-competitor-{n}-posts", "landscape"), ("oma-creatives",), "120m", slot=("creatives", n))
           for n in range(1, COMPETITORS + 1)]
    return [*ads, Spec("landscape-ads", "Competitors: landscape with ads", "landscape-ads",
                       ("creatives-own-ads", *(spec.key for spec in ads)), ("oma-competitors",))]


def requested(state: dict) -> list[Spec]:
    """Every card the requested stages call for, parents first."""
    specs = first_stage(state.get("url", ""))
    specs += confirmed_stage() if state.get("confirmed_at") else []
    specs += competitor_research() if state.get("competitors_at") else []
    specs += own_ads() if state.get("ads_at") else []
    specs += competitor_ads() if state.get("competitor_ads_at") else []
    return specs


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


def render(template: str, values: dict, *, rules: bool = True) -> str:
    text = (CARDS / f"{template}.md").read_text(encoding="utf-8")
    if rules:
        text += (CARDS / "_rules.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _body(graph: Graph, spec: Spec) -> str:
    if spec.slot is None:
        return render(spec.template, {**graph.values, **spec.values})
    return render("_slot", {**graph.values, "title": spec.title, "key": spec.key}, rules=False)  # brief adds them


def create(graph: Graph, spec: Spec, ids: dict[str, str]) -> str:
    """Create (or, by idempotency key, find) one card; returns its id."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(_body(graph, spec))
    args = ["create", spec.title, "--assignee", "default", "--body-file", handle.name,
            "--idempotency-key", f"onboarding:{spec.key}", "--max-runtime", spec.runtime, "--max-retries", "2",
            "--created-by", CREATOR, "--json"]
    for parent in spec.parents:
        args += ["--parent", ids[parent]]
    for skill in spec.skills:
        args += ["--skill", skill]
    if graph.model and spec.template in JUDGMENT:
        args += ["--model", graph.model]
    try:
        created = json.loads(kanban(*args))
    finally:
        os.unlink(handle.name)
    graph.created.append({"key": spec.key, "id": created["id"], "title": spec.title})
    return created["id"]


def _create_all(graph: Graph, specs: list[Spec], ids: dict[str, str]) -> dict[str, str]:
    for spec in specs:
        ids[spec.key] = create(graph, spec, ids)
    return ids


def start(graph: Graph, url: str) -> dict:
    state = _load(graph.state_path)
    _dump(graph.state_path, {**state, "url": url, **({"synthesis_model": graph.model} if graph.model else {})})
    ensure_board()
    _create_all(graph, first_stage(url), {})
    return {"board": BOARD, "cards": graph.created, "next": "waits for the user's confirmation (board.py confirm)"}


def _extend(graph: Graph, *flags: str) -> list[dict]:
    """Request later stages; returns the cards they add. Cards already on the board are found by their keys."""
    state = _load(graph.state_path)
    if not state.get("url"):
        raise SystemExit("ERROR: onboarding has not started; run board.py start first")
    before = {spec.key for spec in requested(state)}
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    state = {**state, **{flag: state.get(flag) or now for flag in flags}}
    _dump(graph.state_path, state)
    graph.model = graph.model or state.get("synthesis_model")
    ensure_board()
    _create_all(graph, requested(state), {})
    return [card for card in graph.created if card["key"] not in before]


def confirm(graph: Graph) -> dict:
    """On the user's confirmation: the deferred stage joins the board, and provisioning is scheduled."""
    cards = _extend(graph, "confirmed_at")
    return {"board": BOARD, "cards": cards, "provisioning_job": _schedule_provisioning(graph)}


def competitors(graph: Graph) -> dict:
    """On request: competitor research joins the board. It never collects ads."""
    return {"board": BOARD, "cards": _extend(graph, "competitors_at")}


def ads(graph: Graph) -> dict:
    """On request: the brand's ads, and the researched competitors' ads, join the board."""
    researched = _load(graph.state_path).get("competitors_at")
    return {"board": BOARD, "cards": _extend(graph, "ads_at", *(["competitor_ads_at"] if researched else []))}


def _schedule_provisioning(graph: Graph) -> str:
    """A no-agent cron job runs ``provision`` outside the card fence; it ends itself after one attempt."""
    state = _load(graph.state_path)
    if state.get("provisioning_job") or "provisioned" in state:
        return state.get("provisioning_job", "")
    scripts = graph.home / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / CRON_SCRIPT).write_text(CRON_WRAPPER.format(board=str(Path(__file__).resolve()), home=str(graph.home)),
                                       encoding="utf-8")
    done = subprocess.run([_hermes(), "cron", "create", "every 10m", "--name", CRON_NAME, "--script", CRON_SCRIPT,
                           "--no-agent", "--deliver", "local", "--catch-up", "off"],
                          capture_output=True, text=True, check=False, timeout=60)
    found = re.search(r"Created job:\s*(?:\x1b\[[0-9;]*m)?([\w-]+)", done.stdout or "")
    if done.returncode != 0 or not found:
        raise RuntimeError(f"hermes cron create failed: {(done.stderr or done.stdout).strip()[:400]}")
    _dump(graph.state_path, {**_load(graph.state_path), "provisioning_job": found.group(1)})
    return found.group(1)


def _index(graph: Graph) -> dict:
    path = graph.brand / "research" / "competitors" / "index.yaml"
    if not path.is_file():
        raise SystemExit(f"ERROR: {path} is missing; a discovery card writes it before any competitor card starts")
    return _load(path)


def _entry(c: dict) -> dict:
    return {"id": c["id"], "name": c.get("name") or c["id"]}


def slots(graph: Graph) -> dict:
    """Check the index against the competitor stage's caps and record which competitor each slot takes."""
    index = _index(graph)
    candidates = index.get("competitors") or []
    direct = [_entry(c) for c in candidates if c.get("tier") == "direct" and c.get("depth") == "full"]
    deeper = [c["id"] for c in candidates if c.get("depth") == "light" or (c.get("tier") != "direct" and c.get("depth") == "full")]
    problems = [(len(candidates) > MAX_CANDIDATES, f"index.yaml lists {len(candidates)} candidates; score at most "
                 f"{MAX_CANDIDATES}, so keep the strongest and drop the rest"),
                (len(direct) > COMPETITORS, f"index.yaml has {len(direct)} direct competitors at `full` depth for "
                 f"{COMPETITORS} slots; keep the top {COMPETITORS} and set the rest to `index_only`"),
                (bool(deeper), f"only direct competitors are researched; set {', '.join(deeper)} to `index_only`"),
                (bool(index.get("references")), "references are not collected; remove them from index.yaml")]
    for failed, message in problems:
        if failed:
            raise SystemExit(f"ERROR: {message}")
    unprofiled = [dict(e) for e in direct if not (graph.brand / "research/competitors" / e["id"] / "profile.md").is_file()]
    state = _load(graph.state_path)
    _dump(graph.state_path, {**state, "assigned": {"profiles": unprofiled, "creatives": direct}})  # copies: no aliases
    return {"direct": [e["id"] for e in direct], "new_profiles": [e["id"] for e in unprofiled]}


def _nth(items: list, n: int, kind: str) -> tuple[dict | None, str]:
    if n <= len(items):
        return items[n - 1], ""
    return None, f"the {kind} list has {len(items)} entr{'y' if len(items) == 1 else 'ies'}, so slot {n} has no target"


def _assigned(graph: Graph, kind: str) -> list:
    assigned = _load(graph.state_path).get("assigned")
    if assigned is None:
        raise SystemExit("ERROR: no slot targets are recorded; the discovery card runs board.py slots first")
    return list(assigned.get(kind) or [])


def _competitor(entry: dict | None) -> dict | None:
    return {"target": entry["id"], "name": entry["name"], "depth": "full"} if entry else None


def _resolve_profile(graph: Graph, n: int) -> tuple[dict | None, str]:
    entry, why = _nth(_assigned(graph, "profiles"), n, "unprofiled direct competitor")
    return _competitor(entry), why


def _resolve_creatives(graph: Graph, n: int) -> tuple[dict | None, str]:
    entry, why = _nth(_assigned(graph, "creatives"), n, "direct full-depth competitor")
    return _competitor(entry), why


def _resolve_campaign(graph: Graph, n: int) -> tuple[dict | None, str]:
    entry, why = _nth(list(_load(graph.state_path).get("campaigns") or []), n, "playbook's campaign")
    return ({"campaign": entry} if entry else None), why


RESOLVERS = {"profile": _resolve_profile, "creatives": _resolve_creatives, "campaign": _resolve_campaign}


def brief(graph: Graph, key: str) -> str:
    """The instructions of card *key*, rendered from what the earlier cards saved."""
    url = _load(graph.state_path).get("url", "")
    every = first_stage(url) + confirmed_stage() + competitor_research() + own_ads() + competitor_ads()
    spec = next((s for s in every if s.key == key), None)
    if spec is None:
        raise SystemExit(f"ERROR: no onboarding card has the key {key!r}")
    if spec.slot is None:
        return render(spec.template, {**graph.values, **spec.values})
    kind, n = spec.slot
    values, why = RESOLVERS[kind](graph, n)
    if values is None:
        return (f"# {spec.title}\n\nThis slot is empty: {why}. Complete this card now with the summary "
                f"\"Empty slot: {why}.\" Do no other work.\n")
    return render(spec.template, {**graph.values, **spec.values, **values})


def _plan_problems(plan: list) -> list[str]:
    problems = [] if 1 <= len(plan) <= CAMPAIGN_SLOTS else [f"give 1 to {CAMPAIGN_SLOTS} campaigns"]
    ids = [c.get("id") for c in plan if isinstance(c, dict)]
    if len(ids) != len(plan) or len(set(ids)) != len(ids):
        problems.append("every campaign needs a distinct `id`")
    for c in (c for c in plan if isinstance(c, dict)):
        roles = c.get("agents") or []
        if not CAMPAIGN_ID.match(str(c.get("id", ""))):
            problems.append(f"{c.get('id')!r}: the id must be lowercase and hyphenated")
        if not (str(c.get("name") or "").strip() and str(c.get("description") or "").strip()):
            problems.append(f"{c.get('id')}: give a name and a one-line description")
        if not {"orchestrator", "publisher"} <= set(roles) or not all(CAMPAIGN_ID.match(str(r)) for r in roles):
            problems.append(f"{c.get('id')}: list agent roles in lowercase, including orchestrator and publisher")
    return problems


def campaigns(graph: Graph, plan_path: Path) -> dict:
    """Save the playbook's campaigns as drafts in ``oma/campaigns/``: a name, a description, and the agents' roles."""
    plan = _load(plan_path).get("campaigns") or []
    problems = _plan_problems(plan)
    if problems:
        raise SystemExit("ERROR: " + "; ".join(problems))
    saved = []
    for c in plan:
        cid, record = c["id"], graph.home / "oma" / "campaigns" / c["id"] / "config.yaml"
        if not _load(record).get("installation_state"):  # never touch a campaign that is installed or installing
            _dump(record, {"id": cid, "name": c["name"].strip(), "description": c["description"].strip(),
                           "orchestrator": f"{cid}__orchestrator", "agents": [f"{cid}__{role}" for role in c["agents"]]})
            checked = _campaign(graph.home, "validate", "campaign", str(record))
            if "error" in checked:
                raise SystemExit(f"ERROR: the draft {record} does not validate: {checked['error']}")
        saved.append({"id": cid, "name": c["name"], "agents": [f"{cid}__{role}" for role in c["agents"]]})
    _dump(graph.state_path, {**_load(graph.state_path), "campaigns": [c["id"] for c in plan]})
    return {"drafts": saved}


def _campaign(home: Path, *args: str) -> dict:
    """The campaign helper against this onboarding's home: a cron script's environment carries no HERMES_HOME."""
    done = subprocess.run([sys.executable, str(CAMPAIGN_HELPER), *args], capture_output=True, text=True, check=False,
                          timeout=900, env={**os.environ, "HERMES_HOME": str(home)})
    if done.returncode != 0:
        return {"error": (done.stderr or done.stdout).strip()[-600:]}
    return json.loads(done.stdout or "{}")


def _install(graph: Graph, cid: str) -> dict:
    """Install an enriched campaign: its staged definition replaces the draft, then it is installed and started."""
    record = graph.home / "oma" / "campaigns" / cid / "config.yaml"
    definition = graph.home / "oma" / "staging" / f"{cid}.yaml"
    draft = record.is_file() and not _load(record).get("installation_state")
    if not definition.is_file() and (draft or not record.is_file()):
        return {"id": cid, "state": "draft" if draft else "missing",
                "error": f"{definition} is missing; its card did not enrich it"}
    if draft:
        temp = record.with_name("config.yaml.part")
        temp.write_text(definition.read_text(encoding="utf-8"), encoding="utf-8")
        temp.replace(record)
    home = graph.home
    result = _campaign(home, "install", cid) if record.is_file() else _campaign(home, "create", str(definition))
    status = _campaign(home, "status", cid)
    if status.get("state") == "installed" and status.get("lifecycle_state") != "resumed":
        result = _campaign(home, "lifecycle", cid, "resumed")
        status = _campaign(home, "status", cid)
    return {"id": cid, "state": status.get("state", "unknown"), "lifecycle": status.get("lifecycle_state"),
            "kanban_board": status.get("kanban_board"), "agents": status.get("agents", []),
            "integrations": status.get("integrations", []),
            **({"error": result.get("error") or status.get("error")} if "error" in result or "error" in status else {})}


def provision(graph: Graph, when_ready: bool) -> dict:
    """Install and start the campaigns once every campaign card is done; report each one."""
    state = _load(graph.state_path)
    if when_ready and "provisioned" in state:
        _end_job(graph)
        return {"provisioned": state["provisioned"]}
    statuses = {t.get("title"): t.get("status") for t in _ours()}
    open_designs = sorted(spec.title for spec in confirmed_stage()
                          if spec.template == "campaign" and statuses.get(spec.title) != "done")
    ids = list(state.get("campaigns") or [])
    if open_designs or not ids:
        waiting = open_designs or ["the playbook card's campaigns (board.py campaigns)"]
        if when_ready:
            return {"waiting": waiting}
        raise SystemExit(f"ERROR: not ready to provision; waiting for {', '.join(waiting)}")
    results = [_install(graph, cid) for cid in ids]
    _dump(graph.state_path, {**_load(graph.state_path), "provisioned": {r["id"]: r["state"] for r in results}})
    _end_job(graph)
    return {"campaigns": results, "complete": all(r["state"] == "installed" for r in results)}


def _end_job(graph: Graph) -> None:
    """One attempt is enough: ``status`` reports a failure, and the onboarding session reruns ``provision``."""
    state = _load(graph.state_path)
    job = state.pop("provisioning_job", None)
    if job:
        subprocess.run([_hermes(), "cron", "remove", job], capture_output=True, text=True, check=False, timeout=60)
        _dump(graph.state_path, state)


def merge_config(home: Path, fragment: Path) -> dict:
    """Parallel cards each own some config keys; merge them one at a time so no card overwrites another."""
    config_path = home / "oma" / "brand" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
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
        config = _load(config_path)
        update = _load(fragment)
        for key, value in update.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        _dump(config_path, config)
        return {"merged": sorted(update)}
    finally:
        lock.unlink(missing_ok=True)


def _ours() -> list[dict]:
    return [task for task in json.loads(kanban("list", "--json") or "[]") if task.get("created_by") == CREATOR]


def status(graph: Graph) -> dict:
    cards = [{"id": t["id"], "status": t.get("status"), "title": t.get("title"),
              "failure": t.get("last_failure_error")} for t in _ours()]
    counts: dict[str, int] = {}
    for item in cards:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    state = _load(graph.state_path)
    first = {spec.title for spec in first_stage(state.get("url", ""))}
    first_done = bool(cards) and all(c["status"] == "done" for c in cards if c["title"] in first)
    return {"board": BOARD, "counts": counts, "cards": cards,
            "stage": "confirmed" if state.get("confirmed_at") else "first",
            "requested": [name for name, flag in (("competitors", "competitors_at"), ("ads", "ads_at")) if state.get(flag)],
            "awaiting_confirmation": first_done and not state.get("confirmed_at"),
            "campaigns": state.get("campaigns", []), "provisioned": state.get("provisioned", {})}


# command -> (extra arguments, handler); ``brief`` prints Markdown, the rest JSON
COMMANDS = {
    "start": ((("--url", {"required": True}), ("--synthesis-model", {})), lambda graph, args: start(graph, args.url)),
    "confirm": ((), lambda graph, args: confirm(graph)),
    "competitors": ((), lambda graph, args: competitors(graph)),
    "ads": ((), lambda graph, args: ads(graph)),
    "brief": ((("key", {}),), lambda graph, args: brief(graph, args.key)),
    "slots": ((), lambda graph, args: slots(graph)),
    "campaigns": ((("plan", {"type": Path}),), lambda graph, args: campaigns(graph, args.plan)),
    "merge-config": ((("file", {"type": Path}),), lambda graph, args: merge_config(graph.home, args.file)),
    "provision": ((("--when-ready", {"action": "store_true"}),), lambda graph, args: provision(graph, args.when_ready)),
    "status": ((), lambda graph, args: status(graph)),
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
    result = COMMANDS[args.command][1](graph, args)
    print(result if isinstance(result, str) else json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
