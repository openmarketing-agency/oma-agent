#!/usr/bin/env python3
"""Validate an OMA creatives collection.

Usage (with the Hermes environment's Python): validate_creatives.py <path-to-oma/brand> <target>
  target: "own" or a competitor/reference id

Checks that every source planned in sources.yaml was collected or has honest coverage, then caps,
labels, winner rules, file references, reuse flags, coverage proof and the 400MB storage cap.
Exits 1 on any error.
"""
import datetime as dt
import statistics
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML, YAMLError
except ImportError:  # pragma: no cover
    print("ERROR: ruamel.yaml is not installed; run with the Hermes environment's Python. Validation was not run.")
    sys.exit(2)

PLATFORMS = {"instagram", "tiktok", "facebook", "x", "linkedin", "youtube", "pinterest", "threads",
             "bluesky", "reddit"}
LIBRARIES = {"meta", "google", "linkedin", "tiktok"}
COVERAGE = {"checked", "limited", "blocked", "not_found", "not_checked"}
FORMATS = {"image", "video", "carousel", "text", "story", "reel", "short", "thread", "other"}
HOOKS = {"question", "bold_claim", "stat", "problem", "demo_first", "before_after", "pov",
         "listicle", "testimonial", "founder", "trend", "meme", "other"}
ANGLES = {"pain", "outcome", "speed", "savings", "social_proof", "authority", "comparison",
          "urgency", "feature_demo", "founder_story", "ugc", "education", "offer", "novelty",
          "identity", "behind_the_scenes", "other"}
LATEST_CAP, TOP_CAP, POSTS_CAP, ADS_CAP = 25, 10, 35, 20
CAP_BYTES = 400 * 1024 * 1024

errors, warnings = [], []


def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.datetime.fromisoformat(str(v)).date()
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
        return YAML(typ="safe").load(path.read_text()) or {}
    except YAMLError as e:
        errors.append(f"{path}: invalid YAML ({e})")
        return {}


def check_coverage(root, cov, where):
    """A status is honest: limited says how much was visible, blocked says where and why."""
    status = (cov or {}).get("status")
    if status not in COVERAGE:
        errors.append(f"{where}: coverage.status must be one of {sorted(COVERAGE)}")
        return status
    note = str((cov or {}).get("note") or "").strip()
    if status == "limited" and not isinstance(cov.get("visible_count"), int):
        errors.append(f"{where}: limited coverage needs visible_count (how many posts or ads were visible)")
    if status in ("limited", "blocked", "not_checked") and not note:
        errors.append(f"{where}: {status} coverage needs a note saying why")
    if status == "blocked":
        proof = cov.get("proof") or {}
        if not proof.get("url"):
            errors.append(f"{where}: blocked coverage needs proof.url (the page that was tried)")
        if proof.get("screenshot"):
            check_file(root, proof["screenshot"], f"{where}/proof", False)
        elif not proof.get("reason"):
            errors.append(f"{where}: blocked coverage needs proof.screenshot or proof.reason")
    return status


def check_history(root, records, where):
    for r in records or []:
        for m in r.get("media") or []:
            check_file(root, m, f"{where}/history/{r.get('id', '?')}", r.get("media_pruned"))


def check_post(root, p, where, median):
    for key in ("url", "posted_at", "captured_at", "caption", "selected_by", "media"):
        if key not in p:
            errors.append(f"{where}: missing '{key}'")
    check_labels(p, where)
    posted, captured = to_date(p.get("posted_at")), to_date(p.get("captured_at"))
    if posted and captured and (captured - posted).days < 2 and not p.get("immature"):
        errors.append(f"{where}: captured within 48h of posting, set immature: true")
    for m in p.get("media") or []:
        check_file(root, m, where, p.get("media_pruned"))
    if not p.get("winner"):
        return
    reason = p.get("winner_reason")
    if reason == "engagement_outlier":
        if p.get("immature"):
            errors.append(f"{where}: immature posts can't be engagement_outlier winners")
        elif median and (p.get("engagement") or 0) < 3 * median:
            errors.append(f"{where}: engagement below 3x platform median ({median})")
    elif reason == "promoted":
        if not p.get("promoted"):
            errors.append(f"{where}: winner_reason promoted needs promoted: true")
    else:
        errors.append(f"{where}: post winner_reason must be engagement_outlier or promoted")


def check_platform(root, pdir):
    plat, where = pdir.name, f"socials/{pdir.name}"
    if plat not in PLATFORMS:
        errors.append(f"{where}: unknown platform folder")
    idx_path = pdir / "index.yaml"
    if not idx_path.is_file():
        errors.append(f"{where}: index.yaml missing")
        return
    idx = load(idx_path)
    status = check_coverage(root, idx.get("coverage"), where)
    posts = idx.get("posts") or []
    if status in ("checked", "limited") and not (idx.get("account") or {}).get("profile_url"):
        errors.append(f"{where}: account.profile_url missing")
    if status in ("checked", "limited") and not posts and not idx.get("history"):
        warnings.append(f"{where}: {status} but no posts were stored")
    if len(posts) > POSTS_CAP:
        errors.append(f"{where}: {len(posts)} selected posts, cap is {POSTS_CAP} (latest 25 + top 10); move older ones to history")
    latest = sum(1 for p in posts if "latest" in (p.get("selected_by") or []))
    top = sum(1 for p in posts if "top" in (p.get("selected_by") or []))
    if latest > LATEST_CAP:
        errors.append(f"{where}: {latest} posts selected as latest, cap is {LATEST_CAP}")
    if top > TOP_CAP:
        errors.append(f"{where}: {top} posts selected as top, cap is {TOP_CAP}")
    mature = [p.get("engagement") for p in posts if not p.get("immature") and isinstance(p.get("engagement"), (int, float))]
    median = statistics.median(mature) if mature else None
    seen = set()
    for p in posts:
        pid = p.get("id", "?")
        if pid in seen:
            errors.append(f"{where}/{pid}: duplicate id")
        seen.add(pid)
        check_post(root, p, f"{where}/{pid}", median)
    check_history(root, idx.get("history"), where)


def check_ad(root, a, where):
    for key in ("url", "first_seen", "last_seen", "active", "days_running", "variant_count", "landing_url", "media"):
        if key not in a:
            errors.append(f"{where}: missing '{key}'")
    check_labels(a, where)
    first, last = to_date(a.get("first_seen")), to_date(a.get("last_seen"))
    days = a.get("days_running")
    if first and last and isinstance(days, int) and abs((last - first).days - days) > 1:
        warnings.append(f"{where}: days_running {days} doesn't match first_seen..last_seen")
    for m in a.get("media") or []:
        check_file(root, m, where, a.get("media_pruned"))
    if not a.get("media") and not a.get("media_pruned"):
        warnings.append(f"{where}: no media stored ({a.get('media_note') or 'no reason recorded'})")
    if a.get("landing_file"):
        check_file(root, a["landing_file"], where, a.get("media_pruned"))
    elif a.get("landing_url"):
        warnings.append(f"{where}: no landing page capture")
    if not a.get("winner"):
        return
    reason = a.get("winner_reason")
    if reason == "long_running":
        if not (a.get("active") and isinstance(days, int) and days >= 30):
            errors.append(f"{where}: long_running needs active: true and days_running >= 30")
    elif reason == "many_variants":
        if (a.get("variant_count") or 0) < 3:
            errors.append(f"{where}: many_variants needs variant_count >= 3")
    else:
        errors.append(f"{where}: ad winner_reason must be long_running or many_variants")


def check_library(root, ldir):
    lib, where = ldir.name, f"ads/{ldir.name}"
    if lib not in LIBRARIES:
        errors.append(f"{where}: unknown library folder")
    idx_path = ldir / "index.yaml"
    if not idx_path.is_file():
        errors.append(f"{where}: index.yaml missing")
        return
    idx = load(idx_path)
    check_coverage(root, idx.get("coverage"), where)
    ads = idx.get("ads") or []
    if len(ads) > ADS_CAP:
        errors.append(f"{where}: {len(ads)} ad concepts, cap is {ADS_CAP}; move the rest to history")
    seen_inactive, seen = False, set()
    for a in ads:
        aid = a.get("id", "?")
        if aid in seen:
            errors.append(f"{where}/{aid}: duplicate id")
        seen.add(aid)
        if a.get("active") is False:
            seen_inactive = True
        elif a.get("active") and seen_inactive:
            errors.append(f"{where}/{aid}: active concepts must be listed before inactive ones")
        check_ad(root, a, f"{where}/{aid}")
    check_history(root, idx.get("history"), where)


def check_plan(root, base, target):
    """Every profile and library in sources.yaml needs an index; the brand's verified profiles must be planned."""
    plan = load(base / "sources.yaml") if (base / "sources.yaml").is_file() else None
    if plan is None:
        errors.append("sources.yaml is missing; list the target's profiles and ad identifiers first")
        return
    for platform, url in (plan.get("socials") or {}).items():
        if platform not in PLATFORMS:
            errors.append(f"sources.yaml: unsupported platform '{platform}' (record it in creatives.md Coverage instead)")
        elif url and not (base / "socials" / platform / "index.yaml").is_file():
            errors.append(f"socials/{platform}: listed in sources.yaml but not collected")
    for library in sorted(LIBRARIES):
        if not (base / "ads" / library / "index.yaml").is_file():
            errors.append(f"ads/{library}: no index.yaml; run the ads collector (a library without an identifier is recorded as not_checked)")
    if target != "own":
        return
    config = load(root / "config.yaml") if (root / "config.yaml").is_file() else {}
    planned = set(plan.get("socials") or {})
    for entry in ((config.get("channels") or {}).get("social") or []):
        if entry.get("status") == "verified" and entry.get("platform") in PLATFORMS and entry["platform"] not in planned:
            errors.append(f"sources.yaml: the brand's verified {entry['platform']} profile is not planned")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    root, target = Path(argv[1]), argv[2]
    base = root / "research" / ("own" if target == "own" else f"competitors/{target}")
    if not base.is_dir():
        print(f"ERROR: target folder {base} not found")
        return 1
    check_plan(root, base, target)
    socials = sorted(d for d in (base / "socials").iterdir() if d.is_dir()) if (base / "socials").is_dir() else []
    libraries = sorted(d for d in (base / "ads").iterdir() if d.is_dir()) if (base / "ads").is_dir() else []
    if not socials and not libraries:
        errors.append("no socials/ or ads/ folders: creatives.md alone is not a collection")
    for pdir in socials:
        check_platform(root, pdir)
    for ldir in libraries:
        check_library(root, ldir)
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
