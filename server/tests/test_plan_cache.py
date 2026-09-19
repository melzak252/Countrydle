import pytest
from unittest.mock import patch, MagicMock
from local_kb_question import QuestionPlan, LocalModeConfig, analyze_question
from utils.plan_cache import PlanCache, normalize_question_key, plan_cache


def test_normalize_question_key():
    k1 = normalize_question_key("Countrydle", "Is it in Europe?")
    k2 = normalize_question_key("countrydle", "  is   it in europe?  ")
    k3 = normalize_question_key("countrydle", "is it in europe")
    assert k1 == k2 == k3
    assert k1 == ("countrydle", "is it in europe")

    # Mode distinction
    k_us = normalize_question_key("USStatedle", "Is it in Europe?")
    assert k_us != k1
    assert k_us[0] == "usstatedle"


def test_plan_cache_get_and_set():
    cache = PlanCache(max_size=5)
    plan = QuestionPlan(
        original_question="Is it in Europe?",
        valid=True,
        supported=True,
        improved_question="Is the country located in Europe?",
        explanation="Europe check",
        plan={"operator": "contains", "left": "continent", "value": "Europe"},
        fallback_reason=None,
    )

    assert cache.get("countrydle", "Is it in Europe?") is None
    cache.set("countrydle", "Is it in Europe?", plan)

    cached = cache.get("countrydle", "  is it in europe? ")
    assert cached is not None
    assert cached.improved_question == "Is the country located in Europe?"

    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1


def test_plan_cache_does_not_cache_transient_errors():
    cache = PlanCache(max_size=5)
    error_plan = QuestionPlan(
        original_question="Is it in Europe?",
        valid=True,
        supported=False,
        improved_question=None,
        explanation=None,
        plan=None,
        fallback_reason="GEMINI_API_KEY is not configured.",
    )
    cache.set("countrydle", "Is it in Europe?", error_plan)
    assert cache.get("countrydle", "Is it in Europe?") is None
    assert cache.stats()["size"] == 0

    http_err_plan = QuestionPlan(
        original_question="Is it in Europe?",
        valid=True,
        supported=False,
        improved_question=None,
        explanation=None,
        plan=None,
        fallback_reason="Gemini planner HTTP error: 500",
    )
    cache.set("countrydle", "Is it in Europe?", http_err_plan)
    assert cache.get("countrydle", "Is it in Europe?") is None


def test_plan_cache_lru_eviction():
    cache = PlanCache(max_size=2)
    p1 = QuestionPlan("q1", True, True, "q1", "e1", {}, None)
    p2 = QuestionPlan("q2", True, True, "q2", "e2", {}, None)
    p3 = QuestionPlan("q3", True, True, "q3", "e3", {}, None)

    cache.set("mode", "q1", p1)
    cache.set("mode", "q2", p2)
    assert cache.get("mode", "q1") is not None  # Touch q1 so q2 becomes LRU

    cache.set("mode", "q3", p3)  # Evicts q2
    assert cache.get("mode", "q1") is not None
    assert cache.get("mode", "q3") is not None
    assert cache.get("mode", "q2") is None


def test_analyze_question_uses_cache():
    from wojewodztwodle.utils import LOCAL_CONFIG

    plan_cache.clear()

    mock_plan = {
        "valid": True,
        "supported": True,
        "improved_question": "Mocked Q?",
        "explanation": "Mocked explanation",
        "plan": {"operator": "exists", "left": "is_coastal"},
        "fallback_reason": None,
    }

    with patch("local_kb_question.gemini_json", return_value=mock_plan) as mock_gemini:
        p1 = analyze_question("Czy to województwo ma dostęp do morza?", LOCAL_CONFIG)
        assert mock_gemini.call_count == 1
        assert p1.improved_question == "Mocked Q?"

        # Second call with variation in case / whitespace
        p2 = analyze_question("  czy to wojewodztwo ma dostęp do morza?  ", LOCAL_CONFIG)
        assert mock_gemini.call_count == 1  # Gemini NOT called again!
        assert p2.improved_question == "Mocked Q?"


def test_countrydle_planner_uses_cache(monkeypatch):
    from countrydle.local_planner import analyze_question_for_local_plan
    import json

    plan_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key_for_test")

    mock_gemini_cm = MagicMock()
    mock_payload = {
        "valid": True,
        "supported": True,
        "improved_question": "Is the country in Europe?",
        "explanation": "Continent check",
        "plan": {"operator": "contains_exact", "left": {"entity": "target_country", "relation": "continent"}, "value": "Europe"},
        "fallback_reason": None,
    }
    mock_gemini_cm.read.return_value = json.dumps({
        "candidates": [{"content": {"parts": [{"text": json.dumps(mock_payload)}]}}]
    }).encode("utf-8")

    with patch("countrydle.local_planner.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_gemini_cm
        p1 = analyze_question_for_local_plan("Is it in Europe?")
        assert mock_urlopen.call_count == 1
        assert p1.valid is True
        assert p1.improved_question == "Is the country in Europe?"

        # Second call with different casing / spaces
        p2 = analyze_question_for_local_plan("  is it IN Europe?  ")
        assert mock_urlopen.call_count == 1  # Cache HIT! urlopen NOT called!
        assert p2.improved_question == "Is the country in Europe?"

    plan_cache.clear()
