from tft_assistant.boards import RiotTrait, boards


def test_boards_reads_each_participants_units_and_riots_trait_counts():
    match = {
        "metadata": {"match_id": "NA1_1"},
        "info": {
            "participants": [
                {
                    "placement": 2,
                    "level": 9,
                    "last_round": 34,
                    "units": [{"character_id": "U_Sivir", "tier": 2, "itemNames": ["I_Sword"]}],
                    "traits": [{"name": "T_Hunter", "num_units": 1, "tier_current": 0, "tier_total": 2}],
                }
            ]
        },
    }

    (board,) = boards(match)

    assert (board.placement, board.level, board.last_round) == (2, 9, 34)
    assert (board.units[0].character_id, board.units[0].stars, board.units[0].items) == ("U_Sivir", 2, ("I_Sword",))
    assert board.riot_traits == {"T_Hunter": RiotTrait(units=1, tier=0, tiers=2)}
