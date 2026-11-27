"""Store and query source-neutral campaign observations."""

from datetime import UTC, date, datetime
import json
from pathlib import Path
import sqlite3

from hermes_cli.oma_campaigns.install import _campaign_config_path, _campaigns_dir
from hermes_cli.oma_campaigns.storage import connect_campaign_data

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    account TEXT NOT NULL,
    metric TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    dimensions TEXT NOT NULL CHECK (json_valid(dimensions)),
    value TEXT NOT NULL CHECK (json_valid(value)),
    unit TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    UNIQUE (source, account, metric, period_start, period_end, dimensions)
)
"""
_BREAKDOWN = "json_extract(dimensions, '$.breakdown')"
_COLUMNS = ("source", "account", "metric", "period_start", "period_end", "dimensions", "value", "unit")
_REFRESH_SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_refresh (
    id INTEGER PRIMARY KEY CHECK (id = 1), last_successful_at TEXT NOT NULL
)
"""
_FILTERS = {"source": "source = ?", "account": "account = ?", "metric": "metric = ?",
            "start": "period_end > ?", "end": "period_start < ?", "before": "id < ?"}


class AnalyticsError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def campaign_dir(home: Path, campaign_id: str) -> Path:
    try:
        path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    except ValueError as exc:
        raise AnalyticsError(404, "Campaign not found.") from exc
    if not path.is_file():  # config-reader: ok — existence check of an authored campaign record
        raise AnalyticsError(404, "Campaign not found.")
    return path.parent


def _stamp(value: object) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise AnalyticsError(422, "Use ISO dates or timestamps with a timezone.")
    try:
        if len(value) == 10:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC).isoformat(timespec="microseconds")
        point = datetime.fromisoformat(value)
        if point.tzinfo is not None:
            return point.astimezone(UTC).isoformat(timespec="microseconds")
    except (ValueError, OverflowError):
        pass
    raise AnalyticsError(422, "Use ISO dates or timestamps with a timezone.")


def _label(value: object, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 512 or not (empty or value.strip()) or (
        value and not value.isprintable()
    ):
        raise AnalyticsError(422, "Invalid analytics label.")
    return value


def _json(value: object) -> str:
    try:
        result = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnalyticsError(422, "Invalid analytics JSON value.") from exc
    if len(result) > 65536:
        raise AnalyticsError(422, "Analytics value is too large.")
    return result


def _prepare(row: dict) -> tuple:
    if not isinstance(row, dict) or row.keys() != set(_COLUMNS) or not isinstance(row["dimensions"], dict):
        raise AnalyticsError(422, "Invalid analytics observation.")
    start, end = _stamp(row["period_start"]), _stamp(row["period_end"])
    if start >= end:
        raise AnalyticsError(422, "Analytics periods must have positive duration.")
    return (_label(row["source"]), _label(row["account"], empty=True), _label(row["metric"]),
            start, end, _json(row["dimensions"]), _json(row["value"]), _label(row["unit"], empty=True))


def _store_observations(conn: sqlite3.Connection, rows, collected: str) -> int:
    prepared = [_prepare(row) for row in rows]
    conn.execute(_SCHEMA)
    conn.execute(f"CREATE INDEX IF NOT EXISTS analytics_by_breakdown ON analytics_observations ({_BREAKDOWN}, id)")
    conn.executemany("""
        INSERT INTO analytics_observations
            (source, account, metric, period_start, period_end, dimensions, value, unit, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, account, metric, period_start, period_end, dimensions)
        DO UPDATE SET value=excluded.value, unit=excluded.unit, collected_at=excluded.collected_at
    """, [(*row, collected) for row in prepared])
    return len(prepared)


def save_observations(home: Path, campaign_id: str, rows: list[dict], *, refresh_complete: bool = False) -> int:
    """Commit one collected batch; invalid rows cannot leave a partial write."""
    directory = campaign_dir(home, campaign_id)
    if not rows and not refresh_complete:
        return 0
    collected = datetime.now(UTC).isoformat(timespec="microseconds")
    with connect_campaign_data(directory, write=True) as conn:
        if refresh_complete:
            conn.execute(_REFRESH_SCHEMA)
            conn.execute("INSERT OR REPLACE INTO analytics_refresh VALUES (1, ?)", (collected,))
        return _store_observations(conn, rows, collected)


def _query_filters(query: dict, breakdown: str | None) -> tuple[str, tuple]:
    conditions = [f"{_BREAKDOWN} IS NULL"] if breakdown is None else [f"{_BREAKDOWN} = ?"]
    args = [] if breakdown is None else [_label(breakdown)]
    for key, value in query.items():
        if value is None:
            continue
        conditions.append(_FILTERS[key])
        args.append(_stamp(value) if key in ("start", "end") else value if key == "before" else _label(value))
    if query["start"] is not None and query["end"] is not None and _stamp(query["start"]) >= _stamp(query["end"]):
        raise AnalyticsError(422, "Analytics start must be before end.")
    return " WHERE " + " AND ".join(conditions), tuple(args)


def _view(row: sqlite3.Row) -> dict:
    return {**dict(row), "value": json.loads(row["value"]), "dimensions": json.loads(row["dimensions"])}


def last_refresh(directory: Path) -> dict:
    with connect_campaign_data(directory) as conn:
        if not conn or not conn.execute("SELECT 1 FROM sqlite_schema WHERE name='analytics_refresh'").fetchone():
            return {"last_successful_refresh_at": None}
        return {"last_successful_refresh_at": conn.execute(
            "SELECT last_successful_at FROM analytics_refresh WHERE id = 1",
        ).fetchone()[0]}


def list_analytics(home: Path, campaign_id: str, *, source: str | None = None, account: str | None = None,
                   metric: str | None = None, start: str | None = None, end: str | None = None,
                   before: int | None = None, limit: int = 50, breakdown: str | None = None) -> dict:
    directory = campaign_dir(home, campaign_id)
    if type(limit) is not int or not 1 <= limit <= 100 or (
        before is not None and (type(before) is not int or not 0 < before < 2**53)
    ):
        raise AnalyticsError(422, "Invalid analytics page.")
    where, args = _query_filters(
        dict(source=source, account=account, metric=metric, start=start, end=end, before=before), breakdown)
    rows, freshness = [], None
    with connect_campaign_data(directory) as conn:
        if conn and conn.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND name='analytics_observations'").fetchone():
            rows = conn.execute(
                "SELECT * FROM analytics_observations" + where + " ORDER BY id DESC LIMIT ?", (*args, limit + 1),
            ).fetchall()
            scope = f"{_BREAKDOWN} IS NULL" if breakdown is None else f"{_BREAKDOWN} = ?"
            freshness_args = () if breakdown is None else (breakdown,)
            freshness = conn.execute(
                f"SELECT MAX(collected_at) FROM analytics_observations WHERE {scope}", freshness_args).fetchone()[0]
    return {"campaign_id": campaign_id, "observations": [_view(row) for row in rows[:limit]],
            "last_collected_at": freshness, "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None}
