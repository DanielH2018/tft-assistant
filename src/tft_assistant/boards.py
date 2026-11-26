"""The eight final boards of a match payload, as the fields an analysis reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BoardUnit:
    character_id: str
    stars: int
    items: tuple[str, ...]


@dataclass(frozen=True)
class Board:
    match_id: str
    placement: int
    level: int
    last_round: int
    units: tuple[BoardUnit, ...]
    riot_trait_counts: dict[str, int]
    """Riot's own count of units per trait, the oracle the trait module is checked against."""


def boards(match: dict[str, Any]) -> list[Board]:
    return [
        Board(
            match["metadata"]["match_id"],
            participant["placement"],
            participant["level"],
            participant["last_round"],
            tuple(
                BoardUnit(unit["character_id"], unit["tier"], tuple(unit.get("itemNames") or ()))
                for unit in participant["units"]
            ),
            {trait["name"]: trait["num_units"] for trait in participant["traits"]},
        )
        for participant in match["info"]["participants"]
    ]
