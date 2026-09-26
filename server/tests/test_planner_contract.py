"""A provider protocol error must never become an accepted or cached plan."""
import pytest

import local_kb_question as local
from us_statedle.utils import LOCAL_CONFIG
from utils.plan_cache import plan_cache


@pytest.fixture(autouse=True)
def empty_plan_cache():
    plan_cache.clear()
    yield
    plan_cache.clear()


@pytest.mark.parametrize("response", [
    {"route": False, "plan": None},
    {"route": "fallback", "plan": [{"operator": "exists", "left": {"entity": "target_state", "relation": "region"}}]},
    {"route": "local", "plan": [{"operator": "invented_operation", "left": {"entity": "target_state", "relation": "region"}}]},
    {"route": "local", "plan": [{"operator": "exists", "left": {"entity": "target_state", "relation": "invented_fact"}}, {"operator": "not", "args": [0]}]},
    {"route": "local", "plan": [{"operator": "equals", "left": {"entity": "target_text_area", "relation": "region"}, "right": {"value": "West"}}]},
    {"route": "local", "plan": [{"operator": "equals", "left": {"entity": "target_state", "relation": "region", "value": "West"}, "right": {"value": "West"}}]},
    {"route": "local", "plan": [{"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "West"}, "negate": True}]},
])
def test_daily_planner_rejects_provider_protocol_errors(monkeypatch, response):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: response)
    with pytest.raises(RuntimeError):
        local.analyze_question("Is it in the West?", LOCAL_CONFIG)
    assert plan_cache.stats()["size"] == 0


def test_cache_does_not_reuse_a_different_model_interpretation(monkeypatch):
    outputs = iter([
        {"route": "local", "plan": [{"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "West"}}]},
        {"route": "fallback", "plan": None, "fallback_reason": "Uncertain interpretation"},
    ])
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: next(outputs))
    monkeypatch.setenv("LOCAL_QUESTION_MODEL", "test-model-a")
    first = local.analyze_question("Is it in the West?", LOCAL_CONFIG)
    assert local.execute_plan(LOCAL_CONFIG, "California", first).answer is True
    monkeypatch.setenv("LOCAL_QUESTION_MODEL", "test-model-b")
    second = local.analyze_question("Is it in the West?", LOCAL_CONFIG)
    assert second.supported is False


def test_compact_plan_preserves_question_and_false_answer(monkeypatch):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local",
        "plan": [{"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "West"}}],
    })
    question = "Is it in the West?"
    result = local.execute_plan(LOCAL_CONFIG, "Indiana", local.analyze_question(question, LOCAL_CONFIG))
    assert result.answer is False
    assert result.question == question


def test_cache_hit_retains_current_original_question_and_no_billed_usage(monkeypatch):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local",
        "plan": [{"operator": "exists", "left": {"entity": "target_state", "relation": "water_access"}}],
    })
    monkeypatch.setenv("LOCAL_QUESTION_MODEL", "test-model")
    local.analyze_question("Does it have water access?", LOCAL_CONFIG)
    evidence = {}
    question = "  Does it HAVE water access? "
    cached = local.analyze_question(question, LOCAL_CONFIG, evidence=evidence)
    assert cached.original_question == question
    assert evidence["cache_hit"] is True
    assert "usage" not in evidence


def test_compilation_preserves_nested_boolean_meaning(monkeypatch):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local", "plan": [
            {"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "West"}},
            {"operator": "equals", "left": {"entity": "target_state", "relation": "is_coastal"}, "right": {"value": 1}},
            {"operator": "and", "args": [0, 1]},
            {"operator": "not", "args": [2]},
        ],
    })
    plan = local.analyze_question("Is it not a coastal western state?", LOCAL_CONFIG)
    assert local.execute_plan(LOCAL_CONFIG, "California", plan).answer is False
    assert local.execute_plan(LOCAL_CONFIG, "Maine", plan).answer is True


def test_compilation_preserves_quantifier_item_scope(monkeypatch):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local", "plan": [
            {"operator": "equals", "left": {"entity": "item", "relation": "name"}, "right": {"value": "Arizona"}},
            {"operator": "any", "items": {"entity": "target_state", "relation": "borders_state"}, "args": [0]},
        ],
    })
    plan = local.analyze_question("Is one of its neighbors Arizona?", LOCAL_CONFIG)
    assert local.execute_plan(LOCAL_CONFIG, "Nevada", plan).answer is True
    assert local.execute_plan(LOCAL_CONFIG, "Maine", plan).answer is False


@pytest.mark.parametrize("nodes", [
    [{"operator": "not", "args": [0]}],
    [
        {"operator": "exists", "left": {"entity": "target_state", "relation": "water_access"}},
        {"operator": "and", "args": [0, 0]},
    ],
    [
        {"operator": "exists", "left": {"entity": "target_state", "relation": "water_access"}},
        {"operator": "exists", "left": {"entity": "target_state", "relation": "is_coastal"}},
    ],
    [{"operator": "exists", "left": {"entity": "item", "relation": "name"}}],
    [
        {"operator": "not", "args": [1]},
        {"operator": "not", "args": [0]},
        {"operator": "exists", "left": {"entity": "target_state", "relation": "water_access"}},
    ],
], ids=["cycle", "shared_subtree", "discarded_predicate", "unbound_item", "disconnected_cycle"])
def test_compilation_rejects_non_tree_or_unbound_plans(monkeypatch, nodes):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local", "plan": nodes,
    })
    with pytest.raises(RuntimeError):
        local.analyze_question("Is it coastal?", LOCAL_CONFIG)
    assert plan_cache.stats()["size"] == 0


def test_forward_referenced_predicate_retains_negation(monkeypatch):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local", "plan": [
            {"operator": "not", "args": [1]},
            {"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "West"}},
        ],
    })
    plan = local.analyze_question("Is it outside the West?", LOCAL_CONFIG)
    assert local.execute_plan(LOCAL_CONFIG, "California", plan).answer is False
    assert local.execute_plan(LOCAL_CONFIG, "Maine", plan).answer is True


def test_boolean_literal_matches_sqlite_boolean_value(monkeypatch):
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: {
        "route": "local", "plan": [
            {"operator": "equals", "left": {"entity": "target_state", "relation": "is_coastal"}, "right": {"value": True}},
        ],
    })
    plan = local.analyze_question("Is it coastal?", LOCAL_CONFIG)
    assert local.execute_plan(LOCAL_CONFIG, "Maine", plan).answer is True
    assert local.execute_plan(LOCAL_CONFIG, "Indiana", plan).answer is False
