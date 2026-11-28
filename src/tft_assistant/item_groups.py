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
_SECOND_SHARE = 0.2
"""A unit joins a second group when this share of its builds fits that group better than any
other. Akali builds for attack damage or for ability power, and one group cannot hold both."""
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
    """Each unit's placements, which order the units for a reader who asks which holds an item best.

    A unit of `units` is counted over all its builds, and a unit of `also` over the builds that fit this group."""
    also: tuple[str, ...] = ()
    """Units of another group that build this group's way on a share of their boards, cheapest first."""


def find_item_groups(
    boards: Sequence[Board],
    static: StaticData,
    *,
    distance: float = 0.42,
    min_builds: int = 30,
) -> tuple[ItemGroup, ...]:
    """Item groups among the boards, largest first.

    A unit counts where it holds two or more finished items and no Thief's Gloves, and it joins
    a group only once `min_builds` such boards exist. `distance` is how unlike two builds may be
    within one group. A unit is in one group by all its builds, and also in each other group that
    `_SECOND_SHARE` of its builds fit best.
    """
    # Each itemised board of a unit: its finished items, the emblems it wears, the placement.
    seen: dict[str, list[tuple[frozenset[str], frozenset[str], int]]] = defaultdict(list)
    for board in boards:
        for unit in board.units:
            if any(_FILLS_THE_SLOTS in item for item in unit.items):
                continue
            build = static.finished_items(unit.items)
            if len(build) >= 2 and unit.character_id in static.units:
                worn = {item for item in unit.items if item in static.items and static.items[item].emblem_of}
                seen[unit.character_id].append((frozenset(build), frozenset(worn), board.placement))

    def how(entries: Sequence[tuple[frozenset[str], frozenset[str], int]]) -> Held:
        counts: Counter[str] = Counter()
        placed_with: Counter[str] = Counter()
        for build, worn, placement in entries:
            for item in build | worn:
                counts[item] += 1
                placed_with[item] += placement

        def often_enough(item: str, count: int) -> bool:
            if static.items[item].emblem_of or static.items[item].is_artifact:
                return count >= _RARE_BOARDS and count / len(entries) >= _RARE_FLOOR
            return count / len(entries) >= _ITEM_FLOOR

        often = {item: count for item, count in counts.items() if often_enough(item, count)}
        return Held(
            len(entries),
            sum(placement for _, _, placement in entries) / len(entries),
            {item: (count / len(entries), placed_with[item] / count) for item, count in sorted(often.items())},
        )

    units = sorted(unit for unit, entries in seen.items() if len(entries) >= min_builds)
    if len(units) < 2:
        return ()
    items = sorted({item for unit in units for build, _, _ in seen[unit] for item in build})
    column = {item: number for number, item in enumerate(items)}
    holds = {
        unit: np.array([[item in build for item in items] for build, _, _ in seen[unit]], dtype=float) for unit in units
    }
    rates = np.array([holds[unit].mean(axis=0) for unit in units])
    labels = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=distance
    ).fit_predict(rates)

    order = sorted(set(labels))
    members = {label: [unit for unit, own in zip(units, labels) if own == label] for label in order}
    typical = {label: rates[labels == label].mean(axis=0) for label in order}
    also: dict[int, dict[str, Held]] = {label: {} for label in order}
    for row, (unit, own) in enumerate(zip(units, labels)):
        # A build fits the group whose units hold its items most. The unit's own group is read
        # without the unit, so the unit's second build does not pass for the group's.
        others = dict(typical)
        if len(members[own]) > 1:
            others[own] = (typical[own] * len(members[own]) - rates[row]) / (len(members[own]) - 1)
        scaled = np.array([others[label] / (np.linalg.norm(others[label]) or 1.0) for label in order])
        fits = (holds[unit] @ scaled.T).argmax(axis=1)
        for number, label in enumerate(order):
            fitting = [entry for entry, fit in zip(seen[unit], fits) if fit == number]
            if label != own and len(fitting) >= max(min_builds, _SECOND_SHARE * len(seen[unit])):
                also[label][unit] = how(fitting)

    by_cost = lambda unit: (static.units[unit].cost, unit)
    groups = []
    for label in order:
        groups.append(
            ItemGroup(
                tuple(
                    items[index]
                    for index in np.argsort(-typical[label])[:_TOP_ITEMS]
                    if typical[label][index] >= _ITEM_FLOOR
                ),
                tuple(sorted(members[label], key=by_cost)),
                {unit: how(seen[unit]) for unit in members[label]} | also[label],
                tuple(sorted(also[label], key=by_cost)),
            )
        )
    return tuple(sorted(groups, key=lambda group: (-len(group.units), group.units)))
