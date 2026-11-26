import dataclasses
import json
from datetime import UTC, datetime

import pytest
from conftest import A_CORE

from tft_assistant.build import build_site
from tft_assistant.snapshot import SCHEMA, build_snapshot
from tft_assistant.store import Selection

NOW = datetime(2026, 12, 3, 12, tzinfo=UTC)


def built(boards, static):
    return build_snapshot("Patch 19.1", Selection(19, 1100, since=NOW), boards, static, built_at=NOW, newest_match=NOW)


@pytest.fixture(scope="module")
def snapshot(planted_boards, planted_static):
    return built(planted_boards, planted_static)


def test_a_snapshot_states_its_selection_and_its_sample(snapshot):
    assert (snapshot["schema"], snapshot["label"], snapshot["boards"]) == (SCHEMA, "Patch 19.1", 200)
    assert snapshot["selection"] == {"set": 19, "since": NOW.isoformat(), "until": None, "platforms": []}
    assert snapshot["unclassified"] == pytest.approx(0.10)
    assert snapshot == json.loads(json.dumps(snapshot))


def test_a_comp_is_named_by_trait_and_carry_and_tiered_by_placement(snapshot):
    assert [(comp["name"], comp["tier"]) for comp in snapshot["comps"]] == [("Alpha A1", "S"), ("Beta B1", "S")]
    assert snapshot["comps"][0]["id"] != snapshot["comps"][1]["id"]


def test_every_unit_item_and_trait_a_comp_names_is_in_the_lookup_tables(snapshot):
    for comp in snapshot["comps"]:
        units = [*comp["core"], *comp["three_stars"], *(place["unit"] for place in comp["board"])]
        units += [unit for package in comp["packages"] for unit in package["units"]]
        units += [pick["holder"] for pick in comp["items"]]
        assert set(units) <= set(snapshot["units"])
        assert {pick["item"] for pick in comp["items"]} <= set(snapshot["items"])
    assert snapshot["units"]["A1"] == {"name": "A1", "cost": 2, "traits": ["T"], "icon": "https://icons.test/A1.png"}
    assert snapshot["traits"]["T"]["name"] == "Trait"


def test_a_comps_default_board_holds_its_core_and_commonest_flex_units_up_to_its_usual_level(snapshot):
    comp = snapshot["comps"][0]
    placed = [place["unit"] for place in comp["board"]]

    assert sorted(placed) == sorted([*A_CORE, "X1", "X2", "Y1"])
    assert comp["board_is_default"] is True
    assert len({(place["row"], place["column"]) for place in comp["board"]}) == 9


def test_comps_that_would_share_a_name_are_told_apart_by_a_core_unit(planted_boards, planted_static):
    same_names = dataclasses.replace(
        planted_static,
        traits=planted_static.traits | {"T_B": dataclasses.replace(planted_static.traits["T_B"], name="Alpha")},
        units=planted_static.units | {"B1": dataclasses.replace(planted_static.units["B1"], name="A1")},
    )

    names = [comp["name"] for comp in built(planted_boards, same_names)["comps"]]

    assert names == ["Alpha A1 · A2", "Alpha A1 · B2"]


def test_the_page_embeds_its_snapshots_as_json_that_reads_back_unchanged(snapshot, tmp_path):
    awkward = {**snapshot, "label": "a </script> in a label"}

    page = build_site([snapshot, awkward], tmp_path).read_text()

    embedded = page.split('<script id="snapshots" type="application/json">')[1].split("</script>")[0]
    assert json.loads(embedded) == [snapshot, awkward]
    assert "/*STYLE*/" not in page and "/*SCRIPT*/" not in page and "/*SNAPSHOTS*/" not in page
