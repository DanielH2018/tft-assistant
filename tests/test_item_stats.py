import pytest

from tft_assistant.boards import Board, BoardUnit
from tft_assistant.item_stats import find_item_stats, kind_of
from tft_assistant.static_data import Item, StaticData

ITEMS = {
    "Edge": Item("Edge", "Edge", ("Sword", "Glove"), None, None, False),
    "Sword": Item("Sword", "Sword", (), None, None, True),
    "Crown": Item("Crown", "Crown", ("Spatula", "Sword"), "T", None, False),
    "Gift": Item("Gift", "Gift", (), "T", None, False),
    "Bright": Item("Bright", "Bright", (), None, "Edge", False),
    "Relic": Item("Relic", "Relic", (), None, None, False, is_artifact=True),
    "Aid": Item("Aid", "Aid", (), None, None, False),
}
STATIC = StaticData(units={}, traits={}, items=ITEMS)


def board(placement, *held):
    return Board("m", placement, 8, 30, tuple(BoardUnit("U", 2, tuple(items)) for items in held), {})


@pytest.mark.parametrize(
    ("item", "kind"),
    [("Edge", "craftable"), ("Sword", "component"), ("Crown", "emblem"), ("Gift", "emblem"), ("Bright", "radiant"), ("Relic", "artifact"), ("Aid", "other")],
)
def test_an_item_has_one_kind_and_an_emblem_with_a_recipe_is_still_an_emblem(item, kind):
    assert kind_of(ITEMS[item]) == kind


def test_an_items_figures_are_over_the_boards_that_hold_it_each_counted_once():
    boards = [board(1, ["Edge", "Edge"], ["Edge"]) for _ in range(20)] + [board(5, ["Edge"]) for _ in range(60)]
    boards += [board(8, ["Crown"]) for _ in range(60)]

    edge, crown = find_item_stats(boards, STATIC)

    assert (edge.item, edge.kind, edge.has_recipe, edge.boards) == ("Edge", "craftable", True, 80)
    assert (edge.share, edge.avg_placement, edge.top4, edge.win_rate) == (80 / 140, 4.0, 0.25, 0.25)
    assert (crown.item, crown.kind, crown.has_recipe, crown.avg_placement) == ("Crown", "emblem", True, 8.0)


def test_an_item_on_few_boards_or_unknown_to_the_set_has_no_row():
    boards = [board(1, ["Edge", "Gift"]) for _ in range(49)] + [board(2, ["Edge", "From another set"]) for _ in range(30)]

    assert [stat.item for stat in find_item_stats(boards, STATIC)] == ["Edge"]
