from tft_assistant.boards import Board, BoardUnit
from tft_assistant.item_groups import find_item_groups
from tft_assistant.static_data import Item, StaticData, Unit


def unit(name, cost):
    return Unit(name, name, cost, ("T",), 1.0, None)


def item(name, *, emblem_of=None, radiant_of=None, is_component=False):
    return Item(name, name, (), emblem_of, radiant_of, is_component)


STATIC = StaticData(
    units={u.api_name: u for u in [unit("Tank1", 1), unit("Tank4", 4), unit("Mage2", 2), unit("Mage5", 5), unit("Rare", 3)]},
    traits={},
    items={
        i.api_name: i
        for i in [
            item("Plate"),
            item("Warmog"),
            item("Visage"),
            item("Deathcap"),
            item("Gauntlet"),
            item("Staff"),
            item("RadiantDeathcap", radiant_of="Deathcap"),
            item("Emblem", emblem_of="T"),
            item("Belt", is_component=True),
        ]
    },
)


def board(*units):
    return Board("NA1_1", 4, 8, 30, tuple(BoardUnit(name, 2, tuple(items)) for name, items in units), {})


def groups_of(boards, **options):
    return [(group.units, set(group.items)) for group in find_item_groups(boards, STATIC, min_builds=3, **options)]


TANK, MAGE = ["Plate", "Warmog", "Visage"], ["Deathcap", "Gauntlet", "Staff"]


def test_units_that_build_alike_share_a_group_listed_cheapest_first():
    boards = [board(("Tank4", TANK), ("Tank1", TANK[:2]), ("Mage5", MAGE), ("Mage2", MAGE[1:])) for _ in range(3)]

    assert groups_of(boards) == [
        (("Mage2", "Mage5"), set(MAGE)),
        (("Tank1", "Tank4"), set(TANK)),
    ]


def test_a_radiant_item_counts_as_its_base_and_emblems_and_components_do_not_count():
    boards = [
        board(("Tank4", TANK), ("Tank1", TANK), ("Mage5", MAGE), ("Mage2", ["RadiantDeathcap", "Gauntlet", "Emblem"]))
        for _ in range(3)
    ] + [board(("Tank1", ["Plate", "Belt", "Emblem"]))]

    assert groups_of(boards) == [
        (("Mage2", "Mage5"), set(MAGE)),
        (("Tank1", "Tank4"), set(TANK)),
    ]


def test_a_unit_with_too_few_builds_joins_no_group():
    boards = [board(("Tank4", TANK), ("Tank1", TANK), ("Mage5", MAGE), ("Mage2", MAGE)) for _ in range(3)]
    boards.append(board(("Rare", MAGE)))

    assert all("Rare" not in units for units, _ in groups_of(boards))
