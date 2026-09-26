"""Cache isolation, eviction and retry-after-failure are observable planner behavior."""
import json

import httpx
import pytest

from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import analyze_question_for_local_plan
from local_kb_question import analyze_question, execute_plan
from us_statedle.utils import LOCAL_CONFIG
from utils import ai_clients
from utils.plan_cache import PlanCache, plan_cache


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    plan_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    yield
    plan_cache.clear()


def test_cache_normalization_preserves_mode_and_contract_boundaries():
    cache = PlanCache(max_size=5)
    cache.set("Countrydle", "Czy państwo leży w Europie?", "country-plan", version="v2:model-a")
    assert cache.get("countrydle", "  CZY panstwo  lezy w Europie ", version="v2:model-a") == "country-plan"
    assert cache.get("us_statedle", "Czy państwo leży w Europie?", version="v2:model-a") is None
    assert cache.get("countrydle", "Czy państwo leży w Europie?", version="v3:model-a") is None
    assert cache.get("countrydle", "Czy państwo leży w Europie?", version="v2:model-b") is None


def test_plan_cache_evicts_least_recently_used_interpretation():
    cache = PlanCache(max_size=2)
    cache.set("mode", "q1", "p1", version="v2")
    cache.set("mode", "q2", "p2", version="v2")
    assert cache.get("mode", "q1", version="v2") == "p1"
    cache.set("mode", "q3", "p3", version="v2")
    assert cache.get("mode", "q1", version="v2") == "p1"
    assert cache.get("mode", "q2", version="v2") is None
    assert cache.get("mode", "q3", version="v2") == "p3"


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
        first = analyze("Does it have a coastline?")
        second = analyze("  DOES it have a coastline? ")
        if country:
            assert execute_local_plan(first.plan, "Portugal", first.original_question).answer is True
            assert execute_local_plan(second.plan, "Switzerland", second.original_question).answer is False
        else:
            assert execute_plan(LOCAL_CONFIG, "California", first).answer is True
            assert execute_plan(LOCAL_CONFIG, "Indiana", second).answer is False


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
