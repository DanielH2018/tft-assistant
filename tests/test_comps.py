import dataclasses

import pytest
from conftest import A_CORE, B_CORE

from tft_assistant.boards import Board, BoardUnit
from tft_assistant.categories import categories_of
from tft_assistant.comp_detail import (
    CARRY,
    TANK,
    BuildItem,
    CompTrait,
    ItemPick,
    KeyUnit,
    SpareComponent,
    SpecialItem,
    Swap,
    build_notes,
    level_ups,
    main_trait,
    special_items,
    tempo,
)
from tft_assistant.comps import FlexPackage, FlexSlot, find_comps
from tft_assistant.item_groups import ItemGroup
from tft_assistant.snapshot import tank_groups_last
from tft_assistant.static_data import Item


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
    assert (comp_a.win_rate, comp_b.win_rate) == (0.1, 0.0)
    assert (comp_a.carries, comp_a.main_trait) == (("A1",), "T_A")


def test_flex_units_played_together_are_a_package_and_packages_never_played_together_share_a_slot(report):
    comp_a, comp_b = report.comps

    assert comp_a.flex == (FlexSlot((FlexPackage(("X1", "X2"), 0.6, 2.0, 1.0, 10 / 60), FlexPackage(("Y1", "Y2"), 0.4, 6.0, 0.0, 0.0))),)
    assert comp_b.flex == (FlexSlot((FlexPackage(("Z1",), 0.5, 4.0, 1.0, 0.0),)), FlexSlot((FlexPackage(("Z2",), 0.5, 4.0, 1.0, 0.0),)))


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


def test_a_comps_style_is_the_cost_it_rerolls_for_or_else_the_level_that_finds_its_carry(report, planted_static):
    comp_a, comp_b = report.comps
    costs = {"A1": 1, "A3": 4, "A4": 5}
    static = dataclasses.replace(
        planted_static,
        units=planted_static.units
        | {unit: dataclasses.replace(planted_static.units[unit], cost=cost) for unit, cost in costs.items()},
    )

    def style(carry, *, level, three_star=()):
        units = tuple(BoardUnit(unit, 3 if unit in three_star else 2, ()) for unit in ["A1", "A2", "A3", "A4", "Dummy"])
        found = tempo([Board("NA1_1", 4, level, 30, units, {}) for _ in range(10)], carry, static)
        return found.style, found.roll_level

    assert (comp_a.tempo.style, comp_a.tempo.roll_level) == ("2-cost reroll", 6)
    assert (comp_b.tempo.style, comp_b.tempo.roll_level) == ("Fast 9", 9)
    assert style("A1", level=8, three_star=("A1", "A2")) == ("1-cost reroll", 5)
    assert style("A3", level=9) == ("Level 8", 8)
    assert style("A4", level=8, three_star=("Dummy",)) == ("Fast 9", 9)
    assert style("A2", level=7) == ("Level 7", 7)


def test_a_comp_is_named_for_its_largest_vertical_and_otherwise_for_a_trait_of_its_carry(planted_static):
    small_but_full, vertical = CompTrait("T_B", 2, 2, 2, 1.0), CompTrait("T_A", 7, 3, 5, 1.0)
    larger, carrys_own, one_tier = CompTrait("T_A", 3, 1, 4, 1.0), CompTrait("T", 2, 1, 3, 1.0), CompTrait("T_U", 3, 1, 1, 1.0)

    assert main_trait([small_but_full, vertical], ("A1",), planted_static) == "T_A"
    assert main_trait([one_tier, larger, carrys_own], ("A1",), planted_static) == "T"
    assert main_trait([one_tier, larger], ("A1",), planted_static) == "T_A"
    assert main_trait([one_tier], ("A1",), planted_static) is None


def test_the_carry_trait_is_an_active_trait_the_carry_and_the_second_carry_both_have(report):
    comp_a, comp_b = report.comps

    assert (comp_a.carries, comp_a.carry_trait) == (("A1",), None)
    assert (comp_b.carries, comp_b.carry_trait) == (("B1", "B3"), "T_C")


def test_item_priority_orders_item_and_holder_pairs_and_compares_placement_with_and_without(report):
    assert report.comps[0].item_priority == (
        ItemPick("Edge", "A1", share=1.0, avg_with=pytest.approx(3.6), avg_without=None),
        ItemPick("Whisper", "A1", share=0.6, avg_with=2.0, avg_without=6.0),
        ItemPick("Plate", "A1", share=0.4, avg_with=6.0, avg_without=2.0),
    )


def test_components_to_take_come_from_the_recipes_of_the_item_priority(report):
    assert report.comps[0].take == ("Glove", "Sword", "Bow")


def test_the_two_components_a_comp_uses_least_list_the_items_its_boards_build_with_them(report):
    comp_a, comp_b = report.comps

    assert comp_b.spare == (
        SpareComponent("Belt", share=pytest.approx(1 / 12), uses=("Cape",)),
        SpareComponent("Bow", share=pytest.approx(2 / 12), uses=("Whisper",)),
    )
    assert [(spare.component, spare.share) for spare in comp_a.spare] == [("Bow", 0.1875), ("Sword", 0.3125)]


def test_an_artifact_lists_its_holder_the_items_beside_it_and_the_units_its_boards_add_and_drop(planted_static):
    relic = Item("Relic", "Relic", (), None, None, False, is_artifact=True)
    static = dataclasses.replace(planted_static, items=planted_static.items | {"Relic": relic})

    def board(flex, held, placement):
        units = (BoardUnit("A1", 2, tuple(held)), BoardUnit("A2", 2, ()), BoardUnit(flex, 2, ()))
        return Board("NA1_1", placement, 8, 30, units, {})

    with_relic = [board("X1", ["Relic", "Edge"], 2) for _ in range(30)]
    without = [board("Y1", ["Edge", "Whisper"], 5) for _ in range(70)]

    assert special_items(with_relic + without, static) == (
        SpecialItem(
            "Relic",
            share=0.3,
            avg_placement=2.0,
            holder="A1",
            holder_share=1.0,
            beside=("Edge",),
            adds=(Swap("X1", 1.0, 0.0),),
            drops=(Swap("Y1", 0.0, 1.0),),
        ),
    )
    assert special_items(with_relic[:19] + without, static) == ()


def test_a_level_above_the_usual_one_lists_the_units_that_come_in_and_the_units_that_go_out(report):
    comp_a, comp_b = report.comps
    (up,) = comp_a.level_ups

    assert (up.level, up.share, up.avg_placement) == (9, 0.4, 6.0)
    assert [(shift.unit, shift.share, shift.share_below) for shift in up.adds] == [("Y1", 1.0, 0.0), ("Y2", 1.0, 0.0)]
    assert [(shift.unit, shift.share, shift.share_below) for shift in up.drops] == [("X1", 0.0, 1.0), ("X2", 0.0, 1.0)]
    assert comp_b.level_ups == ()


def test_key_units_are_the_carry_the_second_carry_and_the_tank_whose_build_is_mostly_defensive(report):
    comp_a, comp_b = report.comps

    assert [(key.unit, key.role) for key in comp_b.key_units] == [("B1", "carry"), ("B3", "2nd carry"), ("B2", "tank")]
    assert comp_b.carries == ("B1", "B3")
    assert [(key.unit, key.role) for key in comp_a.key_units] == [("A1", "carry")]


def unit_builds(*builds):
    """Boards on which U holds the given items, as (items, placement, how many boards)."""
    return [
        Board("NA1_1", placement, 9, 30, (BoardUnit("U", 2, tuple(items)),), {})
        for items, placement, count in builds
        for _ in range(count)
    ]


def test_an_item_is_critical_when_most_builds_have_it_or_a_common_item_is_clearly_missed(planted_static):
    members = unit_builds(
        (["Edge", "Plate"], 3, 30),
        (["Edge", "Whisper"], 3, 30),
        (["Stone", "Cape"], 6, 20),
    )

    notes = {note.item: note for note in build_notes(members, "U", planted_static)}

    assert (notes["Edge"].share, notes["Edge"].critical) == (0.75, True)
    assert (notes["Plate"].share, notes["Plate"].critical) == (0.375, False)
    assert (notes["Stone"].avg_with, notes["Stone"].avg_without, notes["Stone"].critical) == (6.0, 3.0, False)
    assert notes["Whisper"].critical is False

    missed = unit_builds((["Edge", "Plate"], 2, 40), (["Whisper", "Plate"], 6, 30), (["Whisper", "Stone"], 6, 30))
    edge = next(note for note in build_notes(missed, "U", planted_static) if note.item == "Edge")
    assert (edge.share, edge.avg_without, edge.critical) == (0.4, 6.0, True)


def test_an_item_needs_a_partner_when_it_places_better_beside_it_than_the_partner_explains_alone(planted_static):
    members = unit_builds(
        (["Edge", "Whisper"], 2, 30),
        (["Edge", "Plate"], 6, 30),
        (["Whisper", "Plate"], 4, 30),
        (["Plate", "Stone"], 4, 30),
    )

    notes = {note.item: note for note in build_notes(members, "U", planted_static)}

    assert [(pair.partner, pair.avg_together, pair.avg_apart) for pair in notes["Edge"].needs] == [("Whisper", 2.0, 6.0)]
    assert [pair.partner for pair in notes["Whisper"].needs] == ["Edge"]
    assert notes["Plate"].needs == () and notes["Stone"].needs == ()


def test_only_builds_of_the_units_usual_size_are_compared(planted_static):
    members = unit_builds((["Edge", "Whisper", "Plate"], 2, 30), (["Edge", "Whisper"], 8, 10))

    notes = {note.item: note for note in build_notes(members, "U", planted_static)}

    assert (notes["Plate"].share, notes["Edge"].avg_with) == (1.0, 2.0)


def test_a_comparison_with_too_few_builds_on_one_side_yields_no_note(planted_static):
    members = unit_builds((["Edge", "Whisper"], 2, 30), (["Edge", "Plate"], 6, 5), (["Whisper", "Plate"], 4, 30))

    notes = {note.item: note for note in build_notes(members, "U", planted_static)}

    assert notes["Edge"].needs == ()
    assert build_notes(unit_builds((["Edge"], 2, 30)), "U", planted_static) == ()


def test_a_level_that_too_few_boards_reach_is_not_reported(planted_static):
    def board(level, extra):
        units = tuple(BoardUnit(unit, 2, ()) for unit in [*A_CORE, extra])
        return Board("NA1_1", 4, level, 30, units, {})

    members = [board(8, "X1") for _ in range(40)] + [board(9, "Y1") for _ in range(5)]

    assert level_ups(members, planted_static) == ()


def test_a_comp_is_in_the_categories_of_its_tempo_its_critical_item_and_its_vertical(report):
    reroll, fast_nine = report.comps

    assert categories_of(reroll) == ("reroll", "items", "trait:T_A")
    assert categories_of(fast_nine) == ("fast-9", "items", "trait:T_B")


def test_a_comp_just_short_of_every_rule_is_in_no_category(report):
    comp = report.comps[0]
    carry = next(key for key in comp.key_units if key.role == CARRY)
    optional = tuple(dataclasses.replace(note, critical=False) for note in carry.build)
    plain = dataclasses.replace(
        comp,
        tempo=dataclasses.replace(comp.tempo, three_stars=(), roll_level=8),
        key_units=(
            dataclasses.replace(carry, build=optional),
            KeyUnit("A1", TANK, (BuildItem("Tank", 0.9, 3.0, 5.0, critical=True, needs=()),)),
        ),
        traits=(CompTrait("T_A", 3, 1, 3, 0.9), CompTrait("T_Unique", 4, 1, 1, 0.9)),
    )

    assert categories_of(plain) == ()
    vertical = dataclasses.replace(plain, traits=(CompTrait("T_A", 4, 1, 3, 0.9),))
    assert categories_of(vertical) == ("trait:T_A",)


def test_the_groups_tanks_build_in_come_after_the_groups_carries_build_in(report):
    comp = dataclasses.replace(report.comps[0], key_units=(KeyUnit("C1", CARRY), KeyUnit("T1", TANK), KeyUnit("B1", TANK)))
    swing = dataclasses.replace(report.comps[1], key_units=(KeyUnit("B1", CARRY),))
    for_tanks, for_carries = ItemGroup(("Plate",), ("T1", "B1")), ItemGroup(("Edge",), ("C1", "B1"))
    for_neither = ItemGroup(("Odd",), ("Z9",))

    ordered = tank_groups_last([for_tanks, for_carries, for_neither], [comp, swing])

    assert ordered == [for_carries, for_neither, for_tanks]
