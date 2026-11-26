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
class RiotTrait:
    """One line of Riot's own trait tally for a board, which is exact where static data is not."""

    units: int
    tier: int
    tiers: int


@dataclass(frozen=True)
class Board:
    match_id: str
    placement: int
    level: int
    last_round: int
    units: tuple[BoardUnit, ...]
    riot_traits: dict[str, RiotTrait]


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
            {
                trait["name"]: RiotTrait(trait["num_units"], trait["tier_current"], trait["tier_total"])
                for trait in participant["traits"]
            },
        )
        for participant in match["info"]["participants"]
    ]
