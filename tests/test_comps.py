import random

import pytest

from tft_assistant.boards import Board, BoardUnit, RiotTrait
from tft_assistant.comp_detail import CompTrait, ItemPick
from tft_assistant.comps import find_comps
from tft_assistant.static_data import Item, StaticData, Trait, Unit

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
    items={
        "Edge": Item("Edge", "Edge", ("Sword", "Glove"), None, None, False),
        "Whisper": Item("Whisper", "Whisper", ("Bow", "Glove"), None, None, False),
        "Plate": Item("Plate", "Plate", (), None, None, False),
        "Sword": Item("Sword", "Sword", (), None, None, True),
    },
)


def board(units, placement, *, carry, items, trait="T_A", level=9, three_star=None):
    return Board(
        "NA1_1",
        placement,
        level,
        34,
        tuple(BoardUnit(unit, 3 if unit == three_star else 2, tuple(items) if unit == carry else ()) for unit in units),
        {trait: RiotTrait(6, 2, 3), "T_Unique": RiotTrait(1, 1, 1), "T_Inactive": RiotTrait(1, 0, 3)},
    )


@pytest.fixture(scope="module")
def report():
    rng = random.Random(7)
    filler = lambda: rng.choice(FILLERS)
    x_variant = dict(carry="A1", items=["Edge", "Whisper", "Sword"], three_star="A2")
    y_variant = dict(carry="A1", items=["Edge", "Plate", "Sword"], level=8)
    boards = (
        [board([*A_CORE, "X1", "X2", filler(), "Dummy"], 2, **x_variant) for _ in range(60)]
        + [board([*A_CORE, "Y1", "Y2", filler()], 6, **y_variant) for _ in range(40)]
        + [board([*B_CORE, filler()], 4, carry="B1", items=["Edge", "Whisper", "Plate"], trait="T_B") for _ in range(80)]
        + [board(rng.sample(FILLERS, 9), 8, carry=None, items=[]) for _ in range(20)]
        + [board(A_CORE[:5], 8, carry=None, items=[]) for _ in range(10)]
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


def test_a_comp_shows_the_traits_riot_counts_as_active_on_most_of_its_boards(report):
    assert report.comps[0].traits == (
        CompTrait("T_A", units=6, tier=2, tiers=3, share=1.0),
        CompTrait("T_Unique", units=1, tier=1, tiers=1, share=1.0),
    )


def test_tempo_gives_the_final_levels_and_the_units_usually_taken_to_three_stars(report):
    comp_a, comp_b = report.comps

    assert comp_a.tempo.levels == ((8, 0.4), (9, 0.6))
    assert comp_a.tempo.three_stars == ("A2",)
    assert comp_b.tempo.three_stars == ()


def test_item_priority_orders_item_and_holder_pairs_and_compares_placement_with_and_without(report):
    assert report.comps[0].item_priority == (
        ItemPick("Edge", "A1", share=1.0, avg_with=pytest.approx(3.6), avg_without=None),
        ItemPick("Whisper", "A1", share=0.6, avg_with=2.0, avg_without=6.0),
        ItemPick("Plate", "A1", share=0.4, avg_with=6.0, avg_without=2.0),
    )


def test_components_to_take_come_from_the_recipes_of_the_item_priority(report):
    assert report.comps[0].take == ("Glove", "Sword", "Bow")
