"""Boards with two planted comps, for the tests that run the real clustering."""

import random

import pytest

from tft_assistant.boards import Board, BoardUnit, RiotTrait
from tft_assistant.static_data import Item, StaticData, Trait, Unit

A_CORE = [f"A{n}" for n in range(1, 7)]
B_CORE = [f"B{n}" for n in range(1, 9)]
B_CARRIES = ["B1", "B3"]
FILLERS = [f"F{n}" for n in range(60)]


@pytest.fixture(scope="session")
def planted_static():
    return StaticData(
        units={
            name: Unit(name, name, 2, ("T",), 1.0, None, f"https://icons.test/{name}.png")
            for name in [*A_CORE, *B_CORE, *FILLERS, "X1", "X2", "Y1", "Y2", "Z1", "Z2"]
        }
        | {name: Unit(name, name, 2, ("T", "T_C"), 1.0, None, f"https://icons.test/{name}.png") for name in B_CARRIES}
        | {"Dummy": Unit("Dummy", "Target Dummy", 8, (), 0.0, None)},
        traits={
            "T": Trait("T", "Trait", ()),
            "T_A": Trait("T_A", "Alpha", ()),
            "T_B": Trait("T_B", "Beta", ()),
            "T_C": Trait("T_C", "Hunter", ()),
        },
        items={
            "Edge": Item("Edge", "Edge", ("Sword", "Glove"), None, None, False),
            "Whisper": Item("Whisper", "Whisper", ("Bow", "Glove"), None, None, False),
            "Plate": Item("Plate", "Plate", (), None, None, False),
            "Sword": Item("Sword", "Sword", (), None, None, True),
            "Stone": Item("Stone", "Stone", ("Vest", "Vest"), None, None, False, is_defensive=True),
            "Cape": Item("Cape", "Cape", ("Vest", "Belt"), None, None, False, is_defensive=True),
        },
    )


def _board(units, placement, *, carry, items, trait="T_A", level=9, three_star=None, others=None, carry_trait=None):
    builds = {carry: items, **(others or {})}
    shared = {carry_trait: RiotTrait(2, 1, 3)} if carry_trait else {}
    return Board(
        "NA1_1",
        placement,
        level,
        34,
        tuple(BoardUnit(unit, 3 if unit == three_star else 2, tuple(builds.get(unit, ()))) for unit in units),
        {trait: RiotTrait(6, 2, 3), "T_Unique": RiotTrait(1, 1, 1), "T_Inactive": RiotTrait(1, 0, 3), **shared},
    )


@pytest.fixture(scope="session")
def planted_boards():
    """Comp A in two variants, comp B (80 boards), 20 boards of noise and 10 short boards.

    Comp A's 60 level-8 boards hold X1 and X2 and place 2nd on average: 10 place 1st, 10 place 3rd
    and 40 place 2nd. Its 40 level-9 boards hold Y1 and Y2 and place 6th. Comp B itemises a carry (B1), a second carry (B3) and a tank (B2), and its two
    carries share a trait the comp has active (T_C). Half its boards hold Z1 and half hold Z2, as
    often together as chance would have it.
    """
    rng = random.Random(7)
    filler = lambda: rng.choice(FILLERS)
    x_variant = dict(carry="A1", items=["Edge", "Whisper", "Sword"], three_star="A2", level=8)
    y_variant = dict(carry="A1", items=["Edge", "Plate", "Sword"], level=9)
    comp_b = dict(
        carry="B1",
        items=["Edge", "Whisper", "Plate"],
        others={"B3": ["Edge", "Whisper"], "B2": ["Stone", "Cape", "Plate"]},
        trait="T_B",
        carry_trait="T_C",
    )
    return (
        [_board([*A_CORE, "X1", "X2", filler(), "Dummy"], 1 if n < 10 else 3 if n < 20 else 2, **x_variant) for n in range(60)]
        + [_board([*A_CORE, "Y1", "Y2", filler()], 6, **y_variant) for _ in range(40)]
        + [_board([*B_CORE, *(["Z1"] if n < 40 else []), *(["Z2"] if 20 <= n < 60 else [])], 4, **comp_b) for n in range(80)]
        + [_board(rng.sample(FILLERS, 9), 8, carry=None, items=[]) for _ in range(20)]
        + [_board(A_CORE[:5], 8, carry=None, items=[]) for _ in range(10)]
    )
