"""Organic collectors, one per platform, in the ``PLATFORMS`` table.

A collector has a ``profile`` step (account snapshot, candidate posts, coverage) and an optional
``detail`` step that fills one candidate (caption, metrics, media sources). ``run`` fetches details
and media only for candidates that can be selected. Logged-out views often stop early; that is
``limited`` coverage with the visible count, never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
import html
import json
import re
import time
from typing import Callable
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from oma_collect.browser import CLOSE_OVERLAY
from oma_collect.values import (followers_in, from_unix, iso, linkedin_post_time, parse_count, parse_date,
                                parse_iso, tiktok_post_time, x_post_time)

PAGE_PAUSE = 2.0
_MISSING = re.compile(r"(page isn.t available|this account doesn.t exist|couldn.t find this account|"
                      r"page not found|this page isn.t available|user not found|no longer available)", re.IGNORECASE)


@dataclass
class Profile:
    account: dict
    candidates: list[dict]
    status: str = "checked"
    note: str = ""
    visible_count: int | None = None
    proof_reason: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Platform:
    profile: Callable
    detail: Callable | None = None
    needs_browser: bool = True


def _handle(url: str) -> str:
    path = [part for part in urlsplit(url).path.split("/") if part]
    return path[0] if path else ""


def _meta_js() -> str:
    return r"""(() => {
        const meta = name => (document.querySelector(`meta[property="${name}"]`) || document.querySelector(`meta[name="${name}"]`) || {}).content || null;
        return {desc: meta('og:description') || meta('description'), title: meta('og:title'), image: meta('og:image'),
            type: meta('og:type'), text: (document.body ? document.body.innerText : '').slice(0, 6000),
            times: [...document.querySelectorAll('time[datetime]')].map(t => t.getAttribute('datetime')).slice(0, 3),
            aria: [...document.querySelectorAll('[role=group][aria-label], [aria-label$="Reactions"], [aria-label$="reactions"]')].map(e => e.getAttribute('aria-label')).slice(0, 4),
            videos: [...document.querySelectorAll('video')].map(v => v.currentSrc || v.getAttribute('src') || '').filter(s => /^https:/.test(s)),
            posters: [...document.querySelectorAll('video[poster]')].map(v => v.poster).filter(Boolean),
            images: [...document.images].filter(i => i.naturalWidth >= 400).map(i => i.currentSrc || i.src).slice(0, 10)};
    })()"""


def _links_js(pattern: str) -> str:
    return r"""(() => {
        const re = new RegExp(__PATTERN__);
        const links = [...new Set([...document.querySelectorAll('a[href]')].map(a => a.href.split('?')[0]).filter(h => re.test(h)))];
        return {links, text: (document.body ? document.body.innerText : '').slice(0, 4000)};
    })()""".replace("__PATTERN__", json.dumps(pattern))


def _profile_state(ctx, url: str, *, scrolls: int, pattern: str):
    """Open a profile, scroll it (closing overlays by their own Close button), and read its links."""
    browser = ctx.browser()
    state = browser.goto(url, wait=PAGE_PAUSE)
    if state.verdict in ("captcha", "error"):
        return state, None
    browser.scroll(scrolls)
    data = browser.js(_links_js(pattern)) or {"links": [], "text": ""}
    return state, data


def _coverage_from(state, data, *, missing_text: str = "") -> tuple[str, str, int | None, str | None] | None:
    """Return (status, note, visible, proof reason) for failure states, None when the page is usable."""
    if state.verdict == "captcha":
        return "blocked", "A bot challenge appeared; it was not solved or bypassed.", None, "captcha"
    if state.verdict == "error":
        why = "showed a firewall block page" if state.denied else f"returned HTTP {state.http_status} with no public content"
        return "blocked", f"The page {why}; collect it again later.", None, "denied"
    text = (data or {}).get("text", "") + missing_text
    if _MISSING.search(text) or state.verdict == "empty":
        return "not_found", "The profile page does not exist or rendered nothing.", 0, None
    return None


_EMPTY = re.compile(r"(hasn.t (posted|shared)|no posts yet|no videos yet|no threads yet|no pins yet|\b0 posts\b)", re.IGNORECASE)
_PRIVATE = re.compile(r"(this account is private|private account|this profile is private)", re.IGNORECASE)


def _limited_or_checked(profile: Profile, state, text: str = "", want: int = 25) -> Profile:
    """No visible posts is "checked" only when the page says the account has none; otherwise nothing is claimed."""
    visible = len(profile.candidates)
    if visible == 0 and _PRIVATE.search(text or ""):
        profile.status, profile.visible_count, profile.proof_reason = "limited", 0, "private"
        profile.note = "The account is private; a logged-out visitor sees no posts."
        return profile
    if visible == 0 and not _EMPTY.search(text or ""):
        profile.status, profile.proof_reason = "not_checked", "no_posts_rendered"
        profile.note = ("The profile listed no posts and did not say it has none, so the page may not have rendered "
                        "for this browser; nothing was recorded as empty.")
        return profile
    if visible == 0:
        profile.note = "The profile says it has no posts."
        return profile
    if (state.login_dialog or state.login_wall) and visible < want:
        profile.status = "limited"
        profile.visible_count = visible
        profile.note = f"A logged-out visitor sees {visible} posts before a login prompt stops the feed."
        profile.proof_reason = "login_limit"
    return profile


def _failure(handle: str, url: str, failed) -> Profile:
    status, note, visible, reason = failed
    return Profile({"handle": handle, "profile_url": url}, [], status, note, visible, reason)


# ---- Instagram ---------------------------------------------------------------------------

_IG_DESC = re.compile(r"^([\d.,]+[KMB]?) likes?, ([\d.,]+[KMB]?) comments? - [\w.]+ on ([A-Za-z]+ \d{1,2}, \d{4}): (.*)$",
                      re.DOTALL | re.IGNORECASE)


def instagram_profile(ctx, url: str) -> Profile:
    handle = _handle(url)
    state, data = _profile_state(ctx, url, scrolls=3, pattern=r"instagram\.com/([^/]+/)?(p|reel)/[\w-]+/?$")
    failed = _coverage_from(state, data)
    if failed:
        return _failure(handle, url, failed)
    candidates = [{"id": link.rstrip("/").rsplit("/", 1)[-1], "url": link,
                   "format": "reel" if "/reel/" in link else None} for link in data["links"]]
    profile = Profile({"handle": f"@{handle}", "profile_url": url, "followers": followers_in(data["text"])}, candidates)
    return _limited_or_checked(profile, state, data["text"])


def parse_instagram(meta: dict) -> dict:
    match = _IG_DESC.match((meta.get("desc") or "").strip())
    post = {"metrics": {"likes": None, "comments": None, "shares": None, "saves": None, "views": None}}
    if match:
        post["metrics"]["likes"], post["metrics"]["comments"] = parse_count(match.group(1)), parse_count(match.group(2))
        date = parse_date(match.group(3))
        post["posted_at"] = f"{date.isoformat()}T00:00:00Z" if date else None
        post["caption"] = match.group(4).strip().strip('"').strip("“”")
    else:
        post["posted_at"], post["caption"] = None, (meta.get("desc") or "").strip()
    sources = [(src, "video") for src in meta.get("videos") or []][:1]
    if meta.get("image"):
        sources.append((meta["image"], "image"))
    post["media_sources"] = sources
    return post


def instagram_detail(ctx, candidate: dict) -> dict:
    ctx.browser().goto(candidate["url"], wait=PAGE_PAUSE)
    post = parse_instagram(ctx.browser().js(_meta_js()) or {})
    if not candidate.get("format"):
        post["format"] = "video" if any(kind == "video" for _, kind in post["media_sources"]) else "image"
    return post


# ---- TikTok ------------------------------------------------------------------------------

_TT_CARDS = r"""(() => [...document.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]')].map(a => ({
    href: a.href.split('?')[0], views: (a.querySelector('[data-e2e="video-views"]') || {}).innerText || null,
    pinned: /\bpinned\b/i.test(a.innerText), cover: (a.querySelector('img') || {}).src || null})))()"""


def tiktok_profile(ctx, url: str) -> Profile:
    handle = _handle(url).lstrip("@")
    browser = ctx.browser()
    state = browser.goto(url, wait=PAGE_PAUSE)
    failed = _coverage_from(state, {"text": ""})
    if failed:
        return _failure(f"@{handle}", url, failed)
    cards, seen = [], set()
    for _ in range(8):
        for card in browser.js(_TT_CARDS) or []:
            video_id = card["href"].rstrip("/").rsplit("/", 1)[-1]
            if video_id.isdigit() and video_id not in seen and f"@{handle}/" in card["href"].lower():
                seen.add(video_id)
                posted = tiktok_post_time(video_id)
                cards.append({"id": video_id, "url": card["href"], "posted_at": iso(posted), "pinned": card["pinned"],
                              "proxy": parse_count((card.get("views") or "").strip()), "cover": card.get("cover")})
        # Pinned videos can be years old; only the regular feed's age says how far back we have scrolled.
        oldest = min((parse_iso(card["posted_at"]) for card in cards if card["posted_at"] and not card["pinned"]), default=None)
        if len(cards) >= 120 or (oldest and (ctx.moment - oldest).days > 95):
            break
        browser.scroll(1)
    text = browser.js("document.body.innerText.slice(0, 3000)") or ""
    followers = parse_count(_after(text, r"([\d.,]+[KMB]?)\s*\n?\s*Followers"))
    profile = Profile({"handle": f"@{handle}", "profile_url": url, "followers": followers}, cards)
    return _limited_or_checked(profile, state, text, want=0)  # TikTok shows the whole feed; only emptiness is judged


def _after(text: str, pattern: str):
    match = re.search(pattern, text or "", re.IGNORECASE)
    return match.group(1) if match else None


def parse_tiktok_item(item: dict) -> dict:
    stats = item.get("stats") or {}
    video = item.get("video") or {}
    images = ((item.get("imagePost") or {}).get("images") or [])
    sources = []
    if images:
        for image in images[:10]:
            urls = (image.get("imageURL") or {}).get("urlList") or []
            if urls:
                sources.append((urls[0], "image"))
    elif video.get("playAddr") or video.get("downloadAddr"):
        sources.append((video.get("playAddr") or video.get("downloadAddr"), "video"))
    if video.get("cover"):
        sources.append((video["cover"], "image"))
    return {"posted_at": iso(from_unix(item.get("createTime"))), "caption": item.get("desc") or "",
            "hashtags": [tag.get("hashtagName") for tag in item.get("textExtra") or [] if tag.get("hashtagName")],
            "format": "carousel" if len(images) > 1 else "image" if images else "video",
            "metrics": {"likes": parse_count(stats.get("diggCount")), "comments": parse_count(stats.get("commentCount")),
                        "shares": parse_count(stats.get("shareCount")), "saves": parse_count(stats.get("collectCount")),
                        "views": parse_count(stats.get("playCount"))},
            "media_sources": sources, "duration_s": video.get("duration")}


def tiktok_item_from_html(page: str) -> dict | None:
    match = re.search(r'id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', page or "", re.DOTALL)
    if not match:
        return None
    try:
        scope = json.loads(match.group(1)).get("__DEFAULT_SCOPE__", {})
    except ValueError:
        return None
    return ((scope.get("webapp.video-detail") or {}).get("itemInfo") or {}).get("itemStruct") or None


def tiktok_detail(ctx, candidate: dict) -> dict:
    item = None
    for pause in (1.0, 4.0):  # TikTok throttles rapid page fetches; a short pause usually restores the data
        time.sleep(pause)
        item = tiktok_item_from_html(ctx.fetcher.get_text(candidate["url"]))
        if item:
            break
    if item:
        post = parse_tiktok_item(item)
        post["media_referer"] = "https://www.tiktok.com/"
        return post
    ctx.browser().goto(candidate["url"], wait=PAGE_PAUSE)
    meta = ctx.browser().js(_meta_js()) or {}
    desc = meta.get("desc") or ""
    return {"caption": desc.split(": ", 1)[-1], "format": "video",
            "metrics": {"likes": parse_count(_after(desc, r"([\d.,]+[KMB]?) Likes")),
                        "comments": parse_count(_after(desc, r"([\d.,]+[KMB]?) Comments")),
                        "shares": None, "saves": None, "views": None},
            "media_sources": [(src, "image") for src in (meta.get("posters") or [])[:1] or
                              ([candidate["cover"]] if candidate.get("cover") else [])]}


# ---- X -----------------------------------------------------------------------------------

_X_ARIA = re.compile(r"([\d,.]+[KMB]?) (repl(?:y|ies)|reposts?|likes?|bookmarks?|views?)", re.IGNORECASE)
_X_KEYS = {"repl": "comments", "repo": "shares", "like": "likes", "book": "saves", "view": "views"}


def parse_x_metrics(labels: list[str]) -> dict:
    metrics = {"likes": None, "comments": None, "shares": None, "saves": None, "views": None}
    for label in labels or []:
        for count, word in _X_ARIA.findall(label):
            metrics[_X_KEYS[word.lower()[:4]]] = parse_count(count)
    return metrics


def x_profile(ctx, url: str) -> Profile:
    handle = _handle(url)
    state, data = _profile_state(ctx, url, scrolls=3, pattern=rf"(x|twitter)\.com/{re.escape(handle)}/status/\d+$")
    failed = _coverage_from(state, data)
    if failed:
        return _failure(f"@{handle}", url, failed)
    candidates = [{"id": link.rsplit("/", 1)[-1], "url": link, "posted_at": iso(x_post_time(link.rsplit("/", 1)[-1]))}
                  for link in data["links"]]
    followers = parse_count(_after(data["text"], r"([\d.,]+[KMB]?)\s+Followers"))
    profile = Profile({"handle": f"@{handle}", "profile_url": url, "followers": followers}, candidates)
    return _limited_or_checked(profile, state, data["text"])


def x_detail(ctx, candidate: dict) -> dict:
    ctx.browser().goto(candidate["url"], wait=PAGE_PAUSE)
    meta = ctx.browser().js(_meta_js()) or {}
    image = meta.get("image") or ""
    sources = [(image, "image")] if re.search(r"pbs\.twimg\.com/(media|ext_tw_video_thumb|amplify_video_thumb|tweet_video_thumb)", image) else []
    if not sources and meta.get("posters"):
        sources = [(meta["posters"][0], "image")]  # a video post: keep its poster frame
    fmt = "video" if meta.get("posters") or "video_thumb" in image else "image" if sources else "text"
    return {"caption": meta.get("desc") or "", "metrics": parse_x_metrics(meta.get("aria")), "format": fmt,
            "media_sources": sources}


# ---- Facebook ----------------------------------------------------------------------------

_FB_LINK = r"facebook\.com/((?!ads/|help/|login|groups/)[^?#]+/(posts|videos)/[^/?#]+|reel/\d+|photo/?\?fbid=\d+|watch/\?v=\d+)"
_FB_REACTIONS = re.compile(r"All reactions:\s*([\d.,]+[KMB]?)\s+([\d.,]+[KMB]?)?\s*([\d.,]+[KMB]?)?")


def facebook_profile(ctx, url: str) -> Profile:
    handle = _handle(url)
    browser = ctx.browser()
    state = browser.goto(url, wait=PAGE_PAUSE)
    failed = _coverage_from(state, {"text": ""})
    if failed:
        return _failure(handle, url, failed)
    browser.scroll(4)
    data = browser.js(r"""(() => ({links: [...new Set([...document.querySelectorAll('a[href]')].map(a => a.href)
        .filter(h => new RegExp(__PATTERN__).test(h)).map(h => h.replace(/&__tn__=.*$/, '').replace(/&set=.*$/, '')))],
        text: document.body.innerText.slice(0, 4000)}))()""".replace("__PATTERN__", json.dumps(_FB_LINK))) or {"links": [], "text": ""}
    candidates = [{"id": _fb_id(link), "url": link} for link in data["links"] if _fb_id(link)]
    profile = Profile({"handle": handle, "profile_url": url, "followers": followers_in(data["text"])}, candidates)
    return _limited_or_checked(profile, state, data["text"])


def _fb_id(link: str) -> str | None:
    match = re.search(r"(?:fbid=|/posts/|/videos/|/reel/|[?&]v=)([\w.-]+)", link)
    return match.group(1) if match else None


def parse_facebook(meta: dict) -> dict:
    text = meta.get("text") or ""
    match = _FB_REACTIONS.search(text)
    date = parse_date(text)
    sources = [(src, "video") for src in meta.get("videos") or []][:1] + [(src, "image") for src in (meta.get("images") or [])[:1]]
    return {"posted_at": f"{date.isoformat()}T00:00:00Z" if date else None,
            "caption": meta.get("desc") or "",
            "metrics": {"likes": parse_count(match.group(1)) if match else None,
                        "comments": parse_count(match.group(2)) if match and match.group(2) else None,
                        "shares": parse_count(match.group(3)) if match and match.group(3) else None,
                        "saves": None, "views": None},
            "format": "video" if meta.get("videos") else "image" if meta.get("images") else "text",
            "media_sources": sources}


def facebook_detail(ctx, candidate: dict) -> dict:
    ctx.browser().goto(candidate["url"], wait=PAGE_PAUSE)
    ctx.browser().js(CLOSE_OVERLAY)
    return parse_facebook(ctx.browser().js(_meta_js()) or {})


# ---- LinkedIn ----------------------------------------------------------------------------

def linkedin_profile(ctx, url: str) -> Profile:
    handle = [part for part in urlsplit(url).path.split("/") if part][-1]
    state, data = _profile_state(ctx, url, scrolls=3,
                                 pattern=r"linkedin\.com/(posts/[^/?#]+-activity-\d+|feed/update/urn:li:activity:\d+)")
    failed = _coverage_from(state, data)
    if failed:
        return _failure(handle, url, failed)
    candidates = []
    for link in data["links"]:
        activity = re.search(r"activity[-:](\d+)", link)
        if activity:
            candidates.append({"id": activity.group(1), "url": link, "posted_at": iso(linkedin_post_time(activity.group(1)))})
    profile = Profile({"handle": handle, "profile_url": url, "followers": followers_in(data["text"])}, candidates)
    return _limited_or_checked(profile, state, data["text"])


def parse_linkedin(meta: dict) -> dict:
    title, text = meta.get("title") or "", meta.get("text") or ""
    likes = parse_count(_after(title, r"\|\s*([\d.,]+[KMB]?) likes?")) or parse_count(
        _after(" ".join(meta.get("aria") or []), r"([\d.,]+[KMB]?) Reactions"))
    return {"caption": meta.get("desc") or "", "format": "video" if meta.get("videos") else "image" if meta.get("image") else "text",
            "metrics": {"likes": likes, "comments": parse_count(_after(text, r"([\d.,]+[KMB]?) Comments?")),
                        "shares": parse_count(_after(text, r"([\d.,]+[KMB]?) Reposts?")), "saves": None, "views": None},
            "media_sources": [(meta["image"], "image")] if meta.get("image") else []}


def linkedin_detail(ctx, candidate: dict) -> dict:
    ctx.browser().goto(candidate["url"], wait=PAGE_PAUSE)
    return parse_linkedin(ctx.browser().js(_meta_js()) or {})


# ---- Threads -----------------------------------------------------------------------------

def threads_profile(ctx, url: str) -> Profile:
    handle = _handle(url).lstrip("@")
    state, data = _profile_state(ctx, url, scrolls=3, pattern=rf"threads\.(com|net)/@{re.escape(handle)}/post/[\w-]+$")
    failed = _coverage_from(state, data)
    if failed:
        return _failure(f"@{handle}", url, failed)
    candidates = [{"id": link.rsplit("/", 1)[-1], "url": link} for link in data["links"]]
    profile = Profile({"handle": f"@{handle}", "profile_url": url, "followers": followers_in(data["text"])}, candidates)
    return _limited_or_checked(profile, state, data["text"])


def parse_threads(meta: dict) -> dict:
    text = meta.get("text") or ""
    caption = (meta.get("desc") or "").strip()
    tail = text[text.find(caption[:40]) + len(caption):] if caption and caption[:40] in text else text
    counts = re.search(r"(?:^|\s)(\d[\d.,]*[KM]?)\s+(\d[\d.,]*[KM]?)\s+(\d[\d.,]*[KM]?)(?:\s+(\d[\d.,]*[KM]?))?\s", tail)
    metrics = {"likes": None, "comments": None, "shares": None, "saves": None,
               "views": parse_count(_after(text, r"([\d.,]+[KM]?) views"))}
    if counts:
        metrics["likes"], metrics["comments"] = parse_count(counts.group(1)), parse_count(counts.group(2))
        reposts, quotes = parse_count(counts.group(3)), parse_count(counts.group(4)) if counts.group(4) else 0
        metrics["shares"] = (reposts or 0) + (quotes or 0)
    times = meta.get("times") or []
    return {"posted_at": iso(parse_iso(times[0])) if times else None, "caption": caption, "metrics": metrics,
            "format": "video" if meta.get("videos") else "image" if meta.get("image") else "text",
            "media_sources": [(meta["image"], "image")] if meta.get("image") else []}


def threads_detail(ctx, candidate: dict) -> dict:
    ctx.browser().goto(candidate["url"], wait=PAGE_PAUSE)
    return parse_threads(ctx.browser().js(_meta_js()) or {})


# ---- YouTube (RSS over plain HTTP) -------------------------------------------------------

_ATOM = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
         "media": "http://search.yahoo.com/mrss/"}


def parse_youtube_feed(feed: str) -> list[dict]:
    posts = []
    for entry in ET.fromstring(feed).findall("a:entry", _ATOM):
        group = entry.find("media:group", _ATOM)
        link = (entry.find("a:link", _ATOM).get("href") if entry.find("a:link", _ATOM) is not None else "") or ""
        stats = group.find("media:community/media:statistics", _ATOM) if group is not None else None
        rating = group.find("media:community/media:starRating", _ATOM) if group is not None else None
        thumb = group.find("media:thumbnail", _ATOM) if group is not None else None
        title = (entry.findtext("a:title", "", _ATOM) or "").strip()
        description = (group.findtext("media:description", "", _ATOM) if group is not None else "") or ""
        posts.append({"id": entry.findtext("yt:videoId", "", _ATOM), "url": link,
                      "posted_at": iso(parse_iso(entry.findtext("a:published", "", _ATOM))),
                      "caption": f"{title}\n\n{description}".strip(), "format": "short" if "/shorts/" in link else "video",
                      "metrics": {"likes": parse_count(rating.get("count")) if rating is not None else None,
                                  "comments": None, "shares": None, "saves": None,
                                  "views": parse_count(stats.get("views")) if stats is not None else None},
                      "media_sources": [(thumb.get("url"), "image")] if thumb is not None else []})
    return posts


def youtube_profile(ctx, url: str) -> Profile:
    page = ctx.fetcher.get_text(url) or ""
    handle = _handle(url)
    channel = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', page) or re.search(r"/channel/(UC[\w-]{22})", url)
    if not channel:
        return _failure(handle, url, ("not_found", "No YouTube channel ID was found on the page.", 0, None))
    feed = ctx.fetcher.get_text("https://www.youtube.com/feeds/videos.xml", params={"channel_id": channel.group(1)})
    if not feed:
        return _failure(handle, url, ("blocked", "The channel's public RSS feed did not load.", None, "denied"))
    posts = parse_youtube_feed(feed)
    subscribers = _after(page, r'"subscriberCountText":\{[^}]*?"simpleText":"([\d.,]+[KMB]?) subscribers"') or _after(
        page, r'"content":"([\d.,]+[KMB]?) subscribers"')
    profile = Profile({"handle": handle, "profile_url": url, "followers": parse_count(subscribers),
                       "channel_id": channel.group(1)}, posts)
    if len(posts) >= 15:
        profile.status, profile.visible_count = "limited", len(posts)
        profile.note = "YouTube's public feed lists the latest 15 uploads; likes come from the feed, comments are not in it."
    return profile


# ---- Pinterest (RSS over plain HTTP) -----------------------------------------------------

def parse_pinterest_feed(feed: str) -> list[dict]:
    posts = []
    for item in ET.fromstring(feed).iter("item"):
        link = item.findtext("link", "") or ""
        body = item.findtext("description", "") or ""
        image = re.search(r'<img[^>]+src="([^"]+)"', body)
        pin = re.search(r"/pin/(\d+)", link)
        posted = item.findtext("pubDate", "")
        posts.append({"id": pin.group(1) if pin else link.rstrip("/").rsplit("/", 1)[-1], "url": link,
                      "posted_at": iso(_rfc822(posted)), "caption": html.unescape(re.sub(r"<[^>]+>", " ", body)).strip(),
                      "format": "image", "metrics": {"likes": None, "comments": None, "shares": None, "saves": None, "views": None},
                      "media_sources": [(image.group(1), "image")] if image else []})
    return posts


def _rfc822(value: str):
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def pinterest_profile(ctx, url: str) -> Profile:
    handle = _handle(url)
    feed = ctx.fetcher.get_text(f"https://www.pinterest.com/{handle}/feed.rss")
    if not feed:
        return _failure(handle, url, ("not_found", "The profile's public RSS feed did not load.", 0, None))
    posts = parse_pinterest_feed(feed)
    profile = Profile({"handle": handle, "profile_url": url, "followers": None}, posts)
    profile.status, profile.visible_count = "limited", len(posts)
    profile.note = "Pinterest's public feed lists recent pins without save counts; top pins cannot be ranked."
    return profile


# ---- Bluesky (public AppView API) --------------------------------------------------------

_BSKY = "https://public.api.bsky.app/xrpc/"


def parse_bluesky(item: dict, handle: str) -> dict:
    post = item.get("post") or {}
    record = post.get("record") or {}
    embed = post.get("embed") or {}
    images = embed.get("images") or (embed.get("media") or {}).get("images") or []
    sources = [(image.get("fullsize"), "image") for image in images if image.get("fullsize")]
    if embed.get("thumbnail"):
        sources.append((embed["thumbnail"], "image"))
    rkey = (post.get("uri") or "").rsplit("/", 1)[-1]
    return {"id": rkey, "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
            "posted_at": iso(parse_iso(record.get("createdAt"))), "caption": record.get("text") or "",
            "format": "video" if "video" in (embed.get("$type") or "") else "carousel" if len(images) > 1 else "image" if images else "text",
            "metrics": {"likes": post.get("likeCount"), "comments": post.get("replyCount"),
                        "shares": (post.get("repostCount") or 0) + (post.get("quoteCount") or 0), "saves": None, "views": None},
            "media_sources": sources}


def bluesky_profile(ctx, url: str) -> Profile:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    handle = parts[1] if len(parts) > 1 and parts[0] == "profile" else (parts[0] if parts else "")
    profile_data = ctx.fetcher.get_json(_BSKY + "app.bsky.actor.getProfile", params={"actor": handle})
    if not profile_data:
        return _failure(handle, url, ("not_found", "Bluesky has no profile for this handle.", 0, None))
    posts, cursor = [], None
    for _ in range(4):
        page = ctx.fetcher.get_json(_BSKY + "app.bsky.feed.getAuthorFeed",
                                    params={"actor": handle, "limit": 100, "filter": "posts_no_replies",
                                            **({"cursor": cursor} if cursor else {})}) or {}
        for item in page.get("feed") or []:
            if (item.get("post") or {}).get("author", {}).get("handle") == profile_data.get("handle") and not item.get("reason"):
                posts.append(parse_bluesky(item, handle))
        cursor = page.get("cursor")
        oldest = parse_iso(posts[-1]["posted_at"]) if posts else None
        if not cursor or (oldest and (ctx.moment - oldest).days > 95):
            break
    return Profile({"handle": f"@{profile_data.get('handle', handle)}", "profile_url": url,
                    "followers": profile_data.get("followersCount")}, posts)


# ---- Reddit ------------------------------------------------------------------------------

_REDDIT_POSTS = r"""(() => [...document.querySelectorAll('shreddit-post')].map(p => ({
    id: p.getAttribute('id') || '', url: p.getAttribute('permalink') ? 'https://www.reddit.com' + p.getAttribute('permalink') : '',
    title: p.getAttribute('post-title') || '', score: p.getAttribute('score'), comments: p.getAttribute('comment-count'),
    created: p.getAttribute('created-timestamp'), subreddit: p.getAttribute('subreddit-prefixed-name'),
    type: p.getAttribute('post-type'), content: p.getAttribute('content-href'),
    thumb: (p.querySelector('img[src*="redd.it"], img[src*="redditmedia"]') || {}).src || null})))()"""


def parse_reddit(row: dict) -> dict:
    sources = []
    if row.get("type") == "image" and row.get("content"):
        sources.append((row["content"], "image"))
    elif row.get("thumb"):
        sources.append((row["thumb"], "image"))
    return {"id": (row.get("id") or "").replace("t3_", "") or row.get("url", "").rstrip("/").rsplit("/", 2)[-2],
            "url": row.get("url"), "posted_at": iso(parse_iso(row.get("created"))),
            "caption": row.get("title") or "", "subreddit": row.get("subreddit"),
            "format": "image" if sources else "video" if row.get("type") == "video" else "text",
            "metrics": {"likes": parse_count(row.get("score")), "comments": parse_count(row.get("comments")),
                        "shares": None, "saves": None, "views": None},
            "media_sources": sources}


def reddit_profile(ctx, url: str) -> Profile:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    user = parts[1] if len(parts) > 1 and parts[0] in ("user", "u") else (parts[0] if parts else "")
    browser = ctx.browser()
    state = browser.goto(f"https://www.reddit.com/user/{user}/submitted/", wait=PAGE_PAUSE)
    failed = _coverage_from(state, {"text": ""})
    if failed:
        return _failure(f"u/{user}", url, failed)
    browser.scroll(4)
    rows = browser.js(_REDDIT_POSTS) or []
    posts = [parse_reddit(row) for row in rows if row.get("url")]
    profile = Profile({"handle": f"u/{user}", "profile_url": url, "followers": None}, posts)
    return _limited_or_checked(profile, state, browser.js("document.body ? document.body.innerText.slice(0, 4000) : ''") or "")


PLATFORMS: dict[str, Platform] = {
    "instagram": Platform(instagram_profile, instagram_detail),
    "tiktok": Platform(tiktok_profile, tiktok_detail),
    "facebook": Platform(facebook_profile, facebook_detail),
    "x": Platform(x_profile, x_detail),
    "linkedin": Platform(linkedin_profile, linkedin_detail),
    "youtube": Platform(youtube_profile, None, needs_browser=False),
    "pinterest": Platform(pinterest_profile, None, needs_browser=False),
    "threads": Platform(threads_profile, threads_detail),
    "bluesky": Platform(bluesky_profile, None, needs_browser=False),
    "reddit": Platform(reddit_profile, None),
}
