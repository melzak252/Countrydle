import time
import pytest
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


def test_slot_masking_us_states_and_waters():
    """Verify US state entities and water bodies (including typos) mask properly."""
    # Water body with typo
    skel_water, slots_water = mask_query("Does it have access to Antlantic Ocean?", "usstatedle")
    assert skel_water == "does it have access to [WATER_BODY]"
    assert slots_water["WATER_BODY"] == "Atlantic Ocean"

    # State border count
    skel_st, slots_st = mask_query("Does it border 8 states?", "usstatedle")
    assert skel_st == "does it border [NUMBER] states"
    assert slots_st["NUMBER"] == 8

    # Voivodeship count
    skel_voj, slots_voj = mask_query("Czy graniczy z 6 województwami?", "wojewodztwodle")
    assert skel_voj == "czy graniczy z [NUMBER] wojewodztwami"
    assert slots_voj["NUMBER"] == 6


def test_match_slot_template_fast_execution():
    """Verify O(1) hash lookup matches templates in sub-millisecond time."""
    test_queries = [
        ("countrydle", "Does it have 7 neighbors?"),
        ("countrydle", "Does it border more than 5 countries?"),
        ("countrydle", "Czy ma 7 sąsiadów?"),
        ("countrydle", "Is it landlocked?"),
        ("countrydle", "Is it an island?"),
        ("usstatedle", "Does it border 8 states?"),
        ("usstatedle", "Does it border more than 4 states?"),
        ("usstatedle", "Does it have access to Antlantic Ocean?"),
        ("wojewodztwodle", "Czy graniczy z 6 województwami?"),
        ("wojewodztwodle", "Czy ma więcej niż 4 sąsiadów?"),
        ("powiatdle", "Czy graniczy z 5 powiatami?"),
        ("powiatdle", "Czy to miasto na prawach powiatu?"),
    ]

    for mode, q in test_queries:
        t0 = time.perf_counter()
        res = match_slot_template(q, mode)
        duration_ms = (time.perf_counter() - t0) * 1000

        assert res is not None, f"Expected template match for {q!r} in {mode}"
        assert duration_ms < 5.0, f"Template match took {duration_ms:.2f}ms (> 5ms) for {q!r}"
        ast, improved = res
        assert ast is not None
        assert improved is not None
