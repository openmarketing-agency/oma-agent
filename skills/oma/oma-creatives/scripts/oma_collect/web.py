"""Plain HTTP for public pages, feeds, APIs and media, with public-URL checks and size limits."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from oma_collect.browser import Refused, check_public

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
_PAGE_LIMIT = 12 * 1024 * 1024
_MEDIA_LIMIT = 250 * 1024 * 1024


class Fetcher:
    """One cookie-keeping session per collection run (TikTok media needs the page's cookies)."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"})

    def _get(self, url: str, *, params=None, referer=None, limit=_PAGE_LIMIT):
        check_public(url)
        headers = {"Referer": referer} if referer else {}
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=40, stream=True)
        except requests.RequestException:
            return None, b""
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > limit:
                response.close()
                return response, b""
        return response, bytes(body)

    def get_text(self, url: str, *, params=None) -> str | None:
        response, body = self._get(url, params=params)
        if response is None or response.status_code != 200 or not body:
            return None
        return body.decode(response.encoding or "utf-8", errors="replace")

    def get_json(self, url: str, *, params=None):
        response, body = self._get(url, params=params)
        if response is None or response.status_code != 200:
            return None
        try:
            return json.loads(body)
        except ValueError:
            return None

    def download(self, url: str, dest: Path, *, referer: str | None = None) -> tuple[Path | None, str | None]:
        """Save a media URL; returns (path, content type) or (None, reason)."""
        try:
            response, body = self._get(url, referer=referer, limit=_MEDIA_LIMIT)
        except Refused as exc:
            return None, str(exc)
        if response is None:
            return None, "request failed"
        if response.status_code != 200 or not body:
            return None, f"HTTP {response.status_code}" if response.status_code != 200 else "too large or empty"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        return dest, (response.headers.get("content-type") or "").split(";")[0]
