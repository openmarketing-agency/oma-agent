"""The bundled onboarding workflow can load its four companion skills."""

import json
from pathlib import Path
import shutil

from tools.skills_sync import sync_skills
from tools.skills_tool import find_all_skills, skill_view


ONBOARDING_COMPANIONS = {"oma-agents", "oma-brand", "oma-campaigns", "oma-playbook"}
OMA_RESEARCH_SKILLS = {"oma-competitors", "oma-creatives"}
OMA_SKILLS = ONBOARDING_COMPANIONS | OMA_RESEARCH_SKILLS | {"oma-onboarding"}
OLD_SKILLS = {"oma-brands", "oma-playbooks"}


def test_oma_onboarding_loads_with_its_workflow_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert OMA_SKILLS <= set(sync_skills(quiet=True)["copied"])
    onboarding = json.loads(skill_view("oma-onboarding"))
    assert onboarding["success"], onboarding
    assert set(onboarding["related_skills"]) == ONBOARDING_COMPANIONS
    oma_dir = (tmp_path / "skills" / "oma").resolve()
    assert Path(onboarding["skill_dir"]).resolve() == oma_dir / "oma-onboarding"
    for name in ONBOARDING_COMPANIONS | OMA_RESEARCH_SKILLS:
        loaded = json.loads(skill_view(f"oma/{name}"))
        assert loaded["success"], loaded
        assert Path(loaded["skill_dir"]).resolve() == oma_dir / name
    assert (oma_dir / "oma-campaigns" / "scripts" / "campaign.py").is_file()
    assert not (tmp_path / "oma").exists()


def test_named_profile_sync_excludes_oma_and_hides_retained_copies(tmp_path, monkeypatch):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override

    root = tmp_path / "docker-home"
    home = root / "profiles" / "worker"
    monkeypatch.setenv("HERMES_HOME", str(root))
    assert OMA_SKILLS <= set(sync_skills(quiet=True)["copied"])

    token = set_hermes_home_override(home)
    try:
        seeded = set(sync_skills(quiet=True)["copied"])
        assert "hermes-agent" in seeded
        assert OMA_SKILLS.isdisjoint(seeded)
        assert not (home / "skills" / "oma").exists()

        # An older install or an explicit clone can retain the files on disk.
        shutil.copytree(root / "skills" / "oma", home / "skills" / "oma")
        assert OMA_SKILLS.isdisjoint(row["name"] for row in find_all_skills())
        for name in OMA_SKILLS:
            assert not json.loads(skill_view(name))["success"]
            assert not json.loads(skill_view(f"oma/{name}"))["success"]
        assert not json.loads(skill_view("oma-campaigns", file_path="scripts/campaign.py"))["success"]
        assert (home / "skills" / "oma" / "oma-campaigns" / "SKILL.md").is_file()
    finally:
        reset_hermes_home_override(token)

    assert OMA_SKILLS <= {row["name"] for row in find_all_skills()}


def test_default_sync_retires_plural_skills_without_removing_old_data(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    for name in OLD_SKILLS:
        skill = tmp_path / "skills" / "oma" / name / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(f"---\nname: {name}\ndescription: Old skill.\n---\nOld instructions.\n")
    old_records = [tmp_path / "oma" / group / "example" / "config.yaml" for group in ("brands", "playbooks")]
    for record in old_records:
        record.parent.mkdir(parents=True)
        record.write_text("id: example\n")

    assert {"oma-brand", "oma-playbook"} <= set(sync_skills(quiet=True)["copied"])
    assert OLD_SKILLS.isdisjoint(row["name"] for row in find_all_skills())
    for name in OLD_SKILLS:
        assert not json.loads(skill_view(name))["success"]
        assert not json.loads(skill_view(f"oma/{name}"))["success"]
        assert (tmp_path / "skills" / "oma" / name / "SKILL.md").is_file()
    assert all(record.read_text() == "id: example\n" for record in old_records)
    assert not (tmp_path / "oma" / "brand").exists()
    assert not (tmp_path / "oma" / "playbook").exists()
