"""What a comp's own boards say about it: its traits, its tempo, and which unit holds which item."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median, mode

from tft_assistant.boards import Board
from tft_assistant.static_data import StaticData

_TRAIT_FLOOR = 0.50
_VERTICAL = 4
_THREE_STAR_FLOOR = 0.40
_REROLL_COST = 3
_LEVELS_ABOVE_COST = 4
_FAST_LEVEL = 9
_PICK_FLOOR = 0.20
_PICKS_PER_HOLDER = 3
_PICKS = 8
_COMPONENTS = 3
_SPARE_COMPONENTS = 2
_SPARE_USES = 2
_SPARE_USE_FLOOR = 0.05
_LEVEL_BOARDS = 20
_LEVEL_SHARE = 0.05
_LEVEL_SHIFT = 0.15
_LEVEL_UNITS = 4
_KEY_ITEMS = 1.5
_TANK_ITEMS = 0.75
_TANK_SHARE = 0.6
_NOTE_SHARE = 0.10
_NOTE_ITEMS = 5
_NOTE_BUILDS = 20
_CRITICAL_SHARE = 0.70
_CRITICAL_GAP = 0.40
_CRITICAL_GAP_SHARE = 0.40
_PAIR_GAP = 0.50
_PAIR_EXTRA = 0.25
_PAIRINGS = 1
_SPECIAL_BOARDS = 20
_SPECIAL_SHARE = 0.03
_SPECIAL_SHIFT = 0.15
_SPECIAL_UNITS = 3
_SPECIAL_BESIDE = 0.30
_SPECIAL_EMBLEMS = 3
_SPECIAL_ARTIFACTS = 2


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
    style: str
    """What players call the tempo: the unit cost the comp rerolls for, or the level it plays at."""
    roll_level: int
    """The level at which the comp spends its gold on finding its units."""


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


def main_trait(traits: Sequence[CompTrait], carries: Sequence[str], static: StaticData) -> str | None:
    """The trait a comp is named for: its largest vertical, or else its carry's largest trait.

    Only a trait with more than one tier counts, because a one-tier trait says nothing its unit's
    name does not. A vertical is a trait with `_VERTICAL` units. Without one, a trait of the main
    carry names the comp better than a larger trait its front line happens to share.
    """
    tiered = [trait for trait in traits if trait.tiers > 1]
    own = set(static.units[carries[0]].traits) if carries else set()

    def rank(trait: CompTrait) -> tuple:
        vertical = trait.units if trait.units >= _VERTICAL else 0
        return (-vertical, trait.name not in own, -trait.units, -trait.tier / trait.tiers, trait.name)

    return min(tiered, key=rank).name if tiered else None


def carry_trait(traits: Sequence[CompTrait], carries: Sequence[str], static: StaticData) -> str | None:
    """The largest tiered trait the comp has active that its carry and its second carry both have."""
    if len(carries) < 2:
        return None
    shared = set(static.units[carries[0]].traits) & set(static.units[carries[1]].traits)
    return next((trait.name for trait in traits if trait.name in shared and trait.tiers > 1), None)


def tempo(members: Sequence[Board], carry: str | None, static: StaticData) -> Tempo:
    """The levels a comp's boards end at, the units it three-stars, and the style those make.

    The style comes from what the comp rolls for, not from where its boards end: a winning board
    levels past the point at which its comp was built. A comp that usually three-stars a unit of
    cost `_REROLL_COST` or less rerolls for that cost, the main carry's when the carry is one of
    them. Any other comp plays at the level that finds its main carry. A player finds a unit at
    `_LEVELS_ABOVE_COST` levels above its cost, up to `_FAST_LEVEL`. A comp whose carry is cheap
    and not three-starred has no such level, and takes the one most of its boards end at.
    """
    levels = Counter(board.level for board in members)
    starred = Counter(unit for board in members for unit in {u.character_id for u in board.units if u.stars >= 3})
    three_stars = [
        unit for unit, count in starred.items() if unit in static.units and count / len(members) >= _THREE_STAR_FLOOR
    ]
    cost = static.units[carry].cost if carry else 0
    rerolled = [static.units[unit].cost for unit in three_stars if static.units[unit].cost <= _REROLL_COST]
    if rerolled:
        reroll_cost = cost if carry in three_stars and cost <= _REROLL_COST else max(rerolled)
        style, roll_level = f"{reroll_cost}-cost reroll", reroll_cost + _LEVELS_ABOVE_COST
    else:
        usual_level = levels.most_common(1)[0][0]
        roll_level = min(cost + _LEVELS_ABOVE_COST if cost > _REROLL_COST else usual_level, _FAST_LEVEL)
        style = f"Fast {_FAST_LEVEL}" if roll_level == _FAST_LEVEL else f"Level {roll_level}"
    return Tempo(
        tuple((level, count / len(members)) for level, count in sorted(levels.items())),
        tuple(sorted(three_stars, key=lambda unit: (static.units[unit].cost, unit))),
        style,
        roll_level,
    )


class _Holdings:
    """How often each unit holds each finished item on a comp's boards, and how those boards place."""

    def __init__(self, members: Sequence[Board], static: StaticData) -> None:
        self.boards = len(members)
        self._present: Counter[str] = Counter()
        self._present_places: Counter[str] = Counter()
        self.held: Counter[tuple[str, str]] = Counter()
        self._held_places: Counter[tuple[str, str]] = Counter()
        for board in members:
            builds: dict[str, set[str]] = {}
            for unit in board.units:
                builds.setdefault(unit.character_id, set()).update(static.finished_items(unit.items))
            for holder, build in builds.items():
                self._present[holder] += 1
                self._present_places[holder] += board.placement
                for item in build:
                    self.held[item, holder] += 1
                    self._held_places[item, holder] += board.placement

    def pick(self, item: str, holder: str) -> ItemPick:
        count, places = self.held[item, holder], self._held_places[item, holder]
        lacking = self._present[holder] - count
        return ItemPick(
            item,
            holder,
            count / self.boards,
            places / count,
            (self._present_places[holder] - places) / lacking if lacking else None,
        )


def item_priority(members: Sequence[Board], static: StaticData) -> tuple[ItemPick, ...]:
    """The (item, holder) pairs the comp builds most, most common first.

    The placements beside each pair are correlations: a board that completed three items on its
    carry was usually ahead for other reasons too.
    """
    holdings = _Holdings(members, static)
    picks: list[ItemPick] = []
    per_holder: Counter[str] = Counter()
    for (item, holder), count in holdings.held.most_common():
        if count / len(members) < _PICK_FLOOR or len(picks) == _PICKS:
            break
        if per_holder[holder] == _PICKS_PER_HOLDER:
            continue
        per_holder[holder] += 1
        picks.append(holdings.pick(item, holder))
    return tuple(picks)


@dataclass(frozen=True)
class SpareComponent:
    """One of the components a comp uses least, and the items its boards most often put it into."""

    component: str
    share: float
    """The component's share of all the components in the comp's finished items."""
    uses: tuple[ItemPick, ...]


def spare_components(members: Sequence[Board], static: StaticData) -> tuple[SpareComponent, ...]:
    """Where a comp puts the components it uses least, least used first.

    A component's use is counted over the recipes of every finished item on the comp's boards.
    A comp's boards use every component at some rate, so no share marks one as unwanted: the
    `_SPARE_COMPONENTS` least used are listed. Each carries the (item, holder) pairs built with
    it on `_SPARE_USE_FLOOR` of the boards. A component with no such pair is passed over, which
    drops one that only a rare item uses.
    """
    holdings = _Holdings(members, static)
    used: Counter[str] = Counter()
    for (item, _), count in holdings.held.items():
        for component in static.items[item].components:
            used[component] += count
    spare: list[SpareComponent] = []
    for component, count in sorted(used.items(), key=lambda entry: (entry[1], entry[0])):
        built = [
            pair
            for pair, held in holdings.held.most_common()
            if component in static.items[pair[0]].components
            and pair[1] in static.units
            and held / len(members) >= _SPARE_USE_FLOOR
        ]
        if built and len(spare) < _SPARE_COMPONENTS:
            uses = tuple(holdings.pick(*pair) for pair in built[:_SPARE_USES])
            spare.append(SpareComponent(component, count / used.total(), uses))
    return tuple(spare)


CARRY, SECOND_CARRY, TANK = "carry", "second carry", "tank"


@dataclass(frozen=True)
class Pairing:
    """An item does better beside `partner` than apart from it, by more than the partner helps alone."""

    partner: str
    avg_together: float
    avg_apart: float


@dataclass(frozen=True)
class BuildItem:
    item: str
    share: float
    """The share of the unit's builds in this comp that hold the item."""
    avg_with: float
    avg_without: float | None
    critical: bool
    """Most builds have it, or it is a common item whose absence goes with a clearly worse placement."""
    needs: tuple[Pairing, ...]


@dataclass(frozen=True)
class KeyUnit:
    unit: str
    role: str
    build: tuple[BuildItem, ...] = ()


def _mean(placements: Sequence[int]) -> float:
    return sum(placements) / len(placements)


def build_notes(members: Sequence[Board], unit: str, static: StaticData) -> tuple[BuildItem, ...]:
    """The items one unit builds in a comp, most common first, with what the comp's boards say of each.

    A build is a board on which the unit holds its usual number of finished items, two or more.
    Builds of one size are compared with each other, because a build holding both of two items is
    otherwise a more finished build than one holding either, and places better for that reason.

    Every figure is a correlation between a build and its board's placement. A comparison is made
    only when each side of it has `_NOTE_BUILDS` builds, so a small comp yields few notes.
    """
    itemised = []
    for board in members:
        held: set[str] = set()
        for placed in board.units:
            if placed.character_id == unit:
                held |= static.finished_items(placed.items)
        if len(held) >= 2:
            itemised.append((held, board.placement))
    if not itemised:
        return ()
    usual_size = Counter(len(held) for held, _ in itemised).most_common(1)[0][0]
    builds = [(held, placement) for held, placement in itemised if len(held) == usual_size]

    def placements(*, having: Sequence[str] = (), lacking: Sequence[str] = ()) -> list[int]:
        return [
            placement
            for held, placement in builds
            if all(item in held for item in having) and not any(item in held for item in lacking)
        ]

    def compared(first: list[int], second: list[int]) -> bool:
        return len(first) >= _NOTE_BUILDS and len(second) >= _NOTE_BUILDS

    counts = Counter(item for held, _ in builds for item in held)
    common = [item for item, count in counts.most_common() if count / len(builds) >= _NOTE_SHARE]
    notes = []
    for item in common[:_NOTE_ITEMS]:
        with_item, without_item = placements(having=[item]), placements(lacking=[item])
        share = counts[item] / len(builds)
        worse_without = (
            share >= _CRITICAL_GAP_SHARE
            and compared(with_item, without_item)
            and _mean(without_item) - _mean(with_item) >= _CRITICAL_GAP
        )
        needs = []
        for partner in common:
            together, apart = placements(having=[item, partner]), placements(having=[item], lacking=[partner])
            alone, neither = placements(having=[partner], lacking=[item]), placements(lacking=[item, partner])
            if partner == item or not compared(together, apart) or not compared(alone, neither):
                continue
            gain = _mean(apart) - _mean(together)
            partner_alone_helps = _mean(neither) - _mean(alone)
            if gain >= _PAIR_GAP and gain - partner_alone_helps >= _PAIR_EXTRA:
                needs.append((gain, Pairing(partner, _mean(together), _mean(apart))))
        needs.sort(key=lambda found: (-found[0], found[1].partner))
        notes.append(
            BuildItem(
                item,
                share,
                _mean(with_item),
                _mean(without_item) if without_item else None,
                share >= _CRITICAL_SHARE or worse_without,
                tuple(pairing for _, pairing in needs[:_PAIRINGS]),
            )
        )
    return tuple(notes)


def key_units(members: Sequence[Board], static: StaticData) -> tuple[KeyUnit, ...]:
    """The units a comp itemises: its carry, its second carry and its tank, in that order.

    A carry holds `_KEY_ITEMS` finished items on an average board of the comp. The tank is the
    most itemised unit whose items are mostly defensive; it needs only `_TANK_ITEMS`, because
    a comp spreads its defensive items over more than one unit.
    """
    held: Counter[str] = Counter()
    defensive: Counter[str] = Counter()
    for board in members:
        builds: dict[str, set[str]] = {}
        for unit in board.units:
            builds.setdefault(unit.character_id, set()).update(static.finished_items(unit.items))
        for unit, build in builds.items():
            held[unit] += len(build)
            defensive[unit] += sum(static.items[item].is_defensive for item in build)

    def itemised(floor: float) -> list[str]:
        return [unit for unit, count in held.most_common() if count / len(members) >= floor and unit in static.units]

    tanks = [unit for unit in itemised(_TANK_ITEMS) if defensive[unit] / held[unit] >= _TANK_SHARE]
    carries = [unit for unit in itemised(_KEY_ITEMS) if unit not in tanks]
    roles = [*zip(carries, (CARRY, SECOND_CARRY)), *((unit, TANK) for unit in tanks[:1])]
    return tuple(KeyUnit(unit, role, build_notes(members, unit, static)) for unit, role in roles)


@dataclass(frozen=True)
class UnitShift:
    unit: str
    share: float
    """The share of this level's boards that hold the unit."""
    share_below: float
    """The same share one level lower."""


@dataclass(frozen=True)
class LevelUp:
    """How a comp's boards change at one level above its usual one, against the level below."""

    level: int
    share: float
    avg_placement: float
    adds: tuple[UnitShift, ...]
    drops: tuple[UnitShift, ...]


def level_ups(members: Sequence[Board], static: StaticData) -> tuple[LevelUp, ...]:
    """What a comp puts in, and takes out, at each level above the one it usually ends at.

    A level counts once enough of the comp's boards end there. The placement at a higher level
    is better partly because only a winning player reaches it.
    """
    by_level: dict[int, list[Board]] = {}
    for board in members:
        by_level.setdefault(board.level, []).append(board)
    usual = max(by_level, key=lambda level: len(by_level[level]))

    def shares(level: int) -> Counter[str]:
        held = Counter(unit for board in by_level[level] for unit in {u.character_id for u in board.units})
        return Counter(
            {
                unit: count / len(by_level[level])
                for unit, count in held.items()
                if unit in static.units and static.units[unit].traits
            }
        )

    ups = []
    for level in sorted(by_level):
        boards = by_level[level]
        enough = len(boards) >= _LEVEL_BOARDS and len(boards) / len(members) >= _LEVEL_SHARE
        if level <= usual or not enough or level - 1 not in by_level:
            continue
        here, below = shares(level), shares(level - 1)
        shifts = [UnitShift(unit, here[unit], below[unit]) for unit in here.keys() | below.keys()]
        gained = [s for s in shifts if s.share - s.share_below >= _LEVEL_SHIFT]
        lost = [s for s in shifts if s.share_below - s.share >= _LEVEL_SHIFT]
        adds = sorted(gained, key=lambda s: (s.share_below - s.share, s.unit))
        drops = sorted(lost, key=lambda s: (s.share - s.share_below, s.unit))
        ups.append(
            LevelUp(
                level,
                len(boards) / len(members),
                sum(board.placement for board in boards) / len(boards),
                tuple(adds[:_LEVEL_UNITS]),
                tuple(drops[:_LEVEL_UNITS]),
            )
        )
    return tuple(ups)


@dataclass(frozen=True)
class Swap:
    """A unit that the boards holding a special item play more, or less, than the boards without it."""

    unit: str
    share_with: float
    share_without: float


@dataclass(frozen=True)
class SpecialItem:
    """An emblem or an artifact that some of a comp's boards hold, and how those boards differ."""

    item: str
    share: float
    avg_placement: float
    holder: str
    holder_share: float
    """The share of the boards holding the item on which this unit is the one that holds it."""
    beside: tuple[str, ...]
    """The finished items the holder most often builds beside it."""
    adds: tuple[Swap, ...]
    drops: tuple[Swap, ...]


def special_items(members: Sequence[Board], static: StaticData) -> tuple[SpecialItem, ...]:
    """The emblems a comp's boards hold and then the artifacts, commonest first, with what each changes.

    An item counts once `_SPECIAL_BOARDS` boards and `_SPECIAL_SHARE` of the comp hold it. A unit
    comes in or goes out when its share differs by `_SPECIAL_SHIFT` between the boards with the
    item and the boards without. Each figure is a correlation: a player who was offered an
    emblem made other choices too.
    """
    fielded = [
        {u.character_id for u in board.units if u.character_id in static.units and static.units[u.character_id].traits}
        for board in members
    ]
    holding: dict[str, list[tuple[int, str]]] = {}
    for index, board in enumerate(members):
        for unit in board.units:
            for name in set(unit.items):
                item = static.items.get(name)
                if item and (item.emblem_of or item.is_artifact) and unit.character_id in static.units:
                    holding.setdefault(name, []).append((index, unit.character_id))

    def shares(boards: Sequence[int]) -> Counter[str]:
        held = Counter(unit for index in boards for unit in fielded[index])
        return Counter({unit: count / len(boards) for unit, count in held.items()})

    found = []
    for name, held in holding.items():
        boards = {index for index, _ in held}
        if len(boards) < max(_SPECIAL_BOARDS, _SPECIAL_SHARE * len(members)):
            continue
        holder, holder_boards = Counter(unit for _, unit in held).most_common(1)[0]
        beside: Counter[str] = Counter()
        for index, unit in held:
            if unit == holder:
                for placed in members[index].units:
                    if placed.character_id == holder:
                        beside.update(static.finished_items(placed.items) - {name})
        others = [index for index in range(len(members)) if index not in boards]
        swaps: list[Swap] = []
        if len(others) >= _SPECIAL_BOARDS:
            with_item, without = shares(list(boards)), shares(others)
            swaps = [Swap(unit, with_item[unit], without[unit]) for unit in with_item.keys() | without.keys()]
        adds = sorted(swaps, key=lambda swap: (swap.share_without - swap.share_with, swap.unit))
        drops = sorted(swaps, key=lambda swap: (swap.share_with - swap.share_without, swap.unit))
        found.append(
            SpecialItem(
                name,
                len(boards) / len(members),
                _mean([members[index].placement for index in boards]),
                holder,
                min(1.0, holder_boards / len(boards)),
                tuple(item for item, count in beside.most_common(2) if count / holder_boards >= _SPECIAL_BESIDE),
                tuple(s for s in adds if s.share_with - s.share_without >= _SPECIAL_SHIFT)[:_SPECIAL_UNITS],
                tuple(s for s in drops if s.share_without - s.share_with >= _SPECIAL_SHIFT)[:_SPECIAL_UNITS],
            )
        )
    found.sort(key=lambda special: (-special.share, special.item))
    emblems = [special for special in found if static.items[special.item].emblem_of]
    artifacts = [special for special in found if not static.items[special.item].emblem_of]
    return tuple(emblems[:_SPECIAL_EMBLEMS] + artifacts[:_SPECIAL_ARTIFACTS])


def components_to_take(picks: Sequence[ItemPick], static: StaticData) -> tuple[str, ...]:
    """The components the comp's item priority uses most, weighted by how often each pair is built."""
    wanted: Counter[str] = Counter()
    for pick in picks:
        for component in static.items[pick.item].components:
            wanted[component] += pick.share
    return tuple(component for component, _ in wanted.most_common(_COMPONENTS))
