import pytest
from utils.shadow_audit import compare_plans, get_audit_sample_rate, should_audit_template


def test_compare_plans_identical():
    plan_a = [{"operator": "contains", "left": {"entity": "target_country", "relation": "geographic_area"}, "right": {"value": "Southeast Asia"}}]
    plan_b = [{"operator": "contains", "left": {"entity": "target_country", "relation": "geographic_area"}, "right": {"value": "Southeast Asia"}}]
    divergent, div_type, details = compare_plans(plan_a, plan_b, gemini_supported=True, gemini_valid=True)
    assert divergent is False
    assert div_type == "match"


def test_compare_plans_value_mismatch():
    plan_a = [{"operator": "contains", "left": {"entity": "target_country", "relation": "continent"}, "right": {"value": "Africa"}}]
    plan_b = [{"operator": "contains", "left": {"entity": "target_country", "relation": "geographic_area"}, "right": {"value": "Southern Africa"}}]
    divergent, div_type, details = compare_plans(plan_a, plan_b, gemini_supported=True, gemini_valid=True)
    assert divergent is True
    assert div_type == "value_mismatch"
    assert details["template_value"] == "Africa"
    assert details["gemini_value"] == "Southern Africa"


def test_compare_plans_relation_mismatch():
    plan_a = [{"operator": "contains", "left": {"entity": "target_country", "relation": "borders_country"}, "right": {"value": "Germany"}}]
    plan_b = [{"operator": "contains", "left": {"entity": "target_country", "relation": "water_access"}, "right": {"value": "Baltic Sea"}}]
    divergent, div_type, details = compare_plans(plan_a, plan_b, gemini_supported=True, gemini_valid=True)
    assert divergent is True
    assert div_type == "relation_mismatch"


def test_compare_plans_gemini_unsupported_or_invalid():
    plan = [{"operator": "equals", "left": {"entity": "target_country", "relation": "is_island"}, "right": {"value": True}}]
    div_unsupp, type_unsupp, _ = compare_plans(plan, None, gemini_supported=False, gemini_valid=True)
    assert div_unsupp is True
    assert type_unsupp == "gemini_unsupported"

    div_inv, type_inv, _ = compare_plans(plan, plan, gemini_supported=True, gemini_valid=False)
    assert div_inv is True
    assert type_inv == "gemini_invalid"


def test_should_audit_template_sampling(monkeypatch):
    monkeypatch.setenv("TEMPLATE_AUDIT_SAMPLE_RATE", "3")
    results = [should_audit_template() for _ in range(6)]
    # Exactly 2 out of 6 should be True when sample rate is 3
    assert results.count(True) == 2
