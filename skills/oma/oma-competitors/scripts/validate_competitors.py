#!/usr/bin/env python3
"""Validate OMA competitor research under <home>/oma/brand.

Usage: python3 validate_competitors.py <path-to-oma/brand>

Checks index.yaml structure, score totals, tier rules, depth caps and ordering,
evidence, file references, and creatives records. Exits 1 on any error.
"""
import datetime as dt
import re
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML, YAMLError
except ImportError:  # pragma: no cover
    print("ERROR: ruamel.yaml is not installed; run with the Hermes environment's Python. Validation was not run.")
    sys.exit(2)

DIMS = ["job", "buyer", "price", "market", "channel"]
TIERS = {"direct", "indirect", "excluded"}
STATUSES = {"active", "inactive", "acquired"}
DEPTHS = {"full", "light", "index_only"}
BUSINESS_TYPES = {"saas", "open_source", "ecommerce", "local", "marketplace", "other"}
COVERAGE_STATUS = {"checked", "blocked", "not_found", "not_checked"}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
URL = re.compile(r"^https?://\S+$")

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def as_date(value, where):
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        err(f"{where}: '{value}' is not a YYYY-MM-DD date")
        return None


def check_path(root, rel, where, required=True):
    if rel in (None, ""):
        if required:
            err(f"{where}: missing file path")
        return None
    p = Path(str(rel))
    if p.is_absolute() or ".." in p.parts:
        err(f"{where}: path '{rel}' must be relative to oma/brand without '..'")
        return None
    full = (root / p).resolve()
    try:
        full.relative_to(root.resolve())
    except ValueError:
        err(f"{where}: path '{rel}' escapes oma/brand")
        return None
    if not full.is_file():
        err(f"{where}: file '{rel}' does not exist")
        return None
    return full


def expected_tier(c):
    s = c.get("scores") or {}
    job, buyer = s.get("job", 0), s.get("buyer", 0)
    total = sum(s.get(d, 0) for d in DIMS)
    if c.get("status") == "inactive":
        return "excluded"
    if job == 0:
        return "excluded"
    capped = c.get("incumbent") and not c.get("named_by_brand")
    if job == 2 and buyer == 2 and total >= 8 and not capped:
        return "direct"
    if job >= 1 and buyer >= 1 and total >= 5:
        return "indirect"
    return "excluded"


def sort_key(c):
    return (-(c.get("total") or 0), -(c.get("mentions") or 0), c.get("id", ""))


def check_creatives(root, rel, owner):
    """Creatives are validated in depth by oma-creatives; here, check the summary exists."""
    check_path(root, rel, f"{owner}.creatives")


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    root = Path(argv[1])
    index_path = root / "research" / "competitors" / "index.yaml"
    if not index_path.is_file():
        print(f"ERROR: {index_path} not found")
        return 1
    try:
        idx = YAML(typ="safe").load(index_path.read_text()) or {}
    except YAMLError as e:
        print(f"ERROR: index.yaml is invalid YAML: {e}")
        return 1

    for key in ("version", "brand_id", "updated", "frame", "coverage", "competitors"):
        if key not in idx:
            err(f"index.yaml: missing '{key}'")
    if "updated" in idx:
        as_date(idx["updated"], "index.updated")

    frame = idx.get("frame") or {}
    for key in ("category_terms", "job", "buyer", "price_point", "markets", "business_type", "sources"):
        if not frame.get(key):
            err(f"frame: missing '{key}'")
    terms = frame.get("category_terms") or []
    if not 3 <= len(terms) <= 5:
        err(f"frame.category_terms: {len(terms)} terms, need 3 to 5")
    if frame.get("business_type") and frame["business_type"] not in BUSINESS_TYPES:
        err(f"frame.business_type must be one of {sorted(BUSINESS_TYPES)}")

    for i, cov in enumerate(idx.get("coverage") or []):
        if cov.get("status") not in COVERAGE_STATUS:
            err(f"coverage[{i}] ({cov.get('source')}): bad status '{cov.get('status')}'")
        if cov.get("status") in ("blocked", "not_checked") and not cov.get("note"):
            warn(f"coverage[{i}] ({cov.get('source')}): give a reason in 'note'")

    comps = idx.get("competitors") or []
    if len(comps) > 30:
        err(f"competitors: {len(comps)} candidates, cap is 30")
    ids = set()
    for c in comps:
        cid = c.get("id", "?")
        w = f"competitor '{cid}'"
        if not SLUG.match(str(cid)):
            err(f"{w}: id must be a lowercase hyphenated slug")
        if cid in ids:
            err(f"{w}: duplicate id")
        ids.add(cid)
        for key in ("name", "website", "tier", "status", "depth", "scores", "total",
                    "found_via", "mentions", "first_seen", "last_checked"):
            if key not in c:
                err(f"{w}: missing '{key}'")
        if c.get("tier") not in TIERS:
            err(f"{w}: tier must be one of {sorted(TIERS)}")
        if c.get("status") not in STATUSES:
            err(f"{w}: status must be one of {sorted(STATUSES)}")
        if c.get("depth") not in DEPTHS:
            err(f"{w}: depth must be one of {sorted(DEPTHS)}")
        scores = c.get("scores") or {}
        evidence = c.get("score_evidence") or {}
        for d in DIMS:
            v = scores.get(d)
            if v not in (0, 1, 2):
                err(f"{w}: scores.{d} must be 0, 1 or 2")
                continue
            if v > 0 and not URL.match(str(evidence.get(d, ""))):
                err(f"{w}: scores.{d}={v} needs a URL in score_evidence.{d}")
        if c.get("total") != sum(scores.get(d, 0) or 0 for d in DIMS):
            err(f"{w}: total {c.get('total')} != sum of scores")
        if not c.get("found_via"):
            err(f"{w}: found_via must list at least one discovery source")
        exp = expected_tier(c)
        if c.get("tier") in TIERS and c.get("tier") != exp:
            err(f"{w}: tier '{c.get('tier')}' but the rules give '{exp}'")
        if c.get("tier") == "excluded":
            if not c.get("exclusion_reason"):
                err(f"{w}: excluded entries need exclusion_reason")
            if c.get("depth") != "index_only":
                err(f"{w}: excluded entries must be depth index_only")
        for key in ("first_seen", "last_checked"):
            if key in c:
                as_date(c[key], f"{w}.{key}")

    # Depth caps and deterministic ordering
    for tier, depth, required in (("direct", "full", ("profile", "gtm", "creatives")),
                                  ("indirect", "light", ("profile", "gtm"))):
        ranked = sorted([c for c in comps if c.get("tier") == tier], key=sort_key)
        top = {c.get("id") for c in ranked[:5]}
        for c in ranked:
            cid = c.get("id")
            if cid in top and c.get("depth") != depth:
                err(f"competitor '{cid}': ranks in top 5 {tier}, depth must be '{depth}'")
            if cid not in top and c.get("depth") != "index_only":
                err(f"competitor '{cid}': outside top 5 {tier}, depth must be 'index_only'")
            if cid in top:
                for key in required:
                    if key == "creatives":
                        check_creatives(root, c.get(key), f"competitor '{cid}'")
                    else:
                        check_path(root, c.get(key), f"competitor '{cid}'.{key}")

    refs = idx.get("references") or []
    if len(refs) > 3:
        err(f"references: {len(refs)}, cap is 3")
    for r in refs:
        rid = r.get("id", "?")
        if rid in ids:
            err(f"reference '{rid}': already in competitors; a brand is one or the other")
        if not r.get("reason"):
            err(f"reference '{rid}': missing reason")
        check_creatives(root, r.get("creatives"), f"reference '{rid}'")

    for i, sq in enumerate(idx.get("status_quo") or []):
        if not sq.get("name"):
            err(f"status_quo[{i}]: missing name")

    for rel, level in (("research/competitors.md", err),
                       ("research/competitors/discovery.md", err),
                       ("research/competitors/changes.md", warn)):
        if not (root / rel).is_file():
            level(f"{rel} is missing")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    tiers = {t: sum(1 for c in comps if c.get("tier") == t) for t in TIERS}
    print(f"\n{len(comps)} candidates: {tiers['direct']} direct, {tiers['indirect']} indirect, "
          f"{tiers['excluded']} excluded; {len(refs)} references")
    print("PASS" if not errors else f"FAIL: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
