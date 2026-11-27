"""Required campaign tools: needs, chosen providers, optional extras and validation warnings."""

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


def need_provider(result):
    return result["needs"][0]["chosen"]


def test_create_adds_a_provider_and_plan_for_each_unmet_need(oma, capsys):
    from hermes_cli.oma_campaigns.integrations import mentions, missing_needs, with_needed_tools

    tmp_path, _ = oma
    home = tmp_path / ".hermes"
    record = {"integrations": ["instagram", "tiktok", "reddit"], "plans": ["Post on Instagram and TikTok."],
              "integration_categories": ["social media accounts"]}
    revised, added = with_needed_tools(home, record)
    [provider] = added
    assert missing_needs(revised["integrations"]) == []
    assert mentions(provider, revised["plans"][1:]) and revised["plans"][0] == record["plans"][0]
    assert len(revised["integration_categories"]) > 1
    assert with_needed_tools(home, revised) == (revised, [])


def test_needed_provider_prefers_one_the_brand_already_uses(oma):
    from hermes_cli.config import atomic_config_replace
    from hermes_cli.oma_campaigns.integrations import with_needed_tools

    tmp_path, _ = oma
    home = tmp_path / ".hermes"
    atomic_config_replace(home / "oma" / "brand" / "config.yaml", {
        "id": "demo", "name": "Demo", "description": "Example brand",
        "integrations": {"canva": {"status": "observed", "evidence": "research/design.md"}},
    })
    _, added = with_needed_tools(home, {"integrations": ["instagram"], "plans": ["Post on Instagram."]})
    assert added == ["canva"]


def test_required_tools_include_a_provider_for_each_need(oma, capsys):
    from hermes_cli.oma_campaigns.integrations import integration_catalog

    _, main = oma
    assert main(["required-tools", "--channels", "instagram,reddit,blog"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result["integrations"]) == {"instagram", "reddit", "wordpress-com", need_provider(result)}
    assert result["channel_choices"] == {} and result["unmapped"] == []
    [need] = result["needs"]
    assert need["for"] == "instagram" and "image-generation" in need["options"]
    assert need["chosen"] in need["options"]["image-generation"]["providers"]
    catalog = integration_catalog()
    providers = {key for option in need["options"].values() for key in option["providers"]}
    assert providers and all(catalog[key]["composio"] for key in providers)
    assert "social media accounts" in result["integration_categories"]

    assert main(["required-tools", "--channels", "instagram", "--for", "higgsfield"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["needs"] == []
    assert "image-generation" not in result["optional"]


def test_validate_campaign_warns_about_unmet_integration_needs(oma, capsys):
    from hermes_cli.config import atomic_config_write

    tmp_path, main = oma
    definition = tmp_path / "demo.yaml"
    base = {"id": "demo", "name": "Demo", "description": "Test team.", "orchestrator": "demo__orchestrator",
            "agents": ["demo__orchestrator", "demo__publisher"],
            "plans": ["Post on Instagram, answer on Reddit, and make images with Higgsfield."]}
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
        used = [*row.get("optional", ()), *(name for need in row.get("needs", ()) for name in need["any_of"])]
        assert set(used) <= capabilities.keys()
    # A provider picked for a need must not bring needs of its own, or picking could go on forever.
    needed = {name for row in needs["integrations"].values() for need in row.get("needs", ()) for name in need["any_of"]}
    assert not any(needs["integrations"].get(key, {}).get("needs") for name in needed
                   for key in capabilities[name]["providers"])
