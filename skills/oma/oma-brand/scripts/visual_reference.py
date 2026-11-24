"""Inspect and capture an already-open public brand page via browser_exec."""

import base64
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


_INSPECT = r"""(() => {
const absoluteUrl = value => {
    try { return value ? new URL(value, document.baseURI).href : undefined; }
    catch { return undefined; }
};

function findWebsiteLogos() {
    if (/(^|\.)(instagram|tiktok)\.com$/i.test(location.hostname)) return [];
    const marker = /logo(?!ut)|wordmark/i;

    const filename = url => {
        try { return new URL(url).pathname.split('/').pop(); }
        catch { return ''; }
    };
    const homeLink = element => {
        const link = element.closest('a[href]');
        return link?.origin === location.origin && link.pathname === '/';
    };
    const strong = [], home = [], structured = [], previews = [], outsideHeader = [];
    const pageChrome = 'header, [role="banner"], nav, footer';
    const elements = document.querySelectorAll([
        'header img', 'header svg', '[role="banner"] img', '[role="banner"] svg',
        'nav img', 'nav svg', 'footer img', 'footer svg', 'header a[href]', '[itemprop="logo"]',
        '[class*="logo" i]', '[id*="logo" i]', '[class*="wordmark" i]'
    ].join(','));
    for (const element of elements) {
        if (element.closest('[aria-hidden="true"]') && !element.closest('a')) continue;
        const style = getComputedStyle(element);
        const box = element.getBoundingClientRect();
        // Skip hidden themes, off-screen slides and generic full-header containers.
        if (style.visibility !== 'visible' || Number(style.opacity) === 0 ||
            box.width < 12 || box.height < 10 || box.width > 650 || box.height > 225 ||
            box.left + scrollX < 0 || box.top + scrollY < 0) continue;
        const image = element.matches('img');
        if (image && (!element.complete || !element.naturalWidth)) continue;
        const css = /url\(["']?(.*?)["']?\)/.exec(style.backgroundImage + ' ' + style.maskImage)?.[1];
        const svg = element.matches('svg');
        if (!image && !svg && !css) continue;
        const label = ['alt','class','id','aria-label','title'].map(k => element.getAttribute(k) || '').join(' ');
        const url = absoluteUrl(image ? (element.currentSrc || element.getAttribute('src')) :
            style.maskImage === 'none' ? css : undefined);
        const wrapper = element.closest('[itemprop="logo"], [class*="logo" i], [id*="logo" i], [class*="wordmark" i]');
        const explicit = marker.test(label) || marker.test(filename(url)) || !!wrapper;
        const inChrome = !!element.closest(pageChrome);
        if (/captcha|placeholder|spinner|social[-_ ]?(?:icon|logo)|payment[-_ ]?(?:icon|logo)/i.test(label)) continue;
        if (!explicit && !(homeLink(element) && inChrome)) continue;
        const clip = {x: box.left + scrollX, y: box.top + scrollY,
            width: box.width, height: box.height, scale: 1};
        const group = !inChrome ? outsideHeader : explicit ? strong : home;
        group.push({kind: inChrome ? 'site-header' : 'site-mark', url, clip});
    }
    const addStructured = raw => {
        const url = absoluteUrl(typeof raw === 'string' ? raw : raw?.contentUrl || raw?.url || raw?.['@id']);
        if (url) structured.push({kind: 'structured-logo', url});
    };
    document.querySelectorAll('meta[itemprop="logo"], link[itemprop="logo"]').forEach(el =>
        addStructured(el.getAttribute('content') || el.getAttribute('href')));
    for (const script of [...document.querySelectorAll('script[type="application/ld+json"]')].slice(0, 16)) {
        if (script.textContent.length > 250000) continue;
        try {
            const queue = [JSON.parse(script.textContent)];
            for (let i = 0; i < queue.length && i < 100; i++) {
                const entry = queue[i];
                if (!entry || typeof entry !== 'object') continue;
                if (entry.logo) addStructured(entry.logo);
                for (const key of ['@graph', 'publisher', 'brand', 'organization']) {
                    if (entry[key]) queue.push(entry[key]);
                }
                if (Array.isArray(entry)) queue.push(...entry.slice(0, 100));
            }
        } catch { /* unrelated invalid JSON-LD */ }
    }
    for (const el of document.querySelectorAll('meta[property="og:image"], meta[name="twitter:image"]')) {
        const url = absoluteUrl(el.content);
        if (marker.test(filename(url))) previews.push({kind: 'logo-metadata', url});
    }
    const seen = new Set();
    return [...strong, ...structured, ...previews, ...home, ...outsideHeader].filter(candidate => {
        const key = candidate.url || JSON.stringify(candidate.clip);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

function findVisualAssets() {
    const assets = [], seen = new Set();
    const add = (kind, url, label, clip, inlineKey) => {
        if (!url?.startsWith('https:')) url = undefined;
        if (!url && !clip) return;
        const parsed = url && new URL(url);
        const optimized = parsed && parsed.origin === location.origin && parsed.pathname.endsWith('/_next/image');
        const key = JSON.stringify([kind, (optimized && parsed.searchParams.get('url')) || url || inlineKey || clip]);
        if (seen.has(key)) return;
        seen.add(key);
        assets.push({kind, url, label: label.trim().slice(0, 160), clip: url ? undefined : clip});
    };
    const classify = (label, smallSvg = false) => {
        if (/logo(?!ut)|wordmark/i.test(label)) return 'logos';
        if (/illustrat|artwork|diagram/i.test(label)) return 'illustrations';
        if (/\bicon\b|sprite|favicon/i.test(label) || smallSvg) return 'icons';
        if (/\bbackground\b|texture|pattern/i.test(label)) return 'backgrounds';
        return 'images';
    };
    const nodes = document.body ? [document.body, ...document.body.querySelectorAll('*')] : [];
    const maxNodes = 12000, maxAssets = 1000;
    for (let i = 0; i < nodes.length && i < maxNodes && assets.length < maxAssets; i++) {
        const el = nodes[i];
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        if (!box.width || !box.height || style.visibility !== 'visible' || Number(style.opacity) === 0) continue;
        const label = ['alt', 'aria-label', 'title', 'class', 'id'].map(key => el.getAttribute(key) || '').join(' ');
        const x = box.x + scrollX, y = box.y + scrollY;
        const clip = x >= 0 && y >= 0 && box.width <= 1600 && box.height <= 1600
            ? {x, y, width: box.width, height: box.height, scale: 1} : undefined;
        if (el.matches('img')) {
            const lazy = el.getAttribute('data-src') || el.getAttribute('data-original');
            const url = absoluteUrl(el.currentSrc || lazy || el.getAttribute('src'));
            // Keep a declared image URL even when it is lazy or its request failed. Staging still requires decode.
            if (el.naturalWidth > 2 || (!el.naturalWidth && url?.startsWith('https:'))) {
                add(classify(label + ' ' + (url?.split('?')[0].split('/').pop() || '')), url, label, clip);
            }
        } else if (el.matches('svg') && !el.parentElement?.closest('svg')) {
            const title = el.querySelector('title')?.textContent || '';
            const inlineKey = [el.getAttribute('viewBox'), style.color, style.fill, style.stroke, el.innerHTML];
            add(classify(label + ' ' + title, box.width <= 64 && box.height <= 64), undefined, label + ' ' + title,
                clip, inlineKey);
        } else if (el.matches('video[poster]')) {
            add('images', el.poster, label, undefined);
        } else if (el.matches('a[download]')) {
            const url = el.href;
            const name = el.getAttribute('download') || new URL(url).pathname.split('/').pop();
            if (/\.(avif|gif|ico|jpe?g|png|svg|webp)$/i.test(name)) add(classify(name), url, el.innerText, undefined);
        }
        for (const layer of [style, getComputedStyle(el, '::before'), getComputedStyle(el, '::after')]) {
            if (layer !== style && ['none', 'normal'].includes(layer.content)) continue;
            for (const match of layer.backgroundImage.matchAll(/url\(["']?(.*?)["']?\)/g)) {
                const kind = classify(label);
                add(kind === 'images' ? 'backgrounds' : kind, absoluteUrl(match[1]), label, undefined);
            }
            for (const match of layer.maskImage.matchAll(/url\(["']?(.*?)["']?\)/g)) {
                const kind = classify(label);
                add(kind === 'images' ? 'icons' : kind, absoluteUrl(match[1]), label, undefined);
            }
        }
    }
    for (const el of document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')) {
        add('icons', el.href, el.rel, undefined);
    }
    return {assets, limited: nodes.length > maxNodes || assets.length >= maxAssets};
}
    const title = document.title;
    const body = (document.body?.innerText || '').trim().slice(0, 2000);
    const meta = name => document.querySelector(`meta[property="${name}"]`)?.content;
    const images = selector => [...document.querySelectorAll(selector)].map(img => img.currentSrc || img.src);
    const blocked = !!document.querySelector('#slardar-config, ._wafchallengeid, #challenge-running, #challenge-form')
        || /^(just a moment|access denied|attention required|too many requests)\b/i.test(title)
        || /^(please wait\.{2,}|access denied|too many requests|you have been blocked)/i.test(body);
    const login_overlay = [...document.querySelectorAll('[role="dialog"], dialog[open]')]
        .some(dialog => dialog.getClientRects().length && /\b(log ?in|sign in|sign up)\b/i.test(dialog.innerText));
    return {url: location.href, title, body, blocked, login_overlay,
        ...(blocked || login_overlay ? {} : findVisualAssets()),
        logos: blocked ? [] : findWebsiteLogos(),
        images: [
            ...images('header img[alt*="profile picture" i], [data-e2e="user-avatar"] img, img[data-e2e="user-avatar"]'),
            ...images('header img[alt*="logo" i], nav img[alt*="logo" i]'),
            meta('og:image'), document.querySelector('meta[name="twitter:image"]')?.content
        ].filter(Boolean)};
})()"""

# Browser-side download is limited to the current origin, with no credentials or redirects.
# Decode before exporting to PNG so an SVG, HTML error or mislabeled image is never stored as-is.
_READ_LOGO = r"""(async (source) => {
    const url = new URL(source);
    if (url.origin !== location.origin || url.protocol !== 'https:') return null;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500);
    let objectUrl;
    try {
        const r = await fetch(url, {credentials: 'omit', mode: 'same-origin', redirect: 'error', signal: controller.signal});
        const type = r.headers.get('content-type')?.split(';')[0];
        if (!r.ok || !r.body || !type?.startsWith('image/')) return null;
        const reader = r.body.getReader(), chunks = [];
        let bytes = 0;
        for (;;) {
            const {done, value} = await reader.read();
            if (done) break;
            bytes += value.length;
            if (bytes > 3 * 1024 * 1024) return null;
            chunks.push(value);
        }
        objectUrl = URL.createObjectURL(new Blob(chunks, {type}));
        const img = new Image();
        img.src = objectUrl;
        await img.decode();
        const width = img.naturalWidth, height = img.naturalHeight;
        if (width < 8 || height < 8 || width > 8000 || height > 8000) return null;
        const canvas = document.createElement('canvas');
        const scale = Math.min(1, 1600 / Math.max(width, height));
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/png').split(',')[1];
    } catch { return null; }
    finally {
        controller.abort();
        clearTimeout(timer);
        if (objectUrl) URL.revokeObjectURL(objectUrl);
    }
})"""

_SECTION_HEIGHT = 8000
_MAX_SECTIONS = 5


def _page_key(url):
    parsed = urlsplit(url)
    return (parsed.hostname or "").removeprefix("www."), parsed.path.rstrip("/")


def _image_urls(candidates):
    urls = []
    for candidate in candidates:
        try:
            url = urlsplit(candidate)
            if url.scheme == "https" and url.hostname and url.port != 0 and not url.username and not url.password:
                if candidate not in urls:
                    urls.append(candidate)
        except ValueError:
            continue
    return urls


def _origin(url):
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port or 443


def _logo_attempts(candidates, source_url, *, js, cdp, allow_crop):
    # Prefer a real logo file to pixels sampled from a small header or a busy background.
    urls = _image_urls([candidate.get("url") or "" for candidate in candidates])
    same_origin = [url for url in urls if _origin(url) == _origin(source_url)]
    kinds = {candidate.get("url"): candidate["kind"] for candidate in reversed(candidates)}
    for url in same_origin[:4]:
        try:
            yield js(f"{_READ_LOGO}({json.dumps(url)})"), kinds[url], url
        except (RuntimeError, OSError):
            continue
    if not allow_crop:
        return
    for candidate in [candidate for candidate in candidates if candidate.get("clip")][:4]:
        try:
            shot = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip=candidate["clip"])
            yield shot["data"], candidate["kind"], source_url
        except (RuntimeError, OSError, KeyError):
            continue


def _extract_logo(candidates, source_url, directory, name, *, js, cdp, allow_crop):
    for encoded, kind, provenance in _logo_attempts(candidates, source_url, js=js, cdp=cdp, allow_crop=allow_crop):
        if not encoded or len(encoded) > 16 * 1024 * 1024:
            continue
        try:
            data = base64.b64decode(encoded, validate=True)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                continue
        except ValueError:
            continue
        path = directory / f"{name}-logo.png"
        try:
            with path.open("xb") as file:
                file.write(data)
        except OSError:
            return None
        return {"file": str(path), "kind": kind, "source_url": provenance}
    return None


_ASSET_KINDS = ("logos", "illustrations", "icons", "backgrounds", "images")


def _asset_inventory(page, screenshots):
    groups = {kind: [] for kind in _ASSET_KINDS}
    seen = set()
    candidates = [{**logo, "kind": "logos"} for logo in page.get("logos", [])]
    candidates.extend(page.get("assets", []))
    for kind, entries in groups.items():
        for item in candidates:
            if item["kind"] != kind:
                continue
            urls = _image_urls([item.get("url") or ""])
            clip = item.get("clip")
            if urls:
                identity = urls[0]
            elif clip:
                identity = tuple(clip[key] for key in ("x", "y", "width", "height"))
            else:
                continue
            if identity in seen:
                continue
            seen.add(identity)
            entry = {"id": f"{kind}-{len(entries) + 1}", "label": item.get("label", "")}
            if urls:
                entry["url"] = urls[0]
            if clip:
                entry["clip"] = clip
            entries.append(entry)
    return {"source_url": page["url"], "assets": groups, "screenshots": screenshots,
            "limited": bool(page.get("limited"))}


def stage_assets(inventory_path, output_dir, approved_ids, *, js, cdp):
    """Batch-stage explicitly approved inventory entries from the same open public page."""
    ids = set(approved_ids)
    if len(ids) > 12:
        raise ValueError("Stage no more than 12 approved entries per call")
    inventory = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    page = js(_INSPECT)
    if not page or page["blocked"] or page.get("login_overlay") or page["url"] != inventory["source_url"]:
        raise ValueError("Reopen the same unobstructed public page before staging assets")
    # Match back to fresh observations: an edited manifest cannot introduce a new URL or clip.
    current = _asset_inventory(page, [])["assets"]
    outcomes = {}
    for kind in _ASSET_KINDS:
        observed = {row["id"]: row for row in current[kind]}
        for entry in inventory["assets"][kind]:
            asset_id = entry["id"]
            if asset_id not in ids:
                continue
            if observed.get(asset_id) != entry:
                outcomes[asset_id] = {"status": "changed"}
                continue
            candidate = {**entry, "kind": kind}
            outcomes[asset_id] = _stage_asset(candidate, page["url"], Path(output_dir) / kind, js=js, cdp=cdp)
    return {asset_id: outcomes.get(asset_id, {"status": "not_found"}) for asset_id in sorted(ids)}


def _stage_asset(candidate, source_url, directory, *, js, cdp):
    # A clip is a visual reference, not the original asset from an external host.
    for encoded, _, provenance in _logo_attempts([candidate], source_url, js=js, cdp=cdp,
                                                  allow_crop=not candidate.get("url")):
        if not encoded or len(encoded) > 16 * 1024 * 1024:
            continue
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError:
            continue
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            continue
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{hashlib.sha256(data).hexdigest()}.png"
        try:
            with path.open("xb") as file:
                file.write(data)
        except FileExistsError:
            pass  # Identical staged bytes need only one file per category.
        return {"status": "original-render" if provenance != source_url else "rendered-reference",
                "file": str(path), "source_url": provenance}
    return {"status": "unavailable", "source_url": candidate.get("url") or source_url}


def capture_page(source_url, output_dir, name, *, js, cdp):
    """Inventory visuals, extract a primary logo candidate and capture public screenshots."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ValueError("Use a lowercase hyphenated screenshot name")
    page = js(_INSPECT)
    result = {"source_url": source_url, "status": "blocked", "image_candidates": [], "screenshots": []}
    if not page or page["blocked"] or _page_key(page["url"]) != _page_key(source_url):
        return result
    logos = page.get("logos", [])
    login_title = re.match(r"^(?:log ?in|sign in)\s*(?:[|•-]\s*(?:instagram|tiktok))?$", page["title"], re.IGNORECASE)
    if login_title or not (page["body"] or logos):
        return result
    result["image_candidates"] = _image_urls([logo.get("url") or "" for logo in logos] + page["images"])
    overlay = page.get("login_overlay")
    directory = Path(output_dir)
    if logos:
        directory.mkdir(parents=True, exist_ok=True)
        logo = _extract_logo(logos, page["url"], directory, name, js=js, cdp=cdp, allow_crop=not overlay)
        if logo:
            result["logo_candidate"] = logo
    if overlay:
        result["status"] = "login_overlay"
        return result

    result["status"] = "captured"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        size = cdp("Page.getLayoutMetrics")["cssContentSize"]
        width, height = math.ceil(size["width"]), math.ceil(size["height"])
        if not (0 < width <= 3840 and height > 0):
            raise ValueError("Unsupported page dimensions; use viewport screenshots")
        limit = min(height, _MAX_SECTIONS * _SECTION_HEIGHT)
        for y in range(0, limit, _SECTION_HEIGHT):
            suffix = f"-part-{y // _SECTION_HEIGHT + 1:02d}" if height > _SECTION_HEIGHT else ""
            path = directory / f"{name}{suffix}.png"
            if not path.exists():
                clip = {"x": 0, "y": y, "width": width, "height": min(_SECTION_HEIGHT, limit - y), "scale": 1}
                shot = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip=clip)
                data = base64.b64decode(shot["data"], validate=True)
                if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Browser did not return a PNG")
                with path.open("xb") as file:
                    file.write(data)
            result["screenshots"].append(str(path))
        if limit < height:
            result["status"] = "partial"
            result["capture_limit"] = "Page exceeds the screenshot height budget"
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        result["status"] = "partial" if result["screenshots"] else "capture_failed"
        result["capture_limit"] = str(exc)
    inventory = _asset_inventory(page, result["screenshots"])
    manifest = directory / f"{name}-assets.json"
    with manifest.open("x", encoding="utf-8") as file:
        json.dump(inventory, file, ensure_ascii=False, indent=2)
    result["asset_inventory"] = str(manifest)
    result["asset_counts"] = {kind: len(items) for kind, items in inventory["assets"].items()}
    result["asset_inventory_limited"] = inventory["limited"]
    return result
