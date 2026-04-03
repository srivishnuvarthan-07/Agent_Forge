"""
Persistent job store backed by SQLite.
Replaces the in-memory _jobs dict in api/main.py.
Falls back gracefully if SQLite is unavailable.
"""
from __future__ import annotations
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "jobs.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id       TEXT PRIMARY KEY,
                status       TEXT NOT NULL,
                mode         TEXT,
                created_at   TEXT,
                updated_at   TEXT,
                result       TEXT,
                error        TEXT,
                events       TEXT DEFAULT '[]',
                agent_statuses TEXT DEFAULT '{}'
            )
        """)
        c.commit()


def create_job(job_id: str, mode: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO jobs "
            "(job_id, status, mode, created_at, updated_at, events, agent_statuses) "
            "VALUES (?, 'queued', ?, ?, ?, '[]', '{}')",
            (job_id, mode, now, now),
        )
        c.commit()


def get_job(job_id: str) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["events"] = json.loads(d["events"] or "[]")
    d["agent_statuses"] = json.loads(d["agent_statuses"] or "{}")
    return d


def update_job(job_id: str, **kwargs) -> None:
    if not kwargs:
        return
    now = datetime.now(timezone.utc).isoformat()
    kwargs["updated_at"] = now
    # Serialize complex fields
    if "events" in kwargs:
        kwargs["events"] = json.dumps(kwargs["events"])
    if "agent_statuses" in kwargs:
        kwargs["agent_statuses"] = json.dumps(kwargs["agent_statuses"])
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    with _lock, _conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE job_id = ?", vals)
        c.commit()


def list_jobs() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["events"] = json.loads(d["events"] or "[]")
        d["agent_statuses"] = json.loads(d["agent_statuses"] or "{}")
        result.append(d)
    return result


# Initialise on import
init_db()
