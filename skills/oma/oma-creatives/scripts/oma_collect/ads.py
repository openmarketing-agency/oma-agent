"""Ad-library collectors, one per library, in the ``LIBRARIES`` table.

Every library is public and logged out. A collector returns raw concepts; ``run`` merges them,
downloads media and captures landing pages. A bot challenge stops the library with proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import json
import re
import time
from typing import Callable
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from oma_collect.store import ADS
from oma_collect.values import parse_count, parse_date, parse_dates, parse_slash_date

PAUSE = 2.0
MAX_CANDIDATES = 50  # read this many cards, then keep the best ADS concepts

# EU/EEA, UK and Switzerland: the countries TikTok's Commercial Content Library covers.
TIKTOK_COUNTRIES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus", "CZ": "Czech Republic",
    "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
    "HU": "Hungary", "IS": "Iceland", "IE": "Ireland", "IT": "Italy", "LV": "Latvia", "LI": "Liechtenstein",
    "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland",
    "PT": "Portugal", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
    "CH": "Switzerland", "GB": "United Kingdom",
}


@dataclass
class AdsResult:
    ads: list[dict]
    status: str = "checked"
    note: str = ""
    proof_reason: str | None = None
    complete: bool = True
    total_shown: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Library:
    collect: Callable
    home: str  # the public page a coverage proof points to


def _blocked(state, what: str) -> AdsResult | None:
    if state.verdict == "captcha":
        return AdsResult([], "blocked", f"{what} showed a bot challenge; it was not solved or bypassed.", "captcha", False)
    if state.verdict == "error":
        why = "showed a firewall block page" if state.denied else f"returned HTTP {state.http_status} with no public content"
        return AdsResult([], "blocked", f"{what} {why}; collect it again later.", "denied", False)
    return None


def _zero(browser, confirms: str, what: str) -> AdsResult:
    """A zero counts only when the page says so; an unloaded results list is not an empty one."""
    text = browser.js("document.body ? document.body.innerText : ''") or ""
    if re.search(confirms, text, re.IGNORECASE | re.MULTILINE):
        return AdsResult([], "checked", f"{what} lists no ads for this advertiser.", total_shown=0)
    return AdsResult([], "not_checked", f"{what} results did not load, so an empty list was not recorded as no ads.",
                     "search_unavailable", False)


def _landing(href: str | None) -> str | None:
    if not href:
        return None
    parts = urlsplit(href)
    if parts.hostname in ("l.facebook.com", "lm.facebook.com"):
        return (parse_qs(parts.query).get("u") or [None])[0]
    return href


# ---- Meta --------------------------------------------------------------------------------

_FB_PAGE_ID = r"""(() => { const h = document.documentElement.innerHTML;
    const m = h.match(/"delegate_page":\{"id":"(\d+)"/) || h.match(/"pageID":"(\d+)"/);
    return m ? m[1] : null; })()"""

# Cards are read in batches: each is scrolled into view so its lazy media loads, and one evaluate
# call must finish inside the sidecar's script time limit.
_META_BATCH = 12
_META_CARDS = r"""(async (start, limit) => {
    const roots = [];
    for (const d of document.querySelectorAll('div')) {
        const n = (d.innerText.match(/Library ID:/g) || []).length;
        if (n === 1 && d.parentElement && (d.parentElement.innerText.match(/Library ID:/g) || []).length > 1) roots.push(d);
    }
    const out = [];
    for (const [index, r] of roots.entries()) {
        if (index < start || index >= start + limit) continue;
        r.scrollIntoView({block: 'center'});
        await new Promise(s => setTimeout(s, 700));
        const links = [...r.querySelectorAll('a[href]')].map(a => a.href);
        out.push({index, text: r.innerText,
            landing: links.find(h => /l\.facebook\.com\/l\.php/.test(h)) || links.find(h => !/facebook\.com/.test(h)) || null,
            page: links.find(h => /facebook\.com\/(?!ads\/|help\/|l\.php)[^/?]+\/?$/.test(h)) || null,
            videos: [...r.querySelectorAll('video')].map(v => v.getAttribute('src') || '').filter(s => /^https:/.test(s)),
            posters: [...r.querySelectorAll('video')].map(v => v.poster).filter(Boolean),
            images: [...r.querySelectorAll('img')].filter(i => i.naturalWidth > 150).map(i => i.currentSrc || i.src)});
    }
    return {total: roots.length, cards: out};
})"""

_META_SKIP = re.compile(r"^(Active|Inactive|Library ID:.*|Platforms|EU transparency|Open Dropdown|See ad details|See summary details|"
                        r"This ad has multiple versions|Sponsored|Sorry, we're having trouble playing this video\.|"
                        r"\d+ ads? use(s)? this creative and text|Started running on .*|[A-Z][a-z]{2} \d{1,2}, \d{4} - .*)$")


def parse_meta_card(card: dict, today: dt.date) -> dict | None:
    text = card.get("text") or ""
    library_id = re.search(r"Library ID:\s*(\d+)", text)
    if not library_id:
        return None
    lines = [line.strip() for line in text.replace("\u200b", "").split("\n") if line.strip()]
    active = "Active" in lines[:3]
    started = re.search(r"Started running on ([A-Z][a-z]{2} \d{1,2}, \d{4})", text)
    span = re.search(r"([A-Z][a-z]{2} \d{1,2}, \d{4}) - ([A-Z][a-z]{2} \d{1,2}, \d{4})", text)
    first = parse_date(started.group(1)) if started else parse_date(span.group(1)) if span else None
    last = today if active else (parse_date(span.group(2)) if span else None)
    body = [line for line in lines if not _META_SKIP.match(line)]
    advertiser = body[0] if body else None
    copy = body[1:]
    variants = re.search(r"(\d+) ads? use(?:s)? this creative", text)
    media = [(src, "video") for src in card.get("videos") or []][:1]
    media += [(src, "image") for src in (card.get("posters") or [])[:1] + (card.get("images") or [])[:3]]
    return {"id": f"meta-{library_id.group(1)}", "library": "meta",
            "url": f"https://www.facebook.com/ads/library/?id={library_id.group(1)}",
            "advertiser": advertiser, "platforms": [],
            "format": "video" if card.get("videos") or card.get("posters") else "image" if card.get("images") else None,
            "primary_text": copy[0] if copy else "", "headline": copy[-2] if len(copy) >= 3 else None,
            "cta": copy[-1] if len(copy) >= 2 else None, "landing_url": _landing(card.get("landing")),
            "first_seen": first.isoformat() if first else None, "last_seen": last.isoformat() if last else None,
            "active": active, "variant_count": int(variants.group(1)) if variants else 1, "regions": ["ALL"],
            "media_sources": media, "card_index": card.get("index")}


def _meta_url(page_id: str | None, query: str | None) -> str:
    params = {"active_status": "all", "ad_type": "all", "country": "ALL", "media_type": "all"}
    if page_id:
        params["view_all_page_id"] = page_id
    else:
        params.update(q=query, search_type="keyword_exact_phrase")
    return "https://www.facebook.com/ads/library/?" + urlencode(params)


def collect_meta(ctx, spec: dict) -> AdsResult:
    browser = ctx.browser()
    page_id = str(spec.get("page_id") or "") or None
    if not page_id and spec.get("page_url"):
        state = browser.goto(spec["page_url"], wait=PAUSE)
        page_id = browser.js(_FB_PAGE_ID) if state.verdict == "ok" else None
    if not page_id and not spec.get("query"):
        return AdsResult([], "not_found", "No Facebook page ID or search term was available for this advertiser.", complete=False)
    state = browser.goto(_meta_url(page_id, spec.get("query")), wait=PAUSE * 2)
    blocked = _blocked(state, "The Meta Ad Library")
    if blocked:
        return blocked
    total, cards = 0, []
    for _ in range(MAX_CANDIDATES // _META_BATCH + 4):
        batch = browser.js(f"({_META_CARDS})({len(cards)}, {_META_BATCH})") or {}
        total = batch.get("total") or total
        cards.extend(batch.get("cards") or [])
        if len(cards) >= MAX_CANDIDATES:
            break
        if len(cards) >= total:
            before = total
            browser.scroll(2)  # load the next page of cards
            total = (browser.js(f"({_META_CARDS})({len(cards)}, 0)") or {}).get("total") or total
            if total == before:
                break
    ads = [ad for ad in (parse_meta_card(card, ctx.moment.date()) for card in cards) if ad]
    if not ads:
        return _zero(browser, r"(^|\s)~?0 results|no ads match", "The Meta Ad Library")
    name = (spec.get("advertiser") or "").lower()
    if not page_id and name:
        ads = [ad for ad in ads if (ad.get("advertiser") or "").lower() == name]
        if not ads:
            return AdsResult([], "checked", f"A keyword search matched {len(cards)} cards, none from an advertiser named "
                             f"{spec.get('advertiser')}. Add the brand's Facebook page to sources.yaml for an exact search.",
                             complete=False, total_shown=0)
    result = AdsResult(ads, total_shown=total, extra={"page_id": page_id})
    if total >= MAX_CANDIDATES:
        result.note = f"Read the first {total} ad cards; the selection keeps the top {ADS} concepts."
    return result


# ---- Google Ads Transparency Center ------------------------------------------------------

_GOOGLE_LINKS = r"""(() => [...new Set([...document.querySelectorAll('a[href*="/creative/CR"]')].map(a => a.href.split('?')[0]))])()"""
_GOOGLE_DETAIL = r"""(() => ({text: document.body.innerText,
    images: [...document.images].filter(i => i.naturalWidth > 150 && /googlesyndication|ytimg|googleusercontent/.test(i.src)).map(i => i.src),
    videos: [...document.querySelectorAll('iframe[src*="youtube"]')].map(f => f.src)}))()"""
_GOOGLE_FORMATS = {"text": "text", "image": "image", "video": "video"}


def parse_google_detail(url: str, detail: dict, today: dt.date) -> dict:
    text = detail.get("text") or ""
    creative = re.search(r"/creative/(CR\d+)", url)
    last = parse_date(_after(text, r"Last shown:\s*([A-Z][a-z]{2,8} \d{1,2}, \d{4})") or "")
    first = parse_date(_after(text, r"First shown:\s*([A-Z][a-z]{2,8} \d{1,2}, \d{4})") or "")
    variations = re.search(r"\d+ of (\d+) variations", text)
    fmt = (_after(text, r"Format:\s*(\w+)") or "").lower()
    # The header reads "Ad details · FAQ · Ad details · <advertiser>": the name follows the last "Ad details".
    names = [name.strip() for name in re.findall(r"Ad details\s*\n\s*(.+)", text) if name.strip() != "FAQ"]
    advertiser = names[-1] if names else None
    return {"id": f"google-{creative.group(1).lower() if creative else 'unknown'}", "library": "google",
            "url": f"{url}?region=anywhere&hl=en", "advertiser": advertiser, "platforms": [],
            "format": _GOOGLE_FORMATS.get(fmt), "primary_text": "", "headline": None, "cta": None, "landing_url": None,
            "first_seen": first.isoformat() if first else None, "last_seen": last.isoformat() if last else None,
            "active": bool(last and (today - last).days <= 2), "variant_count": int(variations.group(1)) if variations else 1,
            "regions": ["anywhere"], "media_sources": [(src, "image") for src in (detail.get("images") or [])[:3]],
            "youtube": (detail.get("videos") or [None])[0]}


def _after(text: str, pattern: str):
    match = re.search(pattern, text or "")
    return match.group(1).strip() if match else None


_GOOGLE_ADVERTISERS = re.compile(r"/advertiser/(AR\d+)/creative/")


def _google_page_links(browser, url: str, need: int) -> tuple[list[str], str, AdsResult | None]:
    state = browser.goto(url, wait=PAUSE * 4)
    blocked = _blocked(state, "The Google Ads Transparency Center")
    if blocked:
        return [], "", blocked
    links: list[str] = []
    for _ in range(6):
        links = list(dict.fromkeys(links + (browser.js(_GOOGLE_LINKS) or [])))
        if len(links) >= need:
            break
        browser.scroll(1)
    return links, browser.js("document.body.innerText.slice(0, 3000)") or "", None


def collect_google(ctx, spec: dict) -> AdsResult:
    """A domain search previews a few creatives per advertiser; each advertiser's page lists them all."""
    browser = ctx.browser()
    if spec.get("advertiser_id"):
        advertisers = [spec["advertiser_id"]]
        total = None
    elif spec.get("domain"):
        preview, text, blocked = _google_page_links(
            browser, f"https://adstransparency.google.com/?region=anywhere&domain={quote(spec['domain'])}&hl=en", 1)
        if blocked:
            return blocked
        advertisers = list(dict.fromkeys(match.group(1) for link in preview if (match := _GOOGLE_ADVERTISERS.search(link))))
        total = parse_count((_after(text, r"~?([\d,.]+[KM]?) ads") or "").replace("~", ""))
    else:
        return AdsResult([], "not_found", "No advertiser ID or domain was available for this advertiser.", complete=False)
    links: list[str] = []
    for advertiser in advertisers[:3]:
        found, _, blocked = _google_page_links(
            browser, f"https://adstransparency.google.com/advertiser/{quote(advertiser)}?region=anywhere&hl=en", ADS - len(links))
        if blocked:
            return blocked
        links = list(dict.fromkeys(links + found))
        if len(links) >= ADS:
            break
    if not links:
        return _zero(browser, r"(^|\s)0 ads\b|no ads found|didn.t find any ads", "The Google Ads Transparency Center")
    ads = []
    for link in links[:ADS]:
        detail_state = browser.goto(f"{link}?region=anywhere&hl=en", wait=PAUSE * 2)
        if detail_state.verdict == "captcha":
            return AdsResult(ads, "blocked", "A bot challenge appeared on a creative page.", "captcha", False, total)
        ads.append(parse_google_detail(link, browser.js(_GOOGLE_DETAIL) or {}, ctx.moment.date()))
        time.sleep(PAUSE)
    note = "Google shows the last-shown date; the first-shown date is recorded only where the page lists it."
    return AdsResult(ads, note=note, total_shown=total, complete=len(links) <= ADS)


# ---- LinkedIn Ad Library -----------------------------------------------------------------

_LI_CARDS = r"""(() => [...document.querySelectorAll('a[href*="/ad-library/detail/"]')].map(a => {
    const card = a.closest('li, article, [class*=card]') || a.parentElement;
    return {href: a.href.split('?')[0], advertiser: (card ? card.innerText.split('\n').map(s => s.trim()).filter(Boolean)[0] : '') || ''};
}))()"""
_LI_DETAIL = r"""(() => ({text: document.body.innerText,
    images: [...document.images].filter(i => i.naturalWidth > 150 && /licdn/.test(i.src)).map(i => i.src),
    videos: [...document.querySelectorAll('video')].map(v => v.currentSrc || v.getAttribute('src') || '').filter(s => /^https:/.test(s)),
    posters: [...document.querySelectorAll('video[poster]')].map(v => v.poster)}))()"""
_LI_FORMAT = re.compile(r"\b(Single Image|Video|Carousel|Document|Text|Spotlight|Message|Conversation|Event|Follower|Job) Ad\b")


# LinkedIn's button labels; the copy block ends with one when the ad has a button.
_LI_CTAS = {"apply", "apply now", "attend", "buy now", "contact us", "download", "get quote", "join", "learn more",
            "register", "request demo", "see more", "shop now", "sign up", "subscribe", "view quote", "visit website"}


def parse_linkedin_ad(url: str, detail: dict) -> dict:
    """The detail page: copy between "Promoted" and the notice (text, then headline, then the button), the
    "Video Ad"-style format, "Advertiser <name>", the run dates, and the impressions range."""
    text = detail.get("text") or ""
    ad_id = re.search(r"/detail/(\d+)", url)
    copy = _after(text, r"(?s)Promoted\s*\n(.+?)\n(?:Please note|About the ad)") or ""
    lines = [line.strip() for line in copy.split("\n") if line.strip()]
    cta = lines.pop() if lines and lines[-1].lower() in _LI_CTAS else None
    fmt = _LI_FORMAT.search(text)
    dates = parse_dates(_after(text, r"(?:Ran from|Ad duration)([^\n]*\n?[^\n]*)") or "")
    impressions = _after(text, r"Total Impressions\s*\n?\s*([^\n]+)")
    kind = (fmt.group(1).lower() if fmt else "")
    media = [(src, "video") for src in detail.get("videos") or []][:1]
    media += [(src, "image") for src in (detail.get("posters") or [])[:1] + (detail.get("images") or [])[:3]]
    return {"id": f"linkedin-{ad_id.group(1) if ad_id else 'unknown'}", "library": "linkedin", "url": url,
            "advertiser": _after(text, r"Advertiser[ \t]*\n?[ \t]*([^\n]+)"), "paid_by": _after(text, r"Paid for by (.+)"),
            "platforms": ["linkedin"], "format": {"single image": "image", "video": "video", "carousel": "carousel",
                                                  "document": "carousel", "text": "text"}.get(kind, "other" if kind else None),
            "primary_text": " ".join(lines[:-1]) if len(lines) > 1 else (lines[0] if lines else ""),
            "headline": lines[-1] if len(lines) > 1 else None, "cta": cta, "landing_url": None,
            "first_seen": dates[0].isoformat() if dates else None, "last_seen": dates[-1].isoformat() if len(dates) > 1 else None,
            "active": None, "variant_count": 1, "regions": [], "reach": impressions, "media_sources": media}


_LI_ORG = r"""(() => { const m = document.documentElement.innerHTML.match(/urn:li:organization:(\d+)/); return m ? m[1] : null; })()"""


def collect_linkedin(ctx, spec: dict) -> AdsResult:
    """Search by the company's numeric ID when its page is known; an advertiser-name search is fuzzy."""
    browser = ctx.browser()
    if not spec.get("company_id") and spec.get("company_url"):
        state = browser.goto(spec["company_url"], wait=PAUSE)
        blocked = _blocked(state, "LinkedIn")
        if blocked:
            return blocked
        spec = {**spec, "company_id": browser.js(_LI_ORG)}
    params = {"companyIds": spec["company_id"]} if spec.get("company_id") else {"accountOwner": spec.get("advertiser") or ""}
    if not any(params.values()):
        return AdsResult([], "not_found", "No company ID or advertiser name was available.", complete=False)
    state = browser.goto("https://www.linkedin.com/ad-library/search?" + urlencode(params), wait=PAUSE * 2)
    blocked = _blocked(state, "The LinkedIn Ad Library")
    if blocked:
        return blocked
    cards: list[dict] = []
    for _ in range(4):
        seen = {card["href"] for card in cards}
        cards += [card for card in browser.js(_LI_CARDS) or [] if card["href"] not in seen]
        cards = list({card["href"]: card for card in cards}.values())
        if len(cards) >= MAX_CANDIDATES:
            break
        browser.scroll(1)
    if not cards:
        return _zero(browser, r"(^|\s)0 ads match|no ads match|^No results found$", "The LinkedIn Ad Library")
    text = browser.js("document.body.innerText.slice(0, 2000)") or ""
    total = parse_count((_after(text, r"([\d,]+) ads match") or "").replace(",", ""))
    name = (spec.get("advertiser") or "").strip().lower()
    if name and not spec.get("company_id"):
        cards = [card for card in cards if card["advertiser"].lower() == name]
    ads = []
    for card in cards[:ADS]:
        detail_state = browser.goto(card["href"], wait=PAUSE)
        if detail_state.verdict == "captcha":
            return AdsResult(ads, "blocked", "A bot challenge appeared on an ad page.", "captcha", False, total)
        ads.append(parse_linkedin_ad(card["href"], browser.js(_LI_DETAIL) or {}))
        time.sleep(PAUSE)
    note = "" if ads else "The library lists no ads whose advertiser matches this name."
    return AdsResult(ads, note=note or "LinkedIn shows run dates only for some regions; active status is not listed.",
                     total_shown=total, complete=len(cards) <= ADS)


# ---- TikTok Commercial Content Library ---------------------------------------------------

# The country picker is a custom widget: it opens only on a real pointer click, and its options are
# picked by visible text. The search counts only when the field then shows the chosen country.
_TT_COUNTRY_FIELD = ".country_filter_wrapper"
_TT_PICK = r"""(async (country) => {
    const wait = ms => new Promise(s => setTimeout(s, ms));
    for (let i = 0; i < 6; i++) {
        const option = [...document.querySelectorAll('[role=listbox] *, [role=option]')]
            .find(o => o.children.length === 0 && o.innerText && o.innerText.trim() === country);
        if (option) { (option.closest('[role=option], li') || option).click(); await wait(600); break; }
        await wait(500);
    }
    const field = document.querySelector('.country_filter_wrapper');
    return {options: document.querySelectorAll('[role=listbox] [role=option], [role=listbox] li').length,
            chosen: !!(field && field.innerText.includes(country))};
})"""
_TT_SEARCH = r"""(async (name) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    const input = [...document.querySelectorAll('input')].find(i => /name or keyword/i.test(i.placeholder || ''));
    const button = [...document.querySelectorAll('button')].find(b => b.innerText.trim() === 'Search');
    if (!input || !button) return {ok: false};
    setter.call(input, name); input.dispatchEvent(new Event('input', {bubbles: true}));
    button.click();
    await new Promise(s => setTimeout(s, 5000));
    return {ok: true};
})"""
_TT_RESULTS = r"""(() => ({total: (document.body.innerText.match(/Total ads:\s*([\d,]+)/) || [])[1] || null,
    cards: [...document.querySelectorAll('a[href*="ad_id="], a[href*="/ads/detail"]')].map(a => {
        const card = a.closest('[class*=card], li, article') || a;
        return {href: a.href, text: card.innerText};
    })}))()"""


def parse_tiktok_card(card: dict, country: str) -> dict | None:
    ad_id = (parse_qs(urlsplit(card.get("href") or "").query).get("ad_id") or [None])[0]
    if not ad_id:
        return None
    text = card.get("text") or ""
    dates = parse_dates(text) or [day for day in map(parse_slash_date, re.findall(r"\d{2}/\d{2}/\d{4}", text)) if day]
    return {"id": f"tiktok-{ad_id}", "library": "tiktok", "url": card["href"], "platforms": ["tiktok"],
            "advertiser": text.split("\n")[0].strip() if text else None, "format": "video", "primary_text": "",
            "headline": None, "cta": None, "landing_url": None,
            "first_seen": dates[0].isoformat() if dates else None, "last_seen": dates[-1].isoformat() if len(dates) > 1 else None,
            "active": None, "variant_count": 1, "regions": [country],
            "reach": _after(text, r"Unique users seen[:\s]*([^\n]+)"), "media_sources": []}


def _tiktok_search(browser, country: str, name: str) -> AdsResult | None:
    """Run one country's search; a result is returned only when the library must stop."""
    browser.click(_TT_COUNTRY_FIELD)
    picked = browser.js(f"({_TT_PICK})({json.dumps(country)})") or {}
    if not picked.get("chosen"):
        why = ("offered no countries to choose from on this network" if not picked.get("options")
               else f"did not accept {country} as the search country")
        return AdsResult([], "not_checked", f"The TikTok ad library {why}, so no search ran.", "search_unavailable", False)
    if not (browser.js(f"({_TT_SEARCH})({json.dumps(name)})") or {}).get("ok"):
        return AdsResult([], "not_checked", "The TikTok ad library search form was not found.", "search_unavailable", False)
    if browser.current().verdict == "captcha":
        return AdsResult([], "blocked", "The TikTok ad library showed a bot challenge on search; it was not solved "
                         "or bypassed.", "captcha", False)
    return None


def collect_tiktok(ctx, spec: dict) -> AdsResult:
    name = (spec.get("advertiser") or "").strip()
    if not name:
        return AdsResult([], "not_found", "No advertiser name was available.", complete=False)
    browser = ctx.browser()
    countries = spec.get("countries") or list(TIKTOK_COUNTRIES)
    found: dict[str, dict] = {}
    checked: list[str] = []
    for code in countries:
        state = browser.goto("https://library.tiktok.com/ads", wait=PAUSE)
        stop = _blocked(state, "The TikTok ad library") or _tiktok_search(browser, TIKTOK_COUNTRIES.get(code, code), name)
        if stop:
            stop.ads = list(found.values())
            stop.note += f" Checked {len(checked)} of {len(countries)} countries before stopping."
            stop.extra = {"countries_checked": checked}
            return stop
        results = browser.js(_TT_RESULTS) or {}
        for card in results.get("cards") or []:
            ad = parse_tiktok_card(card, code)
            if ad is None:
                continue
            if ad["id"] in found:
                found[ad["id"]]["regions"] = sorted(set(found[ad["id"]]["regions"]) | {code})
            else:
                found[ad["id"]] = ad
        checked.append(code)
        time.sleep(PAUSE)
    note = f"Searched {len(checked)} countries; ads shown in several countries are stored once with every region."
    return AdsResult(list(found.values()), note=note, extra={"countries_checked": checked})


LIBRARIES: dict[str, Library] = {
    "meta": Library(collect_meta, "https://www.facebook.com/ads/library/"),
    "google": Library(collect_google, "https://adstransparency.google.com/"),
    "linkedin": Library(collect_linkedin, "https://www.linkedin.com/ad-library/"),
    "tiktok": Library(collect_tiktok, "https://library.tiktok.com/ads"),
}
