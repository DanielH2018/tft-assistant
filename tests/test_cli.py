from tft_assistant.cli import describe_match


def test_describe_match_reports_mechanic_fields_and_no_player_identity():
    participant = {
        "puuid": "secret-puuid",
        "riotIdGameName": "SomePlayer",
        "placement": 1,
        "level": 9,
        "last_round": 38,
        "gold_left": 3,
        "augments": ["TFT_Augment_A"],
        "units": [{"character_id": "TFT_Unit", "tier": 2, "itemNames": ["TFT_Item_A"]}],
        "traits": [{"name": "TFT_Trait", "num_units": 4, "tier_current": 2}],
    }
    match = {
        "metadata": {"match_id": "NA1_1", "participants": ["secret-puuid"]},
        "info": {"game_version": "Version 1.2", "encounterId": "E1", "participants": [participant]},
    }

    report = "\n".join(describe_match(match))

    assert "info.encounterId" in report and "info.participants[].augments" in report
    assert "secret-puuid" not in report and "SomePlayer" not in report
