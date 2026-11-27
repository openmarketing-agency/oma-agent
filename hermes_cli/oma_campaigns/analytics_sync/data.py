"""Persist detailed analytics and page checkpoints in campaign-local transactions."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from hermes_cli.oma_campaigns.analytics import AnalyticsError, _json, _label, _store_observations
from hermes_cli.oma_campaigns.storage import connect_campaign_data

_STATE = """
CREATE TABLE IF NOT EXISTS analytics_datasets (
    source TEXT NOT NULL, server TEXT NOT NULL, dataset TEXT NOT NULL, account TEXT NOT NULL,
    progress TEXT NOT NULL CHECK (json_valid(progress)),
    state TEXT NOT NULL, last_successful_at TEXT,
    PRIMARY KEY (source, server, dataset, account)
)
"""
_RECORDS = """
CREATE TABLE IF NOT EXISTS analytics_records (
    seq INTEGER PRIMARY KEY, source TEXT NOT NULL, server TEXT NOT NULL,
    dataset TEXT NOT NULL, account TEXT NOT NULL, record_id TEXT NOT NULL,
    record TEXT NOT NULL CHECK (json_valid(record)), collected_at TEXT NOT NULL,
    UNIQUE (source, server, dataset, account, record_id)
)
"""


@dataclass(frozen=True)
class Dataset:
    source: str
    server: str
    name: str
    account: str

    def key(self) -> tuple[str, str, str, str]:
        return (self.source, self.server, self.name, self.account)


def _has_table(conn: sqlite3.Connection | None, table: str) -> bool:
    return bool(conn and conn.execute("SELECT 1 FROM sqlite_schema WHERE name = ?", (table,)).fetchone())


def checkpoint(directory: Path, dataset: Dataset) -> dict:
    with connect_campaign_data(directory) as conn:
        row = conn.execute(
            "SELECT progress FROM analytics_datasets WHERE (source, server, dataset, account) = (?, ?, ?, ?)",
            dataset.key(),
        ).fetchone() if _has_table(conn, "analytics_datasets") else None
    return json.loads(row["progress"]) if row else {}


def _store_state(conn: sqlite3.Connection, dataset: Dataset, progress: dict, state: str, stamp: str) -> None:
    conn.execute(_STATE)
    conn.execute("""
        INSERT INTO analytics_datasets VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, server, dataset, account) DO UPDATE SET
            progress=excluded.progress, state=excluded.state,
            last_successful_at=COALESCE(excluded.last_successful_at, analytics_datasets.last_successful_at)
    """, (*dataset.key(), _json(progress), state, stamp if state == "current" else None))


def save_page(directory: Path, dataset: Dataset, progress: dict, state: str, *,
              observations: Sequence[dict] = (), records: Sequence[dict] = ()) -> int:
    """Commit a validated page and its progress together so retries never skip records."""
    from agent.redact import is_secret_field_name, redact_sensitive_text

    def scrub(value):
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items() if not is_secret_field_name(key)}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return redact_sensitive_text(value, force=True, redact_url_credentials=True) if isinstance(value, str) else value

    stamp = datetime.now(UTC).isoformat(timespec="microseconds")
    prepared = [(*dataset.key(), _label(record["id"]), _json(scrub(record["data"])), stamp) for record in records]
    with connect_campaign_data(directory, write=True) as conn:
        _store_state(conn, dataset, progress, state, stamp)
        count = _store_observations(conn, observations, stamp) if observations else 0
        if prepared:
            conn.execute(_RECORDS)
            conn.executemany("""
                INSERT INTO analytics_records
                    (source, server, dataset, account, record_id, record, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (source, server, dataset, account, record_id)
                DO UPDATE SET record=excluded.record, collected_at=excluded.collected_at
            """, prepared)
    return count + len(prepared)


def mark_unseen(directory: Path, seen: set[Dataset]) -> None:
    """Keep historical coverage and progress while flagging disconnected datasets."""
    with connect_campaign_data(directory) as conn:
        if not _has_table(conn, "analytics_datasets"):
            return
        keys = [Dataset(*row) for row in conn.execute(
            "SELECT source, server, dataset, account FROM analytics_datasets WHERE state != 'unavailable'"
        )]
    missing = [dataset.key() for dataset in keys if dataset not in seen]
    if missing:
        with connect_campaign_data(directory, write=True) as conn:
            conn.executemany("""
                UPDATE analytics_datasets SET state = 'unavailable'
                WHERE (source, server, dataset, account) = (?, ?, ?, ?)
            """, missing)


def coverage(directory: Path) -> list[dict]:
    with connect_campaign_data(directory) as conn:
        if not _has_table(conn, "analytics_datasets"):
            return []
        rows = conn.execute("""
            SELECT source, server, dataset, account, state, last_successful_at,
                   json_extract(progress, '$.from') AS requested_from,
                   json_extract(progress, '$.checked_from') AS checked_from,
                   json_extract(progress, '$.through') AS collected_through
            FROM analytics_datasets ORDER BY source, server, dataset, account
        """).fetchall()
    return [dict(row) for row in rows]


def list_records(directory: Path, *, source: str, dataset: str, before: int | None = None, limit: int = 50) -> dict:
    _label(source)
    _label(dataset)
    if type(limit) is not int or not 1 <= limit <= 100 or (
        before is not None and (type(before) is not int or not 0 < before < 2**53)
    ):
        raise AnalyticsError(422, "Invalid analytics records page.")
    with connect_campaign_data(directory) as conn:
        rows = conn.execute("""
            SELECT * FROM analytics_records WHERE source = ? AND dataset = ? AND (? IS NULL OR seq < ?)
            ORDER BY seq DESC LIMIT ?
        """, (source, dataset, before, before, limit + 1)).fetchall() if _has_table(conn, "analytics_records") else []
    return {
        "records": [{**dict(row), "record": json.loads(row["record"])} for row in rows[:limit]],
        "next_cursor": rows[limit - 1]["seq"] if len(rows) > limit else None,
    }
