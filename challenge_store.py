"""
challenge_store.py — SQLite-backed shared challenge board.

All 23 team members (3 Vegas + 20 Singapore) read/write the same database.
Thread-safe: every operation opens a short-lived connection with WAL mode.

Schema
------
challenges  — one row per challenge
messages    — conversation history per challenge (agent + human turns)
events      — append-only log broadcast to WebSocket clients
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "data" / "ctf_board.db"
DB_PATH.parent.mkdir(exist_ok=True)

CATEGORIES = ["web", "crypto", "binary", "forensics", "osint", "misc", "recon", "unknown"]
STATUSES   = ["unsolved", "in_progress", "solved", "abandoned"]

_lock = threading.Lock()


@contextmanager
def _conn():
    with _lock:
        con = sqlite3.connect(DB_PATH, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS challenges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                category    TEXT    NOT NULL DEFAULT 'unknown',
                points      INTEGER DEFAULT 0,
                description TEXT    NOT NULL DEFAULT '',
                files       TEXT    DEFAULT '[]',      -- JSON array of filenames
                status      TEXT    NOT NULL DEFAULT 'unsolved',
                flag        TEXT    DEFAULT NULL,
                assigned_to TEXT    DEFAULT NULL,      -- team member name or NULL
                profile     TEXT    DEFAULT 'ctf-singapore',
                iterations  INTEGER DEFAULT 0,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_id INTEGER NOT NULL REFERENCES challenges(id),
                role         TEXT    NOT NULL,   -- 'human' | 'ai' | 'tool' | 'system'
                content      TEXT    NOT NULL,
                tool_name    TEXT    DEFAULT NULL,
                created_at   TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                type         TEXT    NOT NULL,   -- 'challenge_added' | 'status_changed' | 'flag_found' | 'message'
                challenge_id INTEGER,
                payload      TEXT    NOT NULL,   -- JSON
                created_at   TEXT    NOT NULL
            );
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Challenges ────────────────────────────────────────────────────────────────

def add_challenge(
    title: str,
    description: str,
    category: str = "unknown",
    points: int = 0,
    files: list[str] | None = None,
    profile: str = "ctf-singapore",
    assigned_to: str | None = None,
) -> int:
    now = _now()
    files_json = json.dumps(files or [])
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO challenges
               (title, category, points, description, files, status, profile, assigned_to, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (title, category, points, description, files_json, "unsolved", profile, assigned_to, now, now),
        )
        cid = cur.lastrowid
        _append_event(con, "challenge_added", cid, {"title": title, "category": category})
    return cid


def get_challenge(challenge_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM challenges WHERE id=?", (challenge_id,)).fetchone()
        if row:
            return _row_to_dict(row)
    return None


def list_challenges(status: str | None = None, category: str | None = None) -> list[dict]:
    query = "SELECT * FROM challenges"
    params: list[Any] = []
    clauses = []
    if status:
        clauses.append("status=?"); params.append(status)
    if category:
        clauses.append("category=?"); params.append(category)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    with _conn() as con:
        rows = con.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_challenge_status(
    challenge_id: int,
    status: str,
    flag: str | None = None,
    iterations: int | None = None,
    assigned_to: str | None = None,
) -> None:
    now = _now()
    with _conn() as con:
        fields = ["status=?", "updated_at=?"]
        vals: list[Any] = [status, now]
        if flag is not None:
            fields.append("flag=?"); vals.append(flag)
        if iterations is not None:
            fields.append("iterations=?"); vals.append(iterations)
        if assigned_to is not None:
            fields.append("assigned_to=?"); vals.append(assigned_to)
        vals.append(challenge_id)
        con.execute(f"UPDATE challenges SET {', '.join(fields)} WHERE id=?", vals)
        payload: dict = {"status": status}
        if flag:
            payload["flag"] = flag
        _append_event(con, "status_changed", challenge_id, payload)


def assign_challenge(challenge_id: int, assignee: str, profile: str) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "UPDATE challenges SET assigned_to=?, profile=?, updated_at=? WHERE id=?",
            (assignee, profile, now, challenge_id),
        )
        _append_event(con, "assigned", challenge_id, {"assignee": assignee, "profile": profile})


# ── Messages ──────────────────────────────────────────────────────────────────

def add_message(
    challenge_id: int,
    role: str,
    content: str,
    tool_name: str | None = None,
) -> int:
    now = _now()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO messages (challenge_id, role, content, tool_name, created_at) VALUES (?,?,?,?,?)",
            (challenge_id, role, content[:10000], tool_name, now),
        )
        mid = cur.lastrowid
        if role == "ai" and len(content) > 20:
            _append_event(con, "message", challenge_id, {"role": role, "preview": content[:120]})
    return mid


def get_messages(challenge_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM messages WHERE challenge_id=? ORDER BY id ASC",
            (challenge_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Events (for WebSocket broadcast) ─────────────────────────────────────────

def _append_event(con: sqlite3.Connection, etype: str, challenge_id: int | None, payload: dict) -> None:
    con.execute(
        "INSERT INTO events (type, challenge_id, payload, created_at) VALUES (?,?,?,?)",
        (etype, challenge_id, json.dumps(payload), _now()),
    )


def poll_events_since(event_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT 100",
            (event_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_event_id() -> int:
    with _conn() as con:
        row = con.execute("SELECT MAX(id) FROM events").fetchone()
    return row[0] or 0


# ── Stats ─────────────────────────────────────────────────────────────────────

def scoreboard() -> dict:
    with _conn() as con:
        total  = con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
        solved = con.execute("SELECT COUNT(*) FROM challenges WHERE status='solved'").fetchone()[0]
        pts_row = con.execute("SELECT SUM(points) FROM challenges WHERE status='solved'").fetchone()
        points = pts_row[0] or 0
        by_cat = con.execute(
            "SELECT category, COUNT(*) as n, SUM(CASE WHEN status='solved' THEN 1 ELSE 0 END) as s "
            "FROM challenges GROUP BY category"
        ).fetchall()
    return {
        "total": total,
        "solved": solved,
        "unsolved": total - solved,
        "points": points,
        "by_category": [dict(r) for r in by_cat],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if "files" in d and d["files"]:
        try:
            d["files"] = json.loads(d["files"])
        except json.JSONDecodeError:
            d["files"] = []
    return d
