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


def board(*units, placement=4):
    return Board("NA1_1", placement, 8, 30, tuple(BoardUnit(name, 2, tuple(items)) for name, items in units), {})


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


def test_a_unit_holding_thiefs_gloves_counts_toward_no_group():
    gloves = ["TFT_Item_ThiefsGloves", "Deathcap", "Gauntlet"]
    boards = [board(("Tank4", TANK), ("Tank1", TANK), ("Mage5", MAGE), ("Mage2", MAGE)) for _ in range(3)]
    boards += [board(("Tank1", gloves), ("Rare", gloves)) for _ in range(5)]

    assert groups_of(boards) == [
        (("Mage2", "Mage5"), set(MAGE)),
        (("Tank1", "Tank4"), set(TANK)),
    ]


def test_a_unit_with_too_few_builds_joins_no_group():
    boards = [board(("Tank4", TANK), ("Tank1", TANK), ("Mage5", MAGE), ("Mage2", MAGE)) for _ in range(3)]
    boards.append(board(("Rare", MAGE)))

    assert [units for units, _ in groups_of(boards)] == [("Mage2", "Mage5"), ("Tank1", "Tank4")]


def test_a_group_knows_how_each_unit_places_overall_and_with_each_item():
    mage = [("Mage5", MAGE), ("Mage2", MAGE[1:])]
    boards = [board(*mage, ("Tank4", TANK), ("Tank1", TANK[:2]), placement=2) for _ in range(3)]
    boards += [board(*mage, ("Tank4", TANK[:2]), ("Tank1", TANK[:2]), placement=6)]

    tanks = next(group for group in find_item_groups(boards, STATIC, min_builds=3) if "Tank4" in group.units)

    assert (tanks.held["Tank4"].boards, tanks.held["Tank4"].avg_placement) == (4, 3.0)
    assert tanks.held["Tank4"].items["Visage"] == (0.75, 2.0)
    assert tanks.held["Tank4"].items["Plate"] == (1.0, 3.0)


def test_an_emblem_or_an_artifact_is_listed_at_a_hundredth_of_a_units_boards_and_ten_of_them():
    static = StaticData(
        units=STATIC.units,
        traits={},
        items=STATIC.items | {"Relic": Item("Relic", "Relic", (), None, None, False, is_artifact=True)},
    )
    plain = [board(("Mage5", MAGE), ("Mage2", MAGE), placement=5) for _ in range(180)]
    with_emblem = [board(("Mage5", [*MAGE[:2], "Emblem"]), ("Mage2", MAGE), placement=2) for _ in range(12)]
    with_relic = [board(("Mage5", [*MAGE[:2], "Relic"]), ("Mage2", [*MAGE[:2], "Relic"]), placement=3) for _ in range(9)]

    (group,) = find_item_groups([*plain, *with_emblem, *with_relic, *[board(("Mage2", ["Staff", "Deathcap"])) for _ in range(9)]], static)

    held = group.held["Mage5"].items
    assert held["Emblem"] == (12 / 201, 2.0)
    assert "Relic" not in held
    assert "Emblem" not in group.items
    assert {"Relic", "Emblem"}.isdisjoint(group.held["Mage2"].items)


def test_a_unit_that_builds_two_ways_is_also_in_the_group_of_its_second_build():
    flex = [board(("Rare", TANK)) for _ in range(6)] + [board(("Rare", MAGE), placement=2) for _ in range(4)]
    boards = [board(("Tank4", TANK), ("Tank1", TANK), ("Mage5", MAGE), ("Mage2", MAGE)) for _ in range(5)] + flex

    tanks, mages = sorted(find_item_groups(boards, STATIC, min_builds=3), key=lambda group: "Deathcap" in group.items)

    assert (tanks.units, tanks.also) == (("Tank1", "Rare", "Tank4"), ())
    assert (mages.units, mages.also) == (("Mage2", "Mage5"), ("Rare",))
    assert (tanks.held["Rare"].boards, mages.held["Rare"].boards) == (10, 4)
    assert mages.held["Rare"].avg_placement == 2.0 and set(mages.held["Rare"].items) == set(MAGE)


def test_a_second_build_on_too_few_boards_joins_no_second_group():
    flex = [board(("Rare", TANK)) for _ in range(18)] + [board(("Rare", MAGE)) for _ in range(3)]
    boards = [board(("Tank4", TANK), ("Tank1", TANK), ("Mage5", MAGE), ("Mage2", MAGE)) for _ in range(5)] + flex

    assert [group.also for group in find_item_groups(boards, STATIC, min_builds=3)] == [(), ()]
