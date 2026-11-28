from tft_assistant.descriptions import hashed, render, render_trait


def test_a_value_is_read_by_its_name_or_by_the_hash_of_its_name_and_may_be_a_share():
    values = {"Stacks": 7.0, hashed("Reduction"): 0.1}

    assert render("Gain @Stacks@ stacks and lose @Reduction*100@% Mana.", values) == "Gain 7 stacks and lose 10% Mana."
    assert hashed("JuggernautDurability") == "{6eab9c5e}"


def test_markup_becomes_lines_and_a_stat_picture_becomes_the_stat_unless_its_name_follows():
    template = "<tftbold>Gain 2 effects:</tftbold><li>@AD*100@% %i:scaleAD%%i:scaleAP%<br><br>%i:scaleHealth% +@HP@ Health {{TFT_Keyword_X}}"

    assert render(template, {"AD": 0.12, "HP": 150.0}) == "Gain 2 effects:\n12% Attack Damage and Ability Power\n+150 Health"


def test_a_line_that_names_a_value_the_data_lacks_is_left_out():
    assert render("Deal bonus damage.<br>Damage dealt: @TFTUnitProperty.item:Damage@", {}) == "Deal bonus damage."
    assert render(None, {}) == ""


def test_a_trait_has_an_opening_and_a_line_for_each_breakpoint_read_with_its_own_values():
    template = "Gain @Flat@ Armor.<br><row>(@MinUnits@) @Team*100@% %i:scaleDR%</row><br><row>(@MinUnits@) @Team*100@% %i:scaleDR%</row>"
    effects = [
        {"minUnits": 2, "variables": {"Flat": 5.0, "Team": 0.04}},
        {"minUnits": 4, "variables": {"Flat": 5.0, hashed("Team"): 0.06}},
        {"minUnits": 6, "variables": {}},
    ]

    assert render_trait(template, effects) == ("Gain 5 Armor.", ("(2) 4% Durability", "(4) 6% Durability", ""))
