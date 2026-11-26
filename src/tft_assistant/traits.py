"""Which traits a set of units and emblems makes active, and how far each is from its next tier."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from tft_assistant.static_data import StaticData, Trait


@dataclass(frozen=True)
class TraitCount:
    trait: Trait
    units: int
    tier: int
    """How many breakpoints the count has reached; 0 means the trait is not active."""
    style: int
    next_at: int | None
    """The unit count of the next breakpoint, or None at the last one."""


def count_traits(units: Iterable[tuple[str, Sequence[str]]], static: StaticData) -> list[TraitCount]:
    """Count each trait over (unit, items held) pairs, most units first.

    Two copies of one unit count once. An emblem adds its trait to a holder that lacks it.
    """
    holders: dict[str, set[str]] = {}
    for character_id, items in units:
        unit = static.units.get(character_id)
        own = set(unit.traits) if unit else set()
        granted = {static.items[item].emblem_of for item in items if item in static.items} - {None}
        for trait in own | granted:
            holders.setdefault(trait, set()).add(character_id)

    counts = []
    for api_name, members in holders.items():
        trait = static.traits[api_name]
        reached = [point for point in trait.breakpoints if point.min_units <= len(members)]
        ahead = [point for point in trait.breakpoints if point.min_units > len(members)]
        counts.append(
            TraitCount(
                trait,
                len(members),
                len(reached),
                reached[-1].style if reached else 0,
                ahead[0].min_units if ahead else None,
            )
        )
    return sorted(counts, key=lambda count: (-count.tier, -count.units, count.trait.name))
