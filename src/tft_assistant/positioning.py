"""Where a unit usually stands, for a board nobody has positioned by hand.

A match payload records no positions, so this is a default from what the static data does say:
a unit's attack range, and its role where the range is missing.
"""

from __future__ import annotations

from collections.abc import Sequence

from tft_assistant.static_data import StaticData, Unit

ROWS, COLUMNS = 4, 7

_FRONT_ROLES = ("Tank", "Fighter")
_CENTRE_OUT = (3, 2, 4, 1, 5, 0, 6)
_CORNER_IN = (0, 1, 2, 3, 4, 5, 6)


def usual_row(unit: Unit) -> int:
    """The row a unit usually takes: 0 is the front row and `ROWS - 1` the back."""
    if unit.attack_range >= 1:
        return min(int(unit.attack_range), ROWS) - 1
    return 0 if unit.role and unit.role.endswith(_FRONT_ROLES) else ROWS - 1


def default_board(units: Sequence[str], carries: Sequence[str], static: StaticData) -> dict[str, tuple[int, int]]:
    """A (row, column) for each unit: each in its usual row, tanks central, carries in a back corner.

    A row that would hold more than `COLUMNS` units passes the extras to the next row inward.
    """
    rows: list[list[str]] = [[] for _ in range(ROWS)]
    for unit in units:
        rows[usual_row(static.units[unit])].append(unit)

    placed: dict[str, tuple[int, int]] = {}
    for row in (0, ROWS - 1, 1, ROWS - 2):
        standing = sorted(rows[row], key=lambda unit: (unit not in carries, -static.units[unit].cost, unit))
        inward = row + 1 if row < ROWS // 2 else row - 1
        rows[inward] += standing[COLUMNS:]
        columns = _CORNER_IN if row == ROWS - 1 else _CENTRE_OUT
        for unit, column in zip(standing, columns):
            placed[unit] = (row, column)
    return placed
