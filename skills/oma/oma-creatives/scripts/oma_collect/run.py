"""Command entry points: plan sources, collect organic posts and ads, export and apply labels."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import json
import logging
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests

from oma_collect import landing, media, store
from oma_collect.ads import LIBRARIES
from oma_collect.browser import Refused, TabGone, Unavailable, open_browser
from oma_collect.social import PLATFORMS
from oma_collect.values import iso, now, parse_iso, slug
from oma_collect.web import Fetcher

logger = logging.getLogger(__name__)

DETAIL_ALL_UP_TO = 40
DETAIL_TOP_BY_PROXY = 20
_FIELDS = ("id", "url", "posted_at", "caption", "hashtags", "format", "metrics", "media_sources", "media_referer",
           "pinned", "subreddit", "duration_s")


@dataclass
class Context:
    brand: Path
    target: str
    moment: dt.datetime = field(default_factory=now)
    harness_cdp: object = None
    fetcher: Fetcher = field(default_factory=Fetcher)
    _browser: object = None

    @property
    def root(self) -> Path:
        return store.target_root(self.brand, self.target)

    @property
    def home(self) -> Path:
        return self.brand.parents[1]

    def browser(self):
        if self._browser is None:
            self._browser = open_browser(self.harness_cdp)
        return self._browser

    def rel(self, path: Path) -> str:
        return path.relative_to(self.brand).as_posix()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()


def read_sources(root: Path) -> dict:
    sources = store.load(root / "sources.yaml")
    if not sources:
        raise FileNotFoundError(f"{root / 'sources.yaml'} is missing; write it first (see references/sources.md)")
    unknown = set(sources.get("socials") or {}) - set(PLATFORMS)
    if unknown:
        raise ValueError(f"sources.yaml lists unsupported platforms: {sorted(unknown)}")
    return sources


def plan_own(brand: Path) -> dict:
    """Write the brand's sources.yaml from the verified profiles in config.yaml."""
    config = store.load(brand / "config.yaml")
    socials = {entry["platform"]: entry["url"] for entry in (config.get("channels") or {}).get("social") or []
               if entry.get("status") == "verified" and entry.get("platform") in PLATFORMS and entry.get("url")}
    root = store.target_root(brand, "own")
    sources = store.load(root / "sources.yaml") or {}
    website = (config.get("website") or {}).get("url")
    sources.update({"target": "own", "name": config.get("name"), "website": website})
    sources["socials"] = {**socials, **(sources.get("socials") or {})}
    unsupported = sorted({entry.get("platform") for entry in (config.get("channels") or {}).get("social") or []
                          if entry.get("status") == "verified" and entry.get("platform") not in PLATFORMS})
    sources["unsupported"] = [platform for platform in unsupported if platform]
    defaults = ad_defaults(config.get("name"), website, sources["socials"])
    ads = sources.get("ads") or {}
    sources["ads"] = {library: ads.get(library) or defaults.get(library) for library in LIBRARIES}
    store.dump(root / "sources.yaml", sources)
    return sources


def ad_defaults(name: str | None, website: str | None, socials: dict) -> dict:
    """Ad-library identifiers derived from what research already verified."""
    domain = (urlsplit(website).hostname or "").removeprefix("www.") if website else ""
    defaults = {}
    if socials.get("facebook"):
        defaults["meta"] = {"page_url": socials["facebook"], "advertiser": name}
    elif name:
        defaults["meta"] = {"query": name, "advertiser": name}
    if domain:
        defaults["google"] = {"domain": domain}
    if socials.get("linkedin") or name:
        defaults["linkedin"] = {"company_url": socials.get("linkedin"), "advertiser": name}
    if name:
        defaults["tiktok"] = {"advertiser": name}
    return defaults


# ---- organic -----------------------------------------------------------------------------

def _for_detail(candidates: list[dict], moment: dt.datetime) -> list[dict]:
    if len(candidates) <= DETAIL_ALL_UP_TO:
        return candidates
    dated = sorted(candidates, key=lambda post: parse_iso(post.get("posted_at")) or moment, reverse=True)
    window = moment - dt.timedelta(days=store.TOP_WINDOW_DAYS)
    by_proxy = sorted((post for post in candidates if post.get("proxy") is not None
                       and (parse_iso(post.get("posted_at")) or moment) >= window), key=lambda post: post["proxy"], reverse=True)
    chosen = {post["id"]: post for post in dated[:store.LATEST] + by_proxy[:DETAIL_TOP_BY_PROXY]}
    return list(chosen.values())


def _hashtags(caption: str) -> list[str]:
    return sorted(set(tag.lower() for tag in re.findall(r"#(\w+)", caption or "")))


def _post_record(candidate: dict) -> dict:
    post = {key: candidate[key] for key in _FIELDS if key in candidate}
    post.setdefault("metrics", {"likes": None, "comments": None, "shares": None, "saves": None, "views": None})
    post.setdefault("caption", "")
    post.setdefault("hashtags", _hashtags(post["caption"]))
    return post


def _save_media(ctx: Context, folder: Path, record: dict) -> None:
    sources = record.pop("media_sources", None) or []
    referer = record.pop("media_referer", None)
    if record.get("media") or not sources:
        record.setdefault("media", [])
        return
    stored, failures = [], []
    for number, (url, kind) in enumerate(sources, 1):
        path, reason = media.save(ctx.fetcher, url, folder / slug(record["id"]), f"media-{number}", kind,
                                  referer=referer)
        if path:
            stored.append(ctx.rel(path))
        elif reason:
            failures.append(reason)
    record["media"] = stored
    if failures and not stored:
        record["media_note"] = "Media not saved: " + "; ".join(sorted(set(failures)))


def _proof(ctx: Context, folder: Path, url: str, reason: str | None, needs_browser: bool) -> dict | None:
    if not reason:
        return None
    proof = {"url": url, "reason": reason}
    if needs_browser and ctx._browser is not None:
        try:
            proof["screenshot"] = ctx.rel(ctx.browser().screenshot(folder / "proof.png"))
        except (Unavailable, OSError):
            pass  # the coverage note and URL still record the attempt
    return proof


def _detail(spec, ctx: Context, candidate: dict) -> dict:
    try:
        return spec.detail(ctx, candidate)
    except TabGone:
        return spec.detail(ctx, candidate)  # the sidecar dropped the tab mid-read; the retry opens a new one


def collect_platform(ctx: Context, platform: str, url: str) -> dict:
    folder = ctx.root / "socials" / platform
    index = store.load(folder / "index.yaml")
    spec = PLATFORMS[platform]
    try:
        with store.source_lock(ctx.home, platform):
            profile = spec.profile(ctx, url)
            proof = _proof(ctx, folder, url, profile.proof_reason, spec.needs_browser)
            details = _for_detail(profile.candidates, ctx.moment) if spec.detail else profile.candidates
            errors: list[str] = []
            for candidate in details:
                if spec.detail:
                    try:
                        candidate.update(_detail(spec, ctx, candidate))
                    except (Unavailable, Refused, requests.RequestException, KeyError, ValueError, TypeError) as exc:
                        errors.append(f"{exc.__class__.__name__}: {exc}"[:160])  # one bad post must not drop the platform
            posts = [store.finish_post(_post_record(c), profile.account.get("followers"), ctx.moment)
                     for c in details]
    except (Unavailable, Refused) as exc:
        index["coverage"] = store.coverage("not_checked", f"Collection could not run: {exc}")
        store.dump(folder / "index.yaml", index)
        return {"source": platform, "status": "not_checked", "note": str(exc)}
    selected, history = store.select_posts(store.merge_posts(index, posts, ctx.moment), ctx.moment)
    for post in selected:
        _save_media(ctx, folder, post)
    for post in history:
        post.pop("media_sources", None)
        post.pop("media_referer", None)
        post.setdefault("media", [])
    store.mark_post_winners(selected)
    window = ctx.moment - dt.timedelta(days=store.TOP_WINDOW_DAYS)
    recent = sum(1 for c in profile.candidates if (parse_iso(c.get("posted_at")) or window) > window)
    note = profile.note + (f" {len(errors)} posts could not be read (first: {errors[0]})." if errors else "")
    account = {**profile.account, "captured_at": iso(ctx.moment),
               "posts_last_90d": recent if profile.status == "checked" else "unknown"}
    index.update({"account": account, "posts": selected, "history": history,
                  "coverage": store.coverage(profile.status, note.strip(), visible_count=profile.visible_count, proof=proof)})
    store.dump(folder / "index.yaml", index)
    return {"source": platform, "status": profile.status, "posts": len(selected), "history": len(history),
            "visible": profile.visible_count, "note": note.strip()}


def run_organic(brand: Path, target: str, *, only: str | None = None, harness_cdp=None) -> list[dict]:
    ctx = Context(brand, target, harness_cdp=harness_cdp)
    sources = read_sources(ctx.root)
    results = []
    try:
        for platform, url in (sources.get("socials") or {}).items():
            if only and platform != only:
                continue
            if not url:
                folder = ctx.root / "socials" / platform
                index = store.load(folder / "index.yaml")
                index["coverage"] = store.coverage("not_found", "No verified profile on this platform.")
                store.dump(folder / "index.yaml", index)
                results.append({"source": platform, "status": "not_found"})
                continue
            results.append(collect_platform(ctx, platform, url))
    finally:
        ctx.close()
    link_promotions(ctx.root)
    return results


# ---- ads ---------------------------------------------------------------------------------

_PAGE_MEDIA = r"""(() => ({videos: [...document.querySelectorAll('video')].map(v => v.currentSrc || v.getAttribute('src') || '').filter(s => /^https:/.test(s)),
    images: [...document.images].filter(i => i.naturalWidth > 200).map(i => i.currentSrc || i.src).slice(0, 3)}))()"""


def _media_from_page(ctx: Context, ad: dict) -> None:
    """Some cards (Meta "multiple versions") show no media until their own page is opened."""
    for _ in range(2):
        try:
            state = ctx.browser().goto(ad["url"], wait=3)
            found = (ctx.browser().js(_PAGE_MEDIA) or {}) if state.verdict == "ok" else {}
        except TabGone:
            continue  # the sidecar dropped the tab mid-read; one retry opens a new one
        except (Unavailable, Refused) as exc:
            ad["media_note"] = f"Ad page not opened: {exc}"
            return
        ad["media_sources"] = [(src, "video") for src in found.get("videos") or []][:1] + [
            (src, "image") for src in found.get("images") or []][:2]
        return


def _collect_with_retry(ctx: Context, library: str, spec: dict):
    """Heavy library pages can crash the sidecar's tab; collect once more in a fresh tab before giving up."""
    try:
        return LIBRARIES[library].collect(ctx, spec)
    except TabGone:
        ctx.close()
        ctx._browser = None
        return LIBRARIES[library].collect(ctx, spec)


def _finish_ads(ctx: Context, folder: Path, selected: list[dict], history: list[dict]) -> None:
    """Media and landing pages, ad by ad: one failing ad is noted on that ad and never drops the library."""
    for ad in selected:
        if not ad.get("media") and not ad.get("media_sources"):
            _media_from_page(ctx, ad)
        _save_media(ctx, folder, ad)
    for ad in history:
        ad.pop("media_sources", None)
        ad.setdefault("media", [])
    landing.capture(ctx, folder, selected)


def _library_not_checked(folder: Path, index: dict, library: str, note: str) -> dict:
    index["coverage"] = store.coverage("not_checked", note)
    index.setdefault("ads", [])
    store.dump(folder / "index.yaml", index)
    return {"source": library, "status": "not_checked", "note": note}


def collect_library(ctx: Context, library: str, spec) -> dict:
    folder = ctx.root / "ads" / library
    index = store.load(folder / "index.yaml")
    if not spec or (isinstance(spec, dict) and spec.get("skip")):
        reason = spec.get("skip") if isinstance(spec, dict) else "No advertiser identifier was listed in sources.yaml."
        return _library_not_checked(folder, index, library, str(reason))
    try:
        with store.source_lock(ctx.home, f"ads-{library}"):
            result = _collect_with_retry(ctx, library, spec)
            proof = _proof(ctx, folder, LIBRARIES[library].home, result.proof_reason, True)
            fresh = [store.finish_ad({k: v for k, v in ad.items() if k != "card_index"}) for ad in result.ads]
            selected, history = store.merge_ads(index, fresh, complete=result.complete and result.status == "checked")
            _finish_ads(ctx, folder, selected, history)
    except (Unavailable, Refused) as exc:
        return _library_not_checked(folder, index, library, f"Collection could not run: {exc}")
    except Exception as exc:  # a library page that changed breaks only its own parser, not the run
        logger.exception("The %s ads collector failed", library)
        return _library_not_checked(folder, index, library,
                                    f"The {library} collector failed ({type(exc).__name__}: {exc}); rerun it once fixed.")
    store.mark_ad_winners(selected)
    index.update({"ads": selected, "history": history,
                  "coverage": store.coverage(result.status, result.note, proof=proof, total_shown=result.total_shown,
                                             **result.extra)})
    store.dump(folder / "index.yaml", index)
    return {"source": library, "status": result.status, "ads": len(selected), "history": len(history),
            "total_shown": result.total_shown, "note": result.note}


def run_ads(brand: Path, target: str, *, only: str | None = None, countries: list[str] | None = None,
            defer: str | None = None, harness_cdp=None) -> list[dict]:
    """Collect each library in ``sources.yaml``; ``defer`` records them all as not checked, for a later run."""
    ctx = Context(brand, target, harness_cdp=harness_cdp)
    sources = read_sources(ctx.root)
    specs = {library: {"skip": defer} if defer else (sources.get("ads") or {}).get(library) for library in LIBRARIES}
    if countries and isinstance(specs.get("tiktok"), dict):
        specs["tiktok"] = {**specs["tiktok"], "countries": countries}
    results = []
    try:
        for library, spec in specs.items():
            if not only or library == only:
                results.append(collect_library(ctx, library, spec))
    finally:
        ctx.close()
    link_promotions(ctx.root)
    pruned = store.prune(brand, ctx.root)
    if pruned:
        results.append({"source": "storage", "pruned_records": pruned})
    return results


# ---- links and labels --------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())[:60]


def link_promotions(root: Path) -> int:
    """An ad reusing an organic post's caption is ``promoted_from`` that post (skill How to Run step 4)."""
    posts = {}
    for index_path in (root / "socials").glob("*/index.yaml"):
        for post in store.load(index_path).get("posts") or []:
            key = _norm(post.get("caption"))
            if len(key) >= 20:
                posts[key] = (index_path, post["id"])
    linked, promoted = 0, {}
    for index_path in (root / "ads").glob("*/index.yaml"):
        index = store.load(index_path)
        changed = False
        for ad in index.get("ads") or []:
            match = posts.get(_norm(ad.get("primary_text")))
            if match and not ad.get("promoted_from"):
                ad["promoted_from"] = f"{match[0].parent.name}/{match[1]}"
                promoted.setdefault(match[0], set()).add(match[1])
                changed, linked = True, linked + 1
        if changed:
            store.dump(index_path, index)
    for index_path, ids in promoted.items():
        index = store.load(index_path)
        for post in index.get("posts") or []:
            if post["id"] in ids:
                post["promoted"] = True
        store.mark_post_winners(index.get("posts") or [])
        store.dump(index_path, index)
    return linked


def export_labels(brand: Path, target: str) -> list[dict]:
    root = store.target_root(brand, target)
    todo = []
    for kind, key in (("socials", "posts"), ("ads", "ads")):
        for index_path in sorted((root / kind).glob("*/index.yaml")):
            for record in store.load(index_path).get(key) or []:
                if any(record.get(label) is None for label in ("hook_type", "angle", "structure")) or record.get("format") is None:
                    todo.append({"source": f"{kind}/{index_path.parent.name}", "id": record["id"], "url": record.get("url"),
                                 "format": record.get("format"),
                                 "text": (record.get("caption") or record.get("primary_text") or "")[:600],
                                 "media": record.get("media") or [], "landing_facts": record.get("landing_facts")})
    return todo


def apply_labels(brand: Path, target: str, labels: list[dict], allowed: dict[str, set]) -> dict:
    """Write agent labels into the indexes; values outside the taxonomy are rejected, not stored."""
    root = store.target_root(brand, target)
    by_source: dict[str, dict] = {}
    rejected = []
    for entry in labels:
        bad = [key for key, values in allowed.items() if entry.get(key) is not None and entry[key] not in values]
        if bad:
            rejected.append({"id": entry.get("id"), "invalid": bad})
            continue
        by_source.setdefault(entry["source"], {})[entry["id"]] = entry
    applied = 0
    for source, entries in by_source.items():
        index_path = root / source / "index.yaml"
        index = store.load(index_path)
        for record in (index.get("posts") or []) + (index.get("ads") or []):
            entry = entries.get(record["id"])
            if not entry:
                continue
            for key in ("format", "hook_type", "angle", "structure", "landing_summary"):
                if entry.get(key) is not None:
                    record[key] = entry[key]
            applied += 1
        store.dump(index_path, index)
    return {"applied": applied, "rejected": rejected}


def dumps(results) -> str:
    return json.dumps(results, ensure_ascii=False, indent=1)
