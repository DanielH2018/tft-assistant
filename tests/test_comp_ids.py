from tft_assistant.comp_ids import CompIds


def test_a_comp_keeps_its_id_when_one_unit_of_its_core_changes(tmp_path):
    ids = CompIds(tmp_path / "comp-ids.json")
    (first,) = ids.assign(19, [("A1", "A2", "A3", "A4", "A5")])

    (later,) = CompIds(tmp_path / "comp-ids.json").assign(19, [("A1", "A2", "A3", "A4", "A6")])

    assert later == first


def test_a_core_that_shares_too_little_with_any_remembered_core_is_another_comp(tmp_path):
    ids = CompIds(tmp_path / "comp-ids.json")
    (first,) = ids.assign(19, [("A1", "A2", "A3", "A4", "A5")])

    (two_swapped,) = ids.assign(19, [("A1", "A2", "A3", "A6", "A7")])
    (other_set,) = ids.assign(20, [("A1", "A2", "A3", "A4", "A5")])

    assert two_swapped != first
    assert other_set == first, "a set remembers its own cores, so the same core mints the same id there"


def test_two_comps_of_one_analysis_never_take_one_id(tmp_path):
    ids = CompIds(tmp_path / "comp-ids.json")
    (remembered,) = ids.assign(19, [("A1", "A2", "A3", "A4", "A5")])

    exact, variant = ids.assign(19, [("A1", "A2", "A3", "A4", "A5"), ("A1", "A2", "A3", "A4", "A6")])

    assert exact == remembered
    assert variant != remembered


def test_a_comp_that_drops_out_of_one_analysis_has_its_id_when_it_returns(tmp_path):
    ids = CompIds(tmp_path / "comp-ids.json")
    (first,) = ids.assign(19, [("A1", "A2", "A3", "A4", "A5")])
    ids.assign(19, [("B1", "B2", "B3", "B4", "B5")])

    (returned,) = ids.assign(19, [("A1", "A2", "A3", "A4", "A5")])

    assert returned == first
