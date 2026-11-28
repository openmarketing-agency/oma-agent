"""``index.yaml`` records: selection, winners, rerun merges, coverage, pruning and per-source locks.

Each index keeps the current selection in ``posts``/``ads`` (capped as the skill defines) and every
older record in ``history``, so reruns never delete a record outside the pruning rules.
"""

from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import os
from pathlib import Path
import statistics
import time

from ruamel.yaml import YAML

from oma_collect.values import iso, now, parse_iso

LATEST, TOP, ADS = 25, 10, 20
TOP_WINDOW_DAYS, IMMATURE_HOURS, REFRESH_DAYS = 90, 48, 14
STORAGE_CAP = 400 * 1024 * 1024
PRUNE_AGE_DAYS = 180
LABELS = ("format", "hook_type", "angle", "structure")


def _yaml() -> YAML:
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.width = 4096
    return yaml


def load(path: Path) -> dict:
    if not path.is_file():
        return {}
    return _yaml().load(path.read_text(encoding="utf-8")) or {}


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".yaml.part")
    with temp.open("w", encoding="utf-8") as stream:
        _yaml().dump(data, stream)
    temp.replace(path)


def target_root(brand: Path, target: str) -> Path:
    return brand / "research" / ("own" if target == "own" else f"competitors/{target}")


def coverage(status: str, note: str = "", **extra) -> dict:
    block = {"status": status, "date": now().date().isoformat(), "note": note}
    block.update({key: value for key, value in extra.items() if value is not None})
    return block


# ---- posts -------------------------------------------------------------------------------

def engagement(metrics: dict) -> int | None:
    values = [metrics.get(key) for key in ("likes", "comments", "shares", "saves")]
    present = [int(value) for value in values if isinstance(value, (int, float))]
    return sum(present) if present else None


def finish_post(post: dict, followers: int | None, moment: dt.datetime) -> dict:
    """Fill the derived fields of a freshly collected post."""
    post["engagement"] = engagement(post.get("metrics") or {})
    rate = post["engagement"] / followers if post["engagement"] is not None and followers else None
    post["engagement_rate"] = round(rate, 4) if rate is not None else None
    posted = parse_iso(post.get("posted_at"))
    post["captured_at"] = iso(moment)
    post["immature"] = bool(posted and moment - posted < dt.timedelta(hours=IMMATURE_HOURS))
    for key in LABELS:
        post.setdefault(key, None)
    post.setdefault("promoted", False)
    post.setdefault("media_pruned", False)
    post["reuse"] = "not_permitted"
    return post


def _posted(post: dict) -> dt.datetime:
    return parse_iso(post.get("posted_at")) or dt.datetime.min.replace(tzinfo=dt.UTC)


def select_posts(records: list[dict], moment: dt.datetime) -> tuple[list[dict], list[dict]]:
    """Latest 25 (pinned only when they fall inside by date) plus the top 10 mature posts of 90 days."""
    by_date = sorted(records, key=_posted, reverse=True)
    latest = [post for post in by_date if post.get("posted_at")][:LATEST]
    window = moment - dt.timedelta(days=TOP_WINDOW_DAYS)
    ranked = sorted((post for post in records if post.get("engagement") is not None and not post.get("immature")
                     and _posted(post) >= window), key=lambda post: post["engagement"], reverse=True)[:TOP]
    chosen = {id(post) for post in latest} | {id(post) for post in ranked}
    for post in records:
        post["selected_by"] = [tag for tag, group in (("latest", latest), ("top", ranked))
                               if any(post is member for member in group)]
    selected = sorted((post for post in records if id(post) in chosen), key=_posted, reverse=True)
    history = sorted((post for post in records if id(post) not in chosen), key=_posted, reverse=True)
    return selected, history


def mark_post_winners(posts: list[dict]) -> None:
    mature = [post["engagement"] for post in posts if not post.get("immature") and post.get("engagement") is not None]
    median = statistics.median(mature) if mature else None
    for post in posts:
        if median and not post.get("immature") and (post.get("engagement") or 0) >= 3 * median:
            post["winner"], post["winner_reason"] = True, "engagement_outlier"
        elif post.get("promoted"):
            post["winner"], post["winner_reason"] = True, "promoted"
        else:
            post["winner"], post["winner_reason"] = False, None


def merge_posts(index: dict, fresh: list[dict], moment: dt.datetime) -> list[dict]:
    """Keep every stored record and its labels; refresh metrics on posts younger than 14 days."""
    stored = {post["id"]: post for post in (index.get("posts") or []) + (index.get("history") or [])}
    for post in fresh:
        old = stored.get(post["id"])
        if old is None:
            stored[post["id"]] = post
            continue
        if moment - _posted(old) <= dt.timedelta(days=REFRESH_DAYS):
            for key in ("metrics", "engagement", "engagement_rate", "captured_at", "immature"):
                old[key] = post.get(key)
        if old.get("media_pruned") is False and not old.get("media") and post.get("media"):
            old["media"] = post["media"]
    return list(stored.values())


# ---- ads ---------------------------------------------------------------------------------

def finish_ad(ad: dict) -> dict:
    first, last = parse_iso(ad.get("first_seen")), parse_iso(ad.get("last_seen"))
    ad["days_running"] = (last - first).days if first and last else ad.get("days_running")
    for key in LABELS:
        ad.setdefault(key, None)
    for key in ("promoted_from", "landing_file", "landing_summary", "reach"):
        ad.setdefault(key, None)
    ad.setdefault("media_pruned", False)
    ad["reuse"] = "not_permitted"
    return ad


def _ad_rank(ad: dict):
    return (0 if ad.get("active") else 1, -(ad.get("days_running") or 0), -(ad.get("variant_count") or 1))


def mark_ad_winners(ads: list[dict]) -> None:
    for ad in ads:
        if ad.get("active") and (ad.get("days_running") or 0) >= 30:
            ad["winner"], ad["winner_reason"] = True, "long_running"
        elif (ad.get("variant_count") or 0) >= 3:
            ad["winner"], ad["winner_reason"] = True, "many_variants"
        else:
            ad["winner"], ad["winner_reason"] = False, None


def merge_ads(index: dict, fresh: list[dict], *, complete: bool) -> tuple[list[dict], list[dict]]:
    """Active concepts first by days running; an ad missing from a complete check becomes inactive."""
    stored = {ad["id"]: ad for ad in (index.get("ads") or []) + (index.get("history") or [])}
    seen = set()
    for ad in fresh:
        seen.add(ad["id"])
        old = stored.get(ad["id"])
        if old is None:
            stored[ad["id"]] = ad
            continue
        for key in ("last_seen", "active", "variant_count", "regions", "reach", "platforms"):
            if ad.get(key) is not None:
                old[key] = ad[key]
        first = [value for value in (parse_iso(old.get("first_seen")), parse_iso(ad.get("first_seen"))) if value]
        old["first_seen"] = min(first).date().isoformat() if first else old.get("first_seen")
        if not old.get("media") and ad.get("media"):
            old["media"] = ad["media"]
        finish_ad(old)
    if complete:
        for ad_id, ad in stored.items():
            if ad_id not in seen and ad.get("active"):
                ad["active"] = False
    ordered = sorted(stored.values(), key=_ad_rank)
    return ordered[:ADS], ordered[ADS:]


# ---- storage -----------------------------------------------------------------------------

def folder_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def prune(brand: Path, root: Path, cap: int = STORAGE_CAP) -> int:
    """Delete media in the skill's order until the target fits; returns the number of pruned records."""
    if folder_size(root) <= cap:
        return 0
    cutoff = now() - dt.timedelta(days=PRUNE_AGE_DAYS)
    pruned = 0
    for kind in ("ads", "socials"):
        for index_path in sorted((root / kind).glob("*/index.yaml")):
            index = load(index_path)
            key = "ads" if kind == "ads" else "posts"
            changed = False
            for record in (index.get(key) or []) + (index.get("history") or []):
                stamp = parse_iso(record.get("last_seen" if kind == "ads" else "posted_at"))
                old_inactive = kind == "socials" or not record.get("active")
                if record.get("winner") or record.get("media_pruned") or not (stamp and stamp < cutoff and old_inactive):
                    continue
                for rel in record.get("media") or []:
                    (brand / rel).unlink(missing_ok=True)
                record["media_pruned"], changed, pruned = True, True, pruned + 1
                if folder_size(root) <= cap:
                    break
            if changed:
                dump(index_path, index)
            if folder_size(root) <= cap:
                return pruned
    return pruned


@contextmanager
def source_lock(home: Path, source: str, *, wait_seconds: int = 1800, stale_seconds: int = 3600):
    """One collector per source at a time across parallel workers (rate limits are per site)."""
    lock_dir = home / "cache" / "oma-creatives" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir / f"{source}.lock"
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time():.0f}".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue  # released between our attempt and the check
            if age > stale_seconds:
                lock.unlink(missing_ok=True)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"another worker still holds the {source} collector lock")
            time.sleep(5)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)
