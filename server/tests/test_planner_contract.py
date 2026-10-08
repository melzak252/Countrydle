"""A provider protocol error must never become an accepted or cached plan."""
import importlib
import sqlite3
from dataclasses import replace
from pathlib import Path
import pytest

import local_kb_question as local
from us_statedle.utils import LOCAL_CONFIG
from utils.plan_cache import plan_cache


@pytest.fixture(autouse=True)
def empty_plan_cache(monkeypatch, tmp_path):
    cache = importlib.import_module("utils.plan_cache").PlanCache(db_path=tmp_path / "cache.sqlite")
    monkeypatch.setattr(importlib.import_module("utils.plan_cache"), "plan_cache", cache)
    monkeypatch.setitem(globals(), "plan_cache", cache)


@pytest.fixture(autouse=True)
def private_state_facts(monkeypatch, tmp_path):
    database = tmp_path / "state-facts.sqlite"
    with sqlite3.connect(database) as connection:
        schema = Path(__file__).resolve().parents[1] / "us_statedle" / "local_kb" / "schema.sql"
        connection.executescript(schema.read_text(encoding="utf-8"))
        connection.executemany(
            "INSERT INTO us_states (id, name, region, division, is_coastal) VALUES (?, ?, ?, ?, ?)",
            [(1, "California", "West", "Pacific", 1),
             (2, "Indiana", "Midwest", "East North Central", 0),
             (3, "Maine", "Northeast", "New England", 1),
             (4, "Nevada", "West", "Mountain", 0),
             (5, "Arizona", "West", "Mountain", 0)],
        )
        connection.execute(
            "INSERT INTO us_state_borders_states (state_id, border_state_name) VALUES (?, ?)",
            (4, "Arizona"),
        )
    monkeypatch.setitem(globals(), "LOCAL_CONFIG", replace(LOCAL_CONFIG, db_path=database))


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
    calls = 0

    def generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            pytest.fail("Cache hits must not invoke a billed provider request")
        return {
            "route": "local",
            "plan": [{"operator": "exists", "left": {"entity": "target_state", "relation": "is_coastal"}}],
        }

    monkeypatch.setattr(local, "gemini_json", generate)
    monkeypatch.setenv("LOCAL_QUESTION_MODEL", "test-model")
    local.analyze_question("Does it have water access?", LOCAL_CONFIG)
    evidence = {}
    question = "  Does it HAVE water access? "
    cached = local.analyze_question(question, LOCAL_CONFIG, evidence=evidence)
    assert cached.original_question == question
    assert evidence["cache_hit"] is True
    assert "usage" not in evidence
    assert calls == 1
    assert local.execute_plan(LOCAL_CONFIG, "California", cached).answer is True
    assert local.execute_plan(LOCAL_CONFIG, "Indiana", cached).answer is False


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
        local.analyze_question("Is it in the West?", LOCAL_CONFIG)
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


@pytest.mark.parametrize("changed_field", ["mode_notes", "scalar_relations", "supported_relations"])
def test_cache_misses_after_semantic_config_change(monkeypatch, changed_field):
    responses = iter([
        {"route": "local", "plan": [{"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "West"}}]},
        {"route": "fallback", "plan": None, "fallback_reason": "Changed interpretation contract"},
    ])
    monkeypatch.setattr(local, "gemini_json", lambda *args, **kwargs: next(responses))
    question = "Is it in the West?"
    first = local.analyze_question(question, LOCAL_CONFIG)
    assert local.execute_plan(LOCAL_CONFIG, "California", first).answer is True
    updates = {
        "mode_notes": LOCAL_CONFIG.mode_notes + "\nRequire clarification for informal regions.",
        "scalar_relations": {**LOCAL_CONFIG.scalar_relations, "region": "division"},
        "supported_relations": [*LOCAL_CONFIG.supported_relations, "new_relation"],
    }
    changed = replace(LOCAL_CONFIG, **{changed_field: updates[changed_field]})
    evidence = {}
    second = local.analyze_question(question, changed, evidence=evidence)
    assert evidence["cache_hit"] is False
    assert second.supported is False
