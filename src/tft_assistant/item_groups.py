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
_RARE_FLOOR = 0.01
_RARE_BOARDS = 10
"""An emblem or an artifact is on few boards of any unit, so a tenth of them is a bar it never
clears. It is listed at a hundredth of a unit's itemised boards, and on ten boards or more, which
is enough to keep out an item a unit held once or twice."""
_FILLS_THE_SLOTS = "ThiefsGloves"
"""Part of the API name of Thief's Gloves, plain and radiant, in every set. The item fills its
holder's other slots with items of its own choosing, so that unit's items say nothing of how
the unit is built."""


@dataclass(frozen=True)
class Held:
    """How one unit places on the boards where it holds two or more finished items."""

    boards: int
    avg_placement: float
    items: dict[str, tuple[float, float]]
    """Each item it holds often enough: the share of those boards, and its average placement there.

    Often enough is a tenth of the boards for an item a player builds, and a hundredth, with ten
    boards at least, for an emblem or an artifact. An emblem is here although it counts toward no group."""


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

    A unit counts where it holds two or more finished items and no Thief's Gloves, and it joins
    a group only once `min_builds` such boards exist. `distance` is how unlike two builds may be within one group.
    """
    held: dict[str, Counter[str]] = defaultdict(Counter)
    builds: Counter[str] = Counter()
    placed: Counter[str] = Counter()
    placed_with: dict[str, Counter[str]] = defaultdict(Counter)
    emblems: dict[str, Counter[str]] = defaultdict(Counter)
    for board in boards:
        for unit in board.units:
            if any(_FILLS_THE_SLOTS in item for item in unit.items):
                continue
            build = static.finished_items(unit.items)
            if len(build) >= 2 and unit.character_id in static.units:
                builds[unit.character_id] += 1
                held[unit.character_id].update(build)
                placed[unit.character_id] += board.placement
                worn = {item for item in unit.items if item in static.items and static.items[item].emblem_of}
                emblems[unit.character_id].update(worn)
                for item in build | worn:
                    placed_with[unit.character_id][item] += board.placement

    def often_enough(unit: str, item: str, count: int) -> bool:
        if static.items[item].emblem_of or static.items[item].is_artifact:
            return count >= _RARE_BOARDS and count / builds[unit] >= _RARE_FLOOR
        return count / builds[unit] >= _ITEM_FLOOR

    def how(unit: str) -> Held:
        counts = held[unit] + emblems[unit]
        often = {item: count for item, count in counts.items() if often_enough(unit, item, count)}
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
