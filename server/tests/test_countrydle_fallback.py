from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from countrydle import _do_ask_question, utils
from countrydle.local_planner import QuestionPlan
from schemas.countrydle import QuestionBase, QuestionCreate, QuestionEnhanced


@pytest.fixture
def enhanced_question():
    return QuestionEnhanced(
        original_question="Was the Central African Republic part of the Axis powers during World War II?",
        question="Was the Central African Republic part of the Axis powers during World War II?",
        valid=True,
        explanation="A yes/no historical question.",
        intent="Check Axis membership during World War II.",
        required_info="The country's Axis membership during World War II.",
    )


@pytest.mark.parametrize("answer", [True, False, None])
def test_fallback_accepts_boolean_answers_and_explicit_abstention(monkeypatch, enhanced_question, answer):
    monkeypatch.setattr(utils, "gemini_json", lambda *args, **kwargs: {
        "answer": answer,
        "explanation": "Historical records establish the requested fact." if answer is not None else "The available evidence is insufficient to determine this fact.",
    })
    result = utils.answer_question_for_entity(enhanced_question, "Central African Republic", "")
    assert result["answer"] is answer


@pytest.mark.parametrize("response", [
    {"explanation": "The provider omitted the answer."},
    {"answer": "false", "explanation": "The provider returned text instead of a boolean."},
    {"answer": 0, "explanation": "The provider returned a number instead of a boolean."},
    {"answer": [], "explanation": "The provider returned an invalid answer type."},
    [],
    {"answer": False, "explanation": None},
    {"answer": False, "explanation": "Known answer.", "debug": "unexpected provider field"},
])
def test_fallback_rejects_malformed_provider_answers(monkeypatch, enhanced_question, response):
    monkeypatch.setattr(utils, "gemini_json", lambda *args, **kwargs: response)

    with pytest.raises(ValueError):
        utils.answer_question_for_entity(enhanced_question, "Central African Republic", "")


@pytest.mark.anyio
async def test_provider_schema_failure_is_unavailable_not_an_invalid_question(monkeypatch, async_client):
    day = SimpleNamespace(id=7, country_id=31)
    monkeypatch.setattr("countrydle.CountrydleRepository.get_today_country", AsyncMock(return_value=day))
    monkeypatch.setattr("countrydle.gutils.analyze_and_answer_locally",
                        AsyncMock(side_effect=ValueError("Provider omitted the answer")))
    response = await async_client.post("/countrydle/question", json={"question": "Is it in Europe?"})
    assert response.status_code == 503
    assert "valid" not in response.json()

@pytest.mark.anyio
async def test_valid_abstention_does_not_record_or_consume_daily_question(monkeypatch):
    day = SimpleNamespace(id=7, country_id=31)
    question = QuestionCreate(
        user_id=10,
        day_id=7,
        original_question="Is the country's population above 20 million?",
        question="Is the country's population above 20 million?",
        valid=True,
        answer=None,
        explanation="The available evidence is insufficient to determine the population threshold.",
        intent="Compare population with a threshold.",
        required_info="Population",
        context=None,
    )
    monkeypatch.setattr("countrydle.CountrydleRepository.get_today_country", AsyncMock(return_value=day))
    monkeypatch.setattr("countrydle.check_question_available", AsyncMock())
    monkeypatch.setattr("countrydle.gutils.analyze_and_answer_locally", AsyncMock(return_value=(question, None)))
    persist = AsyncMock()
    monkeypatch.setattr("countrydle.CountrydleQuestionsRepository.create_question", persist)
    consume = AsyncMock()
    monkeypatch.setattr("countrydle.consume_question", consume)
    request = Request({
        "type": "http", "method": "POST", "path": "/countrydle/question",
        "headers": [], "query_string": b"", "scheme": "http",
        "server": ("test", 80), "client": ("test", 80),
    })

    with pytest.raises(HTTPException) as error:
        await _do_ask_question(
            QuestionBase(question="Is the country's population above 20 million?"),
            SimpleNamespace(id=10), object(), request, Response(),
        )

    assert error.value.status_code == 503
    assert persist.await_count == 0
    assert consume.await_count == 0


@pytest.mark.anyio
async def test_invalid_question_stays_in_existing_rejection_flow(monkeypatch):
    invalid_plan = QuestionPlan(
        original_question="Tell me about the country.", valid=False, supported=False,
        improved_question=None, explanation="This is not a yes/no question.", plan=None,
    )

    class CountryRepository:
        def __init__(self, session):
            pass

        async def get(self, country_id):
            return SimpleNamespace(name="Poland")

    monkeypatch.setattr(utils, "CountryRepository", CountryRepository)
    monkeypatch.setattr(utils, "analyze_question_for_local_plan", lambda *args, **kwargs: invalid_plan)

    question, plan = await utils.analyze_and_answer_locally(
        "Tell me about the country.", SimpleNamespace(id=4, country_id=31), None, object(),
    )

    assert question.valid is False
    assert question.answer is None
    assert question.explanation == "This is not a yes/no question."
    assert plan is invalid_plan
