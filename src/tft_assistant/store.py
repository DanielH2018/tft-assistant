"""SQLite store of raw match payloads, read through a Selection.

The store keeps each payload as Riot returned it and indexes only what a Selection filters on,
so an analysis can change its method, or read a field a later set adds, without a second crawl.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("~/.local/share/tft-assistant/matches.db").expanduser()

RANKED_QUEUE = 1100

_SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    match_id   TEXT PRIMARY KEY,
    platform   TEXT NOT NULL,
    set_number INTEGER NOT NULL,
    patch      TEXT NOT NULL,
    queue_id   INTEGER NOT NULL,
    started_at REAL NOT NULL,
    payload    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS matches_by_selection ON matches (set_number, queue_id, patch, started_at);
"""


def patch_of(game_version: str) -> str:
    """The patch a client version string belongs to: its first two numbers."""
    found = re.search(r"(\d+)\.(\d+)", game_version)
    if not found:
        raise ValueError(f"no patch number in game version {game_version!r}")
    return f"{found[1]}.{found[2]}"


@dataclass(frozen=True)
class Selection:
    """Which matches an analysis reads. An empty tuple or None leaves that field open."""

    set_number: int
    patches: tuple[str, ...] = ()
    since: datetime | None = None
    until: datetime | None = None
    platforms: tuple[str, ...] = ()
    queue_id: int = RANKED_QUEUE

    def _where(self) -> tuple[str, list[Any]]:
        clauses, values = ["set_number = ?", "queue_id = ?"], [self.set_number, self.queue_id]
        for column, chosen in (("patch", self.patches), ("platform", self.platforms)):
            if chosen:
                clauses.append(f"{column} IN ({', '.join('?' * len(chosen))})")
                values += chosen
        if self.since:
            clauses.append("started_at >= ?")
            values.append(self.since.timestamp())
        if self.until:
            clauses.append("started_at < ?")
            values.append(self.until.timestamp())
        return " AND ".join(clauses), values


@dataclass(frozen=True)
class PatchSummary:
    set_number: int
    patch: str
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
            patch_of(info["game_version"]),
            info["queue_id"],
            info["game_datetime"] / 1000,
            zlib.compress(json.dumps(payload, separators=(",", ":")).encode()),
        )
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO matches VALUES (?, ?, ?, ?, ?, ?, ?)", row)

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

    def patches(self, queue_id: int = RANKED_QUEUE) -> list[PatchSummary]:
        """Every set and patch the store holds, so a caller can offer them as selections."""
        with self._lock:
            rows = self._db.execute(
                "SELECT set_number, patch, COUNT(*), MIN(started_at), MAX(started_at) FROM matches"
                " WHERE queue_id = ? GROUP BY set_number, patch ORDER BY MIN(started_at)",
                (queue_id,),
            ).fetchall()
        return [
            PatchSummary(set_number, patch, count, datetime.fromtimestamp(first), datetime.fromtimestamp(last))
            for set_number, patch, count, first, last in rows
        ]
