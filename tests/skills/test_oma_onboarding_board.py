"""Onboarding runs as a Kanban card graph: the board script's shape, idempotency, slot cards and config merges.

A fake ``hermes`` on PATH stores cards in a JSON file, so the real script runs unchanged offline. Like the
real Kanban fence, it refuses every call from a card worker's commands (``HERMES_DELEGATED_CHILD_CONTEXT``).
"""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view

FAKE_HERMES = r'''#!PYTHON
import json, os, sys
if sys.argv[1] == "--print-runtime-command":  # the campaign helper's launcher; not a Kanban call
    print(json.dumps([sys.executable, "-m", sys.argv[3]])); sys.exit(0)
if os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT"):
    print("kanban: delegate_task child contexts cannot mutate Kanban tasks or boards", file=sys.stderr); sys.exit(1)
state_path = os.environ["FAKE_KANBAN_STATE"]
state = json.load(open(state_path)) if os.path.exists(state_path) else {"boards": [], "tasks": []}
args = sys.argv[1:]
if args[0] == "cron":
    state.setdefault("cron", []).append(args[1:]); json.dump(state, open(state_path, "w"))
    if args[1] == "create":
        print("Created job: \x1b[33mjob_1\x1b[0m")
    sys.exit(0)
assert args[0] == "kanban"
args = args[1:]
if args[:2] == ["boards", "list"]:
    print("  ".join(state["boards"]) or "default"); sys.exit(0)
if args[:2] == ["boards", "create"]:
    state["boards"].append(args[2]); json.dump(state, open(state_path, "w")); sys.exit(0)
assert args[0] == "--board"
args = args[2:]
verb, rest = args[0], args[1:]
def opt(name, many=False):
    found = [rest[i + 1] for i, a in enumerate(rest) if a == name]
    return found if many else (found[0] if found else None)
if verb == "create":
    key = opt("--idempotency-key")
    for task in state["tasks"]:
        if key and task["key"] == key:
            print(json.dumps(task)); sys.exit(0)
    task = {"id": f"t_{len(state['tasks']) + 1}", "title": rest[0], "key": key, "created_by": opt("--created-by"),
            "status": "todo", "parents": opt("--parent", True), "skills": opt("--skill", True),
            "model_override": opt("--model"), "body": open(opt("--body-file")).read()}
    state["tasks"].append(task)
    json.dump(state, open(state_path, "w"))
    print(json.dumps(task))
elif verb == "list":
    print(json.dumps([{k: v for k, v in t.items() if k != "key"} for t in state["tasks"]]))
'''


@pytest.fixture
def board(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = Path(json.loads(skill_view("oma/oma-onboarding"))["skill_dir"])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "hermes"
    fake.write_text(FAKE_HERMES.replace("PYTHON", sys.executable))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "kanban.json"
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_KANBAN_STATE": str(state)}
    home = tmp_path / "home"
    (home / "oma" / "brand").mkdir(parents=True)

    def cli(*args, worker=True):
        """Run board.py; ``worker`` runs it the way a card worker does, behind the Kanban fence."""
        fence = {"HERMES_DELEGATED_CHILD_CONTEXT": str(tmp_path)} if worker else {}
        return subprocess.run([sys.executable, str(skill / "scripts" / "board.py"), *args], capture_output=True,
                              text=True, env={**env, "HERMES_HOME": str(home), **fence}, check=False)

    def run(*args, worker=True):
        done = cli(*args, worker=worker)
        assert done.returncode == 0, done.stderr
        return done.stdout

    def tasks():
        return {t["title"]: t for t in json.loads(state.read_text())["tasks"]}

    def finish(*titles):
        data = json.loads(state.read_text())
        for task in data["tasks"]:
            if task["title"] in titles:
                task["status"] = "done"
        state.write_text(json.dumps(data))

    def cron():
        return json.loads(state.read_text()).get("cron", [])

    return SimpleNamespace(cli=cli, run=run, tasks=tasks, home=home, finish=finish, cron=cron,
                           script=skill / "scripts" / "board.py", env=env)


def _start(run, home, *extra):
    return json.loads(run("start", str(home), "--url", "https://brand.example/", *extra, worker=False))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _parents(cards):
    ids = {t["id"]: t["title"] for t in cards.values()}
    return lambda title: {ids[p] for p in cards[title]["parents"]}


@pytest.mark.platforms("posix")
def test_start_builds_the_first_stage_and_waits_without_scheduling_anything(board):
    run, tasks, home = board.run, board.tasks, board.home
    _start(run, home)
    first = tasks()
    _start(run, home)
    assert tasks().keys() == first.keys(), "a second start returns the same cards"

    parents = _parents(first)
    assert len(first) == 4 and first["Brand: website, channels, integrations, docs"]["parents"] == []
    assert "board.py" in first["Strategy: playbook and campaigns"]["body"]
    assert parents("Strategy: playbook and campaigns") == {
        "Brand: website, channels, integrations, docs", "Brand: market research",
        "Creatives: the brand's own posts and summary"}
    assert not [title for title in first if "ompetitor" in title or "epository" in title]
    own = first["Creatives: the brand's own posts and summary"]["body"]
    assert "--defer" in own and "{" not in own
    assert board.cron() == []

    board.finish(*first)
    status = json.loads(run("status", str(home), worker=False))
    assert status["stage"] == "first" and status["awaiting_confirmation"] is True


@pytest.mark.platforms("posix")
def test_confirm_adds_the_deferred_stage_once_and_schedules_provisioning(board):
    run, tasks, home = board.run, board.tasks, board.home
    _start(run, home, "--synthesis-model", "strong/model")
    run("confirm", str(home), worker=False)
    cards = tasks()
    run("confirm", str(home), worker=False)
    assert tasks().keys() == cards.keys() and len(board.cron()) == 1, "a second confirm adds nothing"

    parents = _parents(cards)
    assert len(cards) == 12 and not [title for title in cards if "ompetitor" in title or " ads" in title]
    assert parents("Brand: design system") == {"Brand: screenshots and visual assets",
                                               "Creatives: the brand's own posts and summary"}
    assert parents("Strategy: playbook refresh") == {"Strategy: playbook and campaigns", "Brand: design system"}
    assert parents("Campaign 5: agents and plan") == {"Strategy: playbook refresh"}
    assert cards["Strategy: playbook refresh"]["model_override"] == "strong/model"
    create = board.cron()[0]
    assert create[:2] == ["create", "every 10m"] and "--no-agent" in create
    assert "--when-ready" in (home / "scripts" / create[create.index("--script") + 1]).read_text()
    assert json.loads(run("status", str(home), worker=False))["stage"] == "confirmed"


@pytest.mark.platforms("posix")
def test_competitor_research_joins_only_on_request_and_fills_its_slots_behind_the_fence(board):
    cli, run, tasks, home = board.cli, board.run, board.tasks, board.home
    assert cli("competitors", str(home), worker=False).returncode != 0, "it needs a started board"
    _start(run, home)
    added = json.loads(run("competitors", str(home), worker=False))["cards"]
    cards = tasks()
    assert json.loads(run("competitors", str(home), worker=False))["cards"] == [], "a second request adds nothing"
    assert tasks().keys() == cards.keys() and board.cron() == []
    parents = _parents(cards)
    assert len(added) == 12 and not [title for title in cards if title.endswith(" ads")], "ads are their own stage"
    assert parents("Competitors: discover, score and tier") == {"Brand: website, channels, integrations, docs"}
    assert parents("Creatives: competitor 3 posts and summary") == {"Competitor 3: profile and teardown"}
    assert parents("Competitors: landscape") >= {
        "Creatives: competitor 5 posts and summary", "Competitor 5: profile and teardown",
        "Creatives: the brand's own posts and summary"}

    brand = home / "oma/brand"
    direct = lambda ident, depth="full": {"id": ident, "name": ident.title(), "tier": "direct", "depth": depth}
    for index in ({"competitors": [direct(f"c{n}") for n in range(6)]},
                  {"competitors": [direct("gamma"), {"id": "canva", "tier": "indirect", "depth": "light"}]},
                  {"competitors": [direct(f"c{n}", "index_only") for n in range(31)]},
                  {"competitors": [direct("gamma")], "references": [{"id": "notion"}]}):
        _write(brand / "research/competitors/index.yaml", index)
        assert cli("slots", str(home)).returncode != 0, index
    (brand / "research/competitors/gamma").mkdir(parents=True)
    (brand / "research/competitors/gamma/profile.md").write_text("# Gamma\n")
    _write(brand / "research/competitors/index.yaml", {"competitors": [direct(i) for i in ("gamma", "pitch", "tome")]})
    assert json.loads(run("slots", str(home)))["new_profiles"] == ["pitch", "tome"]
    assert "Pitch" in run("brief", str(home), "competitor-1") and "Tome" in run("brief", str(home), "competitor-2")
    assert "slot is empty" in run("brief", str(home), "competitor-3")
    posts = run("brief", str(home), "creatives-competitor-1-posts")
    assert "Gamma" in posts and "--defer" in posts
    assert "slot is empty" in run("brief", str(home), "creatives-competitor-4-posts")


@pytest.mark.platforms("posix")
def test_one_ads_request_collects_the_brands_and_the_researched_competitors_ads(board):
    run, tasks, home = board.run, board.tasks, board.home
    _start(run, home)
    own = json.loads(run("ads", str(home), worker=False))["cards"]
    assert [card["title"] for card in own] == ["Creatives: the brand's own ads"], "no competitors researched yet"

    research = [card["title"] for card in json.loads(run("competitors", str(home), worker=False))["cards"]]
    assert not [title for title in research if title.endswith(" ads")], "competitor research never collects ads"
    again = [card["title"] for card in json.loads(run("ads", str(home), worker=False))["cards"]]
    assert "Creatives: competitor 2 ads" in again and "Competitors: landscape with ads" in again
    assert "Creatives: the brand's own ads" not in again, "a repeated request adds only what is new"

    cards = tasks()
    parents = _parents(cards)
    assert parents("Creatives: competitor 2 ads") == {"Creatives: competitor 2 posts and summary", "Competitors: landscape"}
    assert parents("Competitors: landscape with ads") == {
        "Creatives: the brand's own ads", *(f"Creatives: competitor {n} ads" for n in range(1, 6))}
    assert "replaces the deferred records" in cards["Creatives: the brand's own ads"]["body"]
    assert json.loads(run("ads", str(home), worker=False))["cards"] == []
    assert json.loads(run("status", str(home), worker=False))["requested"] == ["competitors", "ads"]


@pytest.mark.platforms("posix")
def test_ads_requested_with_competitor_research_on_the_board_collect_both_at_once(board):
    run, home = board.run, board.home
    _start(run, home)
    run("competitors", str(home), worker=False)
    added = [card["title"] for card in json.loads(run("ads", str(home), worker=False))["cards"]]
    assert {"Creatives: the brand's own ads", "Creatives: competitor 5 ads", "Competitors: landscape with ads"} <= set(added)


@pytest.mark.platforms("posix")
def test_the_playbook_saves_named_campaigns_as_drafts_that_the_job_installs_once_enriched(board):
    cli, run, home = board.cli, board.run, board.home
    _start(run, home)
    plan = home / "plan.yaml"
    _write(plan, {"campaigns": [{"id": "seo", "name": "Search", "description": "Capture search intent.",
                                 "agents": ["orchestrator", "writer", "publisher"]},
                                {"id": "community", "name": "Community", "description": "Grow the Discord.",
                                 "agents": ["orchestrator", "responder", "publisher"]}]})
    for bad in ({"campaigns": [{"id": "seo", "name": "Search", "description": "x", "agents": ["orchestrator", "writer"]}]},
                {"campaigns": [{"id": "Bad_ID", "name": "x", "description": "x", "agents": ["orchestrator", "publisher"]}]}):
        _write(home / "bad.yaml", bad)
        assert cli("campaigns", str(home), str(home / "bad.yaml")).returncode != 0, bad
    drafts = json.loads(run("campaigns", str(home), str(plan)))["drafts"]
    assert drafts[1]["agents"] == ["community__orchestrator", "community__responder", "community__publisher"]
    record = YAML(typ="safe").load((home / "oma/campaigns/seo/config.yaml").read_text())
    assert record == {"id": "seo", "name": "Search", "description": "Capture search intent.",
                      "orchestrator": "seo__orchestrator", "agents": ["seo__orchestrator", "seo__writer", "seo__publisher"]}

    run("confirm", str(home), worker=False)
    assert "agents and plan for `community`" in run("brief", str(home), "campaign-2")
    assert "slot is empty" in run("brief", str(home), "campaign-3")
    assert "Campaign 1: agents and plan" in json.loads(
        run("provision", str(home), "--when-ready", worker=False))["waiting"]
    board.finish(*(f"Campaign {n}: agents and plan" for n in range(1, 6)))
    done = json.loads(run("provision", str(home), "--when-ready", worker=False))
    assert [(c["id"], c["state"]) for c in done["campaigns"]] == [("seo", "draft"), ("community", "draft")]
    assert "did not enrich" in done["campaigns"][0]["error"] and done["complete"] is False
    assert board.cron()[-1] == ["remove", "job_1"], "one attempt ends the job; the session reruns provision"

    # The cron job runs provision without HERMES_HOME; the campaign helper must still read this home.
    (home / "oma/staging").mkdir(parents=True)
    (home / "oma/staging/seo.yaml").write_text((home / "oma/campaigns/seo/config.yaml").read_text())
    elsewhere = board.home.parent / "elsewhere"
    done = subprocess.run([sys.executable, str(board.script), "provision", str(home)], capture_output=True, text=True,
                          env={**board.env, "HERMES_HOME": str(elsewhere)}, check=False)
    seo = json.loads(done.stdout)["campaigns"][0]
    assert str(elsewhere) not in seo.get("error", ""), seo


def test_parallel_cards_merge_their_own_config_keys(board):
    run, home = board.run, board.home
    config = home / "oma/brand/config.yaml"
    fragment = home / "core.yaml"
    fragment.write_text("id: brand\nresearch:\n  market_report: research/market.md\nchannels: {blog: {status: verified}}\n")
    run("merge-config", str(home), str(fragment))  # the first merge creates the config
    fragments = {"assets.yaml": "logos: {primary: logos/a.png}\n",
                 "landscape.yaml": "research:\n  competitor_report: research/competitors.md\n"}
    for name, text in fragments.items():
        (home / name).write_text(text)
        run("merge-config", str(home), str(home / name))

    merged = YAML(typ="safe").load(config.read_text())
    assert merged["research"] == {"market_report": "research/market.md", "competitor_report": "research/competitors.md"}
    assert merged["logos"] == {"primary": "logos/a.png"} and merged["channels"]["blog"]["status"] == "verified"
    assert not (home / "oma/brand/.config.lock").exists()
