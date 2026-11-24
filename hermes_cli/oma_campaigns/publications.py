"""Campaign publication records and the publisher's Kanban handoff (no provider calls)."""

import argparse
from contextlib import AbstractContextManager, closing, contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from hmac import compare_digest
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
from typing import Literal, overload
from urllib.parse import urlsplit
from uuid import uuid4

from agent.runtime_scope import bind_profile_scope
from hermes_constants import get_hermes_home
from hermes_cli import kanban_db
from hermes_cli.kanban_db_connect import connect_closing
from hermes_cli.oma_campaigns.install import _campaign_config_path, _campaigns_dir, _status
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import DEFAULT_CAMPAIGN_MODE, _member, read_mapping
from hermes_cli.sqlite_safe_read import connect_tracked

_ID = re.compile(r"[a-f0-9]{32}")
_MAX_DRAFT_BYTES = 96 * 1024
_SCHEMA = """
CREATE TABLE IF NOT EXISTS publications (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL CHECK (revision > 0),
    status TEXT NOT NULL CHECK (status IN ('pending_approval', 'approved', 'publishing', 'published', 'failed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    task_id TEXT,
    claim_token TEXT,
    result TEXT
);
CREATE TABLE IF NOT EXISTS publication_revisions (
    publication_id TEXT NOT NULL REFERENCES publications(id),
    revision INTEGER NOT NULL,
    draft TEXT NOT NULL,
    PRIMARY KEY (publication_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_publications_task ON publications(task_id);
"""
_SELECT = """SELECT p.*, r.draft FROM publications p JOIN publication_revisions r
    ON r.publication_id = p.id AND r.revision = p.revision"""


class PublicationError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _campaign(home: Path, campaign_id: str) -> tuple[Path, dict]:
    try:
        path = _campaign_config_path(_campaigns_dir(home), campaign_id)
        config = read_mapping(path)
    except FileNotFoundError:
        raise PublicationError(404, "Campaign not found.") from None
    validate_record("campaign", config, path)
    if config["id"] != campaign_id:
        raise PublicationError(404, "Campaign not found.")
    return path.parent, config


def _publisher(home: Path, config: dict) -> tuple[str, str]:
    with bind_profile_scope(home, hydrate_secrets=False):
        campaign = _status(home, config["id"], config)
    publisher = f"{config['id']}__publisher"
    if campaign["state"] != "installed" or publisher not in campaign["present_profiles"]:
        raise PublicationError(409, "Install the campaign's publisher agent before queuing a publication.")
    return publisher, campaign["kanban_board"]


@overload
def _db(directory: Path, *, write: Literal[True]) -> AbstractContextManager[sqlite3.Connection]: ...


@overload
def _db(directory: Path, *, write: Literal[False] = False) -> AbstractContextManager[sqlite3.Connection | None]: ...


@contextmanager
def _db(directory: Path, *, write: bool = False):
    path = _member(directory, "publications.sqlite3")
    if path.exists() and not path.is_file():
        raise OSError("Publication storage is not a regular file.")
    if not write and not path.exists():
        yield None
        return
    if write:
        # Keep unpublished content private even when a worker's default umask is permissive.
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("Publication storage is not a regular file.")
        finally:
            os.close(fd)
    with closing(sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if write:
            conn.executescript(_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
        with conn:
            yield conn


def _row(conn: sqlite3.Connection | None, publication_id: str) -> sqlite3.Row:
    if not isinstance(publication_id, str) or not _ID.fullmatch(publication_id):
        raise PublicationError(404, "Publication not found.")
    row = conn.execute(_SELECT + " WHERE p.id = ?", (publication_id,)).fetchone() if conn else None
    if row is None:
        raise PublicationError(404, "Publication not found.")
    return row


def _check_revision(row: sqlite3.Row, revision: object) -> None:
    if type(revision) is not int or revision < 1:
        raise PublicationError(422, "A positive publication revision is required.")
    if row["revision"] != revision:
        raise PublicationError(409, "This publication changed. Review the new revision before continuing.")


def _view(row: sqlite3.Row) -> dict:
    approval = {"revision": row["revision"], "by": row["approved_by"], "at": row["approved_at"],
                "source": "human" if row["approved_by"] else "automatic"}
    return {
        **json.loads(row["draft"]),
        **{k: row[k] for k in ("id", "revision", "status", "task_id", "created_at", "updated_at")},
        "approval": approval if row["approved_at"] else None,
        "result": json.loads(row["result"]) if row["result"] else None,
    }


def list_publications(home: Path, campaign_id: str, *, before: int | None = None, limit: int = 30) -> dict:
    if type(limit) is not int or not 1 <= limit <= 50 or (
        before is not None and (type(before) is not int or not 0 < before < 2**53)
    ):
        raise PublicationError(422, "Invalid publications page.")
    directory, config = _campaign(home, campaign_id)
    with _db(directory) as conn:
        rows = conn.execute(
            _SELECT + " WHERE (? IS NULL OR p.seq < ?) ORDER BY p.seq DESC LIMIT ?", (before, before, limit + 1),
        ).fetchall() if conn else []
    publications = [_view(row) for row in rows[:limit]]
    claimed = [item for item in publications if item["status"] == "publishing" and item["task_id"]]
    if claimed and (board := config.get("kanban_board")):
        active = _active_publication_tasks(home, board, [item["task_id"] for item in claimed])
        if active is not None:
            for item in claimed:
                if item["task_id"] not in active:
                    item["needs_verification"] = True
    return {"campaign_id": campaign_id, "mode": config.get("mode", DEFAULT_CAMPAIGN_MODE),
            "publications": publications,
            "next_cursor": rows[limit - 1]["seq"] if len(rows) > limit else None}


def _active_publication_tasks(home: Path, board: str, task_ids: list[str]) -> set[str] | None:
    # Keep the publication listing read-only and bounded even if Kanban is busy.
    slots = ",".join("?" for _ in task_ids)
    try:
        with bind_profile_scope(home, hydrate_secrets=False):
            path = kanban_db.kanban_db_path(board=board).resolve()
        with closing(connect_tracked(path.as_uri() + "?mode=ro", uri=True, timeout=0.25, tracking_path=path)) as conn:
            return {row[0] for row in conn.execute(
                f"SELECT id FROM tasks WHERE status = 'running' AND id IN ({slots})", task_ids,
            )}
    except (OSError, sqlite3.Error):
        # An unavailable board does not tell us whether the current worker stopped.
        return None


def _draft_json(draft: dict) -> str:
    validate_record("publication", draft, "Draft")
    payload = json.dumps(draft, ensure_ascii=False, sort_keys=True)
    if "\x00" in payload or "\\u0000" in payload or len(payload.encode()) > _MAX_DRAFT_BYTES:
        raise PublicationError(422, "The publication is too large or contains invalid text.")
    return payload


def _agent_campaign() -> tuple[Path, str, str]:
    profile = get_hermes_home().resolve()
    if profile.parent.name != "profiles" or "__" not in profile.name:
        raise PublicationError(403, "Run this command from a campaign agent profile.")
    return profile.parent.parent, profile.name.split("__", 1)[0], profile.name


def save_publication(home: Path, campaign_id: str, agent_id: str, draft: dict, *,
                     publication_id: str | None = None, revision: int | None = None) -> dict:
    directory, config = _campaign(home, campaign_id)
    if agent_id not in config["agents"]:
        raise PublicationError(403, "The agent does not belong to this campaign.")
    payload = _draft_json(draft)
    automatic = publication_id is None and config.get("mode", DEFAULT_CAMPAIGN_MODE) == "yolo"
    at = _now()
    with _db(directory, write=True) as conn:
        if publication_id is None:
            if revision is not None:
                raise PublicationError(422, "A new publication has no previous revision.")
            publication_id, revision = uuid4().hex, 1
            if automatic:
                _publisher(home, config)
            conn.execute("INSERT INTO publications (id, revision, status, created_at, updated_at, approved_at) "
                         "VALUES (?, 1, ?, ?, ?, ?)",
                         (publication_id, "approved" if automatic else "pending_approval", at, at, at if automatic else None))
        else:
            row = _row(conn, publication_id)
            _check_revision(row, revision)
            if row["status"] != "pending_approval":
                raise PublicationError(409, "Only publications awaiting approval can be edited.")
            revision = row["revision"] + 1
            conn.execute("UPDATE publications SET revision = ?, updated_at = ? WHERE id = ?", (revision, at, publication_id))
        conn.execute("INSERT INTO publication_revisions VALUES (?, ?, ?)", (publication_id, revision, payload))
        record = _view(_row(conn, publication_id))
    return _enqueue(home, directory, config, publication_id, record["revision"]) if automatic else record


def approve_publication(home: Path, campaign_id: str, publication_id: str, revision: int, approver: str) -> dict:
    directory, config = _campaign(home, campaign_id)
    if config.get("mode", DEFAULT_CAMPAIGN_MODE) not in ("approve", "control"):
        raise PublicationError(409, "This campaign does not use manual publication approval.")
    if not isinstance(approver, str) or not 0 < len(approver) <= 128 or not approver.isprintable() or not approver.strip():
        raise PublicationError(422, "A valid approver is required.")
    if not _member(directory, "publications.sqlite3").is_file():
        raise PublicationError(404, "Publication not found.")
    with _db(directory, write=True) as conn:
        row = _row(conn, publication_id)
        _check_revision(row, revision)
        if row["status"] == "pending_approval" or (row["status"] == "approved" and row["approved_by"] is None):
            _publisher(home, config)
            at = _now()
            conn.execute("UPDATE publications SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ? WHERE id = ?",
                         (approver, at, at, publication_id))
        elif row["approved_by"] is None:
            raise PublicationError(409, "The publication is no longer awaiting approval.")
    return _enqueue(home, directory, config, publication_id, revision)


def _enqueue(home: Path, directory: Path, config: dict, publication_id: str, revision: int) -> dict:
    # Approval commits before a task can run. A retry repairs an interrupted handoff without duplicating it.
    with _db(directory, write=True) as conn:
        row = _row(conn, publication_id)
        _check_revision(row, revision)
        if row["status"] != "approved" or row["task_id"]:
            return _view(row)
        publisher, board = _publisher(home, config)
        with bind_profile_scope(home, hydrate_secrets=False), connect_closing(board=board) as board_conn:
            task_id = kanban_db.create_task(
                board_conn, board=board, assignee=publisher, created_by="oma-publications",
                title=f"Publish publication {publication_id}",
                body=(f"Publication ID: {publication_id}; revision: {revision}. "
                      f"Claim the saved revision with `python -m hermes_cli.oma_campaigns.publications claim {publication_id} {revision}`. "
                      "Publish the returned content unchanged to its exact account and target. "
                      f"Before completing this task, run `python -m hermes_cli.oma_campaigns.publications finish "
                      f"{publication_id} {revision}`. Pass JSON on stdin with `claim_token` from claim and `result` "
                      "containing the verified `provider_id` and optional `url`, or `error` only for a definitive rejection. "
                      "If receipt recording fails, retry finish with the same receipt, never the send. "
                      "If claim refuses, do not publish. If delivery is uncertain, do not resend; report it for verification."),
                idempotency_key=f"oma-publication:{publication_id}:{revision}",
            )
        conn.execute("UPDATE publications SET task_id = ?, updated_at = ? WHERE id = ?", (task_id, _now(), publication_id))
        return _view(_row(conn, publication_id))


def claim_publication(home: Path, campaign_id: str, agent_id: str, publication_id: str, revision: int) -> dict:
    directory, config = _campaign(home, campaign_id)
    if agent_id != _publisher(home, config)[0]:
        raise PublicationError(403, "Only the campaign publisher can claim publications.")
    with _db(directory, write=True) as conn:
        row = _row(conn, publication_id)
        _check_revision(row, revision)
        mode = config.get("mode", DEFAULT_CAMPAIGN_MODE)
        if (config.get("lifecycle_state", "resumed") != "resumed"
                or row["status"] != "approved" or not row["task_id"]
                or (mode in ("approve", "control") and not row["approved_by"])):
            raise PublicationError(409, "This revision is not available to publish.")
        token = uuid4().hex
        conn.execute("UPDATE publications SET status = 'publishing', claim_token = ?, updated_at = ? WHERE id = ?",
                     (token, _now(), publication_id))
        return {**_view(_row(conn, publication_id)), "claim_token": token}


def human_approved_task(directory: Path, task_id: str) -> bool:
    """Control only admits a Kanban task linked to a human-approved publication."""
    try:
        with _db(directory) as conn:
            return bool(conn and conn.execute(
                "SELECT 1 FROM publications WHERE task_id = ? AND approved_by IS NOT NULL AND status = 'approved'",
                (task_id,),
            ).fetchone())
    except (OSError, ValueError, sqlite3.Error):
        return False


def finish_publication(home: Path, campaign_id: str, agent_id: str, publication_id: str, revision: int,
                       token: str, result: dict) -> dict:
    directory, config = _campaign(home, campaign_id)
    if agent_id != _publisher(home, config)[0]:
        raise PublicationError(403, "Only the campaign publisher can record a result.")
    if not isinstance(result, dict) or set(result) not in ({"provider_id"}, {"provider_id", "url"}, {"error"}):
        raise PublicationError(422, "Supply a provider receipt or a definitive error.")
    if any(not isinstance(value, str) or not value.strip() or len(value) > 2048 for value in result.values()):
        raise PublicationError(422, "Invalid publication result.")
    if "url" in result:
        url = urlsplit(result["url"])
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise PublicationError(422, "Invalid receipt URL.")
    if not isinstance(token, str) or not _ID.fullmatch(token):
        raise PublicationError(409, "The publisher does not own this claim.")
    receipt_key = sha256(token.encode("ascii")).hexdigest()
    with _db(directory, write=True) as conn:
        row = _row(conn, publication_id)
        _check_revision(row, revision)
        if row["status"] in ("published", "failed") and compare_digest(row["claim_token"] or "", receipt_key):
            saved = _view(row)
            if {key: value for key, value in saved["result"].items() if key != "published_at"} != result:
                raise PublicationError(409, "A different result is already recorded for this claim.")
            return saved
        if row["status"] != "publishing" or not compare_digest(row["claim_token"] or "", token):
            raise PublicationError(409, "The publisher does not own this claim.")
        at = _now()
        status = "failed" if "error" in result else "published"
        result = {**result, "published_at": at} if status == "published" else result
        # Keep only the digest on a settled claim so a receipt can be replayed, but the token cannot be read back.
        conn.execute("UPDATE publications SET status = ?, claim_token = ?, result = ?, updated_at = ? WHERE id = ?",
                     (status, receipt_key, json.dumps(result), at, publication_id))
        return _view(_row(conn, publication_id))


def _input() -> dict:
    payload = sys.stdin.buffer.read(_MAX_DRAFT_BYTES + 1)
    if len(payload) > _MAX_DRAFT_BYTES:
        raise PublicationError(422, "Publication input is too large.")
    return json.loads(payload)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("save", help="Submit a draft (JSON on stdin)")
    save.add_argument("--id")
    save.add_argument("--revision", type=int)
    for name, help_text in (("claim", "Claim an approved revision (publisher only)"),
                            ("finish", "Record {claim_token, result} on stdin (publisher only)")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("id")
        sub.add_argument("revision", type=int)
    args = parser.parse_args(argv)
    try:
        scope = _agent_campaign()
        if args.command == "save":
            result = save_publication(*scope, _input(), publication_id=args.id, revision=args.revision)
        elif args.command == "claim":
            result = claim_publication(*scope, args.id, args.revision)
        else:
            data = _input()
            if not isinstance(data, dict) or set(data) != {"claim_token", "result"}:
                raise PublicationError(422, "Supply {claim_token, result} on stdin.")
            result = finish_publication(*scope, args.id, args.revision, data["claim_token"], data["result"])
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"OMA publications: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
