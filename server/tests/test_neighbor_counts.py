import pytest
from countrydle.template_compiler import compile_template_plan
from countrydle.local_answering import execute_local_plan
from us_statedle.utils import LOCAL_CONFIG as US_CONFIG
from wojewodztwodle.utils import LOCAL_CONFIG as WOJ_CONFIG
from powiatdle.utils import LOCAL_CONFIG as POW_CONFIG
from local_kb_question import analyze_question, execute_plan


def test_countrydle_exact_and_comparison_neighbor_counts():
    """Verify Countrydle evaluates exact and relative neighbor counts locally."""
    # Poland: 7 neighbors (Belarus, Czech Republic, Germany, Lithuania, Russia, Slovakia, Ukraine)
    cases = [
        ("Does it border 7 countries?", True),
        ("Does it have 7 neighbors?", True),
        ("Does it border 8 countries?", False),
        ("Does it have 6 neighbors?", False),
        ("Does it border more than 5 countries?", True),
        ("Does it border more than 7 countries?", False),
        ("Does it border fewer than 8 countries?", True),
        ("Does it border fewer than 7 countries?", False),
        ("Czy ma 7 sąsiadów?", True),
        ("Czy ma więcej niż 5 sąsiadów?", True),
        ("Czy ma mniej niż 8 sąsiadów?", True),
        ("Czy graniczy z 7 państwami?", True),
    ]

    for q, expected in cases:
        ast, imp = compile_template_plan(q)
        assert ast is not None, f"Failed template match for {q}"
        ans = execute_local_plan(ast, "Poland", imp)
        assert ans is not None
        assert ans.answer is expected, f"Failed for {q}: expected {expected}, got {ans.answer}"
        assert "7 neighboring countries" in ans.explanation


def test_countrydle_islands_zero_neighbors():
    """Verify islands evaluate 0 neighbors correctly."""
    ast, imp = compile_template_plan("Does it have 0 neighbors?")
    assert ast is not None
    ans_aus = execute_local_plan(ast, "Australia", imp)
    assert ans_aus.answer is True

    ans_pol = execute_local_plan(ast, "Poland", imp)
    assert ans_pol.answer is False


def test_us_statedle_neighbor_counts():
    """Verify US Statedle evaluates bordering state counts locally."""
    # Tennessee borders 8 states; Washington borders 2; Hawaii borders 0
    cases = [
        ("Tennessee", "Does it border 8 states?", True),
        ("Tennessee", "Does it border more than 4 states?", True),
        ("Tennessee", "Does it border fewer than 5 states?", False),
        ("Washington", "Does it border 2 states?", True),
        ("Washington", "Does it border 8 states?", False),
        ("Washington", "Does it border more than 4 states?", False),
        ("Hawaii", "Does it border 0 states?", True),
    ]

    for state, q, expected in cases:
        plan = analyze_question(q, US_CONFIG, use_cache=False)
        assert plan.valid is True
        assert plan.supported is True
        ans = execute_plan(US_CONFIG, state, plan)
        assert ans is not None
        assert ans.answer is expected, f"Failed for {state} - {q}: expected {expected}, got {ans.answer}"


def test_wojewodztwodle_neighbor_counts():
    """Verify Województwodle evaluates neighboring voivodeship counts locally."""
    # Mazowieckie borders 6 voivodeships
    cases = [
        ("Mazowieckie", "Czy graniczy z 6 województwami?", True),
        ("Mazowieckie", "Czy ma 6 sąsiadów?", True),
        ("Mazowieckie", "Czy ma 5 sąsiadów?", False),
        ("Mazowieckie", "Czy ma więcej niż 4 sąsiadów?", True),
        ("Mazowieckie", "Czy ma mniej niż 8 sąsiadów?", True),
    ]

    for voivodeship, q, expected in cases:
        plan = analyze_question(q, WOJ_CONFIG, use_cache=False)
        assert plan.valid is True
        assert plan.supported is True
        ans = execute_plan(WOJ_CONFIG, voivodeship, plan)
        assert ans is not None
        assert ans.answer is expected, f"Failed for {voivodeship} - {q}: expected {expected}, got {ans.answer}"
        assert "6 sąsiednimi województwami" in ans.explanation


def test_powiatdle_neighbor_counts():
    """Verify Powiatdle evaluates neighboring powiat counts locally."""
    # Powiat tatrzański borders only 1 other powiat (nowotarski)
    cases = [
        ("Powiat tatrzański", "Czy graniczy z 1 powiatem?", True),
        ("Powiat tatrzański", "Czy graniczy z 5 powiatami?", False),
        ("Powiat tatrzański", "Czy ma więcej niż 2 sąsiadów?", False),
    ]

    for powiat, q, expected in cases:
        plan = analyze_question(q, POW_CONFIG, use_cache=False)
        assert plan.valid is True
        assert plan.supported is True
        ans = execute_plan(POW_CONFIG, powiat, plan)
        assert ans is not None
        assert ans.answer is expected, f"Failed for {powiat} - {q}: expected {expected}, got {ans.answer}"
        assert "1 sąsiednimi powiatami" in ans.explanation
