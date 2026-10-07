"""Durable fallback-answer reuse through the production async runner and SQL cache."""
from collections import deque
from datetime import date
import asyncio
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.base import Base


@pytest.fixture
async def fallback_db(tmp_path):
    from db.repositories import fallback_answers as cache

    path = tmp_path / "fallback.sqlite"
    url = f"sqlite+aiosqlite:///{path}"

    cache_tables = [Base.metadata.tables["fallback_answers"],
                    Base.metadata.tables["fallback_answer_blocks"]]

    async def open_database():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(sync_connection, tables=cache_tables)
            )
        return engine, async_sessionmaker(engine, expire_on_commit=False)

    engine, sessions = await open_database()
    yield SimpleNamespace(cache=cache, path=path, url=url, engine=engine, sessions=sessions,
                          open_database=open_database)
    await engine.dispose()

@pytest.fixture
def fallback(monkeypatch, fallback_db):
    from utils import fallback as runner
    from utils import fallback_answers

    monkeypatch.setenv("GEMINI_QUIZ_MODEL", "test-model-a")
    responses = deque()
    provider_calls = []
    retrievals = []
    state = SimpleNamespace(context="Poland hosted the event in 2001.",
                            prompts=("Stable game rules.", "Exact question data."),
                            provider_entered=None, provider_release=None,
                            today=date(2026, 10, 4))
    monkeypatch.setattr(runner, "utc_today", lambda: state.today)

    def provider(*args, **kwargs):
        if state.provider_entered is not None:
            state.provider_entered.set()
            if not state.provider_release.wait(timeout=5):
                raise TimeoutError("Test did not release the provider")
        provider_calls.append(kwargs.copy())
        evidence = kwargs.get("evidence")
        if evidence is not None:
            evidence.update(provider="gemini", usage={"input_tokens": 100}, response_id="paid")
        result = responses.popleft()
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(fallback_answers, "gemini_json", provider)

    async def retrieve(*args, **kwargs):
        retrievals.append(kwargs)
        return [SimpleNamespace(text=state.context)] if state.context else [], [0.1]

    monkeypatch.setattr(runner, "get_fragments_matching_question", retrieve)

    def prompt_builder(question, entity_name, context):
        return state.prompts

    def answerer(question, entity_name, context, *, model, deadline, evidence=None):
        system_prompt, question_prompt = prompt_builder(question, entity_name, context)
        return fallback_answers.get_answer(system_prompt, question_prompt, model=model,
                                           deadline=deadline, evidence=evidence)

    question = SimpleNamespace(original_question="Did it host the event?",
                               question="Did the country host the event?")
    arguments = dict(question=question, entity_name="Poland", cache_scope=("countrydle", 31),
                     filter_key="country_id", filter_value=31, collection_name="countrydle",
                     context_limit=5, answerer=answerer, prompt_builder=prompt_builder)

    async def run(*, evidence=None, session=None, **changes):
        async with fallback_db.sessions() as owned_session:
            return await runner.retrieve_and_answer(
                **(arguments | changes), session=session or owned_session, evidence=evidence,
            )

    def answer(value, explanation=None):
        if explanation is None:
            explanation = "The country hosted the event." if value is True else "The country did not host the event."
        return {"answer": value, "explanation": explanation}

    return SimpleNamespace(db=fallback_db, cache=fallback_db.cache, responses=responses,
                           provider_calls=provider_calls, retrievals=retrievals, state=state,
                           arguments=arguments, run=run, answer=answer, prompt_builder=prompt_builder)


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.anyio
async def test_committed_answer_survives_worker_restart_as_fresh_unbilled_result(fallback, value, monkeypatch):
    fallback.responses.extend([fallback.answer(value), fallback.answer(not value)])
    first_evidence = {}
    first, context, vector = await fallback.run(evidence=first_evidence)
    assert first["answer"] is value
    first["explanation"] = "caller mutation"
    await fallback.db.engine.dispose()
    engine, sessions = await fallback.db.open_database()
    fallback.db.engine = engine
    fallback.db.sessions = sessions

    hit_evidence = {}
    second, second_context, second_vector = await fallback.run(evidence=hit_evidence)
    assert second == fallback.answer(value)
    assert second is not first
    assert second_context == context
    assert second_vector == vector
    assert len(fallback.provider_calls) == 1
    assert len(fallback.retrievals) == 2
    assert hit_evidence["fallback"]["provider"] == "answer_cache"
    assert hit_evidence["fallback"]["cache_hit"] is True
    assert "usage" not in hit_evidence["fallback"]
    await engine.dispose()


@pytest.mark.parametrize("changes", [
    {"cache_scope": ("powiatdle", 31)},
    {"cache_scope": ("countrydle", 32)},
    {"entity_name": "Republic of Poland"},
    {"question": SimpleNamespace(original_question="Did Poland host the event?", question="Did the country host the event?")},
    {"question": SimpleNamespace(original_question="Did it host the event?", question="Did Poland host the event?")},
])
@pytest.mark.anyio
async def test_changed_identity_scope_cannot_reuse(fallback, changes):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])
    await fallback.run()
    result, _, _ = await fallback.run(**changes)
    assert result["answer"] is False
    assert len(fallback.provider_calls) == 2


@pytest.mark.parametrize("change", ["context", "model", "system prompt", "question prompt", "date"])
@pytest.mark.anyio
async def test_changed_evidence_model_prompt_or_daily_date_cannot_reuse(fallback, monkeypatch, change):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])
    await fallback.run()
    if change == "context":
        fallback.state.context = "Poland hosted the event in 2002."
    elif change == "model":
        monkeypatch.setenv("GEMINI_QUIZ_MODEL", "test-model-b")
    elif change == "system prompt":
        fallback.state.prompts = ("Revised game rules.", "Exact question data.")
    elif change == "question prompt":
        fallback.state.prompts = ("Stable game rules.", "Revised exact question data.")
    else:
        fallback.state.today = date(2026, 10, 5)
    result, _, _ = await fallback.run()
    assert result["answer"] is False
    assert len(fallback.provider_calls) == 2


@pytest.mark.parametrize("changes", [{"context": ""}, {"cache_scope": None}])
@pytest.mark.anyio
async def test_empty_context_and_scope_less_diagnostics_bypass_persistence(fallback, changes):
    fallback.responses.extend([fallback.answer(False), fallback.answer(True)])
    changes = dict(changes)
    if "context" in changes:
        fallback.state.context = changes.pop("context")
    result, _, _ = await fallback.run(**changes)
    assert result["answer"] is False
    result, _, _ = await fallback.run(**changes)
    assert result["answer"] is True
    assert len(fallback.provider_calls) == 2


@pytest.mark.anyio
async def test_null_malformed_and_provider_error_do_not_poison_later_answer(fallback):
    fallback.responses.extend([fallback.answer(None), {"answer": "false", "explanation": "bad"},
                               RuntimeError("provider failed"), fallback.answer(True)])
    assert (await fallback.run())[0]["answer"] is None
    with pytest.raises(ValueError):
        await fallback.run()
    with pytest.raises(RuntimeError, match="provider failed"):
        await fallback.run()
    assert (await fallback.run())[0]["answer"] is True
    assert len(fallback.provider_calls) == 4


@pytest.mark.anyio
async def test_exact_accented_question_identity_is_not_folded(fallback):
    accented = SimpleNamespace(original_question="Does it contain 'é'?", question="Does it contain 'é'?")
    plain = SimpleNamespace(original_question="Does it contain 'e'?", question="Does it contain 'e'?")
    fallback.responses.extend([fallback.answer(False), fallback.answer(True)])
    assert (await fallback.run(question=accented))[0]["answer"] is False
    assert (await fallback.run(question=plain))[0]["answer"] is True
    assert len(fallback.provider_calls) == 2


@pytest.mark.anyio
async def test_continental_and_country_scopes_share_canonical_country_answer(fallback):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])
    await fallback.run(cache_scope=("continental", 31))
    result, _, _ = await fallback.run(cache_scope=("countrydle", 31))
    assert result["answer"] is True
    assert len(fallback.provider_calls) == 1
    assert len(fallback.retrievals) == 2


@pytest.mark.anyio
async def test_report_committed_during_generation_prevents_late_cache_repopulation(fallback):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])
    entered = threading.Event()
    release = threading.Event()
    fallback.state.provider_entered = entered
    fallback.state.provider_release = release

    generation = asyncio.create_task(fallback.run())
    assert await asyncio.to_thread(entered.wait, 5), "Provider did not start"
    try:
        async with fallback.db.sessions() as report_session:
            await fallback.cache.invalidate(
                report_session, mode="countrydle", entity_name="Poland",
                original_question=fallback.arguments["question"].original_question,
                question=fallback.arguments["question"].question,
                context=fallback.state.context, game_date=fallback.state.today,
            )
            await report_session.commit()
    finally:
        release.set()

    assert (await generation)[0]["answer"] is True
    fallback.state.provider_entered = None
    result, _, _ = await fallback.run()
    assert result["answer"] is False
    assert len(fallback.provider_calls) == 2


@pytest.mark.anyio
async def test_custom_game_date_aligns_cache_identity_and_report_invalidation(fallback):
    custom_date = date(2026, 9, 29)
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])

    # 1. First run with custom_date caches the answer
    first, _, _ = await fallback.run(game_date=custom_date)
    assert first["answer"] is True
    assert len(fallback.provider_calls) == 1

    # 2. Second run with custom_date is a cache hit (provider not called again)
    second_evidence = {}
    second, _, _ = await fallback.run(game_date=custom_date, evidence=second_evidence)
    assert second["answer"] is True
    assert len(fallback.provider_calls) == 1
    assert second_evidence.get("fallback", {}).get("cache_hit") is True

    # 3. Report invalidates under custom_date
    async with fallback.db.sessions() as report_session:
        await fallback.cache.invalidate(
            report_session,
            mode="countrydle",
            entity_name="Poland",
            original_question=fallback.arguments["question"].original_question,
            question=fallback.arguments["question"].question,
            context=fallback.state.context,
            game_date=custom_date,
        )
        await report_session.commit()

    # 4. Third run with custom_date misses cache due to block, calls provider
    third, _, _ = await fallback.run(game_date=custom_date)
    assert third["answer"] is False
    assert len(fallback.provider_calls) == 2
