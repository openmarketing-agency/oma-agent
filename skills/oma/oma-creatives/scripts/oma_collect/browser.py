"""Page drivers for public collection: Camofox REST first, the Hermes browser via CDP as a fallback.

Both drivers expose the same small surface (``goto``, ``js``, ``screenshot``, ``close``) so every
collector runs unchanged on either. Sessions are fresh and logged out; nothing here logs in, solves
a challenge or removes an overlay except through the page's own visible Close button.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import time
from urllib.parse import quote, urlsplit
from uuid import uuid4

import requests


class Unavailable(Exception):
    """The browser backend cannot be reached or does not support what collection needs."""


class Refused(Exception):
    """A URL is not a public HTTP(S) page Hermes policy allows."""


class ApiError(Unavailable):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class TabGone(Unavailable):
    """Camofox closed the tab (it expires idle or crashed tabs); a new navigation can recover."""


@dataclass(frozen=True)
class PageState:
    url: str
    title: str
    http_status: int
    text_len: int
    captcha: bool
    login_dialog: bool
    login_wall: bool
    denied: bool = False

    @property
    def verdict(self) -> str:
        """``ok``, ``captcha``, ``error`` (a denial or firewall block page) or ``empty`` (nothing rendered)."""
        if self.captcha:
            return "captcha"
        if self.denied or (self.http_status >= 400 and self.text_len < 200):
            return "error"
        return "empty" if self.text_len < 40 else "ok"


_SETTLE = """({href: location.href, ready: document.readyState, title: document.title,
    text: Math.round((document.body?.innerText || '').length / 50)})"""

# The LinkedIn Ad Library embeds an invisible reCAPTCHA Enterprise anchor on every detail page;
# only a visible challenge counts.
_SIGNALS = r"""(() => {
    const text = document.body ? document.body.innerText : '';
    const low = text.toLowerCase();
    const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
    const dialogs = [...document.querySelectorAll('[role=dialog], dialog[open]')].filter(visible);
    const frames = [...document.querySelectorAll('iframe')].filter(f => visible(f) && f.offsetWidth > 120
        && /captcha|challenge/i.test(f.src) && !/recaptcha\/enterprise\/anchor/.test(f.src));
    return {href: location.href, title: document.title, text_len: text.length,
        captcha: frames.length > 0 || !!document.querySelector('._wafchallengeid, #challenge-running, #challenge-form')
            || /verify you are human|security check|unusual traffic|select \d+ objects that|slide to verify|press and hold/.test(low),
        login_dialog: dialogs.some(d => /\b(log ?in|sign in|sign up|join now)\b/i.test(d.innerText)),
        login_wall: /log in to (see|continue)|sign up to see|create an account to|log in or sign up|sign in to see|join to see/.test(low),
        // A web-application firewall page (LinkedIn: "Sorry, you have been blocked") is a denial, not an empty result.
        // X answers headless Chrome with "Access to x.com was denied ... HTTP ERROR 403".
        denied: /^(sorry, )?you have been blocked|you've been blocked|access (to [^\n]{1,60} )?(was|has been )?denied|you don.t have authorization to view this page|http error 40[13]|request blocked|too many requests|temporarily (blocked|restricted)/.test(low.trim().slice(0, 400)),
        // CDP navigation reports no HTTP status; the page's own navigation timing does.
        status: ((performance.getEntriesByType('navigation') || [])[0] || {}).responseStatus || 0};
})()"""

# Uses only the overlay's own visible Close/Dismiss control, as the creatives skill allows.
# Instagram's Close control is an <svg aria-label="Close">, which has no .click(); dispatch a click on
# its button ancestor instead. Never let overlay handling break collection.
CLOSE_OVERLAY = r"""(() => { try {
    const labels = /^(close|dismiss|not now|×)$/i;
    for (const dialog of document.querySelectorAll('[role=dialog], dialog[open]')) {
        if (!dialog.getClientRects().length) continue;
        for (const el of dialog.querySelectorAll('[aria-label], button, [role=button]')) {
            const label = (el.getAttribute('aria-label') || el.innerText || '').trim();
            if (!labels.test(label) || !el.getClientRects().length) continue;
            const target = el.closest('button, [role=button], a') || el;
            if (typeof target.click === 'function') target.click();
            else target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
            return label;
        }
    }
    return null;
} catch (e) { return null; } })()"""

SCROLL = "window.scrollBy(0, Math.round(innerHeight * 1.8)); document.documentElement.scrollHeight"


def check_public(url: str) -> None:
    from tools.browser_url_policy import evaluate_url_safety, url_is_private
    from tools.url_safety import is_safe_url

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise Refused(f"Only public HTTP(S) pages can be collected: {url}")
    if url_is_private(url) or not is_safe_url(url):
        raise Refused(f"Refusing a private or unsafe address: {url}")
    if evaluate_url_safety(url):
        raise Refused(f"Hermes browser policy does not allow {url}")


def _state(signals: dict, http_status: int) -> PageState:
    return PageState(url=str(signals.get("href") or ""), title=str(signals.get("title") or ""),
                     http_status=http_status or int(signals.get("status") or 0), text_len=int(signals.get("text_len") or 0),
                     captcha=bool(signals.get("captcha")), login_dialog=bool(signals.get("login_dialog")),
                     login_wall=bool(signals.get("login_wall")), denied=bool(signals.get("denied")))


class _Driver:
    """Shared settle and page-state logic; subclasses provide ``_navigate``, ``js`` and ``_png``."""

    name = "browser"
    settle_reads = 16
    pause = 0.5

    def goto(self, url: str, *, wait: float = 0.0) -> PageState:
        check_public(url)
        status = self._navigate(url)
        self._settle()
        if wait:
            time.sleep(wait)
        state = _state(self.js(_SIGNALS) or {}, status)
        if state.verdict == "empty":
            time.sleep(3)  # a boot screen ("Please wait...") clears; a dead page stays empty
            state = _state(self.js(_SIGNALS) or {}, status)
        return state

    def current(self, http_status: int = 0) -> PageState:
        """The page state now, without navigating (after a click or a search)."""
        return _state(self.js(_SIGNALS) or {}, http_status)

    def _settle(self) -> None:
        previous = None
        for _ in range(self.settle_reads):
            current = self.js(_SETTLE)
            if current == previous and (not isinstance(current, dict) or current.get("ready") == "complete"):
                return
            previous = current
            time.sleep(self.pause)

    def scroll(self, times: int, *, pause: float = 2.0) -> None:
        for _ in range(times):
            self.js(CLOSE_OVERLAY)
            self.js(SCROLL)
            time.sleep(pause)

    def click(self, selector: str) -> bool:
        """A DOM click; Camofox overrides this with a real pointer click, which custom widgets need."""
        return bool(self.js(f"(() => {{ const el = document.querySelector({json.dumps(selector)}); if (!el) return false; el.click(); return true; }})()"))

    def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self._png())
        return path

    def js(self, expression: str):
        raise NotImplementedError

    def _navigate(self, url: str) -> int:
        raise NotImplementedError

    def _png(self) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        return None


class CamofoxBrowser(_Driver):
    """One private, logged-out Camofox tab reused for a collection run."""

    name = "camofox"

    def __init__(self, http: requests.Session, base_url: str):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.user = f"oma-creatives-{uuid4().hex}"
        self.path: str | None = None

    @classmethod
    def from_env(cls) -> CamofoxBrowser | None:
        from hermes_cli.config import get_env_value

        url = (get_env_value("CAMOFOX_URL") or "").strip()
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        http = requests.Session()
        http.trust_env = False
        key = (get_env_value("CAMOFOX_API_KEY") or "").strip()
        if key:
            http.headers["Authorization"] = f"Bearer {key}"
        return cls(http, url)

    def _request(self, method: str, path: str, *, data=None, params=None, timeout=60, raw=False):
        for attempt in range(2):
            try:
                response = self.http.request(method, self.base_url + path, json=data, params=params,
                                             timeout=timeout, allow_redirects=False)
                break
            except requests.RequestException as exc:
                if attempt:
                    raise Unavailable(f"Camofox did not respond: {exc.__class__.__name__}") from exc
                time.sleep(2)  # a dropped connection to the sidecar is usually momentary
        if response.status_code in (404, 410) and path.startswith("/tabs/"):
            raise TabGone(f"Camofox no longer has tab {path.split('/')[2]}")
        if not 200 <= response.status_code < 300:
            raise ApiError(f"Camofox API returned HTTP {response.status_code} for {path.rsplit('/', 1)[-1]}",
                           response.status_code)
        if raw:
            return response.content
        body = response.json()
        if not isinstance(body, dict):
            raise Unavailable("Camofox returned an unexpected response")
        return body

    def _tab(self) -> str:
        if self.path is None:
            created = self._request("POST", "/tabs", data={"userId": self.user, "sessionKey": self.user})
            tab_id = created.get("tabId")
            if not isinstance(tab_id, str) or not tab_id:
                raise Unavailable("Camofox did not create a tab")
            self.path = f"/tabs/{quote(tab_id, safe='')}"
            self._request("POST", f"{self.path}/viewport", data={"userId": self.user, "width": 1440, "height": 900})
        return self.path

    def goto(self, url: str, *, wait: float = 0.0) -> PageState:
        try:
            return super().goto(url, wait=wait)
        except TabGone:
            self.path = None  # open a fresh tab in the same private session and navigate again
            return super().goto(url, wait=wait)

    def _navigate(self, url: str) -> int:
        result = self._request("POST", f"{self._tab()}/navigate", data={"userId": self.user, "url": url}, timeout=90)
        return int(result.get("httpStatus") or 0)

    def click(self, selector: str) -> bool:
        try:
            return bool(self._request("POST", f"{self._tab()}/click", data={"userId": self.user, "selector": selector}).get("ok"))
        except ApiError:
            return False

    def js(self, expression: str):
        data = {"userId": self.user, "expression": expression, "timeoutMs": 30000}
        for attempt in range(4):
            try:
                result = self._request("POST", f"{self._tab()}/evaluate", data=data, timeout=45)
                break
            except ApiError as exc:
                # 500: the page reloaded mid-script and destroyed its context. 503: the sidecar is busy (heavy
                # media pages). Both clear on a later attempt.
                if exc.status not in (500, 503) or attempt == 3:
                    raise
                time.sleep(2.0 * (attempt + 1))
        if result.get("ok") is False and "result" not in result:
            raise Unavailable("Camofox page evaluation failed")
        return result.get("result")

    def _png(self) -> bytes:
        return self._request("GET", f"{self._tab()}/screenshot", params={"userId": self.user, "fullPage": "false"},
                             raw=True)

    def close(self) -> None:
        if self.path is not None:
            try:
                self._request("DELETE", f"/sessions/{self.user}", timeout=10)
            except Unavailable:
                pass  # the server expires idle sessions on its own


class HarnessBrowser(_Driver):
    """The Hermes browser inside ``browser_exec``: pass the harness ``cdp`` function."""

    name = "hermes-browser"

    def __init__(self, cdp):
        self.cdp = cdp

    def _navigate(self, url: str) -> int:
        self.cdp("Page.navigate", url=url)
        return 0  # CDP navigation reports no HTTP status; the page state decides

    def js(self, expression: str):
        reply = self.cdp("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if reply.get("exceptionDetails"):
            return None
        return (reply.get("result") or {}).get("value")

    def _png(self) -> bytes:
        return base64.b64decode(self.cdp("Page.captureScreenshot", format="png")["data"])


def open_browser(harness_cdp=None) -> _Driver:
    """Camofox when configured and reachable, else the Hermes browser when running in ``browser_exec``."""
    if harness_cdp is not None:
        return HarnessBrowser(harness_cdp)
    browser = CamofoxBrowser.from_env()
    if browser is None:
        raise Unavailable("Camofox is not configured; rerun this step inside browser_exec (see SKILL.md)")
    browser._tab()  # fail fast when the sidecar is down, before any source is marked checked
    return browser
