from datetime import timedelta
from http.cookies import SimpleCookie
from uuid import uuid4
import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException, Request, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from continental.utils import get_continent_country_names
from db.models import Country, CountrydleDay
from db.models.continental import ContinentCode
from db.models.flagdle import FlagdleDay
from db.repositories.country import CountryRepository
from db.repositories.countrydle import CountrydleRepository
from db.repositories.flagdle import FlagdleDayRepository
from friend_matches import providers
from app import app
from daily_clock import utc_today
import db.models as models
from db.models.guest_participation import GuestParticipation
from db.models.user import UserPoints
from users.utils import get_current_user, get_current_or_guest_user
from utils.guest_session import GUEST_IDENTITY_COOKIE, get_guest_identity


@pytest.fixture
def facts(tmp_path):
    path = tmp_path / "countries.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE countries (id INTEGER PRIMARY KEY, app_country_name TEXT, cca3 TEXT, cca2 TEXT);
            CREATE TABLE country_continents (country_id INTEGER, continent TEXT);
            INSERT INTO countries VALUES (1, 'Israel', 'ISR', 'IL'), (2, 'Azerbaijan', 'AZE', 'AZ'),
                (3, 'Kosovo', 'XKX', 'XK'), (4, 'Poland', 'POL', 'PL');
            INSERT INTO country_continents VALUES (1, 'Asia'), (2, 'Europe'), (2, 'Asia'),
                (3, 'Europe'), (4, 'Europe');
        """)
    return path


def test_continental_pools_apply_game_policy_without_removing_facts(facts):
    assert get_continent_country_names(ContinentCode.EUROPE, facts) == ["Kosovo", "Poland"]
    assert get_continent_country_names(ContinentCode.ASIA, facts) == ["Azerbaijan"]
    with sqlite3.connect(facts) as conn:
        assert conn.execute("SELECT app_country_name FROM countries WHERE cca3='ISR'").fetchone() == ("Israel",)


def test_duel_pools_share_country_and_continental_eligibility(facts, monkeypatch):
    engine = SimpleNamespace(db_path=facts, table="countries", name_column="app_country_name",
                             key_column="cca3", code_column="cca2")
    monkeypatch.setattr(providers, "_engine", lambda mode: engine)
    providers._entity_pool.cache_clear()
    try:
        assert {e["name"] for e in providers.list_entities("countrydle")} == {"Azerbaijan", "Kosovo", "Poland"}
        assert {e["name"] for e in providers.list_entities("europe")} == {"Kosovo", "Poland"}
        assert {e["name"] for e in providers.list_entities("asia")} == {"Azerbaijan"}
    finally:
        providers._entity_pool.cache_clear()


@pytest.fixture
def country_session():
    engine = create_engine("sqlite://")
    Country.__table__.create(engine)
    CountrydleDay.__table__.create(engine)
    FlagdleDay.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([Country(id=1, name="Israel", official_name="State of Israel", md_file="Israel.md"),
                         Country(id=2, name="Azerbaijan", official_name="Republic of Azerbaijan", md_file="Azerbaijan.md"),
                         Country(id=3, name="Kosovo", official_name="Republic of Kosovo", md_file="Kosovo.md")])
        session.commit()
        yield SimpleNamespace(execute=AsyncMock(side_effect=session.execute),
                              add=session.add, commit=AsyncMock(side_effect=session.commit),
                              refresh=AsyncMock(side_effect=session.refresh))
    engine.dispose()


@pytest.mark.real_database
@pytest.mark.anyio
async def test_country_pool_excludes_israel_but_historical_lookup_retains_it(country_session):
    repo = CountryRepository(country_session)
    assert {c.name for c in await repo.get_all_countries()} == {"Azerbaijan", "Kosovo"}
    assert (await repo.get(1)).name == "Israel"


@pytest.mark.real_database
@pytest.mark.anyio
@pytest.mark.parametrize("country_id,name,mode", [(1, "Kosovo", None), (None, " State of Israel ", None),
                                                  (2, "Kosovo", "europe")])
async def test_ineligible_guess_rejected_by_id_or_name(country_session, country_id, name, mode):
    with pytest.raises(HTTPException) as exc:
        await CountryRepository(country_session).validate_guess(country_id, name, mode)
    assert exc.value.status_code == 400


@pytest.mark.real_database
@pytest.mark.anyio
async def test_active_ineligible_target_is_blocked_but_history_is_readable(country_session):
    today_utc = utc_today()
    country_session.add(CountrydleDay(country_id=1, date=today_utc))
    country_session.add(CountrydleDay(country_id=1, date=today_utc - timedelta(days=1)))
    await country_session.commit()
    repo = CountrydleRepository(country_session)
    with pytest.raises(HTTPException) as exc:
        await repo.get_today_country()
    assert exc.value.status_code == 503
    yesterday = await repo.get_day_country_by_date(today_utc - timedelta(days=1))
    assert yesterday.country_id == 1


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/countrydle/guess", "/flagdle/guess", "/continental/asia/guess",
                                 "/continental/europe/guess"])
async def test_guess_endpoints_reject_disabled_id_even_with_eligible_name(async_client, monkeypatch, path):
    monkeypatch.setattr(CountryRepository, "get", AsyncMock(
        return_value=SimpleNamespace(id=1, name="Israel", official_name="State of Israel")))
    response = await async_client.post(path, json={"country_id": 1, "guess": "Poland"})
    assert response.status_code == 400


async def seed_guest_sync_originals(factory, client, mode, disabled=None):
    prefix = {"countrydle": "Countrydle", "flagdle": "Flagdle", "continental": "Continental"}[mode]
    day_model, state_model, guess_model, question_model = (
        getattr(models, prefix + suffix) for suffix in ("Day", "State", "Guess", "Question")
    )
    path = "/continental/europe" if mode == "continental" else f"/{mode}"
    participation_mode = "continental:europe" if mode == "continental" else mode
    request = Request({
        "type": "http", "scheme": "https", "headers": [], "path": "/",
        "query_string": b"", "server": ("test", 443),
    })
    response = Response()
    identity = get_guest_identity(request, response)
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    client.cookies.set(GUEST_IDENTITY_COOKIE, cookie[GUEST_IDENTITY_COOKIE].value)
    max_guesses = 12 if mode == "flagdle" else 3
    max_questions = 8 if mode == "continental" else 10
    won = disabled == "target"
    async with factory() as session:
        session.add(Country(id=100, name="Israel", official_name="State of Israel", md_file=""))
        await session.flush()
        day = day_model(id=9, country_id=100 if won else 1, date=utc_today())
        if mode == "continental":
            day.continent = ContinentCode.EUROPE
        session.add(day)
        await session.flush()
        state_values = dict(
            user_id=1, day_id=9, questions_asked=0, guesses_made=0,
            remaining_guesses=max_guesses, is_game_over=False, won=False, points=0,
        )
        if mode == "flagdle":
            state_values["revealed_stage"] = 1
        else:
            state_values["remaining_questions"] = max_questions
        session.add(state_model(**state_values))
        session.add(GuestParticipation(
            guest_id=identity, mode=participation_mode, day_id=9,
            questions_asked=1, guesses_made=1, won=won,
        ))
        guess_values = dict(
            id=1, day_id=9, guest_id=identity, user_id=None,
            guess="Israel" if disabled else "Germany", answer=won, elapsed_seconds=15,
        )
        if "country_id" in guess_model.__table__.columns:
            guess_values["country_id"] = 100 if disabled else 2
        guess = guess_model(**guess_values)
        question = question_model(
            id=1, day_id=9, guest_id=identity, user_id=None,
            original_question="Is it in Europe?", question="Is the country in Europe?",
            valid=True, answer=not won, explanation="Persisted answer",
            context="Original private evidence", fact_provenance=[],
        )
        session.add_all([guess, question])
        await session.commit()
    return SimpleNamespace(
        path=path, mode=participation_mode, identity=identity, day=day_model, state=state_model,
        guess=guess_model, question=question_model, max_guesses=max_guesses,
        max_questions=max_questions, won=won,
    )


def client_sync_projection():
    return {
        "date": utc_today().isoformat(),
        "state": {
            "remaining_questions": 0, "remaining_guesses": 0,
            "questions_asked": 99, "guesses_made": 99,
            "won": True, "is_game_over": True, "points": 99999, "revealed_stage": 12,
        },
        "questions": [2],
        "guesses": [{"country_id": 100, "guess": "Israel"}],
    }


@pytest.fixture
async def guest_sync_client(daily_api_client):
    user = SimpleNamespace(
        id=1, username="eligibility", email="eligibility@example.com", verified=True, is_admin=False,
    )
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_or_guest_user] = lambda: user
    try:
        yield daily_api_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.real_database
@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["countrydle", "flagdle", "continental"])
@pytest.mark.parametrize("disabled", ["target", "original_guess"])
async def test_guest_sync_rejects_disabled_country_before_importing_progress(
    daily_api_db, guest_sync_client, mode, disabled,
):
    case = await seed_guest_sync_originals(daily_api_db, guest_sync_client, mode, disabled)
    # Rejection checks the current target or signed originals, never client projections.
    body = client_sync_projection()
    body["guesses"] = [{"country_id": 1, "guess": "Poland"}]
    body["questions"] = []
    response = await guest_sync_client.post(case.path + "/sync", json=body)
    assert response.status_code == (503 if disabled == "target" else 400), response.text
    async with daily_api_db() as session:
        state = (await session.scalars(select(case.state))).one()
        participation = (await session.scalars(select(GuestParticipation))).one()
        guesses = list((await session.scalars(select(case.guess))).all())
        questions = list((await session.scalars(select(case.question))).all())
        points = await session.get(UserPoints, 1)
        assert (state.questions_asked, state.guesses_made, state.remaining_guesses,
                state.won, state.is_game_over, state.points) == (0, 0, case.max_guesses, False, False, 0)
        if mode != "flagdle":
            assert state.remaining_questions == case.max_questions
        else:
            assert state.revealed_stage == 1
        assert (participation.guest_id, participation.user_id, participation.questions_asked,
                participation.guesses_made, participation.won) == (case.identity, None, 1, 1, case.won)
        assert [(row.id, row.guest_id, row.user_id, row.guess, row.answer) for row in guesses] == [
            (1, case.identity, None, "Israel", case.won),
        ]
        if "country_id" in case.guess.__table__.columns:
            assert [row.country_id for row in guesses] == [100]
        assert [(row.id, row.guest_id, row.user_id, row.original_question, row.answer,
                 row.context, row.fact_provenance) for row in questions] == [
            (1, case.identity, None, "Is it in Europe?", not case.won, "Original private evidence", []),
        ]
        assert (points.points, points.streak, points.longest_streak) == (37, 2, 2)


@pytest.mark.real_database
@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["countrydle", "flagdle", "continental"])
async def test_guest_sync_claims_only_signed_originals_once_and_ignores_client_authority(
    daily_api_db, guest_sync_client, mode,
):
    case = await seed_guest_sync_originals(daily_api_db, guest_sync_client, mode)
    other_identity = str(uuid4())
    other_guess_values = dict(
        id=2, day_id=9, guest_id=other_identity, user_id=None, guess="Poland", answer=True,
    )
    if "country_id" in case.guess.__table__.columns:
        other_guess_values["country_id"] = 1
    async with daily_api_db() as session:
        session.add_all([
            case.guess(**other_guess_values),
            case.question(id=2, day_id=9, guest_id=other_identity, user_id=None,
                          original_question="Does it border Germany?", question="Does it border Germany?",
                          valid=True, answer=True, explanation="Other browser's answer", fact_provenance=[]),
        ])
        await session.commit()
    for _ in range(2):
        response = await guest_sync_client.post(case.path + "/sync", json=client_sync_projection())
        assert response.status_code == 200, response.text
        result = response.json()
        assert (result["state"]["guesses_made"], result["state"]["remaining_guesses"],
                result["state"]["won"], result["state"]["is_game_over"]) == (1, case.max_guesses - 1, False, False)
        if mode != "flagdle":
            assert (result["state"]["questions_asked"], result["state"]["remaining_questions"]) == (
                1, case.max_questions - 1,
            )
        else:
            assert result["state"]["revealed_stage"] == 2
        assert [(row["id"], row["guess"], row["answer"]) for row in result["guesses"]] == [(1, "Germany", False)]
        assert [(row["id"], row["original_question"], row["answer"]) for row in result["questions"]] == [
            (1, "Is it in Europe?", True),
        ]
    async with daily_api_db() as session:
        states = list((await session.scalars(select(case.state))).all())
        assert len(states) == 1
        assert (states[0].questions_asked, states[0].guesses_made, states[0].points) == (1, 1, 0)
        if mode != "flagdle":
            assert states[0].remaining_questions == case.max_questions - 1
        else:
            assert states[0].revealed_stage == 2
        guesses = list((await session.scalars(select(case.guess).order_by(case.guess.id))).all())
        questions = list((await session.scalars(select(case.question).order_by(case.question.id))).all())
        assert [(row.id, row.guest_id, row.user_id, row.answer) for row in guesses] == [
            (1, case.identity, 1, False), (2, other_identity, None, True),
        ]
        assert [(row.id, row.guest_id, row.user_id, row.original_question) for row in questions] == [
            (1, case.identity, 1, "Is it in Europe?"), (2, other_identity, None, "Does it border Germany?"),
        ]
        participation = (await session.scalars(select(GuestParticipation))).one()
        assert (participation.guest_id, participation.user_id, participation.questions_asked,
                participation.guesses_made, participation.won) == (case.identity, 1, 1, 1, False)
        points = await session.get(UserPoints, 1)
        assert (points.points, points.streak, points.longest_streak) == (37, 2, 2)


@pytest.mark.real_database
@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["world", "flagdle"])
async def test_generation_cooldown_fallback_still_excludes_israel(country_session, monkeypatch, mode):
    model = CountrydleDay if mode == "world" else FlagdleDay
    for cid in (2, 3):
        country_session.add(model(country_id=cid, date=utc_today() - timedelta(days=cid)))
    await country_session.commit()
    monkeypatch.setattr("db.repositories.countrydle.random.choice", lambda pool: pool[0])
    if mode == "world":
        day = await CountrydleRepository(country_session).generate_new_day_country(day_date=utc_today())
    else:
        day = await FlagdleDayRepository(country_session).generate_new_day_flag(target_date=utc_today())
    assert day.country_id == 2


def test_country_migration_preserves_guest_play_and_repairs_only_unplayed_targets():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/e0f1a2b3c4d5_add_kosovo_and_repair_targets.py"
    spec = importlib.util.spec_from_file_location("kosovo_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            Country.__table__.create(conn)
            conn.execute(Country.__table__.insert(), [
                {"id": 1, "name": "Israel", "md_file": "Israel.md"},
                {"id": 2, "name": "Azerbaijan", "md_file": "Azerbaijan.md"},
            ])
            conn.exec_driver_sql("CREATE TABLE daily_blog_posts (date DATE)")
            conn.exec_driver_sql("CREATE TABLE guest_participations (mode TEXT, day_id INTEGER)")
            for mode, country_id, participation_mode in [
                ("countrydle", 1, "countrydle"),
                ("flagdle", 1, "flagdle"),
                ("continental", 2, "continental:europe"),
            ]:
                conn.exec_driver_sql(
                    f"CREATE TABLE {mode}_days (id INTEGER PRIMARY KEY, country_id INTEGER, date DATE, continent TEXT)"
                )
                for suffix in ("states", "guesses", "questions"):
                    conn.exec_driver_sql(f"CREATE TABLE {mode}_{suffix} (day_id INTEGER)")
                for day_id in (1, 2):
                    conn.exec_driver_sql(
                        f"INSERT INTO {mode}_days VALUES (?, ?, CURRENT_DATE, 'europe')",
                        (day_id, country_id),
                    )
                conn.exec_driver_sql(
                    "INSERT INTO guest_participations VALUES (?, 1)", (participation_mode,)
                )
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
                migration.upgrade()
            kosovo_id = conn.exec_driver_sql("SELECT id FROM countries WHERE name = 'Kosovo'").scalar_one()
            for mode, original_id in [("countrydle", 1), ("flagdle", 1), ("continental", 2)]:
                assert conn.exec_driver_sql(
                    f"SELECT country_id FROM {mode}_days WHERE id = 1"
                ).scalar_one() == original_id
                assert conn.exec_driver_sql(
                    f"SELECT country_id FROM {mode}_days WHERE id = 2"
                ).scalar_one() == kosovo_id
    finally:
        engine.dispose()
