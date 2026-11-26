"""Campaign-local SQLite storage, shared by features that persist campaign data."""

from contextlib import AbstractContextManager, closing, contextmanager
import os
from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory
from typing import Literal, overload

from hermes_cli.oma_campaigns.source import _member

_DATA_NAME = "data.sqlite3"
_LEGACY_NAME = "publications.sqlite3"
_PUBLICATIONS = """
CREATE TABLE IF NOT EXISTS publications (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL CHECK (revision > 0),
    status TEXT NOT NULL CHECK (status IN ('draft', 'pending_approval', 'approved', 'publishing', 'published', 'failed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    task_id TEXT,
    claim_token TEXT,
    result TEXT
);
"""
_REVISIONS = """
CREATE TABLE IF NOT EXISTS publication_revisions (
    publication_id TEXT NOT NULL REFERENCES publications(id),
    revision INTEGER NOT NULL,
    draft TEXT NOT NULL,
    PRIMARY KEY (publication_id, revision)
);
"""
_INDEX = "CREATE INDEX IF NOT EXISTS idx_publications_task ON publications(task_id);"


def _existing_file(directory: Path, name: str) -> Path | None:
    path = _member(directory, name)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(mode):
        raise OSError("Campaign data storage is not a regular file.")
    return path


def campaign_data_exists(directory: Path) -> bool:
    return bool(_existing_file(directory, _DATA_NAME) or _existing_file(directory, _LEGACY_NAME))


def _initialize(path: Path, legacy: Path | None) -> None:
    # Stage a private, complete database. Concurrent first writers must not replace the winner.
    with TemporaryDirectory(prefix=".campaign-data-", dir=path.parent) as tmp:
        staged = Path(tmp) / path.name
        staged.touch(mode=0o600, exist_ok=False)
        with closing(sqlite3.connect(staged)) as dest:
            if legacy is not None:
                with closing(sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)) as source:
                    # Pin a read snapshot with SQLite's normal busy timeout before backup, which
                    # otherwise retries busy errors indefinitely. Include committed WAL contents.
                    source.execute("BEGIN")
                    source.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone()
                    source.backup(dest)
                dest.execute("PRAGMA journal_mode = DELETE")
            dest.executescript(_PUBLICATIONS + _REVISIONS + _INDEX)
        try:
            os.link(staged, path)
        except FileExistsError:
            if _existing_file(path.parent, path.name) is None:
                raise


def _enable_publication_drafts(conn: sqlite3.Connection) -> None:
    definition = conn.execute("SELECT sql FROM sqlite_schema WHERE name = 'publications' AND type = 'table'").fetchone()
    if "'draft'" in definition[0]:
        return
    # Rebuild only the publication tables to widen their CHECK constraint. The caller's
    # write transaction makes the migration atomic, including both sides of the foreign key.
    conn.execute("ALTER TABLE publication_revisions RENAME TO publication_revisions_previous")
    conn.execute("ALTER TABLE publications RENAME TO publications_previous")
    conn.execute(_PUBLICATIONS)
    conn.execute(_REVISIONS)
    conn.execute("INSERT INTO publications SELECT * FROM publications_previous")
    conn.execute("INSERT INTO publication_revisions SELECT * FROM publication_revisions_previous")
    conn.execute("DROP TABLE publication_revisions_previous")
    conn.execute("DROP TABLE publications_previous")
    conn.execute(_INDEX)


@overload
def connect_campaign_data(directory: Path, *, write: Literal[True]) -> AbstractContextManager[sqlite3.Connection]: ...


@overload
def connect_campaign_data(directory: Path, *, write: Literal[False] = False) -> AbstractContextManager[sqlite3.Connection | None]: ...


@contextmanager
def connect_campaign_data(directory: Path, *, write: bool = False):
    """Open campaign data; only writers initialize storage or import the legacy database."""
    path = _existing_file(directory, _DATA_NAME)
    if path is None:
        legacy = _existing_file(directory, _LEGACY_NAME)
        if write:
            path = directory / _DATA_NAME
            _initialize(path, legacy)
        else:
            path = _existing_file(directory, _DATA_NAME) or legacy
            if path is None:
                yield None
                return
    with closing(sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if write:
            conn.execute("BEGIN IMMEDIATE")
        with conn:
            if write:
                _enable_publication_drafts(conn)
            yield conn
