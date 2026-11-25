"""Read-only analytics sources invoked by the fixed analyst job (no model/tool turns)."""

from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from agent.secret_scope import load_env_file
from hermes_cli.oma_campaigns.analytics import AnalyticsError, campaign_dir, save_observations
from hermes_cli.oma_campaigns.source import _member, read_mapping
from hermes_cli.oma_campaigns.storage import connect_campaign_data


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _report(url: str, token: str, body: dict) -> dict:
    request = Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + token,
    })
    with build_opener(_NoRedirect()).open(request, timeout=15) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("Analytics response exceeds the supported size.")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Invalid analytics response.")
    return data


def _observation(source: str, account: str, metric: str, day: date, value, unit: str, **dimensions) -> dict:
    return dict(source=source, account=account, metric=metric, period_start=day.isoformat(),
                period_end=(day + timedelta(days=1)).isoformat(), value=value, unit=unit, dimensions=dimensions)


def _publications(directory: Path, campaign_id: str, today: date) -> list[dict]:
    first_day = today - timedelta(days=6)
    with connect_campaign_data(directory) as conn:
        rows = conn.execute("""
            SELECT substr(created_at,1,10) AS day, COUNT(*) AS total
            FROM publications WHERE created_at >= ? GROUP BY day
        """, (first_day.isoformat(),)).fetchall() if conn else []
        sent = conn.execute("""
            SELECT substr(json_extract(result,'$.published_at'),1,10) AS day, COUNT(*) AS total
            FROM publications WHERE status='published' AND json_extract(result,'$.published_at') >= ? GROUP BY day
        """, (first_day.isoformat(),)).fetchall() if conn else []
    return [_observation("oma-publications", campaign_id, metric, date.fromisoformat(row["day"]), row["total"], "count")
            for metric, group in (("drafts_created", rows), ("published", sent)) for row in group]


def _ga4(account: str, token: str, today: date) -> list[dict]:
    if not re.fullmatch(r"[0-9]{1,20}", account):
        raise ValueError("Use a GA4 property ID.")
    metrics = ("sessions", "activeUsers", "screenPageViews", "keyEvents")
    data = _report(f"https://analyticsdata.googleapis.com/v1beta/properties/{account}:runReport", token, {
        "dateRanges": [{"startDate": (today - timedelta(days=7)).isoformat(), "endDate": today.isoformat()}],
        "dimensions": [{"name": "date"}], "metrics": [{"name": name} for name in metrics], "limit": 10,
    })
    return [_observation("google-analytics", account, name,
                         datetime.strptime(row["dimensionValues"][0]["value"], "%Y%m%d").date(),
                         float(value["value"]), "count", timezone=data.get("metadata", {}).get("timeZone"))
            for row in data.get("rows", []) for name, value in zip(metrics, row["metricValues"], strict=True)]


def _search_console(account: str, token: str, today: date) -> list[dict]:
    if not account.startswith(("sc-domain:", "https://", "http://")):
        raise ValueError("Use a Search Console property ID.")
    data = _report(f"https://www.googleapis.com/webmasters/v3/sites/{quote(account, safe='')}/searchAnalytics/query", token, {
        "startDate": (today - timedelta(days=9)).isoformat(), "endDate": today.isoformat(),
        "dimensions": ["date"], "rowLimit": 10, "dataState": "all",
    })
    return [_observation("google-search-console", account, name, date.fromisoformat(row["keys"][0]), row[name], unit,
                         timezone="America/Los_Angeles")
            for row in data.get("rows", []) for name, unit in (
                ("clicks", "count"), ("impressions", "count"), ("ctr", "ratio"), ("position", "position"),
            )]


_ADAPTERS = {"google-analytics": _ga4, "google-search-console": _search_console}


def validate_bindings(bindings: object) -> None:
    if not isinstance(bindings, list) or len(bindings) > 8:
        raise ValueError("analytics_sources must contain up to eight read-only source bindings.")
    seen = set()
    for row in bindings:
        if (not isinstance(row, dict) or set(row) != {"source", "account", "token_env"}
                or not all(isinstance(v, str) for v in row.values()) or row["source"] not in _ADAPTERS
                or not 0 < len(row["account"]) <= 512 or not row["account"].isprintable()
                or not re.fullmatch(r"OMA_ANALYTICS_GOOGLE_[A-Z_0-9]{1,48}", row["token_env"])):
            raise ValueError("Invalid analytics source binding.")
        key = row["source"], row["account"]
        if key in seen:
            raise ValueError("Duplicate analytics source binding.")
        seen.add(key)


def _active(config_path: Path, cancel_event) -> None:
    if (cancel_event is not None and cancel_event.is_set()) or read_mapping(config_path).get("lifecycle_state") != "resumed":
        raise AnalyticsError(409, "Analytics collection cancelled because the campaign is stopped.")


def collect(home: Path, campaign_id: str, profile: Path, cancel_event=None) -> int:
    from hermes_cli.oma_campaigns.install import _install_lock

    directory = campaign_dir(home, campaign_id)
    config_path = _member(directory, "config.yaml")
    _active(config_path, cancel_event)
    config = read_mapping(config_path)
    analyst = _member(_member(_member(home, "oma"), "agents"), profile.name)
    bindings = read_mapping(_member(analyst, "config.yaml")).get("analytics_sources", [])
    validate_bindings(bindings)
    today = datetime.now(UTC).date()
    rows = _publications(directory, campaign_id, today)
    failures = []
    credentials = load_env_file(_member(profile, ".env")) if bindings else {}
    for binding in bindings:
        _active(config_path, cancel_event)
        source = binding["source"]
        token = credentials.get(binding["token_env"])
        if source not in config.get("integrations", []) or not token:
            failures.append(source)
            continue
        try:
            rows.extend(_ADAPTERS[source](binding["account"], token, today))
        except (OSError, KeyError, ValueError, TypeError):
            failures.append(source)
    # Do not hold the campaign lock or a SQL connection across provider requests.
    with _install_lock(config_path):
        _active(config_path, cancel_event)
        count = save_observations(home, campaign_id, rows, refresh_complete=not failures)
    if failures:
        raise AnalyticsError(503, "Analytics refresh was incomplete: " + ", ".join(sorted(set(failures))) + ".")
    return count
