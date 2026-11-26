from tft_assistant.positioning import usual_row
from tft_assistant.static_data import Unit


def unit(name, attack_range, role=None):
    return Unit(name, name, 2, ("T",), attack_range, role)


UNITS = [
    unit("Tank", 1.0),
    unit("Reach", 2.0),
    unit("Archer", 4.0),
    unit("Sniper", 6.0),
    unit("RolelessTank", 0.0, "APTank"),
    unit("RolelessCaster", 0.0, "APCaster"),
    unit("Unknown", 0.0),
]


def test_a_unit_takes_the_row_of_its_attack_range_and_of_its_role_where_range_is_missing():
    rows = {u.api_name: usual_row(u) for u in UNITS}

    assert rows == {
        "Tank": 0,
        "Reach": 1,
        "Archer": 3,
        "Sniper": 3,
        "RolelessTank": 0,
        "RolelessCaster": 3,
        "Unknown": 3,
    }
