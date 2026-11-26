"""Boards with two planted comps, for the tests that run the real clustering."""

import random

import pytest

from tft_assistant.boards import Board, BoardUnit, RiotTrait
from tft_assistant.static_data import Item, StaticData, Trait, Unit

A_CORE = [f"A{n}" for n in range(1, 7)]
B_CORE = [f"B{n}" for n in range(1, 9)]
FILLERS = [f"F{n}" for n in range(60)]


@pytest.fixture(scope="session")
def planted_static():
    return StaticData(
        units={
            name: Unit(name, name, 2, ("T",), 1.0, None, f"https://icons.test/{name}.png")
            for name in [*A_CORE, *B_CORE, *FILLERS, "X1", "X2", "Y1", "Y2"]
        }
        | {"Dummy": Unit("Dummy", "Target Dummy", 8, (), 0.0, None)},
        traits={"T": Trait("T", "Trait", ()), "T_A": Trait("T_A", "Alpha", ()), "T_B": Trait("T_B", "Beta", ())},
        items={
            "Edge": Item("Edge", "Edge", ("Sword", "Glove"), None, None, False),
            "Whisper": Item("Whisper", "Whisper", ("Bow", "Glove"), None, None, False),
            "Plate": Item("Plate", "Plate", (), None, None, False),
            "Sword": Item("Sword", "Sword", (), None, None, True),
        },
    )


def _board(units, placement, *, carry, items, trait="T_A", level=9, three_star=None):
    return Board(
        "NA1_1",
        placement,
        level,
        34,
        tuple(BoardUnit(unit, 3 if unit == three_star else 2, tuple(items) if unit == carry else ()) for unit in units),
        {trait: RiotTrait(6, 2, 3), "T_Unique": RiotTrait(1, 1, 1), "T_Inactive": RiotTrait(1, 0, 3)},
    )


@pytest.fixture(scope="session")
def planted_boards():
    """Comp A in two variants (60 and 40 boards), comp B (80), 20 boards of noise and 10 short boards."""
    rng = random.Random(7)
    filler = lambda: rng.choice(FILLERS)
    x_variant = dict(carry="A1", items=["Edge", "Whisper", "Sword"], three_star="A2")
    y_variant = dict(carry="A1", items=["Edge", "Plate", "Sword"], level=8)
    return (
        [_board([*A_CORE, "X1", "X2", filler(), "Dummy"], 2, **x_variant) for _ in range(60)]
        + [_board([*A_CORE, "Y1", "Y2", filler()], 6, **y_variant) for _ in range(40)]
        + [_board([*B_CORE, filler()], 4, carry="B1", items=["Edge", "Whisper", "Plate"], trait="T_B") for _ in range(80)]
        + [_board(rng.sample(FILLERS, 9), 8, carry=None, items=[]) for _ in range(20)]
        + [_board(A_CORE[:5], 8, carry=None, items=[]) for _ in range(10)]
    )
