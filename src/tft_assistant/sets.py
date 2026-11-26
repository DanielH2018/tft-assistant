"""A set's own facts: its static-data source, its ranked queue and its patch calendar.

A match payload carries no patch number, so the calendar here is what turns a patch name into
the time window a Selection filters on.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from tft_assistant.static_data import StaticData, document
from tft_assistant.store import Selection

SETS_DIR = Path(__file__).parent / "data" / "sets"


def latest_set_number(sets_dir: Path = SETS_DIR) -> int:
    return max(int(entry.name) for entry in sets_dir.iterdir() if entry.is_dir())


@dataclass(frozen=True)
class Patch:
    name: str
    starts: datetime


@dataclass(frozen=True)
class GameSet:
    number: int
    static_data: str
    ranked_queue: int
    patches: tuple[Patch, ...]
    defensive_components: tuple[str, ...] = ()
    offensive_components: tuple[str, ...] = ()

    @classmethod
    def load(cls, number: int, sets_dir: Path = SETS_DIR) -> GameSet:
        with (sets_dir / str(number) / "set.toml").open("rb") as file:
            facts = tomllib.load(file)
        patches = sorted((Patch(p["name"], p["starts"]) for p in facts["patches"]), key=lambda p: p.starts)
        return cls(
            number,
            facts["static_data"],
            facts["ranked_queue"],
            tuple(patches),
            tuple(facts.get("defensive_components", ())),
            tuple(facts.get("offensive_components", ())),
        )

    def roster(self) -> StaticData:
        """This set's units, traits and items, with the facts the set file adds to them."""
        return StaticData.from_document(
            document(), self.static_data, self.defensive_components, self.offensive_components
        )

    def window(self, patch: str) -> tuple[datetime, datetime | None]:
        """When a patch was live: from its start to the next patch's start, or open-ended."""
        for index, candidate in enumerate(self.patches):
            if candidate.name == patch:
                following = self.patches[index + 1 :]
                return candidate.starts, following[0].starts if following else None
        raise KeyError(f"set {self.number} has no patch {patch!r}; it has {[p.name for p in self.patches]}")

    def patch_at(self, moment: datetime) -> str | None:
        """The patch live at a moment, or None before the calendar's first entry."""
        live = [patch.name for patch in self.patches if patch.starts <= moment]
        return live[-1] if live else None

    def standing_selections(self, now: datetime) -> list[tuple[str, Selection]]:
        """The selections a build always produces, each with the label the page shows for it."""
        live = self.patches[-1].name
        standing = [
            (f"Patch {live}", self.selection(patch=live)),
            (f"Patch {live}, last 3 days", self.selection(patch=live, since=now - timedelta(days=3))),
            (f"Patch {live}, last 24 hours", self.selection(patch=live, since=now - timedelta(days=1))),
        ]
        if len(self.patches) > 1:
            previous = self.patches[-2].name
            standing.append((f"Patch {previous}", self.selection(patch=previous)))
        standing.append((f"Set {self.number}, every stored match", self.selection()))
        return standing

    def selection(
        self,
        *,
        patch: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        platforms: tuple[str, ...] = (),
    ) -> Selection:
        """Ranked matches of this set, narrowed to a patch, a time window, or both."""
        if patch:
            starts, ends = self.window(patch)
            since = max(since, starts) if since else starts
            until = min(until, ends) if until and ends else until or ends
        return Selection(self.number, self.ranked_queue, since, until, platforms)
