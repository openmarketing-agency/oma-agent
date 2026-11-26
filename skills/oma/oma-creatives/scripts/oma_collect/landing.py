"""One above-the-fold capture per distinct ad landing page, shared by every ad that links to it."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from oma_collect.browser import Refused, TabGone, Unavailable

_TRACKING = ("utm_", "fbclid", "gclid", "msclkid", "ttclid", "li_fat_id", "mc_", "_hs")
_FACTS = r"""(() => {
    const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.top < innerHeight && r.bottom > 0; };
    const text = el => (el.innerText || el.value || '').replace(/\s+/g, ' ').trim();
    return {title: document.title, url: location.href,
        headlines: [...document.querySelectorAll('h1, h2')].filter(visible).map(text).filter(Boolean).slice(0, 3),
        description: (document.querySelector('meta[name=description]') || {}).content || null,
        ctas: [...new Set([...document.querySelectorAll('a, button, input[type=submit]')].filter(visible).map(text)
            .filter(t => t && t.length <= 32))].slice(0, 6)};
})()"""


def landing_key(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith(_TRACKING)]
    return urlunsplit((parts.scheme, (parts.hostname or "").removeprefix("www."), parts.path.rstrip("/"), urlencode(query), ""))


def capture(ctx, folder: Path, ads: list[dict]) -> int:
    """Fill ``landing_file`` and ``landing_facts``; the agent writes ``landing_summary`` from them."""
    done: dict[str, tuple[str | None, dict]] = {
        landing_key(ad["landing_url"]): (ad["landing_file"], ad.get("landing_facts") or {})
        for ad in ads if ad.get("landing_url") and ad.get("landing_file")}
    captured = 0
    for ad in ads:
        url = ad.get("landing_url")
        if not url or ad.get("landing_file"):
            continue
        key = landing_key(url)
        if key not in done:
            done[key] = _capture_one(ctx, folder / ad["id"], url)
            captured += done[key][0] is not None
        ad["landing_file"], ad["landing_facts"] = done[key]
        if done[key][0] is None:
            ad["landing_summary"] = ad.get("landing_summary") or done[key][1].get("unavailable")
    return captured


def _capture_one(ctx, folder: Path, url: str) -> tuple[str | None, dict]:
    """A failed landing page is noted on its ads; it never stops the library."""
    for attempt in range(2):
        try:
            browser = ctx.browser()
            state = browser.goto(url, wait=2)
            if state.verdict != "ok":
                return None, {"unavailable": f"Landing page not captured: the page was {state.verdict}."}
            facts = browser.js(_FACTS) or {}
            return ctx.rel(browser.screenshot(folder / "landing.png")), facts
        except TabGone:
            if attempt:
                return None, {"unavailable": "Landing page not captured: the browser tab kept closing."}
        except (Refused, Unavailable) as exc:
            return None, {"unavailable": f"Landing page not captured: {exc}"}
    return None, {"unavailable": "Landing page not captured."}
