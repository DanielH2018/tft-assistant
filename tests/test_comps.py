import random

import pytest

from tft_assistant.boards import Board, BoardUnit, RiotTrait
from tft_assistant.comps import find_comps
from tft_assistant.static_data import StaticData, Trait, Unit

A_CORE = [f"A{n}" for n in range(1, 7)]
B_CORE = [f"B{n}" for n in range(1, 9)]
FILLERS = [f"F{n}" for n in range(60)]

STATIC = StaticData(
    units={
        name: Unit(name, name, 2, ("T",), 1.0, None)
        for name in [*A_CORE, *B_CORE, *FILLERS, "X1", "X2", "Y1", "Y2"]
    }
    | {"Dummy": Unit("Dummy", "Target Dummy", 8, (), 0.0, None)},
    traits={"T": Trait("T", "Trait", ())},
    items={},
)


def board(units, placement, carry=None, trait="T_A"):
    return Board(
        "NA1_1",
        placement,
        9,
        34,
        tuple(BoardUnit(unit, 2, ("Item",) * 3 if unit == carry else ()) for unit in units),
        {trait: RiotTrait(6, 2, 3), "T_Unique": RiotTrait(1, 1, 1)},
    )


@pytest.fixture(scope="module")
def report():
    rng = random.Random(7)
    filler = lambda: rng.choice(FILLERS)
    boards = (
        [board([*A_CORE, "X1", "X2", filler(), "Dummy"], 2, carry="A1") for _ in range(60)]
        + [board([*A_CORE, "Y1", "Y2", filler()], 6, carry="A1") for _ in range(40)]
        + [board([*B_CORE, filler()], 4, carry="B1", trait="T_B") for _ in range(80)]
        + [board(rng.sample(FILLERS, 9), 8) for _ in range(20)]
        + [board(A_CORE[:5], 8) for _ in range(10)]
    )
    return find_comps(boards, STATIC)


def test_two_variants_of_a_comp_are_one_comp_and_a_different_comp_stays_apart(report):
    assert [set(comp.core) for comp in report.comps] == [set(A_CORE), set(B_CORE)]


def test_a_comp_reports_its_share_placement_carry_and_main_trait(report):
    comp_a, comp_b = report.comps

    assert (comp_a.boards, comp_a.share) == (100, 0.5)
    assert comp_a.avg_placement == pytest.approx(3.6)
    assert (comp_a.top4, comp_b.top4) == (0.6, 1.0)
    assert (comp_a.carries, comp_a.main_trait) == (("A1",), "T_A")


def test_flex_units_played_together_form_one_package_with_its_own_placement(report):
    packages = {package.units: (package.share, package.avg_placement) for package in report.comps[0].packages}

    assert packages == {("X1", "X2"): (0.6, 2.0), ("Y1", "Y2"): (0.4, 6.0)}
    assert report.comps[1].packages == ()


def test_boards_that_resemble_no_comp_are_unclassified_and_short_boards_are_left_out(report):
    assert report.boards == 200
    assert report.unclassified == pytest.approx(0.10)
