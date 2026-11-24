"""The shared OMA schemas accept YAML records and reject malformed metadata."""

import json
from importlib.resources import files
from pathlib import Path

import hermes_yaml as yaml
import pytest
from jsonschema import Draft202012Validator


def validator(kind):
    resource = files("hermes_cli.oma_campaigns").joinpath("schemas", f"{kind}.schema.json")
    schema = json.loads(resource.read_text(encoding="utf-8-sig"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize("kind", ["brand", "playbook", "campaign", "agent"])
def test_oma_record_fixture(kind):
    fixture = Path(__file__).with_name("fixtures") / "oma_records" / f"{kind}.yaml"
    record = yaml.safe_load(fixture.read_text(encoding="utf-8-sig"))
    validator(kind).validate(record)


@pytest.mark.parametrize(("kind", "fields"), [
    ("brand", {"knowledge_base_file": "../notes.md"}),
    ("brand", {"knowledge_base_file": "docs/../notes.md"}),
    ("brand", {"website": {"status": "verified"}}),
    ("brand", {"website": {"status": "not_found", "url": "https://example.invalid"}}),
    ("brand", {"screenshots": [{"file": "screenshots/home.png"}]}),
    ("brand", {"screenshots": [{"file": "screenshots/../home.png", "source_url": "https://example.invalid"}]}),
    ("brand", {"screenshots": [{"file": "images/home.png", "source_url": "https://example.invalid"}]}),
    ("brand", {"screenshots": [{"file": "screenshots/home.html", "source_url": "https://example.invalid"}]}),
    ("brand", {"integrations": {"google_analytics": {"status": "connected"}}}),
    ("brand", {"integrations": {"google_analytics": {"status": "observed"}}}),
    ("brand", {"documentation": {"public": {"status": "verified", "url": "javascript:alert(1)"}}}),
    ("playbook", {"strategy": ["not inline"]}),
    ("campaign", {"agents": ["demo__worker"]}),
    ("campaign", {"agents": ["demo__orchestrator", "other__orchestrator"]}),
    ("campaign", {"goals": "not a list"}),
    ("campaign", {"integrations": ["google_analytics"]}),
    ("campaign", {"integrations": ["x", "x"]}),
    ("campaign", {"integration_categories": "analytics"}),
    ("campaign", {"integration_categories": ["analytics", "analytics"]}),
    ("campaign", {"integration_categories": [" "]}),
    ("campaign", {"integration_categories": [1]}),
    ("campaign", {"lifecycle_state": "running"}),
    ("campaign", {"model": 1}),
    ("agent", {"jobs": [{"id": "review", "schedule": "1d"}]}),
    ("agent", {"mcp_servers": {"docs": "not a mapping"}}),
    ("agent", {"available-keys": ["not a variable name"]}),
    ("agent", {"effective": {"model": "legacy-model"}}),
])
def test_schema_rejects_invalid_fields(kind, fields):
    record: dict[str, object] = {"id": "demo", "name": "Demo", "description": "Example"}
    if kind == "playbook":
        record["strategy"] = ""
    if kind == "campaign":
        record.update(orchestrator="demo__orchestrator", agents=["demo__orchestrator"])
    if kind == "agent":
        record["campaign_id"] = None
    assert not validator(kind).is_valid({**record, **fields})


def test_legacy_fields_still_validate():
    identity = {"id": "demo", "name": "Demo", "description": "Example"}
    validator("brand").validate({**identity, "knowledge_base": "Original inline brand notes."})
    validator("playbook").validate({**identity, "strategy": "", "brand_id": "old-brand"})
    validator("campaign").validate({**identity, "version": "0.1.0", "playbook": "old-playbook",
                                    "orchestrator": "demo__orchestrator", "agents": ["demo__orchestrator"]})
    validator("agent").validate({**identity, "campaign_id": None, "version": "0.1.0",
                                 "effective": {"mcp_servers": {}},
                                 "future_hermes_section": {"new_option": True}})
