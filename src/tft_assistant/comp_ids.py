"""The id each comp keeps from one analysis to the next.

Clustering finds a comp again with a slightly different core: a unit crosses the core threshold,
or a patch moves one. An id made from the core alone would change with it, and everything keyed
by the id, such as the comp a reader has open, would lose its comp. So a file remembers the core
each id last had, and a comp takes the id of the remembered core it shares the most units with.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from tft_assistant.paths import state_path

DEFAULT_PATH = state_path("comp-ids.json", "~/.local/share/tft-assistant/comp-ids.json")

_SAME_COMP = 0.6
"""Two cores are one comp when the units they share are at least this share of the units either has.

A core of five that swaps one unit shares four of six, 0.67, and keeps its id. One that swaps two
shares three of seven, 0.43, and is a different comp.
"""


def _overlap(first: Sequence[str], second: Sequence[str]) -> float:
    return len(set(first) & set(second)) / len(set(first) | set(second))


def _new_id(core: Sequence[str], taken: set[str]) -> str:
    text = " ".join(sorted(core))
    while True:
        found = hashlib.sha1(text.encode()).hexdigest()[:10]
        if found not in taken:
            return found
        text += " " + found


class CompIds:
    """The ids of every set's comps, in one JSON file."""

    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self._path = Path(path)

    def assign(self, set_number: int, cores: Sequence[Sequence[str]]) -> list[str]:
        """An id for each core, in order, and the file updated to hold them.

        A core takes the id of the remembered core of its set that it overlaps most, when the two
        are one comp. The cores of one call are different comps, so no two of them take one id. A
        core that matches nothing gets an id of its own. An id no core took stays in the file,
        because a comp that drops out of one analysis can return in the next.
        """
        every_set = json.loads(self._path.read_text()) if self._path.exists() else {}
        known: dict[str, list[str]] = every_set.setdefault(str(set_number), {})

        pairs = sorted(
            (
                (_overlap(core, remembered), position, comp_id)
                for position, core in enumerate(cores)
                for comp_id, remembered in known.items()
            ),
            key=lambda pair: (-pair[0], pair[1], pair[2]),
        )
        ids: dict[int, str] = {}
        for overlap, position, comp_id in pairs:
            if overlap >= _SAME_COMP and position not in ids and comp_id not in ids.values():
                ids[position] = comp_id
        for position, core in enumerate(cores):
            if position not in ids:
                ids[position] = _new_id(core, set(known) | set(ids.values()))
            known[ids[position]] = sorted(core)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        scratch = self._path.with_suffix(".tmp")
        scratch.write_text(json.dumps(every_set, indent=1, sort_keys=True))
        scratch.replace(self._path)
        return [ids[position] for position in range(len(cores))]
