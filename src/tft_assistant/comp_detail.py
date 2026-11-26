"""What a comp's own boards say about it: its traits, its tempo, and which unit holds which item."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median, mode

from tft_assistant.boards import Board
from tft_assistant.static_data import StaticData

_TRAIT_FLOOR = 0.50
_THREE_STAR_FLOOR = 0.40
_PICK_FLOOR = 0.20
_PICKS_PER_HOLDER = 3
_PICKS = 8
_COMPONENTS = 3


@dataclass(frozen=True)
class CompTrait:
    """A trait most of the comp's boards have active, as Riot's own tally counts it."""

    name: str
    units: int
    tier: int
    tiers: int
    share: float


@dataclass(frozen=True)
class Tempo:
    levels: tuple[tuple[int, float], ...]
    """The share of boards that end at each player level, lowest level first."""
    three_stars: tuple[str, ...]
    """Units the comp usually takes to three stars, which marks a reroll comp."""


@dataclass(frozen=True)
class ItemPick:
    item: str
    holder: str
    share: float
    """The share of the comp's boards on which the holder has the item."""
    avg_with: float
    avg_without: float | None
    """Placement of the holder's boards that lack the item, or None when every one has it."""


def typical_traits(members: Sequence[Board]) -> tuple[CompTrait, ...]:
    active: dict[str, list] = {}
    for board in members:
        for name, trait in board.riot_traits.items():
            if trait.tier > 0:
                active.setdefault(name, []).append(trait)
    traits = [
        CompTrait(
            name,
            int(median(trait.units for trait in found)),
            mode(trait.tier for trait in found),
            found[0].tiers,
            len(found) / len(members),
        )
        for name, found in active.items()
        if len(found) / len(members) >= _TRAIT_FLOOR
    ]
    return tuple(sorted(traits, key=lambda trait: (-trait.units, -trait.tier / trait.tiers, trait.name)))


def tempo(members: Sequence[Board], static: StaticData) -> Tempo:
    levels = Counter(board.level for board in members)
    starred = Counter(unit for board in members for unit in {u.character_id for u in board.units if u.stars >= 3})
    three_stars = [
        unit for unit, count in starred.items() if unit in static.units and count / len(members) >= _THREE_STAR_FLOOR
    ]
    return Tempo(
        tuple((level, count / len(members)) for level, count in sorted(levels.items())),
        tuple(sorted(three_stars, key=lambda unit: (static.units[unit].cost, unit))),
    )


def item_priority(members: Sequence[Board], static: StaticData) -> tuple[ItemPick, ...]:
    """The (item, holder) pairs the comp builds most, most common first.

    The placements beside each pair are correlations: a board that completed three items on its
    carry was usually ahead for other reasons too.
    """
    present: Counter[str] = Counter()
    present_places: Counter[str] = Counter()
    holding: Counter[tuple[str, str]] = Counter()
    holding_places: Counter[tuple[str, str]] = Counter()
    for board in members:
        builds: dict[str, set[str]] = {}
        for unit in board.units:
            builds.setdefault(unit.character_id, set()).update(static.finished_items(unit.items))
        for holder, build in builds.items():
            present[holder] += 1
            present_places[holder] += board.placement
            for item in build:
                holding[item, holder] += 1
                holding_places[item, holder] += board.placement

    picks: list[ItemPick] = []
    per_holder: Counter[str] = Counter()
    for (item, holder), count in holding.most_common():
        if count / len(members) < _PICK_FLOOR or len(picks) == _PICKS:
            break
        if per_holder[holder] == _PICKS_PER_HOLDER:
            continue
        per_holder[holder] += 1
        lacking = present[holder] - count
        picks.append(
            ItemPick(
                item,
                holder,
                count / len(members),
                holding_places[item, holder] / count,
                (present_places[holder] - holding_places[item, holder]) / lacking if lacking else None,
            )
        )
    return tuple(picks)


def components_to_take(picks: Sequence[ItemPick], static: StaticData) -> tuple[str, ...]:
    """The components the comp's item priority uses most, weighted by how often each pair is built."""
    wanted: Counter[str] = Counter()
    for pick in picks:
        for component in static.items[pick.item].components:
            wanted[component] += pick.share
    return tuple(component for component, _ in wanted.most_common(_COMPONENTS))
