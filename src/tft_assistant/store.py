"""SQLite store of raw match payloads, read through a Selection.

The store keeps each payload as Riot returned it and indexes only what a Selection filters on,
so an analysis can change its method, or read a field a later set adds, without a second crawl.
A payload names no patch, so a patch is a time window that `sets.GameSet` resolves.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tft_assistant.paths import state_path

DEFAULT_PATH = state_path("matches.db", "~/.local/share/tft-assistant/matches.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    match_id   TEXT PRIMARY KEY,
    platform   TEXT NOT NULL,
    set_number INTEGER NOT NULL,
    queue_id   INTEGER NOT NULL,
    started_at REAL NOT NULL,
    payload    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS matches_by_selection ON matches (set_number, queue_id, started_at);
"""


@dataclass(frozen=True)
class Selection:
    """Which matches an analysis reads. None or an empty tuple leaves that field open."""

    set_number: int
    queue_id: int
    since: datetime | None = None
    until: datetime | None = None
    platforms: tuple[str, ...] = ()

    def _where(self) -> tuple[str, list[Any]]:
        clauses, values = ["set_number = ?", "queue_id = ?"], [self.set_number, self.queue_id]
        if self.platforms:
            clauses.append(f"platform IN ({', '.join('?' * len(self.platforms))})")
            values += self.platforms
        if self.since:
            clauses.append("started_at >= ?")
            values.append(self.since.timestamp())
        if self.until:
            clauses.append("started_at < ?")
            values.append(self.until.timestamp())
        return " AND ".join(clauses), values


@dataclass(frozen=True)
class Holding:
    set_number: int
    queue_id: int
    matches: int
    first: datetime
    last: datetime


class Store:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    def add_match(self, platform: str, payload: dict[str, Any]) -> None:
        info = payload["info"]
        row = (
            payload["metadata"]["match_id"],
            platform,
            info["tft_set_number"],
            info["queue_id"],
            info["game_datetime"] / 1000,
            zlib.compress(json.dumps(payload, separators=(",", ":")).encode()),
        )
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO matches VALUES (?, ?, ?, ?, ?, ?)", row)

    def missing(self, match_ids: Iterable[str]) -> list[str]:
        """The given IDs that the store does not hold, in the given order."""
        ids = list(match_ids)
        with self._lock:
            held = {
                row[0]
                for row in self._db.execute(
                    f"SELECT match_id FROM matches WHERE match_id IN ({', '.join('?' * len(ids))})", ids
                )
            }
        return [match_id for match_id in ids if match_id not in held]

    def count(self, selection: Selection) -> int:
        where, values = selection._where()
        with self._lock:
            return self._db.execute(f"SELECT COUNT(*) FROM matches WHERE {where}", values).fetchone()[0]

    def matches(self, selection: Selection) -> Iterator[dict[str, Any]]:
        where, values = selection._where()
        with self._lock:
            rows = self._db.execute(f"SELECT payload FROM matches WHERE {where} ORDER BY started_at", values).fetchall()
        for (payload,) in rows:
            yield json.loads(zlib.decompress(payload))

    def capped(self, selection: Selection, limit: int) -> Selection:
        """A selection narrowed to its `limit` newest matches, or itself when it holds no more than that.

        The narrowed selection starts where its `limit`-th newest match started, so it says in its
        own terms which matches an analysis read.
        """
        where, values = selection._where()
        with self._lock:
            rows = self._db.execute(
                f"SELECT started_at FROM matches WHERE {where} ORDER BY started_at DESC LIMIT 2 OFFSET ?",
                [*values, limit - 1],
            ).fetchall()
        if len(rows) < 2:
            return selection
        return replace(selection, since=datetime.fromtimestamp(rows[0][0], UTC))

    def newest(self, selection: Selection) -> datetime | None:
        """When the latest match of a selection started, or None when it holds no match."""
        where, values = selection._where()
        with self._lock:
            started = self._db.execute(f"SELECT MAX(started_at) FROM matches WHERE {where}", values).fetchone()[0]
        return datetime.fromtimestamp(started, UTC) if started else None

    def holdings(self) -> list[Holding]:
        """How many matches the store holds for each set and queue, and the span they cover."""
        with self._lock:
            rows = self._db.execute(
                "SELECT set_number, queue_id, COUNT(*), MIN(started_at), MAX(started_at) FROM matches"
                " GROUP BY set_number, queue_id ORDER BY set_number, COUNT(*) DESC"
            ).fetchall()
        return [
            Holding(set_number, queue_id, count, datetime.fromtimestamp(first, UTC), datetime.fromtimestamp(last, UTC))
            for set_number, queue_id, count, first, last in rows
        ]
