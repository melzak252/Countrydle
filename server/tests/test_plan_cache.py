"""Disk-backed cache isolation and retry-after-failure are observable planner behavior."""
import json

import httpx
import pytest

from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import analyze_question_for_local_plan
from local_kb_question import analyze_question, execute_plan
from us_statedle.utils import LOCAL_CONFIG
from utils import ai_clients, plan_cache as plan_cache_module
from utils.plan_cache import PlanCache


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    cache = PlanCache(db_path=tmp_path / "shared_plan_cache.sqlite")
    monkeypatch.setattr(plan_cache_module, "plan_cache", cache)
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    return cache


def test_cache_normalization_preserves_mode_and_contract_boundaries(tmp_path):
    cache = PlanCache(db_path=tmp_path / "plan_cache.sqlite")
    cache.set("Countrydle", "Czy państwo leży w Europie?", "country-plan", version="v2:model-a")
    assert cache.get("countrydle", "  CZY panstwo  lezy w Europie ", version="v2:model-a") == "country-plan"
    assert cache.get("us_statedle", "Czy państwo leży w Europie?", version="v2:model-a") is None
    assert cache.get("countrydle", "Czy państwo leży w Europie?", version="v3:model-a") is None
    assert cache.get("countrydle", "Czy państwo leży w Europie?", version="v2:model-b") is None


def test_plan_cache_persists_plans_across_instances(tmp_path):
    database = tmp_path / "plan_cache.sqlite"
    first = PlanCache(db_path=database)
    first.set("countrydle", "Is it coastal?", {"route": "local", "plan": [{"operator": "exists"}]}, version="v2")

    second = PlanCache(db_path=database)
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


def test_plan_cache_reads_after_another_instance_writes(tmp_path):
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
        first = analyze("Does it have shoreline access?")
        second = analyze("  DOES it have shoreline access? ")
        if country:
            assert execute_local_plan(first.plan, "Portugal", first.original_question).answer is True
            assert execute_local_plan(second.plan, "Switzerland", second.original_question).answer is False
        else:
            assert execute_plan(LOCAL_CONFIG, "California", first).answer is True
            assert execute_plan(LOCAL_CONFIG, "Indiana", second).answer is False


def test_country_prompt_cutover_ignores_old_interpretation(monkeypatch, isolated_cache):
    from countrydle.local_planner import DEFAULT_MODEL, QuestionPlan
    from planner_protocol import PLANNER_VERSION

    monkeypatch.setenv("LOCAL_QUESTION_MODEL", DEFAULT_MODEL)
    question = "Does the country have at least ten million people?"
    old_plan = QuestionPlan(
        original_question=question, valid=True, supported=True,
        improved_question=None, explanation=None,
        plan={"operator": "less_than",
              "left": {"entity": "target_country", "relation": "population"},
              "right": {"value": 10_000_000}},
    )
    isolated_cache.set(
        "countrydle", question, old_plan, version=f"{PLANNER_VERSION}:{DEFAULT_MODEL}",
    )
    response = {
        "route": "local", "plan": [{
            "operator": "greater_than_or_equal",
            "left": {"entity": "target_country", "relation": "population"},
            "right": {"value": 10_000_000},
        }],
    }
    responses = iter([
        httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps(response)}]}}],
        }),
    ])
    with httpx.Client(transport=httpx.MockTransport(lambda request: next(responses))) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        fresh = analyze_question_for_local_plan(question)
        reused = analyze_question_for_local_plan(question.upper())
        assert execute_local_plan(fresh.plan, "Poland", question).answer is True
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


def test_reader_observes_replaced_plan_from_another_instance(tmp_path):
    database = tmp_path / "plan_cache.sqlite"
    writer = PlanCache(db_path=database)
    reader = PlanCache(db_path=database)
    writer.set("countrydle", "Is it coastal?", {"supported": False}, version="v2")
    assert reader.get("countrydle", "Is it coastal?", version="v2") == {"supported": False}

    writer.set("countrydle", "Is it coastal?", {"supported": True}, version="v2")
    assert reader.get("countrydle", "Is it coastal?", version="v2") == {"supported": True}


def test_lookup_deserializes_only_requested_row(tmp_path, monkeypatch):
    database = tmp_path / "plan_cache.sqlite"
    writer = PlanCache(db_path=database)
    writer.set("mode", "other question", {"plan": "unrelated"}, version="v2")
    writer.set("mode", "question", {"plan": "requested"}, version="v2")
    reader = PlanCache(db_path=database)
    deserialize = reader._deserialize
    deserialized = []

    def track_deserialization(plan_json):
        plan = deserialize(plan_json)
        deserialized.append(plan)
        return plan

    monkeypatch.setattr(reader, "_deserialize", track_deserialization)
    assert reader.get("mode", "missing question", version="v2") is None
    assert deserialized == []
    assert reader.get("mode", "question", version="v2") == {"plan": "requested"}
    assert deserialized == [{"plan": "requested"}]


def test_stats_count_persistent_rows_and_clear_is_visible_to_existing_reader(tmp_path):
    database = tmp_path / "plan_cache.sqlite"
    writer = PlanCache(db_path=database)
    reader = PlanCache(db_path=database)
    writer.set("mode", "question", "current", version="v2")
    writer.set("other mode", "question", "old", version="v1")
    assert reader.stats() == {
        "hits": 0, "misses": 0, "size": 2, "storage": "sqlite", "hit_ratio_percent": 0.0,
    }
    assert reader.get("mode", "question", version="v2") == "current"
    assert reader.get("mode", "missing", version="v2") is None
    assert reader.stats() == {
        "hits": 1, "misses": 1, "size": 2, "storage": "sqlite", "hit_ratio_percent": 50.0,
    }

    writer.clear()

    assert writer.stats() == {
        "hits": 0, "misses": 0, "size": 0, "storage": "sqlite", "hit_ratio_percent": 0.0,
    }
    assert reader.get("mode", "question", version="v2") is None
    assert reader.get("other mode", "question", version="v1") is None
    assert reader.stats() == {
        "hits": 1, "misses": 3, "size": 0, "storage": "sqlite", "hit_ratio_percent": 25.0,
    }
    reader.clear()
    assert reader.stats() == {
        "hits": 0, "misses": 0, "size": 0, "storage": "sqlite", "hit_ratio_percent": 0.0,
    }
