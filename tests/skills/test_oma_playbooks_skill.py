"""Exercise OMA playbook provisioning with native profile operations in an isolated home."""

import io
import json
import subprocess
import urllib.error
import urllib.request
import zipfile
from email.message import Message
from pathlib import Path

import pytest


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    repo = tmp_path / "openmarketing.agency"
    team = repo / "playbooks" / "demo"
    team.mkdir(parents=True)
    (team / "config.yaml").write_text(
        "id: demo\nname: Demo\nversion: 0.2.0\ndescription: >-\n  Test team.\n\n"
        "# Keep canonical IDs unchanged.\norchestrator: demo__orchestrator\n"
        "agents:\n  - demo__orchestrator\n  - demo__worker\n", encoding="utf-8")
    for role, version, dependencies in (("orchestrator", "0.1.2", "[shared, local]"), ("worker", "0.2.1", "[]")):
        candidate = team / "agents" / f"demo__{role}"
        candidate.mkdir(parents=True)
        (candidate / "config.yaml").write_text(
            f"id: demo__{role}\nversion: {version}\ndescription: Test role.\noma_skills: {dependencies}\n"
            "agent: {enabled_toolsets: [file]}\njobs: [{id: sample}]\n", encoding="utf-8")
        (candidate / "SOUL.md").write_text(f"I am the {role}.\n", encoding="utf-8")
    for root, name in ((repo, "shared"), (team, "local"), (repo, "unused")):
        skill = root / "skills" / "category" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\nContents.\n",
                                       encoding="utf-8")
        (skill / "support.txt").write_text("Support file.", encoding="utf-8")
    return home, repo


def test_public_catalog_plan_and_install_use_one_r2_snapshot(checkout, monkeypatch, capsys):
    from hermes_cli.oma_playbooks.__main__ import main
    from hermes_cli.oma_playbooks.source import read_mapping

    home, repo = checkout
    commit = "a" * 40
    newer_commit = "d" * 40
    tag = "v1.2.0"
    storage = "https://pub-d3419a6b761b48b38897cf50a5056136.r2.dev"
    release_url = f"{storage}/latest.yaml"
    tagged_release_url = f"{storage}/{tag}/release.yaml"
    archive_urls = [f"{storage}/{tag}/{tree}.zip" for tree in ("playbooks", "skills")]
    newer_urls = [f"{storage}/v1.11.0/{tree}.zip" for tree in ("playbooks", "skills")]
    latest_changed = False
    broken_archive = None

    def snapshot(tree, sha):
        with io.BytesIO() as data:
            with zipfile.ZipFile(data, "w") as archive:
                archive.comment = sha.encode("ascii")
                for path in (repo / tree).rglob("*"):
                    archive.write(path, path.relative_to(repo).as_posix())
                if tree == "skills" and broken_archive == "traversal":
                    archive.writestr("skills/../../escaped", "must not escape")
            return data.getvalue()

    requests = []

    def fetch(request, *, timeout):
        url = request.full_url
        requests.append(url)
        assert not request.has_header("Authorization")
        if url in (release_url, tagged_release_url):
            selected_tag, sha = ("v1.11.0", newer_commit) if url == release_url and latest_changed else (tag, commit)
            assert request.get_header("Accept") == "application/yaml"
            return io.BytesIO(f'tag: "{selected_tag}"\ncommit: "{sha}"\n'.encode())
        assert url in archive_urls + newer_urls
        tree = url.rsplit("/", 1)[1].removesuffix(".zip")
        sha = newer_commit if url in newer_urls else commit
        if tree == "skills" and broken_archive == "missing":
            raise urllib.error.HTTPError(url, 404, "test", Message(), None)
        if tree == "skills" and broken_archive == "wrong commit":
            sha = commit
        return io.BytesIO(snapshot(tree, sha))

    real_run = subprocess.run

    def run(args, *positional, **kwargs):
        assert "ls-remote" not in args
        return real_run(args, *positional, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    monkeypatch.setattr(subprocess, "run", run)
    assert main(["check"]) == 0
    assert json.loads(capsys.readouterr().out)["cached"] is False
    assert requests == [release_url]
    cache = home / "cache" / "oma-playbooks-r2"
    assert not cache.exists()
    legacy_snapshot = home / "cache" / "openmarketing.agency" / commit
    for tree in ("playbooks", "skills"):
        (legacy_snapshot / tree).mkdir(parents=True)
    requests.clear()
    assert main(["catalog"]) == 0
    source = {"repository": "openmarketing-agency/openmarketing.agency", "tag": tag, "commit": commit,
              "base_url": storage}
    assert requests == [release_url, *archive_urls]
    assert json.loads(capsys.readouterr().out)[0]["source"] == source
    requests.clear()
    assert main(["fetch", "--tag", tag]) == 0
    cached = json.loads(capsys.readouterr().out)
    assert cached["downloaded"] is False
    assert Path(cached["cache_path"]) == cache / commit
    assert {entry.name for entry in Path(cached["cache_path"]).iterdir()} == {"playbooks", "skills"}
    assert not (home / "profiles").exists()
    assert main(["plan", "demo", "--tag", tag]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == source
    assert main(["install", "demo", "--tag", tag, "--version", "0.2.0"]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == source
    assert requests == [tagged_release_url] * 3
    assert read_mapping(home / "playbooks" / "demo" / "installation.yaml")["source"] == source
    skills = home / "profiles" / "demo__orchestrator" / "skills"
    for name in ("shared", "local"):
        assert (skills / name / "support.txt").read_text(encoding="utf-8") == "Support file."
    assert main(["status", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == source
    assert requests == [tagged_release_url] * 3

    latest_changed = True
    assert main(["check"]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["source"]["tag"] == "v1.11.0" and checked["cached"] is False
    for broken_archive, message in (("missing", "skills.zip"), ("wrong commit", "does not match commit"),
                                    ("traversal", "Unsafe archive member")):
        assert main(["fetch"]) == 1
        assert message in capsys.readouterr().err
        assert {entry.name for entry in cache.iterdir()} == {commit}
    broken_archive = None
    assert main(["fetch"]) == 0
    refreshed = json.loads(capsys.readouterr().out)
    assert refreshed["downloaded"] is True and refreshed["source"]["commit"] == newer_commit
    assert Path(refreshed["cache_path"]) == cache / newer_commit
    assert read_mapping(home / "playbooks" / "demo" / "installation.yaml")["source"] == source


def test_r2_discovery_bootstraps_only_on_missing_latest(monkeypatch):
    from hermes_cli.oma_playbooks.releases import resolve_release

    storage = "https://pub-d3419a6b761b48b38897cf50a5056136.r2.dev"
    status = 404
    requests = []

    def fetch(request, *, timeout):
        requests.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "test", Message(), None)

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    assert resolve_release().tag == "v0.1.1"
    assert resolve_release("v0.1.1").commit == "80be8c56d59d0680efbe5a72e1baffd45caa55ae"
    assert requests == [f"{storage}/latest.yaml"]
    with pytest.raises(ValueError, match=r"v0\.1\.0/release\.yaml.*404"):
        resolve_release("v0.1.0")
    status = 403
    with pytest.raises(ValueError, match=r"latest\.yaml.*403"):
        resolve_release()


@pytest.mark.parametrize(("tag", "payload"), [
    (None, b'tag: v1.2.3\ncommit: not-a-commit\n'),
    ("v1.2.4", b'tag: v1.2.3\ncommit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n'),
    (None, b'tag: [\n'),
])
def test_r2_discovery_rejects_invalid_manifest(monkeypatch, tag, payload):
    from hermes_cli.oma_playbooks.releases import resolve_release

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(payload))
    with pytest.raises(ValueError, match="Invalid OMA release manifest"):
        resolve_release(tag)


def test_install_saves_playbook_metadata_in_the_ledger_only(checkout):
    from hermes_cli.oma_playbooks.install import install, installed
    from hermes_cli.oma_playbooks.source import read_mapping, resolve

    home, repo = checkout
    plan = resolve(repo, "demo")
    install(home, plan)

    directory = home / "playbooks" / "demo"
    assert not (directory / "config.yaml").exists()
    record = read_mapping(directory / "installation.yaml")
    assert record["description"] == "Test team."
    assert record["source_manifest"] == "playbooks/demo/config.yaml"
    assert installed(home, "demo")[0]["description"] == "Test team."


def test_install_records_agent_versions_and_configures_agent_scratch(checkout):
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import read_user_config_raw
    from hermes_cli.oma_playbooks.install import default_home, install, installed
    from hermes_cli.oma_playbooks.source import catalog, read_mapping, resolve
    from tools.file_tools import read_file_tool, write_file_tool

    home, repo = checkout
    assert default_home() == home.resolve()
    assert [row["id"] for row in catalog(repo)] == ["demo"]
    assert installed(home) == []
    plan = resolve(repo, "demo", "0.2.0")
    record = install(home, plan)
    registry = home / "playbooks" / "demo"
    saved = read_mapping(registry / "installation.yaml")
    assert saved["state"] == "installed" and saved["version"] == "0.2.0"
    assert saved["agents"]["demo__worker"]["version"] == "0.2.1"
    assert record == install(home, plan) == installed(home, "demo")[0]
    for agent in plan.agents:
        profile = home / "profiles" / agent.id
        row = saved["agents"][agent.id]
        scratch = registry / row["scratch_dir"]
        assert scratch.is_dir() and str(scratch.resolve()) in (profile / "SOUL.md").read_text(encoding="utf-8")
        assert row["state"] == "installed" and row["declared_jobs"] == ["sample"]
        assert not (profile / "cron" / "jobs.json").exists()
        assert not (profile / "skills" / "unused").exists()
        raw = read_user_config_raw(profile / "config.yaml")
        assert not {"id", "description", "version", "jobs", "oma_skills"} & raw.keys()
        assert "oma-playbooks" in raw["skills"]["disabled"]
        for name in agent.skills:
            assert (profile / "skills" / name / "support.txt").read_text(encoding="utf-8") == "Support file."
        with bind_profile_scope(profile, hydrate_secrets=False):
            marker = str(scratch / "marker.txt")
            assert not json.loads(write_file_tool(marker, "Scratch check.")).get("error")
            assert "Scratch check." in read_file_tool(marker)
            with pytest.raises(ValueError, match="default OMA Agent"):
                default_home()


def test_missing_skill_and_profile_collision_do_not_publish(checkout):
    from hermes_cli.oma_playbooks.install import install
    from hermes_cli.oma_playbooks.source import resolve

    home, repo = checkout
    with pytest.raises(ValueError, match="expected version"):
        resolve(repo, "demo", "1.0.0")
    missing = repo / "skills" / "category" / "shared" / "SKILL.md"
    missing.rename(missing.with_suffix(".disabled"))
    with pytest.raises(ValueError, match="one eligible OMA package"):
        resolve(repo, "demo")
    assert not (home / "profiles").exists()
    missing.with_suffix(".disabled").rename(missing)
    collision = home / "profiles" / "demo__worker"
    collision.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        install(home, resolve(repo, "demo"))
    assert not (home / "profiles" / "demo__orchestrator").exists()
    assert not (home / "playbooks" / "demo").exists()
