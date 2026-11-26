"""Onboarding runs as a Kanban card graph: the board script's shape, idempotency, fan-out and config merges.

A fake ``hermes`` on PATH stores cards in a JSON file, so the real script runs unchanged offline.
"""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view

FAKE_HERMES = r'''#!PYTHON
import json, os, sys
state_path = os.environ["FAKE_KANBAN_STATE"]
state = json.load(open(state_path)) if os.path.exists(state_path) else {"boards": [], "tasks": []}
args = sys.argv[1:]
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
elif verb == "link":
    child = next(t for t in state["tasks"] if t["id"] == rest[1])
    if rest[0] in child["parents"]:
        print("link already exists", file=sys.stderr); sys.exit(1)
    child["parents"].append(rest[0])
elif verb == "list":
    print(json.dumps([{k: v for k, v in t.items() if k != "key"} for t in state["tasks"]])); sys.exit(0)
json.dump(state, open(state_path, "w"))
if verb == "create":
    print(json.dumps(task))
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

    def run(*args):
        done = subprocess.run([sys.executable, str(skill / "scripts" / "board.py"), *args], capture_output=True,
                              text=True, env=env, check=False)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)

    def tasks():
        return {t["title"]: t for t in json.loads(state.read_text())["tasks"]}

    return run, tasks, home


def _by_id(tasks):
    return {t["id"]: t for t in tasks.values()}


@pytest.mark.platforms("posix")
def test_start_builds_the_stage_graph_and_resumes_instead_of_duplicating(board):
    run, tasks, home = board
    run("start", str(home), "--url", "https://brand.example/", "--repo", "https://github.com/brand/app")
    first = tasks()
    run("start", str(home), "--url", "https://brand.example/")
    assert tasks().keys() == first.keys(), "a second start returns the same cards"

    ids = _by_id(first)
    parents = lambda title: {ids[p]["title"] for p in first[title]["parents"]}
    assert first["Brand: website, channels, integrations, docs"]["parents"] == []
    assert parents("Creatives: the brand's own ads and summary") == {"Creatives: the brand's own posts"}
    assert parents("Brand: design system") == {"Brand: screenshots and visual assets", "Creatives: the brand's own ads and summary"}
    assert parents("Strategy: playbook and campaign choice") >= {
        "Brand: repository analysis", "Brand: market research", "Brand: design system",
        "Competitors: patterns, landscape and validation"}
    body = first["Brand: website, channels, integrations, docs"]["body"]
    assert "https://brand.example/" in body and "merge-config" in body and "{python}" not in body


@pytest.mark.platforms("posix")
def test_discovery_fans_out_competitor_and_creatives_cards_before_the_landscape(board):
    run, tasks, home = board
    run("start", str(home), "--url", "https://brand.example/")
    index = {"competitors": [
        {"id": "gamma", "name": "Gamma", "tier": "direct", "depth": "full"},
        {"id": "pitch", "name": "Pitch", "tier": "direct", "depth": "full"},
        {"id": "canva", "name": "Canva", "tier": "indirect", "depth": "light"},
        {"id": "later", "name": "Later", "tier": "direct", "depth": "index_only"}],
        "references": [{"id": "notion", "name": "Notion"}]}
    path = home / "oma/brand/research/competitors/index.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(index))
    run("fanout", str(home))
    run("fanout", str(home))  # a retried discovery card adds nothing twice

    cards = tasks()
    ids = _by_id(cards)
    landscape = {ids[p]["title"] for p in cards["Competitors: patterns, landscape and validation"]["parents"]}
    assert {"Competitor: Gamma profile and teardown", "Creatives: Gamma ads and summary",
            "Competitor: Pitch profile and teardown", "Creatives: Pitch ads and summary",
            "Competitors: indirect profiles", "Creatives: Notion ads and summary"} <= landscape
    assert "Creatives: Later posts" not in cards, "index-only competitors get no collection"
    assert "Canva (canva)" in cards["Competitors: indirect profiles"]["body"]
    assert ids[cards["Creatives: Gamma posts"]["parents"][0]]["title"] == "Competitor: Gamma profile and teardown"


@pytest.mark.platforms("posix")
def test_playbook_adds_one_design_card_per_campaign_and_provisioning_waits_for_all(board):
    run, tasks, home = board
    run("start", str(home), "--url", "https://brand.example/", "--synthesis-model", "strong/model")
    run("campaigns", str(home), "seo", "community")
    run("campaigns", str(home), "seo", "community", "social")

    cards = tasks()
    ids = _by_id(cards)
    provision = {ids[p]["title"] for p in cards["Campaigns: provision paused teams"]["parents"]}
    assert provision == {"Campaign: design seo", "Campaign: design community", "Campaign: design social"}
    assert cards["Campaign: design seo"]["model_override"] == "strong/model"
    assert cards["Brand: market research"]["model_override"] is None


def test_parallel_cards_merge_their_own_config_keys(board):
    run, _, home = board
    config = home / "oma/brand/config.yaml"
    config.write_text("id: brand\nresearch:\n  market_report: research/market.md\nchannels: {blog: {status: verified}}\n")
    fragments = {"assets.yaml": "logos: {primary: logos/a.png}\n",
                 "landscape.yaml": "research:\n  competitor_report: research/competitors.md\n"}
    for name, text in fragments.items():
        (home / name).write_text(text)
        run("merge-config", str(home), str(home / name))

    merged = YAML(typ="safe").load(config.read_text())
    assert merged["research"] == {"market_report": "research/market.md", "competitor_report": "research/competitors.md"}
    assert merged["logos"] == {"primary": "logos/a.png"} and merged["channels"]["blog"]["status"] == "verified"
    assert not (home / "oma/brand/.config.lock").exists()
