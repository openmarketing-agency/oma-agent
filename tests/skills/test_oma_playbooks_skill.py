"""Exercise OMA playbook provisioning with native profile operations in an isolated home."""

import io
import json
import subprocess
import tarfile
import urllib.error
import urllib.request
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


@pytest.mark.parametrize("latest_status", [200, 404, 403])
def test_public_catalog_plan_and_install_use_one_tagged_snapshot(checkout, monkeypatch, capsys, latest_status):
    from hermes_cli.oma_playbooks.__main__ import main
    from hermes_cli.oma_playbooks.source import read_mapping

    home, repo = checkout
    commit = "a" * 40
    newer_commit = "d" * 40
    tag = "v1.2.0" if latest_status == 200 else "v1.10.0"
    release_url = "https://api.github.com/repos/openmarketing-agency/openmarketing.agency/releases/latest"
    archive_url = f"https://codeload.github.com/openmarketing-agency/openmarketing.agency/tar.gz/{commit}"
    newer_url = archive_url.rsplit("/", 1)[0] + "/" + newer_commit
    latest_changed = False
    broken_archive = False
    (repo / "README.md").write_text("Not a source tree.", encoding="utf-8")

    def snapshot(sha):
        with io.BytesIO() as data:
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                root = f"openmarketing.agency-{sha}"
                archive.add(repo, arcname=root)
                if broken_archive:
                    archive.addfile(tarfile.TarInfo(f"{root}/skills/../../escaped"))
            return data.getvalue()

    requests = []

    def fetch(request, *, timeout):
        url = request.full_url
        requests.append(url)
        assert not request.has_header("Authorization")
        if url == release_url:
            if latest_changed:
                return io.BytesIO(b'{"tag_name":"v1.11.0","draft":false,"prerelease":false}')
            if latest_status != 200:
                headers = Message()
                headers["X-RateLimit-Remaining"] = "0"
                raise urllib.error.HTTPError(url, latest_status, "test", headers, None)
            return io.BytesIO(b'{"tag_name":"v1.2.0","draft":false,"prerelease":false}')
        assert url in (archive_url, newer_url)
        return io.BytesIO(snapshot(url.rsplit("/", 1)[1]))

    real_run = subprocess.run

    def run(args, *positional, **kwargs):
        if "ls-remote" not in args:
            return real_run(args, *positional, **kwargs)
        assert "https://github.com/openmarketing-agency/openmarketing.agency.git" in args
        annotated = "b" * 40
        older = commit if latest_status == 200 else "c" * 40
        refs = (f"{older}\trefs/tags/v1.2.0\n{annotated}\trefs/tags/v1.10.0\n"
                f"{commit}\trefs/tags/v1.10.0^{{}}\n{annotated}\trefs/tags/v2.0.0-rc.1\n")
        if latest_changed:
            refs += f"{newer_commit}\trefs/tags/v1.11.0\n"
        return subprocess.CompletedProcess(args, 0, refs, "")

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    monkeypatch.setattr(subprocess, "run", run)
    assert main(["check"]) == 0
    assert json.loads(capsys.readouterr().out)["cached"] is False
    assert requests == [release_url]
    assert not (home / "cache" / "openmarketing.agency").exists()
    requests.clear()
    assert main(["catalog"]) == 0
    source = {"repository": "openmarketing-agency/openmarketing.agency", "tag": tag, "commit": commit}
    assert requests == [release_url, archive_url]
    assert json.loads(capsys.readouterr().out)[0]["source"] == source
    requests.clear()
    assert main(["fetch", "--tag", tag]) == 0
    cached = json.loads(capsys.readouterr().out)
    assert cached["downloaded"] is False
    assert {entry.name for entry in Path(cached["cache_path"]).iterdir()} == {"playbooks", "skills"}
    assert not (home / "profiles").exists()
    assert main(["plan", "demo", "--tag", tag]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == source
    assert main(["install", "demo", "--tag", tag, "--version", "0.2.0"]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == source
    assert requests == []
    assert read_mapping(home / "playbooks" / "demo" / "installation.yaml")["source"] == source
    skills = home / "profiles" / "demo__orchestrator" / "skills"
    for name in ("shared", "local"):
        assert (skills / name / "support.txt").read_text(encoding="utf-8") == "Support file."
    assert main(["status", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == source
    assert requests == []

    latest_changed = True
    assert main(["check"]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["source"]["tag"] == "v1.11.0" and checked["cached"] is False
    broken_archive = True
    assert main(["fetch"]) == 1
    assert "Unsafe archive member" in capsys.readouterr().err
    cache = home / "cache" / "openmarketing.agency"
    assert {entry.name for entry in cache.iterdir()} == {commit}
    broken_archive = False
    assert main(["fetch"]) == 0
    refreshed = json.loads(capsys.readouterr().out)
    assert refreshed["downloaded"] is True and refreshed["source"]["commit"] == newer_commit
    assert Path(refreshed["cache_path"]) == cache / newer_commit
    assert read_mapping(home / "playbooks" / "demo" / "installation.yaml")["source"] == source


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
