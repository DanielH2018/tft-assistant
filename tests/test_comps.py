import pytest
from conftest import A_CORE, B_CORE

from tft_assistant.comp_detail import CompTrait, ItemPick
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
