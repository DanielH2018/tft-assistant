"""How the boards that hold an item place, for every item the boards hold.

An item's figures are over the boards that hold it at least once, so a board with two copies
counts once. They say how boards with the item did, not what the item did for them: a board
holds an artifact or a radiant item because it was ahead or was offered one.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from tft_assistant.boards import Board
from tft_assistant.static_data import Item, StaticData

MIN_BOARDS = 50
"""An item on fewer boards has no figures worth a row."""

CRAFTABLE = "craftable"
ARTIFACT = "artifact"
EMBLEM = "emblem"
RADIANT = "radiant"
OTHER = "other"

_TRAIT_COMPONENTS = ("Spatula", "FryingPan")
"""How the API names of the two components that make emblems end, in every set. Two of them make a
Tactician's item, which gives a team slot or a shield and is no unit's build."""


def kind_of(item: Item) -> str | None:
    """The one kind an item is listed under, or None for a loose component, which is not listed.

    An emblem is an emblem whether or not it has a recipe. An item made of two emblem components
    is a Tactician's item, and is listed with the items of no kind.
    """
    if item.emblem_of:
        return EMBLEM
    if item.radiant_of:
        return RADIANT
    if item.is_artifact:
        return ARTIFACT
    if item.is_component:
        return None
    if item.components and all(part.endswith(_TRAIT_COMPONENTS) for part in item.components):
        return OTHER
    return CRAFTABLE if item.components else OTHER


@dataclass(frozen=True)
class ItemStat:
    item: str
    kind: str
    has_recipe: bool
    """Two components make it. Among emblems this tells the craftable from the ones a game hands out."""
    boards: int
    share: float
    avg_placement: float
    top4: float
    win_rate: float


def find_item_stats(boards: Sequence[Board], static: StaticData) -> tuple[ItemStat, ...]:
    """The items on at least `MIN_BOARDS` boards, most held first. A loose component has no row."""
    placements: dict[str, list[int]] = defaultdict(list)
    for board in boards:
        for item in {item for unit in board.units for item in unit.items if item in static.items and kind_of(static.items[item])}:
            placements[item].append(board.placement)
    stats = [
        ItemStat(
            item,
            kind_of(static.items[item]) or OTHER,
            bool(static.items[item].components),
            len(placed),
            len(placed) / len(boards),
            sum(placed) / len(placed),
            sum(1 for placement in placed if placement <= 4) / len(placed),
            placed.count(1) / len(placed),
        )
        for item, placed in placements.items()
        if len(placed) >= MIN_BOARDS
    ]
    return tuple(sorted(stats, key=lambda stat: (-stat.boards, stat.item)))
