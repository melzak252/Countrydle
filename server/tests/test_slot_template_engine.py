from slot_template_engine import mask_query


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




