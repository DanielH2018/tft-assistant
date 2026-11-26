"""Group units by the items they hold on real boards.

Units that build alike can hold each other's items. A group read in cost order is a holder
chain: the cheap units that carry a late carry's items on the way up.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from tft_assistant.boards import Board
from tft_assistant.static_data import StaticData

_TOP_ITEMS = 5
_ITEM_FLOOR = 0.10


@dataclass(frozen=True)
class ItemGroup:
    items: tuple[str, ...]
    """The items the group's units hold most often, most common first."""
    units: tuple[str, ...]
    """Cheapest first."""


def _build(items: Sequence[str], static: StaticData) -> set[str]:
    """The finished items of one unit that say how it is built: no emblem, no loose component."""
    build = set()
    for name in items:
        item = static.items.get(name)
        if item and not item.emblem_of and not item.is_component:
            build.add(item.radiant_of or name)
    return build


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
    for board in boards:
        for unit in board.units:
            build = _build(unit.items, static)
            if len(build) >= 2 and unit.character_id in static.units:
                builds[unit.character_id] += 1
                held[unit.character_id].update(build)

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
            )
        )
    return tuple(sorted(groups, key=lambda group: (-len(group.units), group.units)))
