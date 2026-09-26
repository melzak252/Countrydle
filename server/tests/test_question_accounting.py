"""Question accounting against real PostgreSQL transactions, never provider APIs."""
import asyncio
import os
from datetime import date, datetime
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
import db.models as models
from db.models import Country, CountrydleDay, CountrydleQuestion, CountrydleState, User
from db.models.continental import ContinentalDay, ContinentalQuestion, ContinentalState, ContinentCode
from db.models.guest_participation import GuestParticipation
from db.models.powiatdle import PowiatdleDay, PowiatdleQuestion, PowiatdleState
from db.models.us_statedle import USStatedleDay, USStatedleQuestion, USStatedleState
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleQuestion, WojewodztwodleState
from schemas.countrydle import QuestionBase, QuestionCreate

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]
MODES = [
    ("countrydle", CountrydleDay, CountrydleState, CountrydleQuestion, "CountrydleRepository", "get_today_country", "gutils", 10),
    ("continental", ContinentalDay, ContinentalState, ContinentalQuestion, "ContinentalDayRepository", "get_today_day", "gutils", 8),
    ("us_statedle", USStatedleDay, USStatedleState, USStatedleQuestion, "USStatedleDayRepository", "get_today_us_state", "uutils", 8),
    ("powiatdle", PowiatdleDay, PowiatdleState, PowiatdleQuestion, "PowiatdleDayRepository", "get_today_powiat", "putils", 15),
    ("wojewodztwodle", WojewodztwodleDay, WojewodztwodleState, WojewodztwodleQuestion, "WojewodztwodleDayRepository", "get_today_wojewodztwo", "wutils", 5),
]


@pytest.fixture
async def accounting_db():
    url = os.getenv("QUESTION_TEST_DATABASE_URL") or os.getenv("FRIEND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set QUESTION_TEST_DATABASE_URL for isolated PostgreSQL accounting regressions")
    schema = f"question_test_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, pool_size=4, max_overflow=4,
                                 connect_args={"server_settings": {"search_path": schema}})
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            models_needed = (
                "User", "Country", "GuestParticipation", "USState", "Powiat", "Wojewodztwo",
                "CountrydleGuess", "ContinentalGuess", "USStatedleGuess", "PowiatdleGuess",
                "WojewodztwodleGuess", "FlagdleDay", "FlagdleState",
            )
            tables = [getattr(models, name) for name in models_needed]
            for _, day, state, question, *_ in MODES:
                tables.extend((day, state, question))
            dependencies = set(model.__table__ for model in tables)
            for table in list(dependencies):
                for fk in table.foreign_keys:
                    dependencies.add(fk.column.table)
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=list(dependencies)))
        async with factory() as session:
            session.add(User(id=1, username="accounting", email="accounting@example.com", hashed_password="unused"))
            session.add(Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"))
            await session.commit()
        yield factory
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


@pytest.fixture(params=MODES, ids=lambda mode: mode[0])
async def daily_mode(request, accounting_db, monkeypatch):
    name, day_model, state_model, question_model, repo_name, day_method, utils_name, maximum = request.param
    module = import_module(name)
    day_values = {"id": 1, "date": date.today()}
    if name == "continental":
        day_values["continent"] = ContinentCode.EUROPE
    if name in {"countrydle", "continental"}:
        day_values["country_id"] = 1
    async with accounting_db() as session:
        session.add(day_model(**day_values))
        await session.commit()
    day = SimpleNamespace(**{**day_values, "country_id": 1, "us_state_id": 1, "powiat_id": 1, "wojewodztwo_id": 1})

    async def get_day(*args, **kwargs):
        return day

    monkeypatch.setattr(getattr(module, repo_name), day_method, get_day)
    return SimpleNamespace(module=module, name=name, state_model=state_model, question_model=question_model,
                           utils=getattr(module, utils_name), maximum=maximum, factory=accounting_db)


async def request_question(mode, user_id=1):
    async with mode.factory() as session:
        user = await session.get(User, user_id) if user_id else None
        request = Request({"type": "http", "method": "POST", "scheme": "http", "path": "/question", "headers": []})
        # The same durable browser identity across concurrent guest requests.
        request.state.guest_identity = "00000000-0000-0000-0000-000000000001"
        kwargs = dict(question=QuestionBase(question="Is it in Europe?"), user=user,
                      session=session, request=request, response=Response())
        if mode.name == "continental":
            kwargs["continent"] = ContinentCode.EUROPE
        return await mode.module.ask_question(**kwargs)


def provider_result(mode, valid=True, answer=True):
    schema = {
        "countrydle": QuestionCreate, "continental": QuestionCreate,
        "us_statedle": models_to_schema["us_statedle"],
        "powiatdle": models_to_schema["powiatdle"],
        "wojewodztwodle": models_to_schema["wojewodztwodle"],
    }[mode.name]
    return schema(original_question="Is it in Europe?", question="Is it in Europe?",
                  valid=valid, answer=answer, explanation="Evidence unavailable" if answer is None else "Verified fact",
                  context="local_kb:continent", user_id=None, day_id=1)


models_to_schema = {
    mode: getattr(import_module(f"schemas.{mode}"), name)
    for mode, name in (
        ("us_statedle", "USStateQuestionCreate"),
        ("powiatdle", "PowiatQuestionCreate"),
        ("wojewodztwodle", "WojewodztwoQuestionCreate"),
    )
}


@pytest.mark.parametrize("guest", [False, True])
@pytest.mark.parametrize("fallback", [False, True])
async def test_unresolved_and_invalid_leave_quota_and_history_unchanged(daily_mode, monkeypatch, guest, fallback):
    mode = daily_mode
    plan = SimpleNamespace(valid=True, improved_question="Is it in Europe?", explanation="Evidence unavailable")
    for valid, answer in [(True, None), (False, False)]:
        async def local(*args, **kwargs):
            return (None if fallback else provider_result(mode, valid, answer)), plan

        async def ask(*args, **kwargs):
            return provider_result(mode, valid, answer), None

        monkeypatch.setattr(mode.utils, "analyze_and_answer_locally", local)
        monkeypatch.setattr(mode.utils, "question_enhanced_from_plan", lambda *args: plan)
        monkeypatch.setattr(mode.utils, "ask_question", ask)
        if mode.name == "countrydle" and valid and answer is None:
            with pytest.raises(HTTPException) as error:
                await request_question(mode, None if guest else 1)
            assert error.value.status_code == 503
        else:
            result = await request_question(mode, None if guest else 1)
            assert result.valid is False
            assert getattr(result, "answer", None) is None
    async with mode.factory() as session:
        assert await session.scalar(select(func.count()).select_from(mode.question_model)) == 0
        states = list((await session.scalars(select(mode.state_model))).all())
        assert all(state.questions_asked == 0 for state in states)
        assert await session.scalar(select(func.coalesce(func.sum(GuestParticipation.questions_asked), 0))) == 0


@pytest.mark.parametrize("guest", [False, True])
async def test_true_and_false_each_consume_once(daily_mode, monkeypatch, guest):
    mode = daily_mode
    for answer in [True, False]:
        async def local(*args, **kwargs):
            return provider_result(mode, answer=answer), None

        monkeypatch.setattr(mode.utils, "analyze_and_answer_locally", local)
        result = await request_question(mode, None if guest else 1)
        assert result.valid is True and result.answer is answer
    async with mode.factory() as session:
        questions = list((await session.scalars(select(mode.question_model).order_by(mode.question_model.id))).all())
        assert [q.answer for q in questions] == [True, False]
        if guest:
            assert await session.scalar(select(GuestParticipation.questions_asked)) == 2
        else:
            state = (await session.scalars(select(mode.state_model))).one()
            assert (state.questions_asked, state.remaining_questions) == (2, mode.maximum - 2)
            assert {q.user_id for q in questions} == {1}


@pytest.mark.parametrize("guest", [False, True])
async def test_concurrent_last_slot_commits_one_question(daily_mode, monkeypatch, guest):
    mode = daily_mode
    async with mode.factory() as session:
        if guest:
            session.add(GuestParticipation(guest_id="00000000-0000-0000-0000-000000000001",
                mode="continental:europe" if mode.name == "continental" else mode.name,
                day_id=1, questions_asked=mode.maximum - 1, guesses_made=0, won=False))
        else:
            session.add(mode.state_model(user_id=1, day_id=1, questions_asked=mode.maximum - 1,
                                         remaining_questions=1, remaining_guesses=3))
        await session.commit()
    entered = 0
    both = asyncio.Event()

    async def local(*args, **kwargs):
        nonlocal entered
        entered += 1
        if entered == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 5)
        return provider_result(mode, answer=False), None

    monkeypatch.setattr(mode.utils, "analyze_and_answer_locally", local)
    results = await asyncio.gather(*(request_question(mode, None if guest else 1) for _ in range(2)), return_exceptions=True)
    assert sum(isinstance(result, HTTPException) and result.status_code == 400 for result in results) == 1
    assert sum(getattr(result, "valid", False) is True for result in results) == 1
    async with mode.factory() as session:
        assert await session.scalar(select(func.count()).select_from(mode.question_model)) == 1
        if guest:
            assert await session.scalar(select(GuestParticipation.questions_asked)) == mode.maximum
        else:
            state = (await session.scalars(select(mode.state_model))).one()
            assert (state.questions_asked, state.remaining_questions) == (mode.maximum, 0)


async def test_provider_failure_does_not_consume_or_persist(daily_mode, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(daily_mode.utils, "analyze_and_answer_locally", fail)
    if daily_mode.name == "countrydle":
        with pytest.raises(HTTPException) as error:
            await request_question(daily_mode)
        assert error.value.status_code == 503
    else:
        result = await request_question(daily_mode)
        assert result.valid is False and getattr(result, "answer", None) is None
    async with daily_mode.factory() as session:
        assert await session.scalar(select(func.count()).select_from(daily_mode.question_model)) == 0
        assert all(state.questions_asked == 0 for state in (await session.scalars(select(daily_mode.state_model))).all())


async def test_concurrent_first_questions_keep_both_answers_and_one_state(daily_mode, monkeypatch):
    mode = daily_mode
    entered = 0
    both = asyncio.Event()

    async def local(*args, **kwargs):
        nonlocal entered
        entered += 1
        if entered == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 5)
        return provider_result(mode, answer=False), None

    monkeypatch.setattr(mode.utils, "analyze_and_answer_locally", local)
    results = await asyncio.gather(request_question(mode), request_question(mode))
    assert all(result.valid and result.answer is False for result in results)
    async with mode.factory() as session:
        state = (await session.scalars(select(mode.state_model))).one()
        assert (state.questions_asked, state.remaining_questions) == (2, mode.maximum - 2)
        assert await session.scalar(select(func.count()).select_from(mode.question_model)) == 2


async def test_rejected_persistence_rolls_back_question_and_quota(daily_mode, monkeypatch):
    mode = daily_mode

    async def local(*args, **kwargs):
        return provider_result(mode), None

    monkeypatch.setattr(mode.utils, "analyze_and_answer_locally", local)
    # A real failed INSERT after the state has been staged must roll back both.
    table = mode.question_model.__tablename__
    async with mode.factory() as session:
        await session.execute(text(
            f'ALTER TABLE "{table}" ADD CONSTRAINT reject_test_question CHECK (original_question <> \'Is it in Europe?\')'
        ))
        await session.commit()
    if mode.name == "countrydle":
        with pytest.raises(HTTPException) as error:
            await request_question(mode)
        assert error.value.status_code == 503
    else:
        result = await request_question(mode)
        assert result.valid is False and getattr(result, "answer", None) is None
    async with mode.factory() as session:
        assert await session.scalar(select(func.count()).select_from(mode.question_model)) == 0
        assert all(state.questions_asked == 0 for state in (await session.scalars(select(mode.state_model))).all())


async def test_guest_sync_counts_only_claimed_boolean_history_and_preserves_existing_progress(daily_mode):
    mode = daily_mode
    async with mode.factory() as session:
        session.add_all([
            mode.question_model(id=1, day_id=1, original_question="Known yes?", question="Known yes?",
                                valid=True, answer=True, explanation="Verified fact"),
            mode.question_model(id=2, day_id=1, original_question="Known no?", question="Known no?",
                                valid=True, answer=False, explanation="Verified fact"),
            mode.question_model(id=3, day_id=1, original_question="Unknown?", question="Unknown?",
                                valid=True, answer=None, explanation="No evidence"),
            mode.question_model(id=4, day_id=1, original_question="Invalid?", question="Invalid?",
                                valid=False, answer=False, explanation="Invalid"),
        ])
        await session.commit()
    schema_name = {
        "countrydle": "CountrydleSyncSchema", "continental": "ContinentalSyncSchema",
        "us_statedle": "USStatedleSyncSchema", "powiatdle": "PowiatdleSyncSchema",
        "wojewodztwodle": "WojewodztwodleSyncSchema",
    }[mode.name]
    schema = getattr(mode.module, schema_name)
    body = schema.model_validate({
        "date": str(date.today()), "questions": [1, 1, 2, 3, 4, 999999], "guesses": [],
        "state": {"questions_asked": mode.maximum, "remaining_questions": 0, "guesses_made": 0,
                  "remaining_guesses": 2 if mode.name == "wojewodztwodle" else 3,
                  "won": False, "is_game_over": False},
    })
    for _ in range(2):
        async with mode.factory() as session:
            user = await session.get(User, 1)
            kwargs = dict(sync_data=body, user=user, session=session,
                          request=Request({"type": "http", "headers": []}))
            if mode.name == "continental":
                kwargs["continent"] = ContinentCode.EUROPE
            result = await mode.module.sync_guest_data(**kwargs)
            assert (result.state.questions_asked, result.state.remaining_questions) == (2, mode.maximum - 2)
            assert {question.id: question.answer for question in result.questions} == {1: True, 2: False}
    async with mode.factory() as session:
        unresolved = await session.get(mode.question_model, 3)
        invalid = await session.get(mode.question_model, 4)
        assert unresolved.user_id is None and invalid.user_id is None


@pytest.mark.parametrize("guest", [False, True])
async def test_flag_null_is_unresolved_but_false_and_true_are_counted(accounting_db, monkeypatch, guest):
    import flagdle

    async with accounting_db() as session:
        session.add(models.FlagdleDay(id=1, country_id=1, date=date.today()))
        await session.commit()
    day = SimpleNamespace(id=1, country_id=1, country=SimpleNamespace(name="Poland"))

    async def get_day(*args):
        return day

    monkeypatch.setattr(flagdle.FlagdleDayRepository, "get_today_flag", get_day)
    monkeypatch.setattr(flagdle, "analyze_question_for_local_plan", lambda _: SimpleNamespace(
        valid=True, plan={"relation": "flag_colors"}, improved_question="Is it red?", explanation="A flag question",
    ))
    count = 0
    for answer in [None, False, True]:
        monkeypatch.setattr(flagdle, "execute_local_plan", lambda *args, **kwargs: SimpleNamespace(
            answer=answer, question="Is it red?", explanation="Verified flag fact", relation="flag_colors",
        ))
        async with accounting_db() as session:
            user = None if guest else await session.get(User, 1)
            request = Request({"type": "http", "scheme": "http", "path": "/question", "headers": []})
            request.state.guest_identity = "00000000-0000-0000-0000-000000000001"
            result = await flagdle.ask_flag_question(
                QuestionBase(question="Is it red?"), request, Response(), user, session,
            )
        assert result.valid is (answer is not None)
        assert result.answer is answer
        count += int(answer is not None)
        async with accounting_db() as session:
            model = GuestParticipation if guest else models.FlagdleState
            assert await session.scalar(select(func.coalesce(func.sum(model.questions_asked), 0))) == count


async def test_flag_planner_does_not_block_event_loop(accounting_db, monkeypatch):
    import flagdle
    import threading

    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = threading.Event()

    async def get_day(*args):
        return SimpleNamespace(id=1, country_id=1, country=SimpleNamespace(name="Poland"))

    def plan_question(question):
        loop.call_soon_threadsafe(entered.set)
        if not release.wait(3):
            raise TimeoutError("Event loop could not release planner")
        return SimpleNamespace(valid=False, explanation="Unknown")

    monkeypatch.setattr(flagdle.FlagdleDayRepository, "get_today_flag", get_day)
    monkeypatch.setattr(flagdle, "analyze_question_for_local_plan", plan_question)
    async with accounting_db() as session:
        task = asyncio.create_task(flagdle.ask_flag_question(
            QuestionBase(question="Unknown?"),
            Request({"type": "http", "headers": []}), Response(), None, session,
        ))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert not task.done()
        finally:
            release.set()
            result = await task
        assert result.valid is False and result.answer is None


async def test_guest_sync_filling_quota_rejects_an_inflight_answer(daily_mode, monkeypatch):
    mode = daily_mode
    async with mode.factory() as session:
        session.add_all([
            mode.question_model(day_id=1, original_question=f"Known {index}?", question=f"Known {index}?",
                                valid=True, answer=False, explanation="Verified fact")
            for index in range(mode.maximum)
        ])
        await session.commit()
        ids = list((await session.scalars(select(mode.question_model.id))).all())
    entered, release = asyncio.Event(), asyncio.Event()

    async def local(*args, **kwargs):
        entered.set()
        await release.wait()
        return provider_result(mode), None

    monkeypatch.setattr(mode.utils, "analyze_and_answer_locally", local)
    pending = asyncio.create_task(request_question(mode))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        schema_name = {
            "countrydle": "CountrydleSyncSchema", "continental": "ContinentalSyncSchema",
            "us_statedle": "USStatedleSyncSchema", "powiatdle": "PowiatdleSyncSchema",
            "wojewodztwodle": "WojewodztwodleSyncSchema",
        }[mode.name]
        body = getattr(mode.module, schema_name).model_validate({
            "date": str(date.today()), "questions": ids, "guesses": [],
            "state": {"questions_asked": mode.maximum, "remaining_questions": 0, "guesses_made": 0,
                      "remaining_guesses": 2 if mode.name == "wojewodztwodle" else 3,
                      "won": False, "is_game_over": False},
        })
        async with mode.factory() as session:
            user = await session.get(User, 1)
            kwargs = dict(sync_data=body, user=user, session=session,
                          request=Request({"type": "http", "headers": []}))
            if mode.name == "continental":
                kwargs["continent"] = ContinentCode.EUROPE
            synced = await asyncio.wait_for(mode.module.sync_guest_data(**kwargs), 2)
            assert synced.state.remaining_questions == 0
    finally:
        release.set()
        outcomes = await asyncio.gather(pending, return_exceptions=True)
    assert isinstance(outcomes[0], HTTPException) and outcomes[0].status_code == 400
    async with mode.factory() as session:
        state = (await session.scalars(select(mode.state_model))).one()
        assert (state.questions_asked, state.remaining_questions) == (mode.maximum, 0)
        assert await session.scalar(select(func.count()).select_from(mode.question_model)) == mode.maximum


async def test_concurrent_guess_only_sync_imports_once(daily_mode, monkeypatch):
    mode = daily_mode
    guess_model = getattr(models, {
        "countrydle": "CountrydleGuess", "continental": "ContinentalGuess",
        "us_statedle": "USStatedleGuess", "powiatdle": "PowiatdleGuess",
        "wojewodztwodle": "WojewodztwodleGuess",
    }[mode.name])
    repository = getattr(mode.module, {
        "countrydle": "CountrydleGuessRepository", "continental": "ContinentalGuessRepository",
        "us_statedle": "USStatedleGuessRepository", "powiatdle": "PowiatdleGuessRepository",
        "wojewodztwodle": "WojewodztwodleGuessRepository",
    }[mode.name])
    async with mode.factory() as session:
        session.add_all([
            Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"),
            models.USState(id=1, name="California"),
            models.Powiat(id=1, nazwa="Kraków"), models.Wojewodztwo(id=1, nazwa="Dolnośląskie"),
            mode.state_model(user_id=1, day_id=1, questions_asked=0, remaining_questions=mode.maximum,
                             guesses_made=0, remaining_guesses=3, is_game_over=False, won=False),
        ])
        await session.commit()
    add_guess = repository.add_guess

    async def yield_after_insert(self, guess, **kwargs):
        result = await add_guess(self, guess, **kwargs)
        # Force overlap between row insertion and final state update, not a timing assertion.
        await asyncio.sleep(0.03)
        return result

    monkeypatch.setattr(repository, "add_guess", yield_after_insert)
    body = SimpleNamespace(
        date=str(date.today()), questions=[],
        guesses=[SimpleNamespace(guess="Germany", country_id=2, us_state_id=1, powiat_id=1,
                                 wojewodztwo_id=1, elapsed_seconds=None)],
        state=SimpleNamespace(guesses_made=1, remaining_guesses=1 if mode.name == "wojewodztwodle" else 2, is_game_over=False, won=False),
    )

    async def sync():
        async with mode.factory() as session:
            kwargs = dict(sync_data=body, user=await session.get(User, 1), session=session,
                          request=Request({"type": "http", "headers": []}))
            if mode.name == "continental":
                kwargs["continent"] = ContinentCode.EUROPE
            return await mode.module.sync_guest_data(**kwargs)

    await asyncio.gather(sync(), sync())
    async with mode.factory() as session:
        assert await session.scalar(select(func.count()).select_from(guess_model)) == 1
        assert (await session.scalar(select(mode.state_model))).guesses_made == 1


async def test_flag_post_game_questions_remain_unlimited(accounting_db, monkeypatch):
    import flagdle

    async with accounting_db() as session:
        session.add(models.FlagdleDay(id=1, country_id=1, date=date.today()))
        await session.flush()
        session.add(models.FlagdleState(user_id=1, day_id=1, is_game_over=True, remaining_guesses=0,
                                       guesses_made=12, questions_asked=2))
        await session.commit()
    monkeypatch.setattr(flagdle, "analyze_question_for_local_plan", lambda _: SimpleNamespace(
        valid=True, plan={"operator": "exists"}, improved_question="Is it blue?", explanation=None,
    ))
    monkeypatch.setattr(flagdle, "execute_local_plan", lambda *args, **kwargs: SimpleNamespace(
        answer=False, question="Is it blue?", explanation="No blue on the flag.", relation="flag_color",
    ))
    async with accounting_db() as session:
        result = await flagdle.ask_flag_question(
            QuestionBase(question="Is it blue?"), Request({"type": "http", "headers": []}), Response(),
            await session.get(User, 1), session,
        )
        assert result.valid is True and result.answer is False
    async with accounting_db() as session:
        state = await session.scalar(select(models.FlagdleState))
        assert state.questions_asked == 3 and state.is_game_over is True
