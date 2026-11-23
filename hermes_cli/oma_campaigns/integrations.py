"""Canonical OMA integrations and candidates from saved brand evidence."""

from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path

from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping


@lru_cache(maxsize=1)
def integration_catalog() -> dict:
    resource = files("hermes_cli.oma_campaigns").joinpath("schemas", "integrations.json")
    return json.loads(resource.read_text(encoding="utf-8-sig"))


def brand_candidates(home: Path) -> dict:
    path = _member(_member(_member(home, "oma"), "brand"), "config.yaml")
    try:
        record = read_mapping(path)
    except FileNotFoundError:
        return {"candidates": [], "unmapped": []}
    validate_record("brand", record, path)
    catalog = integration_catalog()
    aliases = {
        alias: key for key, row in catalog.items()
        for alias in (key, key.replace("-", "_"), row["composio"], *row.get("aliases", ()))
        if alias
    }
    observed = {key for key, row in record.get("integrations", {}).items() if row["status"] == "observed"}
    observed.update(row["platform"] for row in record.get("channels", {}).get("social", ())
                    if row["status"] == "verified")
    canonical = {aliases.get(key, key.replace("_", "-")) for key in observed}
    supported = {key for key in canonical if catalog.get(key, {}).get("composio")}
    return {"candidates": sorted(supported), "unmapped": sorted(canonical - supported)}
