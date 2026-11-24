"""Run the OMA brand visual helper against a private Camofox tab."""

import argparse
import base64
from io import BytesIO
import json
from pathlib import Path
import runpy
from tempfile import mkdtemp
from typing import Any, cast
from urllib.parse import quote, urlsplit
from uuid import uuid4

import requests
from PIL import Image


class Unavailable(Exception):
    """Camofox could not supply the browser capabilities this workflow needs."""


class PageBlocked(Exception):
    """A page or navigation policy refused access; do not retry via another browser."""


_LAYOUT = """({width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight, viewportHeight: window.innerHeight})"""
_LOAD_LAZY_MEDIA = """(async () => {
    for (let step = 0; step < 12; step++) {
        if (step && scrollY + innerHeight >= document.documentElement.scrollHeight) break;
        scrollTo(0, step * innerHeight);
        await new Promise(resolve => setTimeout(resolve, 170));
    }
    scrollTo(0, 0);
    await Promise.race([document.fonts.ready, new Promise(resolve => setTimeout(resolve, 1200))]);
    return true;
})()"""
_PNG_LIMIT = 64 * 1024 * 1024


class CamofoxTab:
    def __init__(self, http, base_url):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.user = f"oma-brand-{uuid4().hex}"
        self.path: str | None = None
        self.image: Image.Image | None = None
        self.size: dict | None = None

    def request(self, method, path, *, data=None, params=None, screenshot=False, timeout=30):
        try:
            with self.http.request(method, self.base_url + path, json=data, params=params,
                                   timeout=timeout, allow_redirects=False, stream=screenshot) as response:
                if not 200 <= response.status_code < 300:
                    if response.status_code in (403, 429) or (
                        path.endswith("/navigate") and response.status_code not in (401, 404, 405, 501, 503)
                    ):
                        raise PageBlocked("Camofox navigation or access was refused; inspect a permitted source")
                    raise Unavailable(f"Camofox API returned HTTP {response.status_code}")
                if not screenshot:
                    result = response.json()
                    if not isinstance(result, dict):
                        raise Unavailable("Camofox API returned an unexpected response")
                    return result
                result = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    result.extend(chunk)
                    if len(result) > _PNG_LIMIT:
                        raise ValueError("Camofox screenshot exceeds the size budget")
                return bytes(result)
        except requests.RequestException as exc:
            raise Unavailable("Camofox API did not return a usable response") from exc

    def action(self, name, **data):
        return cast(dict, self.request("POST", f"{self.path}/{name}", data={"userId": self.user, **data}))

    def open(self, url, width, height, validate):
        created = cast(dict, self.request("POST", "/tabs", data={"userId": self.user, "sessionKey": self.user}))
        tab_id = created.get("tabId")
        if not isinstance(tab_id, str) or not tab_id:
            raise Unavailable("Camofox did not create a tab")
        self.path = f"/tabs/{quote(tab_id, safe='')}"
        self.action("viewport", width=width, height=height)
        page = self.action("navigate", url=url)
        if page.get("navigationOk") is False or page.get("ok") is False or (page.get("httpStatus") or 0) >= 400:
            raise PageBlocked("The source returned an error or denied access")
        final_url = page.get("url")
        if not final_url or final_url == "about:blank":
            raise PageBlocked("The requested public page did not load")
        validate(final_url)
        return final_url

    def close(self):
        if self.path is not None:
            try:
                self.request("DELETE", f"/sessions/{self.user}", timeout=5)
            except (Unavailable, PageBlocked):
                pass  # The isolated browser session will expire on the server.

    def js(self, expression) -> Any:
        response = self.action("evaluate", expression=expression, timeoutMs=10000)
        if "result" not in response or response.get("ok") is False:
            raise Unavailable("Camofox page evaluation is unavailable")
        return response["result"]

    def screenshot(self, full_page=False):
        png = self.request("GET", f"{self.path}/screenshot", screenshot=True,
                           params={"userId": self.user, "fullPage": str(full_page).lower()})
        try:
            with Image.open(BytesIO(cast(bytes, png)), formats=("PNG",)) as image:
                return image.copy()
        except (OSError, Image.DecompressionBombError) as exc:
            raise Unavailable("Camofox did not return a usable PNG") from exc

    def cdp(self, method, **kwargs):
        # Adapt only the two screenshot operations used by the visual helper.
        size = self.size if self.size is not None else self.js(_LAYOUT)
        self.size = size
        if method == "Page.getLayoutMetrics":
            return {"cssContentSize": size}
        clip = kwargs["clip"]
        if self.image is None:
            self.image = self.screenshot(full_page=size["width"] * size["height"] <= 80_000_000)
        box = tuple(round(value) for value in (clip["x"], clip["y"], clip["x"] + clip["width"],
                                               clip["y"] + clip["height"]))
        if not (0 <= box[0] < box[2] <= self.image.width and 0 <= box[1] < box[3] <= self.image.height):
            raise RuntimeError("Camofox screenshot does not cover the requested section")
        output = BytesIO()
        self.image.crop(box).save(output, format="PNG")
        return {"data": base64.b64encode(output.getvalue()).decode("ascii")}


def run(tab, url, output, *, name=None, inventory=None, approved_ids=(), width=1280, height=900, validate):
    helper = runpy.run_path(str(Path(__file__).with_name("visual_reference.py")))
    try:
        validate(url)
        final_url = tab.open(url, width, height, validate)
        def inspect(expression):
            value = tab.js(expression)
            if expression == helper["_INSPECT"]:
                if not isinstance(value, dict) or not isinstance(value.get("url"), str):
                    raise Unavailable("Camofox did not return rendered page data")
                validate(value["url"])
            return value

        page = inspect(helper["_INSPECT"])
        if page["blocked"] or page.get("login_overlay"):
            return {"status": "blocked" if page["blocked"] else "login_overlay", "backend": "camofox"}
        tab.js(_LOAD_LAZY_MEDIA)
        if inventory is not None:
            assets = helper["stage_assets"](inventory, output, approved_ids, js=inspect, cdp=tab.cdp)
            return {"status": "staged", "backend": "camofox", "assets": assets}
        result = helper["capture_page"](final_url, output, name, js=inspect, cdp=tab.cdp)
        if result["status"] == "capture_failed":
            # Some server builds provide viewport-only screenshots. Keep their inventory and
            # label the viewport honestly instead of switching browsers for the same page.
            path = output / f"{name}-viewport.png"
            with path.open("xb") as file:
                (tab.image if tab.image is not None else tab.screenshot()).save(file, format="PNG")
            result.update(status="partial", screenshots=[str(path)])
            manifest = Path(result["asset_inventory"])
            data = json.loads(manifest.read_text(encoding="utf-8"))
            manifest.write_text(json.dumps({**data, "screenshots": result["screenshots"]}, indent=2), encoding="utf-8")
        return {**result, "backend": "camofox"}
    except Unavailable as exc:
        return {"status": "unavailable", "backend": "camofox", "reason": str(exc)}
    except PageBlocked as exc:
        return {"status": "blocked", "backend": "camofox", "reason": str(exc)}
    finally:
        tab.close()


def _public_url(url):
    from tools.browser_url_policy import evaluate_url_safety, url_is_private
    from tools.url_safety import is_safe_url

    if urlsplit(url).scheme not in ("http", "https") or url_is_private(url) or not is_safe_url(url):
        raise PageBlocked("Only public HTTP(S) brand pages can be captured")
    if evaluate_url_safety(url):
        raise PageBlocked("Hermes browser policy does not allow this URL")


def main():
    from hermes_cli.config import get_env_value, load_config
    from hermes_constants import get_default_hermes_root, get_hermes_home

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--name", help="Lowercase screenshot name (capture mode)")
    mode.add_argument("--inventory", type=Path, help="Existing inventory (stage mode)")
    parser.add_argument("--approve", nargs="+", default=[], help="Explicitly approved inventory IDs")
    parser.add_argument("--width", type=int, choices=range(100, 3841), default=1280, metavar="100–3840")
    parser.add_argument("--height", type=int, choices=range(100, 2161), default=900, metavar="100–2160")
    args = parser.parse_args()
    home = get_hermes_home()
    if home.resolve() != get_default_hermes_root(home=home).resolve():
        parser.error("This helper is only for the OMA default profile")
    config = load_config()
    url = (get_env_value("CAMOFOX_URL") or "").strip()
    parts = urlsplit(url)
    result = {"status": "unavailable", "backend": "camofox"}
    if config.get("browser", {}).get("restrict_evaluate"):
        result["reason"] = "Browser evaluation is restricted; report the gap rather than bypassing it"
        result["status"] = "blocked"
    elif parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        result["reason"] = "Camofox is not configured"
    else:
        cache = home / "cache" / "oma-brand"
        cache.mkdir(parents=True, exist_ok=True)
        output = Path(mkdtemp(prefix="camofox-", dir=cache))
        with requests.Session() as http:
            http.trust_env = False
            key = (get_env_value("CAMOFOX_API_KEY") or "").strip()
            if key:
                http.headers["Authorization"] = f"Bearer {key}"
            result = run(CamofoxTab(http, url), args.url, output, name=args.name, inventory=args.inventory,
                         approved_ids=args.approve, width=args.width, height=args.height, validate=_public_url)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
