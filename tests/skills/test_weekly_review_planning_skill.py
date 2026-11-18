"""The weekly review blueprint's procedure is available from the optional catalog."""
from pathlib import Path


def test_weekly_review_is_installable_from_the_optional_catalog(monkeypatch):
    from cron.blueprint_catalog import get_blueprint
    from tools.skills_hub_official import OptionalSkillSource

    repo = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("HERMES_OPTIONAL_SKILLS", str(repo / "optional-skills"))
    blueprint = get_blueprint("weekly-review")
    assert blueprint is not None
    (name,) = blueprint.skills
    bundle = OptionalSkillSource().fetch(f"official/productivity/{name}")
    assert bundle is not None and bundle.name == name
    assert "SKILL.md" in bundle.files
