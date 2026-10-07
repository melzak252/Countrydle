import time
import pytest

from generic_template_compiler import (
    compile_generic_template_plan,
    check_generic_open_ended_question,
)
from powiatdle.utils import LOCAL_CONFIG as POW_CONFIG
from wojewodztwodle.utils import LOCAL_CONFIG as WOJ_CONFIG
from us_statedle.utils import LOCAL_CONFIG as US_CONFIG
from local_kb_question import analyze_question


def test_powiatdle_templates_match_and_execute_fast():
    cases = [
        ("czy jest to miasto na prawach powiatu?", "is_city_county", 1),
        ("czy to powiat ziemski", "is_city_county", 0),
        ("mazowieckie?", "voivodeship", "Mazowieckie"),
        ("wielkopolskie", "voivodeship", "Wielkopolskie"),
        ("czy graniczy z pomorskim?", "borders_voivodeship", "Pomorskie"),
        ("czy ten powiat ma dostęp do morza?", "water_access", None),
        ("czy przez powiat płynie Wisła?", "major_rivers", "Wisła"),
        ("czy powiat graniczy z Niemcami?", "borders_country", "Niemcy"),
        ("czy tablice mają 2 litery?", "registration_plates", 2),
        ("czy tablice mają 3 litery?", "registration_plates", 3),
    ]

    for question, expected_relation, expected_value in cases:
        t0 = time.perf_counter()
        res = compile_generic_template_plan(question, "powiatdle")
        duration_ms = (time.perf_counter() - t0) * 1000

        assert res is not None, f"Expected template match for {question!r}"
        assert duration_ms < 5.0, f"Template match took {duration_ms:.2f}ms (> 5ms) for {question!r}"

        ast, improved = res
        op = ast.get("operator")
        if expected_relation == "water_access":
            assert op == "exists"
            assert ast["left"]["relation"] == "water_access"
        elif expected_relation == "is_city_county":
            assert op == "equals"
            assert ast["right"]["value"] == expected_value
        elif expected_relation == "registration_plates":
            assert op == "char_count_equals"
            assert ast["right"]["value"] == expected_value
        elif expected_relation == "borders_country":
            assert op == "contains_exact"
            assert ast["right"]["value"] == expected_value
        elif expected_relation in ("voivodeship", "borders_voivodeship"):
            assert ast["right"]["value"] == expected_value


def test_wojewodztwodle_templates_match_and_execute_fast():
    cases = [
        ("czy to województwo graniczy z Niemcami?", "borders_country", "Niemcy"),
        ("czy graniczy z czechami", "borders_country", "Czechy"),
        ("czy to województwo ma dostęp do morza?", "is_coastal", True),
        ("czy graniczy z województwem wielkopolskim", "borders_voivodeship", "Wielkopolskie"),
        ("czy płynie przez nie Odra?", "major_rivers", "Odra"),
    ]

    for question, expected_relation, expected_value in cases:
        t0 = time.perf_counter()
        res = compile_generic_template_plan(question, "wojewodztwodle")
        duration_ms = (time.perf_counter() - t0) * 1000

        assert res is not None, f"Expected template match for {question!r}"
        assert duration_ms < 5.0, f"Template match took {duration_ms:.2f}ms (> 5ms) for {question!r}"

        ast, improved = res
        assert ast.get("operator") in ("equals", "contains_exact", "contains_text")




def test_open_ended_rejection():
    assert check_generic_open_ended_question("jaka jest stolica?") is not None
    assert check_generic_open_ended_question("what is the capital?") is not None
    assert check_generic_open_ended_question("jaki to powiat?") is not None
    assert check_generic_open_ended_question("czy jest to miasto na prawach powiatu?") is None


def test_analyze_question_generates_valid_plan():
    plan = analyze_question("czy jest to miasto na prawach powiatu?", POW_CONFIG, use_cache=True)
    assert plan.valid is True
    assert plan.supported is True
    assert plan.plan == {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": True}}

def test_washington_atlantic_access_is_false():
    """Verify Washington has Pacific access but NOT Atlantic Ocean access (even with 'Antlantic' typo)."""
    from local_kb_question import execute_plan

    # 1. Antlantic typo
    plan_typo = analyze_question("Does it have access to Antlantic Ocean?", US_CONFIG, use_cache=False)
    assert plan_typo.valid is True
    ans_wa_typo = execute_plan(US_CONFIG, "Washington", plan_typo)
    assert ans_wa_typo.answer is False
    assert "Atlantic Ocean" in ans_wa_typo.question

    ans_me_typo = execute_plan(US_CONFIG, "Maine", plan_typo)
    assert ans_me_typo.answer is True

    # 2. Standard Atlantic
    plan_clean = analyze_question("Does it have access to Atlantic Ocean?", US_CONFIG, use_cache=False)
    ans_wa_clean = execute_plan(US_CONFIG, "Washington", plan_clean)
    assert ans_wa_clean.answer is False

    # 3. Pacific access is True for Washington
    plan_pac = analyze_question("Does it have access to Pacific Ocean?", US_CONFIG, use_cache=False)
    ans_wa_pac = execute_plan(US_CONFIG, "Washington", plan_pac)
    assert ans_wa_pac.answer is True
