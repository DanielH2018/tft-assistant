"""Group units by the items they hold on real boards.

Units that build alike can hold each other's items. A group read in cost order is a holder
chain: the cheap units that carry a late carry's items on the way up.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from tft_assistant.boards import Board
from tft_assistant.static_data import StaticData

_TOP_ITEMS = 5
_ITEM_FLOOR = 0.10


@dataclass(frozen=True)
class Held:
    """How one unit places on the boards where it holds two or more finished items."""

    boards: int
    avg_placement: float
    items: dict[str, tuple[float, float]]
    """Each item it holds on a tenth of those boards or more: the share of them, and its average placement there."""


@dataclass(frozen=True)
class ItemGroup:
    items: tuple[str, ...]
    """The items the group's units hold most often, most common first."""
    units: tuple[str, ...]
    """Cheapest first."""
    held: dict[str, Held] = field(default_factory=dict)
    """Each unit's placements, which order the units for a reader who asks which holds an item best."""


def find_item_groups(
    boards: Sequence[Board],
    static: StaticData,
    *,
    distance: float = 0.45,
    min_builds: int = 30,
) -> tuple[ItemGroup, ...]:
    """Item groups among the boards, largest first.

    A unit counts where it holds two or more finished items, and it joins a group only once
    `min_builds` such boards exist. `distance` is how unlike two builds may be within one group.
    """
    held: dict[str, Counter[str]] = defaultdict(Counter)
    builds: Counter[str] = Counter()
    placed: Counter[str] = Counter()
    placed_with: dict[str, Counter[str]] = defaultdict(Counter)
    for board in boards:
        for unit in board.units:
            build = static.finished_items(unit.items)
            if len(build) >= 2 and unit.character_id in static.units:
                builds[unit.character_id] += 1
                held[unit.character_id].update(build)
                placed[unit.character_id] += board.placement
                for item in build:
                    placed_with[unit.character_id][item] += board.placement

    def how(unit: str) -> Held:
        often = {item: count for item, count in held[unit].items() if count / builds[unit] >= _ITEM_FLOOR}
        return Held(
            builds[unit],
            placed[unit] / builds[unit],
            {item: (count / builds[unit], placed_with[unit][item] / count) for item, count in sorted(often.items())},
        )

    units = sorted(unit for unit, count in builds.items() if count >= min_builds)
    if len(units) < 2:
        return ()
    items = sorted({item for unit in units for item in held[unit]})
    rates = np.array([[held[unit][item] / builds[unit] for item in items] for unit in units])
    labels = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=distance
    ).fit_predict(rates)

    groups = []
    for label in set(labels):
        members = [unit for unit, own in zip(units, labels) if own == label]
        typical = rates[labels == label].mean(axis=0)
        groups.append(
            ItemGroup(
                tuple(items[index] for index in np.argsort(-typical)[:_TOP_ITEMS] if typical[index] >= _ITEM_FLOOR),
                tuple(sorted(members, key=lambda unit: (static.units[unit].cost, unit))),
                {unit: how(unit) for unit in members},
            )
        )
    return tuple(sorted(groups, key=lambda group: (-len(group.units), group.units)))
