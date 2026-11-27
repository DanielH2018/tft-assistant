import subprocess
import sys

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


def test_the_cli_loads_no_analysis_library_until_a_command_analyses():
    """`tft serve` runs in a small container, and numpy and scikit-learn cost it 100 MB."""
    loaded = subprocess.run(
        [sys.executable, "-c", "import sys, tft_assistant.cli; print(sorted({'numpy', 'sklearn'} & set(sys.modules)))"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert loaded.stdout.strip() == "[]"
