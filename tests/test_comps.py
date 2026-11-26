import pytest
from conftest import A_CORE, B_CORE

from tft_assistant.boards import Board, BoardUnit
from tft_assistant.comp_detail import CompTrait, ItemPick, level_ups
from tft_assistant.comps import find_comps


@pytest.fixture(scope="module")
def report(planted_boards, planted_static):
    return find_comps(planted_boards, planted_static)


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

    assert comp_a.tempo.levels == ((8, 0.6), (9, 0.4))
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


def test_a_level_above_the_usual_one_lists_the_units_that_come_in_and_the_units_that_go_out(report):
    comp_a, comp_b = report.comps
    (up,) = comp_a.level_ups

    assert (up.level, up.share, up.avg_placement) == (9, 0.4, 6.0)
    assert [(shift.unit, shift.share, shift.share_below) for shift in up.adds] == [("Y1", 1.0, 0.0), ("Y2", 1.0, 0.0)]
    assert [(shift.unit, shift.share, shift.share_below) for shift in up.drops] == [("X1", 0.0, 1.0), ("X2", 0.0, 1.0)]
    assert comp_b.level_ups == ()


def test_key_units_are_the_carry_the_second_carry_and_the_tank_whose_build_is_mostly_defensive(report):
    comp_a, comp_b = report.comps

    assert [(key.unit, key.role) for key in comp_b.key_units] == [("B1", "carry"), ("B3", "second carry"), ("B2", "tank")]
    assert comp_b.carries == ("B1", "B3")
    assert [(key.unit, key.role) for key in comp_a.key_units] == [("A1", "carry")]


def test_a_level_that_too_few_boards_reach_is_not_reported(planted_static):
    def board(level, extra):
        units = tuple(BoardUnit(unit, 2, ()) for unit in [*A_CORE, extra])
        return Board("NA1_1", 4, level, 30, units, {})

    members = [board(8, "X1") for _ in range(40)] + [board(9, "Y1") for _ in range(5)]

    assert level_ups(members, planted_static) == ()
