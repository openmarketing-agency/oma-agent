"""Canonical OMA integrations, brand-derived candidates, and what each integration needs."""

from collections import Counter
from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path
import re
from typing import Iterable

from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import _member, read_mapping


def _schema_json(name: str) -> dict:
    resource = files("hermes_cli.oma_campaigns").joinpath("schemas", name)
    return json.loads(resource.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def integration_catalog() -> dict:
    return _schema_json("integrations.json")


@lru_cache(maxsize=1)
def integration_needs() -> dict:
    return _schema_json("integration-needs.json")


@lru_cache(maxsize=1)
def _slug_categories() -> dict[str, list[str]]:
    by_slug: dict[str, list[str]] = {}
    for label, slugs in _schema_json("composio-categories.json")["categories"].items():
        for slug in slugs:
            by_slug.setdefault(slug, []).append(label)
    return by_slug


def _aliases(catalog: dict) -> dict[str, str]:
    return {
        alias: key for key, row in catalog.items()
        for alias in (key, key.replace("-", "_"), row["composio"], *row.get("aliases", ()))
        if alias
    }


def _canonical(raw: str, aliases: dict[str, str]) -> str:
    return aliases.get(raw, raw.replace("_", "-"))


def brand_candidates(home: Path) -> dict:
    path = _member(_member(_member(home, "oma"), "brand"), "config.yaml")
    try:
        record = read_mapping(path)
    except FileNotFoundError:
        return {"candidates": [], "unmapped": []}
    validate_record("brand", record, path)
    catalog = integration_catalog()
    aliases = _aliases(catalog)
    observed = {key for key, row in record.get("integrations", {}).items() if row["status"] == "observed"}
    observed.update(row["platform"] for row in record.get("channels", {}).get("social", ())
                    if row["status"] == "verified")
    canonical = {_canonical(key, aliases) for key in observed}
    supported = {key for key in canonical if catalog.get(key, {}).get("composio")}
    return {"candidates": sorted(supported), "unmapped": sorted(canonical - supported)}


def _ranked(options: Iterable[str], preferred: set[str]) -> list[str]:
    """Keep the curated order, but put integrations the brand already shows first."""
    options = list(options)
    return [key for key in options if key in preferred] + [key for key in options if key not in preferred]


def _categories(keys: Iterable[str]) -> list[str]:
    catalog, by_slug = integration_catalog(), _slug_categories()
    return list(dict.fromkeys(label for key in keys for label in by_slug.get(catalog[key]["composio"], ())))


def _capability_category(capability: str) -> list[str]:
    """The label most of a capability's providers share, so one suggestion covers it."""
    providers = integration_needs()["capabilities"][capability]["providers"]
    counts = Counter(label for key in providers for label in _categories([key]))
    return [counts.most_common(1)[0][0]] if counts else []


def _provided(selected: Iterable[str]) -> set[str]:
    selected = set(selected)
    return {name for name, row in integration_needs()["capabilities"].items()
            if selected.intersection(row["providers"])}


def missing_needs(selected: Iterable[str]) -> list[dict]:
    """Needs of the selected integrations that no selected integration provides."""
    selected = list(selected)
    rows, provided = integration_needs()["integrations"], _provided(selected)
    return [{"for": key, **need} for key in selected for need in rows.get(key, {}).get("needs", ())
            if not provided.intersection(need["any_of"])]


def _terms(key: str) -> set[str]:
    row = integration_catalog().get(key, {})
    names = (key, key.replace("-", " "), row.get("name", ""), row.get("composio", "").replace("_", " "),
             *row.get("aliases", ()))
    return {name.strip().lower() for name in names if name and name.strip()}


def mentions(key: str, texts: Iterable[str]) -> bool:
    """Whether any text names the integration by its ID, display name, or Composio slug."""
    pattern = "|".join(re.escape(term) for term in sorted(_terms(key), key=len, reverse=True))
    found = re.compile(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])")
    return any(found.search(text.lower()) for text in texts)


def unplanned(record: dict) -> list[str]:
    """Declared integrations that no plan names, so no agent is given work for them."""
    plans = record.get("plans", ())
    return [key for key in record.get("integrations", ()) if not mentions(key, plans)]


def campaign_warnings(record: dict) -> list[str]:
    capabilities = integration_needs()["capabilities"]
    warnings = [f"{key} is declared but no plan uses it: add a plan saying what it produces and which role owns it"
                for key in unplanned(record)]
    for need in missing_needs(record.get("integrations", ())):
        names = " or ".join(capabilities[name]["name"].lower() for name in need["any_of"])
        warnings.append(f"{need['for']} needs {names}: {need['why']} Add one provider to integrations "
                        f"(see `recommend --for {need['for']}`), or plan the fallback: {need['fallback']}")
    return warnings


def _select(ids: Iterable[str], channels: Iterable[str], observed: set[str]) -> tuple[list, dict, list]:
    catalog, channel_map = integration_catalog(), integration_needs()["channels"]
    aliases = _aliases(catalog)
    selected, choices, unmapped = [], {}, []
    for raw in ids:
        key = _canonical(raw, aliases)
        (selected if catalog.get(key, {}).get("composio") else unmapped).append(key)
    for channel in channels:
        options = channel_map.get(channel)
        if not options:
            unmapped.append(channel)
            continue
        picked = ([key for key in options if key in selected] or [key for key in options if key in observed][:1]
                  or (options if len(options) == 1 else []))
        selected.extend(picked)
        if not picked:
            choices[channel] = _ranked(options, observed)
    return list(dict.fromkeys(selected)), choices, list(dict.fromkeys(unmapped))


def _complements(selected: list[str], skip: set[str], observed: set[str]) -> dict:
    capabilities, rows = integration_needs()["capabilities"], integration_needs()["integrations"]
    found: dict[str, list[str]] = {}
    for key in selected:
        for name in rows.get(key, {}).get("complements", ()):
            if name not in skip:
                found.setdefault(name, []).append(key)
    return {name: {"name": capabilities[name]["name"], "for": users,
                   "providers": _ranked(capabilities[name]["providers"], observed)}
            for name, users in found.items()}


def recommend(home: Path, ids: Iterable[str] = (), channels: Iterable[str] = ()) -> dict:
    """Suggest integrations for a campaign: chosen ones, their unmet needs, and complements.

    ``channels`` are play channel IDs; a channel with one possible integration, or
    one the brand already shows, is selected, and the rest are returned as choices.
    """
    capabilities = integration_needs()["capabilities"]
    observed = set(brand_candidates(home)["candidates"])
    selected, choices, unmapped = _select(ids, channels, observed)
    needs = [{**need, "options": {name: {"name": capabilities[name]["name"],
                                         "providers": _ranked(capabilities[name]["providers"], observed)}
                                  for name in need["any_of"]}}
             for need in missing_needs(selected)]
    needed = list(dict.fromkeys(name for need in needs for name in need["any_of"]))
    categories = [*_categories(selected), *(label for name in needed for label in _capability_category(name))]
    return {
        "integrations": selected,
        "channel_choices": choices,
        "needs": needs,
        "complements": _complements(selected, _provided(selected) | set(needed), observed),
        "integration_categories": list(dict.fromkeys(categories)),
        "unmapped": unmapped,
    }
