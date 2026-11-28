"""Counts, dates and post-ID timestamps, parsed the same way for every source."""

from __future__ import annotations

import datetime as dt
import re

UTC = dt.UTC
_SUFFIX = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_COUNT = re.compile(r"^\s*([\d][\d,.\s]*)\s*([kmb])?\s*$", re.IGNORECASE)
_FOLLOWERS = re.compile(r"([\d][\d,.]*\s*[KMB]?)\s+(followers|subscribers)\b", re.IGNORECASE)
_MONTH_DATE = re.compile(r"([A-Z][a-z]{2,8})\.? (\d{1,2}), (\d{4})")
_X_EPOCH_MS = 1288834974657


def parse_count(text) -> int | None:
    """``"1.2K"`` → 1200, ``"12,400"`` → 12400; None when the text is not a count."""
    if isinstance(text, int):
        return text
    match = _COUNT.match(str(text or ""))
    if not match:
        return None
    number, suffix = match.group(1).replace(" ", ""), (match.group(2) or "").lower()
    if suffix:
        return round(float(number.replace(",", "")) * _SUFFIX[suffix])
    return int(re.sub(r"[,.]", "", number))


def followers_in(text: str) -> int | None:
    match = _FOLLOWERS.search(text or "")
    return parse_count(match.group(1)) if match else None


def iso(moment: dt.datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> dt.datetime:
    return dt.datetime.now(UTC)


def from_unix(seconds) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(int(seconds), UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def x_post_time(status_id) -> dt.datetime | None:
    """X (Twitter) snowflake IDs carry their creation time in the top 41 bits."""
    try:
        return dt.datetime.fromtimestamp(((int(status_id) >> 22) + _X_EPOCH_MS) / 1000, UTC)
    except (TypeError, ValueError):
        return None


def tiktok_post_time(video_id) -> dt.datetime | None:
    """TikTok video IDs carry their Unix creation time in the top 32 bits."""
    try:
        return from_unix(int(video_id) >> 32)
    except (TypeError, ValueError):
        return None


def linkedin_post_time(activity_id) -> dt.datetime | None:
    """LinkedIn activity IDs carry their creation time in milliseconds in the top 41 bits."""
    try:
        return dt.datetime.fromtimestamp((int(activity_id) >> 22) / 1000, UTC)
    except (TypeError, ValueError):
        return None


def parse_date(text: str) -> dt.date | None:
    """``"Mar 26, 2026"`` or ``"March 26, 2026"``."""
    match = _MONTH_DATE.search(text or "")
    if not match:
        return None
    for pattern in ("%b %d %Y", "%B %d %Y"):
        try:
            return dt.datetime.strptime(" ".join(match.groups()), pattern).date()
        except ValueError:
            continue
    return None


def parse_slash_date(text: str) -> dt.date | None:
    """US-style ``MM/DD/YYYY``, as the TikTok library prints dates."""
    try:
        return dt.datetime.strptime(text.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def parse_dates(text: str) -> list[dt.date]:
    found = []
    for match in _MONTH_DATE.finditer(text or ""):
        date = parse_date(match.group(0))
        if date:
            found.append(date)
    return found


def parse_iso(value) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=UTC)
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def slug(value) -> str:
    """A path-safe ID; case is kept because YouTube and Instagram IDs differ only by case."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-")[:80] or "item"
