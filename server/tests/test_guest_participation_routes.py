"""Exercise solo API activity with real repositories in a disposable PostgreSQL schema."""
from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from db.models.guest_participation import GuestParticipation
from tests.test_guest_participation import participation_db
from utils.guest_session import GUEST_IDENTITY_COOKIE

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]


@pytest.fixture
async def solo_client(participation_db):
    from app import app
    from db import get_db
    from db.base import Base
    import db.models as models
    from users.utils import get_current_or_guest_user

    model_names = (
        "Country", "CountrydleDay", "CountrydleState", "CountrydleQuestion", "CountrydleGuess",
        "USState", "USStatedleDay", "USStatedleState", "USStatedleQuestion", "USStatedleGuess",
        "Powiat", "PowiatdleDay", "PowiatdleState", "PowiatdleQuestion", "PowiatdleGuess",
        "Wojewodztwo", "WojewodztwodleDay", "WojewodztwodleState", "WojewodztwodleQuestion", "WojewodztwodleGuess",
        "ContinentalDay", "ContinentalState", "ContinentalQuestion", "ContinentalGuess",
        "FlagdleDay", "FlagdleState", "FlagdleGuess",
    )
    async with participation_db() as session:
        connection = await session.connection()
        await connection.run_sync(lambda conn: Base.metadata.create_all(
            conn, tables=[getattr(models, name).__table__ for name in model_names]
        ))
        session.add_all([
            models.Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"),
            models.Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"),
            models.USState(id=1, name="Texas"), models.USState(id=2, name="Alaska"),
            models.Powiat(id=1, nazwa="warszawski"), models.Powiat(id=2, nazwa="krakowski"),
            models.Wojewodztwo(id=1, nazwa="mazowieckie"), models.Wojewodztwo(id=2, nazwa="pomorskie"),
        ])
        await session.flush()
        session.add_all([
            models.CountrydleDay(id=1, country_id=1, date=date.today()),
            models.USStatedleDay(id=1, us_state_id=1, date=date.today()),
            models.PowiatdleDay(id=1, powiat_id=1, date=date.today()),
            models.WojewodztwodleDay(id=1, wojewodztwo_id=1, date=date.today()),
            models.ContinentalDay(id=1, continent=models.ContinentCode.EUROPE, country_id=1, date=date.today()),
            models.FlagdleDay(id=1, country_id=1, date=date.today()),
        ])
        await session.commit()

    async def isolated_session():
        async with participation_db() as session:
            yield session

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = isolated_session
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("mode", [
    "countrydle", "us_statedle", "powiatdle", "wojewodztwodle", "continental/europe", "flagdle",
])
async def test_guest_state_establishes_identity_before_questions_without_counting_a_move(
    solo_client, participation_db, mode
):
    response = await solo_client.get(f"/{mode}/state")
    assert response.status_code == 200, response.text
    identity = solo_client.cookies.get(GUEST_IDENTITY_COOKIE)
    assert identity is not None
    await solo_client.get(f"/{mode}/state")
    assert solo_client.cookies.get(GUEST_IDENTITY_COOKIE) == identity
    async with participation_db() as session:
        assert await session.scalar(select(func.count()).select_from(GuestParticipation)) == 0


@pytest.mark.parametrize("mode,payload", [
    ("countrydle", {"guess": "Germany", "country_id": 2}),
    ("us_statedle", {"guess": "Alaska", "us_state_id": 2}),
    ("powiatdle", {"guess": "krakowski", "powiat_id": 2}),
    ("wojewodztwodle", {"guess": "pomorskie", "wojewodztwo_id": 2}),
    ("continental/europe", {"guess": "Germany", "country_id": 2}),
    ("flagdle", {"guess": "Germany", "country_id": 2}),
])
async def test_state_then_repeated_guesses_record_one_browser(solo_client, participation_db, mode, payload):
    state = await solo_client.get(f"/{mode}/state")
    assert state.status_code == 200, state.text
    identity_cookie = solo_client.cookies.get(GUEST_IDENTITY_COOKIE)
    assert identity_cookie
    async with participation_db() as session:
        assert await session.scalar(select(func.count()).select_from(GuestParticipation)) == 0
    invalid = await solo_client.post(f"/{mode}/guess", json={})
    assert invalid.status_code == 422
    async with participation_db() as session:
        assert await session.scalar(select(func.count()).select_from(GuestParticipation)) == 0
    for _ in range(2):
        result = await solo_client.post(f"/{mode}/guess", json=payload)
        assert result.status_code == 200, result.text
    assert solo_client.cookies.get(GUEST_IDENTITY_COOKIE) == identity_cookie
    async with participation_db() as session:
        row = (await session.scalars(select(GuestParticipation))).one()
        assert (row.mode, row.day_id, row.guesses_made, row.questions_asked, row.won) == (
            mode.replace("/", ":"), 1, 2, 0, False,
        )


@pytest.mark.parametrize("mode,utility,schema_name", [
    ("countrydle", "countrydle.utils", "QuestionCreate"),
    ("continental/europe", "countrydle.utils", "QuestionCreate"),
    ("us_statedle", "us_statedle.utils", "USStateQuestionCreate"),
    ("powiatdle", "powiatdle.utils", "PowiatQuestionCreate"),
    ("wojewodztwodle", "wojewodztwodle.utils", "WojewodztwoQuestionCreate"),
])
async def test_only_valid_questions_create_participation(
    solo_client, participation_db, monkeypatch, mode, utility, schema_name
):
    schema_module = "countrydle" if mode.startswith("continental") else mode
    schema = getattr(import_module(f"schemas.{schema_module}"), schema_name)
    answer = schema(
        original_question="Is it in Europe?", question="Is it in Europe?",
        valid=False, answer=None, explanation="Unsupported question",
        user_id=None, day_id=1, context=None,
    )
    planner = AsyncMock(return_value=(answer, None))
    monkeypatch.setattr(f"{utility}.analyze_and_answer_locally", planner)
    invalid = await solo_client.post(f"/{mode}/question", json={"question": "Is it in Europe?"})
    assert invalid.status_code == 200, invalid.text
    async with participation_db() as session:
        assert await session.scalar(select(func.count()).select_from(GuestParticipation)) == 0
    planner.return_value = (answer.model_copy(update={"valid": True, "answer": True}), None)
    valid = await solo_client.post(f"/{mode}/question", json={"question": "Is it in Europe?"})
    assert valid.status_code == 200, valid.text
    async with participation_db() as session:
        row = (await session.scalars(select(GuestParticipation))).one()
        assert (row.mode, row.questions_asked, row.guesses_made) == (mode.replace("/", ":"), 1, 0)


async def test_flag_questions_and_sync_keep_question_only_player(solo_client, participation_db, monkeypatch):
    from app import app
    from db.models.flagdle import FlagdleState
    from users.utils import get_current_user, get_current_or_guest_user
    plan = SimpleNamespace(valid=False, plan=None, improved_question="Is it red?", explanation="Invalid")
    monkeypatch.setattr("flagdle.analyze_question_for_local_plan", lambda _: plan)
    monkeypatch.setattr("flagdle.execute_local_plan", lambda *args, **kwargs: SimpleNamespace(
        question="Is it red?", answer=True, explanation="Red stripe", relation="colors",
    ))
    invalid = await solo_client.post("/flagdle/question", json={"question": "Is it red?"})
    assert invalid.status_code == 200, invalid.text
    async with participation_db() as session:
        assert await session.scalar(select(func.count()).select_from(GuestParticipation)) == 0
    plan.valid, plan.plan = True, {"relation": "colors"}
    result = await solo_client.post("/flagdle/question", json={"question": "Is it red?"})
    assert result.status_code == 200, result.text
    user = SimpleNamespace(id=1, username="first", email="first@example.com", verified=True)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_or_guest_user] = lambda: user
    payload = {
        "date": str(date.today()), "guesses": [],
        "state": {"remaining_guesses": 12, "guesses_made": 0, "revealed_stage": 1, "is_game_over": False, "won": False},
    }
    for _ in range(2):
        synced = await solo_client.post("/flagdle/sync", json=payload)
        assert synced.status_code == 200, synced.text
    account_question = await solo_client.post("/flagdle/question", json={"question": "Is it red?"})
    assert account_question.status_code == 200, account_question.text
    async with participation_db() as session:
        guest = (await session.scalars(select(GuestParticipation))).one()
        state = (await session.scalars(select(FlagdleState))).one()
        assert (guest.user_id, guest.questions_asked, guest.guesses_made) == (1, 1, 0)
        assert (state.questions_asked, state.guesses_made) == (2, 0)


async def test_sync_links_guest_even_when_account_already_has_progress(solo_client, participation_db):
    from app import app
    from db.models import CountrydleState
    from users.utils import get_current_user, get_current_or_guest_user

    guessed = await solo_client.post("/countrydle/guess", json={"guess": "Germany", "country_id": 2})
    assert guessed.status_code == 200, guessed.text
    user = SimpleNamespace(id=1, username="first", email="first@example.com", verified=True)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_or_guest_user] = lambda: user
    # GET creates an untouched account state, not a second participant.
    viewed = await solo_client.get("/countrydle/state")
    assert viewed.status_code == 200, viewed.text
    account_guess = await solo_client.post("/countrydle/guess", json={"guess": "Germany", "country_id": 2})
    assert account_guess.status_code == 200, account_guess.text
    payload = {
        "date": str(date.today()), "questions": [],
        "guesses": [{"guess": "Germany", "country_id": 2}],
        "state": {"remaining_questions": 10, "questions_asked": 0, "remaining_guesses": 2,
                  "guesses_made": 1, "is_game_over": False, "won": False},
    }
    for _ in range(2):
        synced = await solo_client.post("/countrydle/sync", json=payload)
        assert synced.status_code == 200, synced.text
    async with participation_db() as session:
        guest = (await session.scalars(select(GuestParticipation))).one()
        account = (await session.scalars(select(CountrydleState))).one()
        assert (guest.user_id, guest.guesses_made) == (1, 1)
        assert account.guesses_made == 1
        active_accounts = await session.scalar(select(func.count()).select_from(CountrydleState).where(
            (CountrydleState.questions_asked > 0) | (CountrydleState.guesses_made > 0)
        ))
        unlinked_guests = await session.scalar(select(func.count()).select_from(GuestParticipation).where(
            GuestParticipation.user_id.is_(None)
        ))
        assert active_accounts + unlinked_guests == 1
