from tft_assistant.positioning import COLUMNS, default_board, usual_row
from tft_assistant.static_data import StaticData, Unit


def unit(name, attack_range, role=None, cost=2):
    return Unit(name, name, cost, ("T",), attack_range, role)


UNITS = [
    unit("Tank", 1.0, cost=4),
    unit("Reach", 2.0),
    unit("Archer", 4.0),
    unit("Sniper", 6.0, cost=5),
    unit("RolelessTank", 0.0, "APTank"),
    unit("RolelessCaster", 0.0, "APCaster"),
    unit("Unknown", 0.0),
    *[unit(f"Melee{n}", 1.0) for n in range(8)],
]
STATIC = StaticData({u.api_name: u for u in UNITS}, {}, {})


def test_a_unit_takes_the_row_of_its_attack_range_and_of_its_role_where_range_is_missing():
    rows = {u.api_name: usual_row(u) for u in UNITS[:7]}

    assert rows == {
        "Tank": 0,
        "Reach": 1,
        "Archer": 3,
        "Sniper": 3,
        "RolelessTank": 0,
        "RolelessCaster": 3,
        "Unknown": 3,
    }


def test_the_costliest_front_unit_stands_central_and_the_carry_takes_a_back_corner():
    board = default_board(["Tank", "Melee0", "Archer", "Sniper", "Reach"], carries=["Archer"], static=STATIC)

    assert board == {"Tank": (0, 3), "Melee0": (0, 2), "Archer": (3, 0), "Sniper": (3, 1), "Reach": (1, 3)}


def test_a_row_with_more_units_than_columns_passes_the_extras_one_row_inward():
    melee = ["Tank", *[f"Melee{n}" for n in range(8)]]

    board = default_board(melee, carries=[], static=STATIC)

    assert sorted(row for row, _ in board.values()) == [0] * COLUMNS + [1, 1]
    assert len(set(board.values())) == len(melee)
