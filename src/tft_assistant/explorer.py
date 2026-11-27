"""Write a selection's boards beside the page, for the explorer to filter in the browser.

The explorer asks questions the comp list cannot answer, such as how a unit does with one item,
so it needs every board and not an analysis of them. A board is written as a short line of
text: about 50 bytes, so 70,000 boards are a file of a few megabytes that the page loads only
when its Explorer tab opens. A line holds a placement, a level, units, their stars and their
items, and nothing about the player.

    line   = placement level unit*
    unit   = unit-number(2) stars-and-item-count(1) item-number(2)*

Every number is written in `ALPHABET`, one symbol or two. `stars-and-item-count` is the stars
times four plus the number of items. A unit or an item the set's data does not know is left
out, as the analysis leaves it out.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from tft_assistant.boards import Board
from tft_assistant.static_data import StaticData

EXPLORER_DIR = "explorer"

ALPHABET = "".join(chr(code) for code in range(35, 127) if code != 92)
"""The printable characters a JSON string holds without an escape: no quote and no backslash."""

_MOST_ITEMS = 3


def _two(number: int) -> str:
    return ALPHABET[number // len(ALPHABET)] + ALPHABET[number % len(ALPHABET)]


def encode(boards: Sequence[Board], static: StaticData) -> dict[str, Any]:
    """The boards as the document the explorer reads: the unit and item ids, then a line a board."""
    units = sorted(static.units)
    items = sorted(static.items)
    unit_number = {unit: number for number, unit in enumerate(units)}
    item_number = {item: number for number, item in enumerate(items)}
    lines = []
    for board in boards:
        line = [str(board.placement), ALPHABET[board.level]]
        for unit in board.units:
            if unit.character_id not in unit_number:
                continue
            held = [item_number[item] for item in unit.items if item in item_number][:_MOST_ITEMS]
            line.append(_two(unit_number[unit.character_id]) + ALPHABET[unit.stars * 4 + len(held)])
            line.extend(_two(item) for item in held)
        lines.append("".join(line))
    return {"alphabet": ALPHABET, "units": units, "items": items, "boards": "\n".join(lines)}


def write(boards: Sequence[Board], static: StaticData, site: Path) -> str:
    """Write the boards under `site` and return the file's path relative to the page.

    The file is named by a digest of its content, so two selections of the same matches share
    one file and a browser may keep it for good.
    """
    content = json.dumps(encode(boards, static), separators=(",", ":")).encode()
    path = f"{EXPLORER_DIR}/{hashlib.sha256(content).hexdigest()[:20]}.json"
    (site / EXPLORER_DIR).mkdir(parents=True, exist_ok=True)
    (site / path).write_bytes(content)
    return path


def prune(site: Path, kept: Iterable[str]) -> None:
    """Remove the board files under `site` that no snapshot of this build names."""
    folder = site / EXPLORER_DIR
    if folder.is_dir():
        for stale in set(folder.iterdir()) - {site / path for path in kept}:
            stale.unlink()
