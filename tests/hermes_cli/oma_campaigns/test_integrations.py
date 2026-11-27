"""Integration recommendations: needs, complements and campaign validation warnings."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def oma(tmp_path, monkeypatch):
    from hermes_cli.config import atomic_config_write
    from hermes_cli.oma_campaigns import __main__ as cli

    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    brand = home / "oma" / "brand" / "config.yaml"
    brand.parent.mkdir(parents=True)
    atomic_config_write(brand, {
        "id": "demo", "name": "Demo", "description": "Example brand",
        "integrations": {"wordpress_com": {"status": "observed", "evidence": "research/cms.md"}},
    })
    return tmp_path, cli.main


def test_recommend_adds_media_needs_that_a_provider_satisfies(oma, capsys):
    from hermes_cli.oma_campaigns.integrations import integration_catalog

    _, main = oma
    assert main(["recommend", "--channels", "instagram,reddit,blog"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result["integrations"]) == {"instagram", "reddit", "wordpress-com"}
    assert result["channel_choices"] == {} and result["unmapped"] == []
    [need] = result["needs"]
    assert need["for"] == "instagram" and "image-generation" in need["options"]
    catalog = integration_catalog()
    providers = {key for option in need["options"].values() for key in option["providers"]}
    assert providers and all(catalog[key]["composio"] for key in providers)
    assert "social media accounts" in result["integration_categories"]

    assert main(["recommend", "--channels", "instagram", "--for", "higgsfield"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["needs"] == []
    assert "image-generation" not in result["complements"]


def test_validate_campaign_warns_about_unmet_integration_needs(oma, capsys):
    from hermes_cli.config import atomic_config_write

    tmp_path, main = oma
    definition = tmp_path / "demo.yaml"
    base = {"id": "demo", "name": "Demo", "description": "Test team.", "orchestrator": "demo__orchestrator",
            "agents": ["demo__orchestrator", "demo__publisher"]}
    for integrations, warned in ((["instagram", "reddit"], ["instagram"]), (["instagram", "higgsfield"], [])):
        atomic_config_write(definition, {**base, "integrations": integrations})
        assert main(["validate", "campaign", str(definition)]) == 0
        warnings = json.loads(capsys.readouterr().out)["warnings"]
        assert [text.split(" ", 1)[0] for text in warnings] == warned


def test_integration_needs_name_only_composio_tools_and_play_channels():
    import hermes_yaml as yaml
    from hermes_cli.oma_campaigns.integrations import integration_catalog, integration_needs

    catalog, needs = integration_catalog(), integration_needs()
    capabilities = needs["capabilities"]
    vocab = yaml.safe_load((Path(__file__).resolve().parents[3]
                            / "skills/oma/oma-campaigns/plays/vocab.yaml").read_text(encoding="utf-8"))
    assert set(needs["channels"]) <= set(vocab["channels"])
    tools = [*(key for keys in needs["channels"].values() for key in keys),
             *(key for row in capabilities.values() for key in row["providers"]), *needs["integrations"]]
    assert all(catalog.get(key, {}).get("composio") for key in tools)
    for row in needs["integrations"].values():
        used = [*row.get("complements", ()), *(name for need in row.get("needs", ()) for name in need["any_of"])]
        assert set(used) <= capabilities.keys()
