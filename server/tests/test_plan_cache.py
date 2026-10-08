"""Cache isolation, eviction and retry-after-failure are observable planner behavior."""
import json
import importlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import analyze_question_for_local_plan
from local_kb_question import analyze_question, execute_plan
from us_statedle.utils import LOCAL_CONFIG
from utils import ai_clients
from utils.plan_cache import PlanCache, plan_cache


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    cache = PlanCache(db_path=tmp_path / "planner-cache.sqlite")
    monkeypatch.setattr(importlib.import_module("utils.plan_cache"), "plan_cache", cache)
    monkeypatch.setitem(globals(), "plan_cache", cache)
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")


@pytest.fixture(autouse=True)
def private_facts(monkeypatch, tmp_path):
    from countrydle import local_answering

    country_db = tmp_path / "countries.sqlite"
    snapshot = json.loads((Path(__file__).parent / "countrydle_english_facts.json").read_text(encoding="utf-8"))
    with sqlite3.connect(country_db) as connection:
        for table in snapshot["tables"]:
            columns = ", ".join(f'"{name}" {datatype}' for name, datatype in table["columns"])
            connection.execute(f'CREATE TABLE "{table["name"]}" ({columns})')
            placeholders = ", ".join("?" for _ in table["columns"])
            connection.executemany(f'INSERT INTO "{table["name"]}" VALUES ({placeholders})', table["rows"])
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", country_db)

    state_db = tmp_path / "states.sqlite"
    with sqlite3.connect(state_db) as connection:
        connection.executescript("""
            CREATE TABLE us_states (id INTEGER PRIMARY KEY, name TEXT, is_coastal INTEGER);
            INSERT INTO us_states VALUES (1, 'California', 1), (2, 'Indiana', 0);
        """)
    monkeypatch.setitem(globals(), "LOCAL_CONFIG", replace(LOCAL_CONFIG, db_path=state_db))


def test_cache_normalization_preserves_mode_and_contract_boundaries(tmp_path):
    cache = PlanCache(max_size=5, db_path=tmp_path / "cache.sqlite")
    cache.set("Countrydle", "Czy państwo leży w Europie?", "country-plan", version="v2:model-a")
    assert cache.get("countrydle", "  CZY panstwo  lezy w Europie ", version="v2:model-a") == "country-plan"
    assert cache.get("us_statedle", "Czy państwo leży w Europie?", version="v2:model-a") is None
    assert cache.get("countrydle", "Czy państwo leży w Europie?", version="v3:model-a") is None
    assert cache.get("countrydle", "Czy państwo leży w Europie?", version="v2:model-b") is None


def test_plan_cache_evicts_least_recently_used_interpretation(tmp_path):
    cache = PlanCache(max_size=2, db_path=tmp_path / "cache.sqlite")
    cache.set("mode", "q1", "p1", version="v2")
    cache.set("mode", "q2", "p2", version="v2")
    assert cache.get("mode", "q1", version="v2") == "p1"
    cache.set("mode", "q3", "p3", version="v2")
    assert cache.get("mode", "q1", version="v2") == "p1"
    assert cache.stats()["size"] == 2
    assert cache.get("mode", "q2", version="v2") == "p2"
    assert cache.get("mode", "q3", version="v2") == "p3"

def test_plan_cache_persists_plans_across_instances(tmp_path):
    database = tmp_path / "plan_cache.sqlite"
    first = PlanCache(max_size=5, db_path=database)
    first.set("countrydle", "Is it coastal?", {"route": "local", "plan": [{"operator": "exists"}]}, version="v2")

    second = PlanCache(max_size=5, db_path=database)
    assert second.get("countrydle", "is it coastal", version="v2") == {
        "route": "local", "plan": [{"operator": "exists"}],
    }
    assert second.get("countrydle", "is it coastal", version="v3") is None


def test_plan_cache_persists_question_plan_fields(tmp_path):
    from local_kb_question import QuestionPlan

    database = tmp_path / "plan_cache.sqlite"
    plan = QuestionPlan(
        original_question="Is it coastal?", valid=True, supported=False,
        improved_question="Is it on the coast?", explanation=None, plan=None,
        fallback_reason="coastline facts are unavailable",
    )
    PlanCache(db_path=database).set("countrydle", plan.original_question, plan, version="v2")

    loaded = PlanCache(db_path=database).get("countrydle", plan.original_question, version="v2")
    assert loaded == plan


def test_plan_cache_reads_l2_after_another_instance_writes(tmp_path):
    database = tmp_path / "plan_cache.sqlite"
    reader = PlanCache(db_path=database)
    assert reader.get("mode", "question", version="v2") is None

    PlanCache(db_path=database).set("mode", "question", "persisted", version="v2")

    assert reader.get("mode", "question", version="v2") == "persisted"


@pytest.mark.parametrize("country", [True, False])
def test_cached_plan_remains_target_independent_and_skips_provider(monkeypatch, country):
    response = {
        "route": "local",
        "plan": [{"operator": "exists", "left": {
            "entity": "target_country" if country else "target_state",
            "relation": "water_access" if country else "is_coastal",
        }}],
    }
    calls = 0

    def generate(request):
        nonlocal calls
        calls += 1
        if calls > 1:
            pytest.fail("A cached interpretation must not call the provider again")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(response)}]}}]})

    with httpx.Client(transport=httpx.MockTransport(generate)) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        analyze = analyze_question_for_local_plan if country else lambda q, **kwargs: analyze_question(q, LOCAL_CONFIG, **kwargs)
        first_evidence = {}
        first = analyze("Does it have shoreline access?", evidence=first_evidence)
        hit_evidence = {}
        second = analyze("  DOES it have shoreline access? ", evidence=hit_evidence)
        assert calls == 1
        assert first_evidence["cache_hit"] is False
        assert hit_evidence["cache_hit"] is True
        assert "usage" not in hit_evidence
        if country:
            assert execute_local_plan(first.plan, "Portugal", first.original_question).answer is True
            assert execute_local_plan(second.plan, "Switzerland", second.original_question).answer is False
        else:
            assert execute_plan(LOCAL_CONFIG, "California", first).answer is True
            assert execute_plan(LOCAL_CONFIG, "Indiana", second).answer is False


def test_country_prompt_cutover_ignores_old_interpretation(monkeypatch):
    from countrydle import local_planner

    question = "Does it have shoreline access?"
    coastal = {"operator": "exists", "left": {"entity": "target_country", "relation": "water_access"}}
    responses = iter([
        {"route": "local", "plan": [coastal, {"operator": "not", "args": [0]}]},
        {"route": "local", "plan": [coastal]},
    ])

    def generate(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps(next(responses))}]}}],
        })

    with httpx.Client(transport=httpx.MockTransport(generate)) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        old = analyze_question_for_local_plan(question)
        assert execute_local_plan(old.plan, "Portugal", question).answer is False
        monkeypatch.setattr(local_planner, "COUNTRYDLE_PROMPT_REVISION", local_planner.COUNTRYDLE_PROMPT_REVISION + "-changed")
        evidence = {}
        fresh = analyze_question_for_local_plan(question, evidence=evidence)
        reused = analyze_question_for_local_plan(question.upper())
        assert evidence["cache_hit"] is False
        assert execute_local_plan(fresh.plan, "Portugal", question).answer is True
        assert execute_local_plan(reused.plan, "Switzerland", question).answer is False


@pytest.mark.parametrize("country", [True, False])
def test_provider_failure_does_not_poison_next_attempt(monkeypatch, country):
    responses = iter([
        httpx.Response(503, json={"error": {"message": "unavailable"}}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps({
            "route": "fallback", "plan": None, "fallback_reason": "Unsupported fact",
        })}]}}]}),
    ])
    with httpx.Client(transport=httpx.MockTransport(lambda request: next(responses))) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        analyze = analyze_question_for_local_plan if country else lambda q: analyze_question(q, LOCAL_CONFIG)
        with pytest.raises(httpx.HTTPStatusError):
            analyze("Does it have an ancient observatory?")
        result = analyze("Does it have an ancient observatory?")
        assert result.valid is True and result.supported is False
