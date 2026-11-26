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


def test_a_comp_is_named_by_trait_and_carry_tiered_by_placement_and_carries_its_style(snapshot):
    named = [(comp["name"], comp["tier"], comp["style"]) for comp in snapshot["comps"]]

    assert named == [("Alpha A1", "S", "2-cost reroll"), ("Beta B1", "S", "Fast 9")]
    assert snapshot["comps"][0]["id"] != snapshot["comps"][1]["id"]


def test_every_unit_item_and_trait_a_comp_names_is_in_the_lookup_tables(snapshot):
    for comp in snapshot["comps"]:
        units = [*comp["core"], *comp["three_stars"], *comp["fielded"]]
        units += [unit for slot in comp["flex"] for package in slot for unit in package["units"]]
        units += [pick["holder"] for pick in comp["items"]]
        units += [shift["unit"] for up in comp["level_ups"] for shift in [*up["adds"], *up["drops"]]]
        assert set(units) <= set(snapshot["units"])
        assert {pick["item"] for pick in comp["items"]} <= set(snapshot["items"])
    assert snapshot["units"]["A1"] == {
        "name": "A1",
        "cost": 2,
        "traits": ["T"],
        "icon": "https://icons.test/A1.png",
        "planner_code": None,
        "row": 0,
    }
    assert snapshot["traits"]["T"] == {"name": "Trait", "icon": None, "breakpoints": [2, 4]}
    assert snapshot["items"]["Edge"] == {"name": "Edge", "icon": None, "recipe": ["Sword", "Glove"]}


def test_a_comp_is_fielded_as_its_core_and_commonest_flex_units_up_to_its_usual_level(snapshot):
    assert sorted(snapshot["comps"][0]["fielded"]) == sorted([*A_CORE, "X1", "X2"])


def names_when_both_comps_read_alpha_a1(boards, static, **b3):
    same_names = dataclasses.replace(
        static,
        traits=static.traits | {"T_B": dataclasses.replace(static.traits["T_B"], name="Alpha")},
        units=static.units
        | {"B1": dataclasses.replace(static.units["B1"], name="A1"), "B3": dataclasses.replace(static.units["B3"], **b3)},
    )
    return [comp["name"] for comp in built(boards, same_names)["comps"]]


def test_comps_that_would_share_a_name_are_told_apart_by_the_trait_their_carries_share(planted_boards, planted_static):
    assert names_when_both_comps_read_alpha_a1(planted_boards, planted_static) == ["Alpha A1", "Alpha Hunters"]


def test_comps_whose_carries_share_no_active_trait_are_told_apart_by_a_core_unit(planted_boards, planted_static):
    names = names_when_both_comps_read_alpha_a1(planted_boards, planted_static, traits=("T",))

    assert names == ["Alpha A1 · A2", "Alpha A1 · B2"]


def test_the_page_embeds_its_snapshots_as_json_that_reads_back_unchanged(snapshot, tmp_path):
    awkward = {**snapshot, "label": "a </script> in a label"}

    page = build_site([snapshot, awkward], tmp_path).read_text()

    embedded = page.split('<script id="snapshots" type="application/json">')[1].split("</script>")[0]
    assert json.loads(embedded) == [snapshot, awkward]
    assert "/*STYLE*/" not in page and "/*SCRIPT*/" not in page and "/*SNAPSHOTS*/" not in page
