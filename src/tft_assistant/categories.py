"""The categories a comp belongs to by rule, read from what its boards show.

A category groups comps that want the same thing from a game, so a condition that helps one
helps the rest: a free reroll helps every reroll comp. The rules name no unit, trait or item of
one set. A reader can add a comp to a category or take it out by hand, and that is an edit the
page applies over these.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tft_assistant.comp_detail import CARRY

if TYPE_CHECKING:
    from tft_assistant.comps import Comp

REROLL = "reroll"
"""The comp takes units to three stars, so it spends its gold on rolls at a low level."""

FAST_9 = "fast-9"
"""The comp levels to 9 before it rolls, so it wants gold and experience."""

ITEMS = "items"
"""The comp's carry has an item its boards place clearly worse without."""

TRAIT = "trait:"
"""Before a trait's id: the comp fields that trait as a vertical."""

_FAST_LEVEL = 9
_VERTICAL = 4
"""A tiered trait is a vertical once a usual board has this many of its units."""


def categories_of(comp: Comp) -> tuple[str, ...]:
    """The comp's categories: the tempo it plays, whether it leans on an item, and its verticals."""
    found = []
    if comp.tempo.three_stars:
        found.append(REROLL)
    elif comp.tempo.roll_level >= _FAST_LEVEL:
        found.append(FAST_9)
    if any(note.critical for key in comp.key_units if key.role == CARRY for note in key.build):
        found.append(ITEMS)
    found += [f"{TRAIT}{trait.name}" for trait in comp.traits if trait.tiers > 1 and trait.units >= _VERTICAL]
    return tuple(found)
