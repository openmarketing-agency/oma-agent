#!/usr/bin/env python3
"""Validate an OMA creatives collection.

Usage: python3 validate_creatives.py <path-to-oma/brand> <target>
  target: "own" or a competitor/reference id

Checks socials and ads indexes: caps, labels, winner rules, file references,
reuse flags, and the 400MB storage cap. Exits 1 on any error.
"""
import datetime as dt
import statistics
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML is not installed; validation was not run.")
    sys.exit(2)

PLATFORMS = {"instagram", "tiktok", "x", "linkedin", "facebook", "youtube", "reddit", "threads"}
LIBRARIES = {"meta", "google", "linkedin", "tiktok"}
COVERAGE = {"checked", "blocked", "not_found", "not_checked"}
FORMATS = {"image", "video", "carousel", "text", "story", "reel", "short", "thread", "other"}
HOOKS = {"question", "bold_claim", "stat", "problem", "demo_first", "before_after", "pov",
         "listicle", "testimonial", "founder", "trend", "meme", "other"}
ANGLES = {"pain", "outcome", "speed", "savings", "social_proof", "authority", "comparison",
          "urgency", "feature_demo", "founder_story", "ugc", "education", "offer", "novelty",
          "identity", "behind_the_scenes", "other"}
CAP_BYTES = 400 * 1024 * 1024

errors, warnings = [], []


def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def check_file(root, rel, where, pruned):
    if pruned:
        return
    p = Path(str(rel))
    if p.is_absolute() or ".." in p.parts:
        errors.append(f"{where}: path '{rel}' must be relative to oma/brand without '..'")
        return
    if not (root / p).is_file():
        errors.append(f"{where}: file '{rel}' does not exist")


def check_labels(rec, where):
    for key, allowed in (("format", FORMATS), ("hook_type", HOOKS), ("angle", ANGLES)):
        if rec.get(key) not in allowed:
            errors.append(f"{where}: {key} '{rec.get(key)}' not in taxonomy")
    if rec.get("reuse") != "not_permitted":
        errors.append(f"{where}: reuse must be 'not_permitted'")
    if not rec.get("structure"):
        warnings.append(f"{where}: missing structure note")


def load(path):
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        errors.append(f"{path}: invalid YAML ({e})")
        return {}


def check_socials(root, base):
    sdir = base / "socials"
    if not sdir.is_dir():
        warnings.append("no socials/ directory")
        return
    for pdir in sorted(d for d in sdir.iterdir() if d.is_dir()):
        plat = pdir.name
        where = f"socials/{plat}"
        if plat not in PLATFORMS:
            errors.append(f"{where}: unknown platform folder")
        idx_path = pdir / "index.yaml"
        if not idx_path.is_file():
            errors.append(f"{where}: index.yaml missing")
            continue
        idx = load(idx_path)
        if (idx.get("coverage") or {}).get("status") not in COVERAGE:
            errors.append(f"{where}: coverage.status must be one of {sorted(COVERAGE)}")
        if not (idx.get("account") or {}).get("profile_url"):
            errors.append(f"{where}: account.profile_url missing")
        posts = idx.get("posts") or []
        if len(posts) > 35:
            errors.append(f"{where}: {len(posts)} posts, cap is 35 (latest 25 + top 10)")
        latest = sum(1 for p in posts if "latest" in (p.get("selected_by") or []))
        top = sum(1 for p in posts if "top" in (p.get("selected_by") or []))
        if latest > 25:
            errors.append(f"{where}: {latest} posts selected as latest, cap is 25")
        if top > 10:
            errors.append(f"{where}: {top} posts selected as top, cap is 10")
        mature = [p.get("engagement") for p in posts
                  if not p.get("immature") and isinstance(p.get("engagement"), (int, float))]
        median = statistics.median(mature) if mature else None
        seen = set()
        for p in posts:
            pid = p.get("id", "?")
            w = f"{where}/{pid}"
            if pid in seen:
                errors.append(f"{w}: duplicate id")
            seen.add(pid)
            for key in ("url", "posted_at", "captured_at", "caption", "selected_by", "media"):
                if key not in p:
                    errors.append(f"{w}: missing '{key}'")
            check_labels(p, w)
            posted, captured = to_date(p.get("posted_at")), to_date(p.get("captured_at"))
            if posted and captured and (captured - posted).days < 2 and not p.get("immature"):
                errors.append(f"{w}: captured within 48h of posting, set immature: true")
            for m in p.get("media") or []:
                check_file(root, m, w, p.get("media_pruned"))
            if p.get("winner"):
                reason = p.get("winner_reason")
                if reason == "engagement_outlier":
                    if p.get("immature"):
                        errors.append(f"{w}: immature posts can't be engagement_outlier winners")
                    elif median and (p.get("engagement") or 0) < 3 * median:
                        errors.append(f"{w}: engagement below 3x platform median ({median})")
                elif reason == "promoted":
                    if not p.get("promoted"):
                        errors.append(f"{w}: winner_reason promoted needs promoted: true")
                else:
                    errors.append(f"{w}: post winner_reason must be engagement_outlier or promoted")


def check_ads(root, base):
    adir = base / "ads"
    if not adir.is_dir():
        warnings.append("no ads/ directory")
        return
    for ldir in sorted(d for d in adir.iterdir() if d.is_dir()):
        lib = ldir.name
        where = f"ads/{lib}"
        if lib not in LIBRARIES:
            errors.append(f"{where}: unknown library folder")
        idx_path = ldir / "index.yaml"
        if not idx_path.is_file():
            errors.append(f"{where}: index.yaml missing")
            continue
        idx = load(idx_path)
        if (idx.get("coverage") or {}).get("status") not in COVERAGE:
            errors.append(f"{where}: coverage.status must be one of {sorted(COVERAGE)}")
        ads = idx.get("ads") or []
        if len(ads) > 25:
            errors.append(f"{where}: {len(ads)} ad concepts, cap is 25")
        # Selection order: active concepts are listed before inactive ones.
        seen_inactive = False
        seen = set()
        for a in ads:
            aid = a.get("id", "?")
            w = f"{where}/{aid}"
            if aid in seen:
                errors.append(f"{w}: duplicate id")
            seen.add(aid)
            for key in ("url", "first_seen", "last_seen", "active", "days_running",
                        "variant_count", "landing_url", "media"):
                if key not in a:
                    errors.append(f"{w}: missing '{key}'")
            check_labels(a, w)
            if a.get("active") is False:
                seen_inactive = True
            elif seen_inactive:
                errors.append(f"{w}: active concepts must be listed before inactive ones")
            first, last = to_date(a.get("first_seen")), to_date(a.get("last_seen"))
            days = a.get("days_running")
            if first and last and isinstance(days, int) and abs((last - first).days - days) > 1:
                warnings.append(f"{w}: days_running {days} doesn't match first_seen..last_seen")
            for m in a.get("media") or []:
                check_file(root, m, w, a.get("media_pruned"))
            if a.get("landing_file"):
                check_file(root, a["landing_file"], w, a.get("media_pruned"))
            else:
                warnings.append(f"{w}: no landing page capture")
            if a.get("winner"):
                reason = a.get("winner_reason")
                if reason == "long_running":
                    if not (a.get("active") and isinstance(days, int) and days >= 30):
                        errors.append(f"{w}: long_running needs active: true and days_running >= 30")
                elif reason == "many_variants":
                    if (a.get("variant_count") or 0) < 3:
                        errors.append(f"{w}: many_variants needs variant_count >= 3")
                else:
                    errors.append(f"{w}: ad winner_reason must be long_running or many_variants")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    root, target = Path(argv[1]), argv[2]
    base = root / "research" / ("own" if target == "own" else f"competitors/{target}")
    if not base.is_dir():
        print(f"ERROR: target folder {base} not found")
        return 1
    check_socials(root, base)
    check_ads(root, base)
    if not (base / "creatives.md").is_file():
        errors.append("creatives.md summary is missing")
    size = sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
    if size > CAP_BYTES:
        errors.append(f"target uses {size / 1e6:.0f}MB, cap is 400MB; prune per Storage Rules")
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"\n{target}: {size / 1e6:.1f}MB")
    print("PASS" if not errors else f"FAIL: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
