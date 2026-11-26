"""The row a unit usually stands in, for a board nobody has positioned by hand.

A match payload records no positions, so this is a default from what the static data does say:
a unit's attack range, and its role where the range is missing. The page places a comp's units
within their rows, because the units on a board depend on the flex units picked there.
"""

from __future__ import annotations

from tft_assistant.static_data import Unit

ROWS = 4

_FRONT_ROLES = ("Tank", "Fighter")


def usual_row(unit: Unit) -> int:
    """The row a unit usually takes: 0 is the front row and `ROWS - 1` the back."""
    if unit.attack_range >= 1:
        return min(int(unit.attack_range), ROWS) - 1
    return 0 if unit.role and unit.role.endswith(_FRONT_ROLES) else ROWS - 1
