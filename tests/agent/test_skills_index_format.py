"""Shape of the <available_skills> index rows (single-skill categories, headers, clipped descriptions)."""
import re

import pytest

from agent.prompt_builder import build_skills_system_prompt, clear_skills_system_prompt_cache
from agent.skill_utils import SKILL_PROMPT_DESC_LIMIT, clip_skill_description
from agent.skills_index_delta import index_entries

LONG = "Use when " + "cutting, publishing, or abandoning a Hermes release and its notes, " * 4


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_skills_system_prompt_cache(clear_snapshot=True)
    yield
    clear_skills_system_prompt_cache(clear_snapshot=True)


def _skill(root, rel, desc):
    d = root / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {d.name}\ndescription: {desc}\n---\n\nBody.\n", encoding="utf-8")


def test_index_rows_carry_each_name_once_and_never_a_half_word(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    skills = tmp_path / "skills"
    _skill(skills, "creative/ascii-art", "ASCII art banners.")
    _skill(skills, "creative/pixel-art", "Pixel art sprites.")
    (skills / "creative" / "DESCRIPTION.md").write_text(
        "---\ndescription: Creative content generation and visual design tools.\n---\n", encoding="utf-8")
    _skill(skills, "computer-use", "Drive the desktop.")  # a top-level skill is its own category
    _skill(skills, "github/hermes-release", LONG)

    prompt = build_skills_system_prompt()
    block = re.search(r"<available_skills>\n(.*?)\n</available_skills>", prompt, re.DOTALL).group(1)
    lines = block.splitlines()

    assert "  creative:" in lines and "Creative content generation" not in block
    assert "  - computer-use: Drive the desktop." in lines and "  computer-use:" not in lines
    release = next(line for line in lines if "hermes-release" in line)
    assert release.startswith("  - hermes-release: ")
    shown = release.split(": ", 1)[1]
    assert len(shown) <= SKILL_PROMPT_DESC_LIMIT and shown.endswith("...")
    kept = shown[:-3]
    assert LONG.startswith(kept) and LONG[len(kept)] in " ,"  # cut lands between words
    # The turn-delta parser reads flattened rows like nested ones.
    assert set(index_entries(prompt)) == {"ascii-art", "pixel-art", "hermes-release", "computer-use"}


@pytest.mark.parametrize("oneshot", [False, True], ids=["interactive", "oneshot"])
@pytest.mark.parametrize("has_listed_skill", [False, True], ids=["empty-index", "with-index"])
def test_prompt_guides_search_for_unlisted_oma_skills(monkeypatch, tmp_path, oneshot, has_listed_skill):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1" if oneshot else "0")
    _skill(tmp_path / "oma-bundle" / "skills", "research/global-research", "Research from the shared bundle.")
    if has_listed_skill:
        _skill(tmp_path / "skills", "writing/local-writing", "Write locally.")

    prompt = build_skills_system_prompt(available_tools={"skill_view", "skills_search"})
    assert prompt.startswith("## Skills\n")
    assert "shared OMA skills repository" in prompt and "use skills_search(query)" in prompt
    assert "load a relevant match with skill_view(name)" in prompt
    assert "global-research" not in prompt
    assert set(index_entries(prompt)) == ({"local-writing"} if has_listed_skill else set())

    without_search = build_skills_system_prompt(available_tools={"skill_view"})
    assert "skills_search" not in without_search
    assert bool(without_search) == has_listed_skill


@pytest.mark.parametrize("sep", ["\t", "\u00a0"], ids=["tab", "nbsp"])
def test_clip_cuts_at_any_whitespace_never_inside_a_word(sep):
    desc = f"alpha{sep}" + f"bravo{sep}" * 40
    shown = clip_skill_description(desc)
    assert len(shown) <= SKILL_PROMPT_DESC_LIMIT and shown.endswith("...")
    assert set(shown[:-3].split(sep)) == {"alpha", "bravo"}  # whole words only, no "bra..."
