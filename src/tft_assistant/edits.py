"""What a person writes about a comp, kept apart from what the analysis derives.

An edit belongs to one comp of one set and one field of it. The analysis never reads this
store: the page merges the edits into a snapshot in the browser, so an edit shows without a
rebuild. Unlike the match store, nothing here comes back from an API, so a deployment backs
this file up.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from tft_assistant.paths import state_path

DEFAULT_PATH = state_path("keep/edits.db", "~/.local/share/tft-assistant/edits.db")

FIELDS = {"name": 60, "notes": 4000, "plan": 2000, "categories": 200}
"""Each field a comp's edit may hold, with the longest text it takes."""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS edits (
    set_number INTEGER NOT NULL,
    comp_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (set_number, comp_id, field)
);
"""


class Edits:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    def of_set(self, set_number: int) -> dict[str, dict[str, str]]:
        """Every edit of a set: comp id, then field, then the text."""
        with self._lock:
            rows = self._db.execute(
                "SELECT comp_id, field, value FROM edits WHERE set_number = ? ORDER BY comp_id, field", [set_number]
            ).fetchall()
        found: dict[str, dict[str, str]] = {}
        for comp_id, field, value in rows:
            found.setdefault(comp_id, {})[field] = value
        return found

    def put(self, set_number: int, comp_id: str, field: str, value: str) -> None:
        """Set one field of one comp's edit. An empty text removes the field.

        Raises:
            ValueError: `field` is not one of `FIELDS`, or the text is longer than the field takes.
        """
        if field not in FIELDS:
            raise ValueError(f"an edit has no field {field!r}; it has {sorted(FIELDS)}")
        if len(value) > FIELDS[field]:
            raise ValueError(f"{field} takes {FIELDS[field]} characters, and this text has {len(value)}")
        key = [set_number, comp_id, field]
        with self._lock, self._db:
            if value:
                self._db.execute("INSERT OR REPLACE INTO edits VALUES (?, ?, ?, ?)", [*key, value])
            else:
                self._db.execute("DELETE FROM edits WHERE set_number = ? AND comp_id = ? AND field = ?", key)
