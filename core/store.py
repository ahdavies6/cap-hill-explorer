"""SQLite + FTS5 store. Read-heavy; refresh writes, web reads."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

from config import DB_PATH
from core.categorize import categorize
from core.models import Address, Event

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    uid           TEXT PRIMARY KEY,
    source_id     TEXT,
    origin_id     TEXT,
    title         TEXT,
    description   TEXT,
    url           TEXT,
    begins_on     TEXT,   -- ISO 8601 UTC
    ends_on       TEXT,
    status        TEXT,
    category      TEXT,
    language      TEXT,
    online_address TEXT,
    picture_url   TEXT,
    lat           REAL,
    lng           REAL,
    locality      TEXT,
    tags          TEXT,   -- JSON array
    raw           TEXT,   -- JSON
    fetched_at    TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts
    USING fts5(title, description, content='events', content_rowid='rowid');
CREATE INDEX IF NOT EXISTS idx_events_begins ON events(begins_on);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, events: list[Event]) -> int:
    rows = [_to_row(e) for e in events]
    conn.executemany(
        """
        INSERT INTO events (uid, source_id, origin_id, title, description, url,
            begins_on, ends_on, status, category, language, online_address,
            picture_url, lat, lng, locality, tags, raw, fetched_at)
        VALUES (:uid, :source_id, :origin_id, :title, :description, :url,
            :begins_on, :ends_on, :status, :category, :language, :online_address,
            :picture_url, :lat, :lng, :locality, :tags, :raw, :fetched_at)
        ON CONFLICT(uid) DO UPDATE SET
            title=excluded.title, description=excluded.description,
            url=excluded.url, begins_on=excluded.begins_on, ends_on=excluded.ends_on,
            status=excluded.status, lat=excluded.lat, lng=excluded.lng,
            locality=excluded.locality, tags=excluded.tags, raw=excluded.raw,
            fetched_at=excluded.fetched_at
        """,
        rows,
    )
    conn.commit()
    _reindex_fts(conn)
    return len(rows)


def query(
    conn: sqlite3.Connection,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    text: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM events WHERE 1=1"
    params: list[Any] = []
    if start:
        sql += " AND begins_on >= ?"
        params.append(start.isoformat())
    if end:
        sql += " AND begins_on < ?"
        params.append(end.isoformat())
    if text:
        sql += (
            " AND uid IN (SELECT e.uid FROM events e JOIN events_fts f"
            " ON e.rowid = f.rowid WHERE events_fts MATCH ?)"
        )
        params.append(text)
    sql += " ORDER BY begins_on ASC"
    cur = conn.execute(sql, params)
    return [_from_row(r) for r in cur.fetchall()]


def _to_row(e: Event) -> dict[str, Any]:
    a = e.address or Address()
    return {
        "uid": e.uid,
        "source_id": e.source_id,
        "origin_id": e.origin_id,
        "title": e.title,
        "description": e.description,
        "url": e.url,
        "begins_on": e.begins_on.isoformat(),
        "ends_on": e.ends_on.isoformat() if e.ends_on else None,
        "status": e.status,
        "category": e.category,
        "language": e.language,
        "online_address": e.online_address,
        "picture_url": e.picture_url,
        "lat": a.lat,
        "lng": a.lng,
        "locality": a.locality,
        "tags": json.dumps(e.tags),
        "raw": json.dumps(e.raw, default=str),
        "fetched_at": datetime.utcnow().isoformat(),
    }


def _from_row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["category_group"] = categorize(d.get("title"), d.get("category"), d.get("description"))
    d.pop("raw", None)  # keep API payloads lean
    return d


def _reindex_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO events_fts(events_fts) VALUES('rebuild')")
    conn.commit()
