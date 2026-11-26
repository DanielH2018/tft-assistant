import pytest

from tft_assistant.static_data import CACHE_DIR, StaticData, document
from tft_assistant.traits import count_traits

DOCUMENT = {
    "setData": [
        {
            "mutator": "TFTSet99",
            "traits": [
                {
                    "apiName": "T_Hunter",
                    "name": "Hunter",
                    "effects": [
                        {"minUnits": 4, "maxUnits": 25000, "style": 5},
                        {"minUnits": 2, "maxUnits": 3, "style": 1},
                    ],
                },
                {"apiName": "T_Primal", "name": "Primal", "effects": [{"minUnits": 2, "maxUnits": 25000, "style": 3}]},
            ],
            "champions": [
                {"apiName": "U_Sivir", "name": "Sivir", "cost": 4, "traits": ["Primal", "Hunter"], "stats": {"range": 4}},
                {"apiName": "U_Ashe", "name": "Ashe", "cost": 2, "traits": ["Hunter"], "stats": {"range": 4}},
                {"apiName": "U_Vi", "name": "Vi", "cost": 3, "traits": ["Primal"], "stats": {"range": 1}},
                {"apiName": "U_Dummy", "name": "Target Dummy", "cost": 8, "traits": [], "stats": {}},
            ],
            "items": ["I_EmblemHunter", "I_Sword", "I_Stone", "I_Blade", "I_Vow"],
        }
    ],
    "items": [
        {"apiName": "I_Vow", "name": "Vow", "composition": ["I_Vest", "I_Tear"]},
        {"apiName": "I_Stone", "name": "Stoneplate", "composition": ["I_Vest", "I_Sword"]},
        {"apiName": "I_Blade", "name": "Blade", "composition": ["I_Sword", "I_Sword"]},
        {"apiName": "I_EmblemHunter", "name": "Hunter Emblem", "composition": ["I_Pan", "I_Sword"]},
        {"apiName": "I_Sword", "name": "B.F. Sword", "composition": []},
        {"apiName": "I_OtherSet", "name": "Primal Emblem", "composition": []},
    ],
}

SET = DOCUMENT["setData"][0]
STATIC = StaticData.from_document(DOCUMENT, "TFTSet99")


def counted(units):
    return {count.trait.name: (count.units, count.tier, count.next_at) for count in count_traits(units, STATIC)}


def test_a_trait_reports_its_count_its_tier_and_the_count_of_the_next_breakpoint():
    assert counted([("U_Sivir", []), ("U_Ashe", []), ("U_Dummy", [])]) == {
        "Hunter": (2, 1, 4),
        "Primal": (1, 0, 2),
    }


def test_two_copies_of_a_unit_count_once():
    assert counted([("U_Ashe", []), ("U_Ashe", [])])["Hunter"] == (1, 0, 2)


def test_an_emblem_adds_its_trait_to_a_holder_that_lacks_it_and_not_to_one_that_has_it():
    with_emblems = counted([("U_Sivir", ["I_EmblemHunter"]), ("U_Vi", ["I_EmblemHunter", "I_Sword"])])

    assert with_emblems["Hunter"] == (2, 1, 4)
    assert with_emblems["Primal"] == (2, 1, None)


def test_a_unit_takes_its_team_planner_number_and_the_roster_keeps_the_sets_name():
    variant = {"apiName": "U_Sivir_Primal", "name": "Sivir (Primal)", "cost": 4, "traits": ["Primal"], "stats": {}}
    with_variant = {**DOCUMENT, "setData": [{**SET, "champions": [*SET["champions"], variant]}]}

    static = StaticData.from_document(with_variant, "TFTSet99", planner={"U_Sivir": 1015})

    assert (static.units["U_Sivir"].planner_code, static.units["U_Ashe"].planner_code) == (1015, None)
    assert static.units["U_Sivir_Primal"].planner_code == 1015
    assert static.mutator == "TFTSet99"


def test_an_item_is_an_artifact_when_its_api_name_starts_as_the_set_file_says():
    static = StaticData.from_document(DOCUMENT, "TFTSet99", artifact_prefix="I_St")

    assert static.items["I_Stone"].is_artifact
    assert not static.items["I_Sword"].is_artifact
    assert not STATIC.items["I_Stone"].is_artifact


def test_an_item_outside_the_set_is_not_in_the_roster():
    assert "I_OtherSet" not in STATIC.items
    assert STATIC.items["I_EmblemHunter"].emblem_of == "T_Hunter"


def test_an_item_is_defensive_when_its_recipe_has_a_defensive_component_and_no_offensive_one():
    static = StaticData.from_document(
        DOCUMENT, "TFTSet99", defensive_components=["I_Vest"], offensive_components=["I_Sword"]
    )

    assert static.items["I_Vow"].is_defensive
    assert not static.items["I_Stone"].is_defensive
    assert not static.items["I_Blade"].is_defensive
    assert not static.items["I_Sword"].is_defensive
    assert not STATIC.items["I_Vow"].is_defensive


def test_an_unknown_game_mode_names_the_ones_the_document_has():
    with pytest.raises(KeyError, match="TFTSet99"):
        StaticData.from_document(DOCUMENT, "TFTSet100")


@pytest.mark.skipif(
    not (CACHE_DIR / "cdragon-latest.json").exists(),
    reason="needs Community Dragon's document in the cache; any command that loads static data fetches it",
)
def test_every_set_in_the_real_document_loads_with_units_that_have_known_traits():
    source = document()
    main_modes = [entry["mutator"] for entry in source["setData"] if entry["mutator"] == f"TFTSet{entry['number']}"]

    assert len(main_modes) >= 5
    for mutator in main_modes:
        static = StaticData.from_document(source, mutator)
        playable = [unit for unit in static.units.values() if unit.traits]
        assert len(playable) >= 50, mutator
        assert all(trait in static.traits for unit in playable for trait in unit.traits), mutator
        assert any(item.emblem_of for item in static.items.values()), mutator
