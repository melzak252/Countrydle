from slot_template_engine import mask_query, match_slot_template


def test_slot_masking_entities_and_numbers():
    """Verify that entity names, numbers, operators, and water bodies are properly masked."""
    # Country & Borders
    skel, slots = mask_query("Does it border Germany?", "countrydle")
    assert skel == "does it border [COUNTRY]"
    assert slots["COUNTRY"] == "Germany"

    skel_pl, slots_pl = mask_query("Czy graniczy z Niemcami?", "countrydle")
    assert skel_pl == "czy graniczy z [COUNTRY]"
    assert slots_pl["COUNTRY"] == "Germany"

    # Number of neighbors & comparisons
    skel_cnt, slots_cnt = mask_query("Does it border 7 countries?", "countrydle")
    assert skel_cnt == "does it border [NUMBER] countries"
    assert slots_cnt["NUMBER"] == 7

    skel_comp, slots_comp = mask_query("Does it border more than 5 countries?", "countrydle")
    assert skel_comp == "does it border [COMP_OP] [NUMBER] countries"
    assert slots_comp["COMP_OP"] == "greater_than"
    assert slots_comp["NUMBER"] == 5

    skel_pl_comp, slots_pl_comp = mask_query("Czy ma więcej niż 5 sąsiadów?", "countrydle")
    assert skel_pl_comp == "czy ma [COMP_OP] [NUMBER] sasiadow"
    assert slots_pl_comp["COMP_OP"] == "greater_than"
    assert slots_pl_comp["NUMBER"] == 5


def test_no_cross_mode_fallback():
    # Countrydle query asking for Atlantic Ocean must return target_country, never target_state
    res = match_slot_template("Czy ma dostęp do Oceanu Atlantyckiego?", "countrydle")
    assert res is not None
    ast, _ = res
    assert ast[0]["left"]["entity"] == "target_country"
    assert ast[0]["right"]["value"] == "Atlantic Ocean"

    # Powiatdle-only question asked in countrydle must NOT match
    assert match_slot_template("Czy to miasto na prawach powiatu?", "countrydle") is None
    res_powiat = match_slot_template("Czy to miasto na prawach powiatu?", "powiatdle")
    assert res_powiat is not None
    ast_powiat, _ = res_powiat
    assert ast_powiat["left"]["entity"] == "target_powiat"


def test_country_landlocked_marine_access():
    res = match_slot_template("Czy jest śródlądowe?", "countrydle")
    assert res is not None
    ast, _ = res
    assert ast[0]["left"]["relation"] == "marine_access"


def test_expanded_polish_us_states():
    res_tx = match_slot_template("Czy graniczy z Teksasem?", "usstatedle")
    assert res_tx is not None
    ast_tx, _ = res_tx
    assert ast_tx["right"]["value"] == "Texas"

    res_ca = match_slot_template("Czy graniczy z Kalifornią?", "usstatedle")
    assert res_ca is not None
    ast_ca, _ = res_ca
    assert ast_ca["right"]["value"] == "California"
