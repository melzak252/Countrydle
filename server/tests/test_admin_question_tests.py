"""Read-only explicit-target evaluation, with deterministic planner/provider boundaries."""
from dataclasses import replace
from importlib import import_module
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from admin import router
from countrydle.local_planner import QuestionPlan
from db import get_db
from db.models import Country, Powiat, USState, Wojewodztwo
from db.repositories.country import CountryRepository
from users.utils import get_current_user

pytestmark = pytest.mark.anyio
COUNTRY_GET = CountryRepository.get


class ReadOnlySession:
    """Only entity tables exist; state reads and every write fail the request."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        assert statement.is_select, "Evaluation must not mutate SQL records"
        return self.session.execute(statement)

    @property
    def no_autoflush(self):
        return self.session.no_autoflush


@pytest.fixture
async def admin_client(monkeypatch, tmp_path):
    facts_path = tmp_path / "country_facts.sqlite"
    facts_path.touch()
    monkeypatch.setattr("countrydle.local_answering.DEFAULT_DB_PATH", facts_path)
    engine = create_engine("sqlite://")
    for model in (Country, Powiat, USState, Wojewodztwo):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([
            Country(id=31, name="Poland", md_file="poland.md"),
            Country(id=82, name="Germany", md_file="germany.md"),
            Country(id=145, name="Soviet Union", md_file="soviet-union.md"),
            USState(id=64, name="Texas"),
            Powiat(id=91, nazwa="Kraków"),
            Wojewodztwo(id=27, nazwa="Małopolskie"),
        ])
        session.commit()
        readonly = ReadOnlySession(session)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: readonly
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=10, is_admin=True)
        monkeypatch.setattr(CountryRepository, "get", COUNTRY_GET)

        def forbidden(*args, **kwargs):
            raise AssertionError("Daily state and Qdrant writes are forbidden")

        monkeypatch.setattr("db.repositories.countrydle.CountrydleRepository.get_today_country", forbidden)
        monkeypatch.setattr("db.repositories.countrydle.CountrydleRepository.generate_new_day_country", forbidden)
        monkeypatch.setattr("qdrant.client.upsert", forbidden)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, app
        assert not session.new and not session.dirty and not session.deleted
    engine.dispose()


def plan(*, valid=True, supported=True):
    return QuestionPlan(
        original_question="Is it in Europe?", valid=valid, supported=supported,
        improved_question="Is this country in Europe?" if valid else None,
        explanation="Check continent" if valid else "Ask a yes/no question",
        plan={"operator": "equals", "left": {"relation": "continent"}, "right": "Europe"} if supported else None,
        fallback_reason=None if supported else "Unsupported relation",
    )


def patch_country_local(monkeypatch, question_plan=None):
    question_plan = question_plan or plan()
    monkeypatch.setattr("countrydle.utils.analyze_question_for_local_plan", lambda *args, **kwargs: question_plan)
    monkeypatch.setattr("flagdle.analyze_question_for_local_plan", lambda *args, **kwargs: question_plan)

    def execute(ast, name, question):
        if not question_plan.supported:
            return None
        return SimpleNamespace(
            answer=name == "Poland", question=question,
            explanation=f"Local facts for {name}", relation="continent",
        )

    monkeypatch.setattr("countrydle.utils.execute_local_plan", execute)
    monkeypatch.setattr("flagdle.execute_local_plan", execute)


@pytest.mark.parametrize("endpoint", ["entities?mode=countrydle", ""])
async def test_non_admin_cannot_list_targets_or_evaluate(admin_client, endpoint):
    client, app = admin_client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=10, is_admin=False)
    response = await client.get(f"/admin/question-tests/{endpoint}") if endpoint else await client.post(
        "/admin/question-tests", json={"mode": "countrydle", "entity_id": 31, "question": "Is it in Europe?"},
    )
    assert response.status_code == 403


async def test_anonymous_cannot_list_or_evaluate(admin_client):
    client, app = admin_client
    app.dependency_overrides.pop(get_current_user)
    assert (await client.get("/admin/question-tests/entities?mode=countrydle")).status_code == 401
    assert (await client.post("/admin/question-tests", json={
        "mode": "countrydle", "entity_id": 31, "question": "Is it in Europe?",
    })).status_code == 401


@pytest.mark.parametrize("mode,expected", [
    ("countrydle", [{"id": 82, "name": "Germany"}, {"id": 31, "name": "Poland"}, {"id": 145, "name": "Soviet Union"}]),
    ("flagdle", [{"id": 82, "name": "Germany"}, {"id": 31, "name": "Poland"}, {"id": 145, "name": "Soviet Union"}]),
    ("us_statedle", [{"id": 64, "name": "Texas"}]),
    ("powiatdle", [{"id": 91, "name": "Kraków"}]),
    ("wojewodztwodle", [{"id": 27, "name": "Małopolskie"}]),
])
async def test_entities_use_database_ids_and_include_historical_targets(admin_client, mode, expected):
    client, _ = admin_client
    response = await client.get(f"/admin/question-tests/entities?mode={mode}")
    assert response.status_code == 200, response.text
    assert response.json() == expected


@pytest.mark.parametrize("mode", ["europe", "asia", "africa", "americas"])
async def test_continent_membership_is_identical_for_listing_and_evaluation(admin_client, monkeypatch, mode):
    client, _ = admin_client
    monkeypatch.setattr("admin.question_tests.get_continent_country_names", lambda continent: ["Poland"])
    patch_country_local(monkeypatch)
    listing = await client.get(f"/admin/question-tests/entities?mode={mode}")
    assert listing.json() == [{"id": 31, "name": "Poland"}]
    accepted = await client.post("/admin/question-tests", json={
        "mode": mode, "entity_id": 31, "question": "Is it in Europe?",
    })
    assert accepted.status_code == 200, accepted.text
    rejected = await client.post("/admin/question-tests", json={
        "mode": mode, "entity_id": 82, "question": "Is it in Europe?",
    })
    assert rejected.status_code == 404


@pytest.mark.parametrize("changes", [
    {"question": " "}, {"question": "x" * 101}, {"entity_id": 0}, {"entity_id": -1},
    {"entity_id": True}, {"entity_id": 1.5}, {"mode": "unknown"}, {"extra": "forbidden"},
])
async def test_invalid_request_is_rejected_before_evaluation(admin_client, changes):
    client, _ = admin_client
    payload = {"mode": "countrydle", "entity_id": 31, "question": "Is it in Europe?", **changes}
    assert (await client.post("/admin/question-tests", json=payload)).status_code == 422


async def test_unknown_entity_is_rejected(admin_client):
    client, _ = admin_client
    response = await client.post("/admin/question-tests", json={
        "mode": "countrydle", "entity_id": 999, "question": "Is it in Europe?",
    })
    assert response.status_code == 404
    assert (await client.get("/admin/question-tests/entities?mode=unknown")).status_code == 422


async def test_explicit_target_works_without_day_or_player_and_does_not_write(admin_client, monkeypatch):
    client, _ = admin_client
    patch_country_local(monkeypatch)
    for entity_id, name, expected in [(31, "Poland", True), (82, "Germany", False)]:
        response = await client.post("/admin/question-tests", json={
            "mode": "countrydle", "entity_id": entity_id, "question": "  Is it in Europe?  ",
        })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["entity"] == {"id": entity_id, "name": name}
        assert result["answer"] is expected
        assert result["valid"] is True
        assert result["original_question"] == "Is it in Europe?"
        assert result["source"] == "local_kb"
        assert "day_id" not in result and "user_id" not in result


async def test_invalid_question_is_distinct_from_model_failure(admin_client, monkeypatch):
    client, _ = admin_client
    patch_country_local(monkeypatch, plan(valid=False, supported=False))
    response = await client.post("/admin/question-tests", json={
        "mode": "countrydle", "entity_id": 31, "question": "Tell me the country",
    })
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["answer"] is None
    assert response.json()["source"] == "local_planner"


@pytest.mark.parametrize("mode,entity_id,utility", [
    ("countrydle", 31, "countrydle.utils"), ("us_statedle", 64, "us_statedle.utils"),
    ("powiatdle", 91, "powiatdle.utils"), ("wojewodztwodle", 27, "wojewodztwodle.utils"),
])
async def test_unsupported_plan_uses_daily_retrieval_and_answer_model(admin_client, monkeypatch, mode, entity_id, utility):
    client, _ = admin_client
    module = import_module(utility)
    question_plan = replace(plan(supported=False), improved_question=None)
    planner_name = "analyze_question_for_local_plan" if mode == "countrydle" else "analyze_question"
    monkeypatch.setattr(module, planner_name, lambda *args, **kwargs: question_plan)

    async def fragments(query, *args, **kwargs):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Embedding input must contain question text")
        return [SimpleNamespace(text="Retrieved geographic evidence.")], [0.1]

    monkeypatch.setattr(module, "get_fragments_matching_question", fragments)

    def answer_from_context(prompt):
        return {
            "answer": False if "Retrieved geographic evidence." in prompt else None,
            "explanation": "The retrieved evidence rules this out." if "Retrieved geographic evidence." in prompt else "Insufficient evidence.",
        }

    if mode == "countrydle":
        monkeypatch.setattr(module, "gemini_json", lambda prompt, *args, **kwargs: answer_from_context(prompt))
    else:
        def completion(**kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content=json.dumps(answer_from_context(kwargs["messages"][0]["content"])),
                ))],
                model="test-model", id="test-response", system_fingerprint=None, usage=None,
            )

        client_provider = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
        monkeypatch.setattr(module, "get_openai_client", lambda **kwargs: client_provider)
    response = await client.post("/admin/question-tests", json={
        "mode": mode, "entity_id": entity_id, "question": "Is it in Europe?",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["source"] == "fallback"
    assert result["valid"] is True and result["answer"] is False


@pytest.mark.parametrize("outcome", ["exception", "missing_answer"])
async def test_model_operational_failure_does_not_fabricate_answer(admin_client, monkeypatch, outcome):
    client, _ = admin_client
    patch_country_local(monkeypatch, plan(supported=False))

    async def no_fragments(*args, **kwargs):
        return [], []

    def broken_answer(*args, **kwargs):
        if outcome == "exception":
            raise RuntimeError("provider unavailable; secret provider details")
        return {"explanation": "No usable answer"}

    monkeypatch.setattr("countrydle.utils.get_fragments_matching_question", no_fragments)
    monkeypatch.setattr("countrydle.utils.answer_question_for_entity", broken_answer)
    response = await client.post("/admin/question-tests", json={
        "mode": "countrydle", "entity_id": 31, "question": "Is it in Europe?",
    })
    assert response.status_code == 503
    assert "answer" not in response.json()
    assert "secret provider details" not in response.text


async def test_malformed_planner_response_is_an_operational_error(admin_client, monkeypatch):
    client, _ = admin_client
    monkeypatch.setattr("local_kb_question.gemini_json", lambda *args, **kwargs: {})
    response = await client.post("/admin/question-tests", json={
        "mode": "powiatdle", "entity_id": 91, "question": "Does it have a river?",
    })
    assert response.status_code == 503


@pytest.mark.parametrize("supported", [True, False])
async def test_flagdle_uses_only_local_facts(admin_client, monkeypatch, supported):
    client, _ = admin_client
    patch_country_local(monkeypatch, plan(supported=supported))

    def no_fallback(*args, **kwargs):
        raise AssertionError("Flagdle must not use RAG or fallback answering")

    monkeypatch.setattr("countrydle.utils.ask_question", no_fallback)
    response = await client.post("/admin/question-tests", json={
        "mode": "flagdle", "entity_id": 31, "question": "Is it in Europe?",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["valid"] is supported
    assert result["answer"] is (True if supported else None)
    assert result["source"] == "flag_kb"


async def test_flagdle_missing_facts_is_not_reported_as_invalid_question(admin_client, monkeypatch, tmp_path):
    client, _ = admin_client
    patch_country_local(monkeypatch)
    monkeypatch.setattr("countrydle.local_answering.DEFAULT_DB_PATH", tmp_path / "missing.sqlite")
    response = await client.post("/admin/question-tests", json={
        "mode": "flagdle", "entity_id": 31, "question": "Is it in Europe?",
    })
    assert response.status_code == 503
    assert not (tmp_path / "missing.sqlite").exists()


async def test_flagdle_planner_failure_does_not_fabricate_invalid_question(admin_client, monkeypatch):
    client, _ = admin_client

    def unavailable(*args, **kwargs):
        raise RuntimeError("Planner unavailable")

    monkeypatch.setattr("flagdle.analyze_question_for_local_plan", unavailable)
    response = await client.post("/admin/question-tests", json={
        "mode": "flagdle", "entity_id": 31, "question": "Is it in Europe?",
    })
    assert response.status_code == 503
    assert "valid" not in response.json()


@pytest.mark.parametrize("mode,entity_id", [
    ("us_statedle", 64), ("powiatdle", 91), ("wojewodztwodle", 27),
])
async def test_missing_local_facts_never_creates_sqlite_database(
    admin_client, monkeypatch, tmp_path, mode, entity_id,
):
    client, _ = admin_client
    module = import_module(f"{mode}.utils")
    missing_path = tmp_path / f"{mode}.sqlite"
    monkeypatch.setattr(module, "LOCAL_CONFIG", replace(module.LOCAL_CONFIG, db_path=missing_path))
    monkeypatch.setattr(module, "analyze_question", lambda *args, **kwargs: plan())
    response = await client.post("/admin/question-tests", json={
        "mode": mode, "entity_id": entity_id, "question": "Is it in Europe?",
    })
    assert response.status_code == 503
    assert not missing_path.exists()


async def test_diagnostics_exclude_private_provider_evidence(admin_client, monkeypatch):
    client, _ = admin_client
    patch_country_local(monkeypatch)

    def interpret(*args, evidence, **kwargs):
        evidence.update(
            provider="gemini", model="test-model", cache_hit=False,
            prompt="PRIVATE_SYSTEM_PROMPT", messages=[{"content": "PRIVATE_MESSAGES"}],
            api_key="PRIVATE_API_KEY", raw_response="PRIVATE_RAW_RESPONSE",
            usage={"input_tokens": 0, "output_tokens": 4, "total_tokens": 4, "secret": "PRIVATE_USAGE"},
        )
        return plan()

    monkeypatch.setattr("countrydle.utils.analyze_question_for_local_plan", interpret)
    response = await client.post("/admin/question-tests", json={
        "mode": "countrydle", "entity_id": 31, "question": "Is it in Europe?",
    })
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is True
    diagnostics = response.json()["diagnostics"]
    assert diagnostics["planner"]["usage"]["input_tokens"] == 0
    assert "PRIVATE_" not in response.text
    assert "prompt" not in diagnostics["planner"] and "messages" not in diagnostics["planner"]
