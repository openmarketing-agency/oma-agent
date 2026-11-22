"""Search and load explicit skills without adding bundle skills to every prompt."""

import json
from pathlib import Path

import pytest

from agent.prompt_builder import build_skills_system_prompt
from agent.runtime_scope import bind_profile_scope
from hermes_cli.oma_campaigns.bundle import seed_bundle
from tools import skills_tool
from tools.registry import registry


def _skill(root, category, name, description):
    directory = root / category / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{description}\n", encoding="utf-8",
    )
    return directory


def test_search_resolves_profile_and_shared_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    profile = tmp_path / "skills"
    shared = tmp_path / "oma-bundle" / "skills"
    local_skill = _skill(profile, "writing", "research-tone", "Set the local voice.")
    _skill(shared, "writing", "research-tone", "Use the shared voice.")
    bundle_skill = _skill(shared, "research", "research-market", "Summarize market evidence.")
    (bundle_skill / "references").mkdir()
    (bundle_skill / "references" / "guide.md").write_text("Market guide.", encoding="utf-8")
    _skill(tmp_path / "oma-bundle" / "campaigns" / "seo" / "skills", "research",
           "research-private", "Campaign-private evidence.")

    assert "search_skills" not in registry.get_tool_names_for_toolset("skills")
    raw = registry.dispatch("skills_search", {"query": "ReSeArCh"})
    assert isinstance(raw, str)
    result = json.loads(raw)
    assert result["success"], result
    rows = {row["name"]: row for row in result["skills"]}
    assert set(rows) == {"research-tone", "research-market"}
    assert rows["research-tone"]["description"] == "Set the local voice."
    assert rows["research-market"]["source"] == "oma-bundle"
    assert json.loads(skills_tool.skill_view("research-tone"))["skill_dir"] == str(local_skill)
    assert json.loads(skills_tool.skill_view("research-market"))["skill_dir"] == str(bundle_skill)
    guide = json.loads(skills_tool.skill_view("research-market", "references/guide.md"))
    assert guide["content"] == "Market guide."
    assert "research-market" not in {row["name"] for row in skills_tool.find_all_skills()}
    prompt = build_skills_system_prompt()
    assert "research-tone: Set the local voice." in prompt
    assert "research-market" not in prompt and "Summarize market evidence." not in prompt


def test_search_preserves_named_profile_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    profile = tmp_path / "profiles" / "worker"
    profile.mkdir(parents=True)
    (profile / "config.yaml").write_text("skills:\n  disabled: [research-blocked]\n", encoding="utf-8")
    shared = tmp_path / "oma-bundle" / "skills"
    _skill(shared, "research", "research-shared", "Shared evidence.")
    _skill(shared, "research", "research-blocked", "Disabled evidence.")
    _skill(tmp_path / "skills", "research", "research-other-profile", "Default profile evidence.")
    _skill(profile / "skills", "research", "research-own", "Profile-owned evidence.")

    with bind_profile_scope(profile, hydrate_secrets=False):
        result = json.loads(skills_tool.skills_search("research"))
        assert [row["name"] for row in result["skills"]] == ["research-own", "research-shared"]
        assert not json.loads(skills_tool.skill_view("research-blocked"))["success"]
        prompt = build_skills_system_prompt()
        assert "research-own: Profile-owned evidence." in prompt
        assert "research-shared" not in prompt and "Shared evidence." not in prompt
        assert "research-other-profile" not in prompt and "Default profile evidence." not in prompt


def test_bundle_search_and_load_do_not_follow_symlink(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    shared = tmp_path / "oma-bundle" / "skills"
    shared.mkdir(parents=True)
    outside = _skill(tmp_path / "outside", "research", "research-external", "Outside the source tree.")
    try:
        (shared / outside.name).symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    assert json.loads(skills_tool.skills_search("research-external"))["skills"] == []
    assert not json.loads(skills_tool.skill_view("research-external"))["success"]


def test_seeded_marketingskills_are_discoverable_and_load_on_demand(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    seed_bundle(Path(__file__).resolve().parents[2] / "oma-bundle", tmp_path)
    collection = tmp_path / "oma-bundle" / "skills" / "marketingskills"

    results = json.loads(skills_tool.skills_search("marketingskills"))
    names = {row["name"] for row in results["skills"]}
    packages = {path.parent.name for path in collection.glob("*/SKILL.md")}
    assert {"seo-audit", "conversion-tracking", "copywriting"} <= names
    assert names == packages
    assert all(row["source"] == "oma-bundle" for row in results["skills"])
    assert (collection / "LICENSE").is_file()

    for name in sorted(names):
        skill = json.loads(skills_tool.skill_view(name, preprocess=False))
        assert skill["success"], skill
        assert skill["name"] == name
        assert Path(skill["skill_dir"]) == collection / name
    asset = json.loads(skills_tool.skill_view(
        "conversion-tracking", "assets/gtm-recipes/event-map.json", preprocess=False,
    ))
    assert asset["success"], asset
    assert "seo-audit" not in build_skills_system_prompt()


def test_seeded_social_media_skills_are_discoverable_and_load_on_demand(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    seed_bundle(Path(__file__).resolve().parents[2] / "oma-bundle", tmp_path)
    collection = tmp_path / "oma-bundle" / "skills" / "social-media-skills"
    rows = json.loads(skills_tool.skills_search("social-media-skills"))["skills"]
    names = {row["name"] for row in rows if row["source"] == "oma-bundle"}
    assert {"engagement-routine", "reply-and-comment-writer", "social-strategy"} <= names
    assert names == {path.parent.name for path in collection.glob("*/SKILL.md")}
    assert (collection / "LICENSE").is_file()

    for name in sorted(names):
        skill = json.loads(skills_tool.skill_view(name, preprocess=False))
        assert skill["success"], skill
        assert Path(skill["skill_dir"]) == collection / name
    reference = json.loads(skills_tool.skill_view(
        "social-media-skills/reply-and-comment-writer", "references/replying-to-your-comments.md", preprocess=False,
    ))
    assert reference["success"], reference
    assert "reply-and-comment-writer" not in build_skills_system_prompt()


def test_brand_can_load_qualified_bundle_skill_with_profile_namesake(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    seed_bundle(Path(__file__).resolve().parents[2] / "oma-bundle", tmp_path)
    profile_skill = _skill(tmp_path / "skills", "custom", "product-marketing", "Use the profile's marketing notes.")
    bundle_skill = tmp_path / "oma-bundle" / "skills" / "marketingskills" / "product-marketing"

    bare = json.loads(skills_tool.skill_view("product-marketing", preprocess=False))
    qualified = json.loads(skills_tool.skill_view("marketingskills/product-marketing", preprocess=False))
    assert bare["success"], bare
    assert qualified["success"], qualified
    assert Path(bare["skill_dir"]) == profile_skill
    assert Path(qualified["skill_dir"]) == bundle_skill
