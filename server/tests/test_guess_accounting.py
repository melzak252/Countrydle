"""Real HTTP/isolated PostgreSQL regressions for daily guess acceptance.

Only the database and authentication dependencies are overridden. Local answers,
flag clues, histories, state transitions, and scoring run their real implementations
against disposable PostgreSQL/SQLite data. Database lock gates force overlap rather
than relying on scheduler sleeps or replacing repository methods.
"""
import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db import get_db
from db.base import Base
import db.models as models
from db.models.guest_participation import GuestParticipation
from db.models.user import User, UserPoints
from db.models.continental import ContinentCode
from game_logic import calculate_flagdle_points, calculate_points
from users.utils import get_current_or_guest_user, get_current_user
from utils.guest_session import GUEST_IDENTITY_COOKIE, read_guest_identity

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]

COUNTRIES = (
    (1, "Poland", "Europe"), (2, "Germany", "Europe"),
    (3, "China", "Asia"), (4, "India", "Asia"),
    (5, "Nigeria", "Africa"), (6, "Kenya", "Africa"),
    (7, "Canada", "North America"), (8, "Brazil", "South America"),
)


@dataclass(frozen=True)
class DailyMode:
    key: str
    family: str
    model_prefix: str
    entity_field: str
    target_id: int
    miss_id: int
    target: str
    miss: str
    max_questions: int | None
    max_guesses: int
    question: str
    pool: str | None = None

    @property
    def path(self):
        return f"/{self.family}" + (f"/{self.pool}" if self.pool else "")

    @property
    def cookie(self):
        return f"guest_continental_{self.pool}" if self.pool else f"guest_{self.family}"

    def guess(self, correct=False):
        return {
            "guess": self.target if correct else self.miss,
            self.entity_field: self.target_id if correct else self.miss_id,
            "elapsed_seconds": 120,
        }


MODES = (
    DailyMode("countrydle", "countrydle", "Countrydle", "country_id", 1, 2,
              "Poland", "Germany", 10, 3, "Is it an island?"),
    *(DailyMode(f"continental:{pool}", "continental", "Continental", "country_id", target_id, miss_id,
                target, miss, 8, 3, "Is it an island?", pool)
      for pool, target_id, miss_id, target, miss in (
          ("europe", 1, 2, "Poland", "Germany"),
          ("asia", 3, 4, "China", "India"),
          ("africa", 5, 6, "Nigeria", "Kenya"),
          ("americas", 7, 8, "Canada", "Brazil"),
      )),
    DailyMode("us_statedle", "us_statedle", "USStatedle", "us_state_id", 1, 2,
              "California", "Nevada", 8, 3, "Is it a coastal state?"),
    DailyMode("powiatdle", "powiatdle", "Powiatdle", "powiat_id", 1, 2,
              "krakowski", "warszawski zachodni", 15, 3, "Czy to miasto na prawach powiatu?"),
    DailyMode("wojewodztwodle", "wojewodztwodle", "Wojewodztwodle", "wojewodztwo_id", 1, 2,
              "Małopolskie", "Mazowieckie", 5, 2, "Czy to województwo ma dostęp do morza?"),
    DailyMode("flagdle", "flagdle", "Flagdle", "country_id", 1, 2,
              "Poland", "Germany", None, 12, "Is it an island?"),
)


@pytest.fixture
async def guess_db():
    url = os.getenv("QUESTION_TEST_DATABASE_URL") or os.getenv("FRIEND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set QUESTION_TEST_DATABASE_URL to a disposable PostgreSQL database")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or parsed.database == "guess_country":
        pytest.fail("Guess accounting requires disposable PostgreSQL, never guess_country")
    schema = f"guess_test_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    engine = None
    try:
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            url, pool_size=6, max_overflow=4,
            connect_args={"server_settings": {
                "search_path": schema, "timezone": "UTC", "application_name": schema,
            }},
        )
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        needed = {User.__table__, UserPoints.__table__, GuestParticipation.__table__}
        for name in ("Country", "USState", "Powiat", "Wojewodztwo"):
            needed.add(getattr(models, name).__table__)
        for mode in MODES:
            for suffix in ("Day", "State", "Guess", "Question"):
                needed.add(getattr(models, mode.model_prefix + suffix).__table__)
        pending = list(needed)
        while pending:
            for fk in pending.pop().foreign_keys:
                if fk.column.table not in needed:
                    needed.add(fk.column.table)
                    pending.append(fk.column.table)
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=list(needed)))
        async with factory() as session:
            session.add(User(id=1, username="guess-accounting", email="guess-accounting@example.com",
                             hashed_password="unused", verified=True))
            await session.flush()
            session.add(UserPoints(user_id=1, points=37, streak=2, longest_streak=2))
            session.add_all(models.Country(id=ident, name=name, official_name=name, md_file=f"{ident}.md")
                            for ident, name, _ in COUNTRIES)
            session.add_all([
                models.USState(id=1, name="California", code="CA"),
                models.USState(id=2, name="Nevada", code="NV"),
                models.Powiat(id=1, nazwa="krakowski"),
                models.Powiat(id=2, nazwa="warszawski zachodni"),
                models.Wojewodztwo(id=1, nazwa="Małopolskie"),
                models.Wojewodztwo(id=2, nazwa="Mazowieckie"),
            ])
            await session.commit()
        yield SimpleNamespace(factory=factory, engine=engine, schema=schema)
    finally:
        if engine is not None:
            await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await bootstrap.dispose()


@pytest.fixture
async def guess_http(guess_db, tmp_path, monkeypatch):
    from countrydle import local_answering
    from continental import utils as continental_utils
    from flagdle import utils as flag_utils
    from utils import ai_clients, geo, plan_cache
    from utils.plan_cache import PlanCache
    from utils import guest_session

    # This fixture key signs only isolated test-browser cookies, not real sessions.
    monkeypatch.setattr(guest_session, "SECRET_KEY", "offline-guess-accounting-signing-key-20261006")
    monkeypatch.setenv("COUNTRYDLE_COST_METRICS_DB", str(tmp_path / "metrics.sqlite"))
    monkeypatch.setattr(plan_cache, "plan_cache", PlanCache(db_path=tmp_path / "plans.sqlite"))
    country_path = tmp_path / "country_facts.sqlite"
    with sqlite3.connect(country_path) as connection:
        connection.executescript("""
            CREATE TABLE countries (id INTEGER PRIMARY KEY, app_country_name TEXT,
                official_name TEXT, latitude REAL, longitude REAL, is_island INTEGER);
            CREATE TABLE country_continents (country_id INTEGER, continent TEXT);
            CREATE TABLE country_flag_colors (country_id INTEGER, color TEXT);
            CREATE TABLE country_flag_symbols (country_id INTEGER, symbol TEXT);
        """)
        connection.executemany("INSERT INTO countries VALUES (?, ?, ?, 50, 20, 0)",
                               [(ident, name, name) for ident, name, _ in COUNTRIES])
        connection.executemany("INSERT INTO country_continents VALUES (?, ?)",
                               [(ident, continent) for ident, _, continent in COUNTRIES])
        connection.executemany("INSERT INTO country_flag_colors VALUES (?, 'red')",
                               [(ident,) for ident, _, _ in COUNTRIES])
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", country_path)
    monkeypatch.setattr(continental_utils, "DEFAULT_DB_PATH", country_path)
    monkeypatch.setattr(flag_utils, "FACTS_DB_PATH", country_path)
    monkeypatch.setattr(geo, "_DATA_DIR", tmp_path)
    for family, utility, filename, table, scalar, names in (
        ("us_statedle", "uutils", "us_state_facts.sqlite", "us_states", "is_coastal", ("California", "Nevada")),
        ("powiatdle", "putils", "powiat_facts.sqlite", "powiats", "is_city_county", ("krakowski", "warszawski zachodni")),
        ("wojewodztwodle", "wutils", "voivodeship_facts.sqlite", "voivodeships", "is_coastal", ("Małopolskie", "Mazowieckie")),
    ):
        utils = getattr(import_module(family), utility)
        path = tmp_path / filename
        with sqlite3.connect(path) as connection:
            connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT, {scalar} INTEGER, latitude REAL, longitude REAL)")
            connection.executemany(f"INSERT INTO {table} VALUES (?, ?, ?, 50, 20)",
                                   [(ident, name, int(family == "us_statedle" and ident == 1))
                                    for ident, name in enumerate(names, 1)])
        monkeypatch.setattr(utils, "LOCAL_CONFIG", replace(utils.LOCAL_CONFIG, db_path=path))

    def no_provider(*args, **kwargs):
        raise AssertionError("These accounting regressions must use deterministic local facts, not providers")

    # Fail closed if a template unexpectedly falls through. Never return invented answers.
    monkeypatch.setattr(ai_clients, "generate_gemini_json", no_provider)
    monkeypatch.setattr(ai_clients, "get_openai_client", no_provider)
    monkeypatch.setattr(ai_clients, "get_http_client", no_provider)
    app = FastAPI()
    for family in dict.fromkeys(mode.family for mode in MODES):
        app.include_router(import_module(family).router)

    async def database():
        async with guess_db.factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    async def identity(request: Request, session: AsyncSession = Depends(get_db)):
        return await session.get(User, 1) if request.headers.get("x-accounting-user") == "1" else None

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_or_guest_user] = identity
    app.dependency_overrides[get_current_user] = identity
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                           base_url="http://accounting.test") as client:
        yield client


@pytest.fixture(params=MODES, ids=lambda mode: mode.key)
async def daily_guess_mode(request, guess_db, guess_http):
    spec = request.param
    day_model = getattr(models, spec.model_prefix + "Day")
    today = datetime.now(UTC).date()
    values = dict(id=1, date=today, **{spec.entity_field: spec.target_id})
    if spec.pool:
        values["continent"] = ContinentCode(spec.pool)
    async with guess_db.factory() as session:
        session.add(day_model(**values))
        await session.commit()
    return SimpleNamespace(
        spec=spec, db=guess_db, http=guess_http, today=today, day=day_model,
        state=getattr(models, spec.model_prefix + "State"),
        guess=getattr(models, spec.model_prefix + "Guess"),
        question=getattr(models, spec.model_prefix + "Question"),
    )


async def post_guess(mode, *, guest=False, correct=False, cookies=None):
    headers = {} if guest else {"x-accounting-user": "1"}
    if cookies is not None:
        headers["cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return await mode.http.post(mode.spec.path + "/guess", json=mode.spec.guess(correct), headers=headers)


async def post_question(mode, *, guest=False):
    return await mode.http.post(mode.spec.path + "/question", json={"question": mode.spec.question},
                                headers={} if guest else {"x-accounting-user": "1"})


async def get_state(mode, *, guest=False):
    response = await mode.http.get(mode.spec.path + "/state",
                                   headers={} if guest else {"x-accounting-user": "1"})
    assert response.status_code == 200, response.text
    return response.json()


async def guest_identity(mode):
    await get_state(mode, guest=True)
    token = mode.http.cookies.get(GUEST_IDENTITY_COOKIE)
    assert token is not None
    request = Request({"type": "http", "headers": [(b"cookie", f"{GUEST_IDENTITY_COOKIE}={token}".encode())]})
    identity = read_guest_identity(request)
    assert identity is not None
    return identity


async def seed_progress(mode, *, guest_id=None, guesses=0, questions=0, won=False):
    async with mode.db.factory() as session:
        if guest_id is None:
            values = dict(user_id=1, day_id=1, guesses_made=guesses, questions_asked=questions,
                          remaining_guesses=mode.spec.max_guesses - guesses,
                          won=won, is_game_over=won or guesses >= mode.spec.max_guesses, points=0)
            if mode.spec.max_questions is not None:
                values["remaining_questions"] = mode.spec.max_questions - questions
            if mode.spec.family == "flagdle":
                values["revealed_stage"] = 12 if values["is_game_over"] else min(12, guesses + 1)
            session.add(mode.state(**values))
        else:
            session.add(GuestParticipation(guest_id=guest_id, mode=mode.spec.key, day_id=1,
                                          guesses_made=guesses, questions_asked=questions, won=won))
        for index in range(guesses):
            correct = won and index == guesses - 1
            values = dict(day_id=1, user_id=None if guest_id else 1,
                          guess=mode.spec.target if correct else mode.spec.miss, answer=correct)
            if mode.spec.entity_field in mode.guess.__table__.columns:
                values[mode.spec.entity_field] = mode.spec.target_id if correct else mode.spec.miss_id
            if "guest_id" in mode.guess.__table__.columns:
                values["guest_id"] = guest_id
            session.add(mode.guess(**values))
        await session.commit()


async def snapshot(mode):
    async with mode.db.factory() as session:
        states = list((await session.scalars(select(mode.state).order_by(mode.state.id))).all())
        guesses = list((await session.scalars(select(mode.guess).order_by(mode.guess.id))).all())
        participants = list((await session.scalars(select(GuestParticipation).order_by(GuestParticipation.id))).all())
        points = await session.get(UserPoints, 1)
        return SimpleNamespace(states=states, guesses=guesses, participants=participants,
                               points=(points.points, points.streak, points.longest_streak))


async def expected_points(mode, state):
    # Existing score formulas and mode-specific bonuses are part of the public contract.
    if mode.spec.family == "flagdle":
        return calculate_flagdle_points(won=state.won, guesses_used=state.guesses_made,
                                        elapsed_seconds=120, streak=1)
    config_name = {
        "countrydle": "COUNTRYDLE_CONFIG", "continental": "CONTINENTAL_CONFIG",
        "us_statedle": "USSTATEDLE_CONFIG", "powiatdle": "POWIATDLE_CONFIG",
        "wojewodztwodle": "WOJEWODZTWDLE_CONFIG",
    }[mode.spec.family]
    config = getattr(import_module(mode.spec.family), config_name)
    points = calculate_points(config=config, won=state.won, questions_used=state.questions_asked,
                              guesses_used=state.guesses_made, elapsed_seconds=120, streak=1)
    return points + ({"us_statedle": 200, "powiatdle": 500}.get(mode.spec.family, 0) if state.won else 0)


@asynccontextmanager
async def database_gate(mode, table, *, operation="INSERT", condition=""):
    """Hold a real INSERT/UPDATE before persistence, without changing its outcome."""
    lock_id = int(uuid4().hex[:15], 16)
    when = f" WHEN ({condition})" if condition else ""
    async with mode.db.factory() as session:
        await session.execute(text(f"""
            CREATE FUNCTION accounting_gate() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock({lock_id}); RETURN NEW; END $$
        """))
        await session.execute(text(f'CREATE TRIGGER accounting_gate BEFORE {operation} ON "{table}" '
                                   f'FOR EACH ROW{when} EXECUTE FUNCTION accounting_gate()'))
        await session.commit()
    async with mode.db.engine.connect() as connection:
        await connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
        holder = await connection.scalar(text("SELECT pg_backend_pid()"))
        try:
            yield holder
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})


async def wait_until_contending(mode, holder, tasks, minimum):
    """Observe actual PostgreSQL lock waits or completed requests, not elapsed time."""
    async with asyncio.timeout(10):
        while True:
            async with mode.db.engine.connect() as connection:
                waiting = await connection.scalar(text("""
                    SELECT count(DISTINCT locks.pid)
                    FROM pg_locks locks JOIN pg_stat_activity activity USING (pid)
                    WHERE NOT locks.granted AND locks.pid <> :holder
                        AND activity.application_name = :application
                """), {"holder": holder, "application": mode.db.schema})
            if waiting + sum(task.done() for task in tasks) >= minimum:
                return
            await asyncio.sleep(0.01)


async def overlap(mode, first, second, *, table=None, operation="INSERT", condition=""):
    tasks = []
    try:
        async with database_gate(mode, table or mode.guess.__tablename__, operation=operation, condition=condition) as holder:
            tasks.append(asyncio.create_task(first()))
            await wait_until_contending(mode, holder, tasks, 1)
            # Early failure must not masquerade as an overlapping accepted action.
            if tasks[0].done():
                response = tasks[0].result()
                pytest.fail(f"First action never reached the persistence gate: {response.status_code} {response.text}")
            tasks.append(asyncio.create_task(second()))
            await wait_until_contending(mode, holder, tasks, 2)
        return await asyncio.wait_for(asyncio.gather(*tasks), 10)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("correct", [False, True])
async def test_authenticated_concurrent_last_slot_accepts_exactly_one(daily_guess_mode, correct):
    mode = daily_guess_mode
    await seed_progress(mode, guesses=mode.spec.max_guesses - 1)
    responses = await overlap(mode, lambda: post_guess(mode, correct=correct), lambda: post_guess(mode, correct=correct))
    assert sorted(response.status_code for response in responses) == [200, 400]
    saved = await snapshot(mode)
    assert len(saved.states) == 1
    state = saved.states[0]
    assert (state.guesses_made, state.remaining_guesses, state.is_game_over, state.won) == (mode.spec.max_guesses, 0, True, correct)
    assert len(saved.guesses) == mode.spec.max_guesses
    assert sum(guess.answer is True for guess in saved.guesses) == int(correct)
    assert state.points == await expected_points(mode, state)
    if mode.spec.family in {"countrydle", "continental"}:
        assert saved.points[:2] == (37 + state.points, 3 if correct else 0)


async def test_authenticated_concurrent_first_guesses_share_one_state(daily_guess_mode):
    mode = daily_guess_mode
    responses = await overlap(mode, lambda: post_guess(mode), lambda: post_guess(mode))
    assert [response.status_code for response in responses] == [200, 200]
    saved = await snapshot(mode)
    assert len(saved.states) == 1
    state = saved.states[0]
    assert (state.guesses_made, state.remaining_guesses) == (2, mode.spec.max_guesses - 2)
    assert state.is_game_over is (mode.spec.max_guesses == 2)
    assert state.won is False
    assert [(guess.guess, guess.answer) for guess in saved.guesses] == [(mode.spec.miss, False)] * 2


@pytest.mark.parametrize("question_first", [False, True])
async def test_authenticated_question_guess_overlap_preserves_counters_terminal_and_score(daily_guess_mode, question_first):
    mode = daily_guess_mode
    await seed_progress(mode)
    if question_first:
        question_response, guess_response = await overlap(
            mode, lambda: post_question(mode), lambda: post_guess(mode, correct=True),
            table=mode.state.__tablename__, operation="UPDATE", condition="NEW.questions_asked > OLD.questions_asked",
        )
    else:
        guess_response, question_response = await overlap(mode, lambda: post_guess(mode, correct=True), lambda: post_question(mode))
    assert guess_response.status_code == 200, guess_response.text
    assert question_response.status_code in (200, 400), question_response.text
    accepted = question_response.status_code == 200
    if accepted:
        assert question_response.json()["valid"] is True
        assert question_response.json()["answer"] is (mode.spec.family == "us_statedle")
    if question_first or mode.spec.family == "flagdle":
        assert accepted
    saved = await snapshot(mode)
    state = saved.states[0]
    assert (state.questions_asked, state.guesses_made, state.remaining_guesses, state.is_game_over, state.won) == (int(accepted), 1, mode.spec.max_guesses - 1, True, True)
    if mode.spec.max_questions is not None:
        assert state.remaining_questions == mode.spec.max_questions - int(accepted)
    else:
        assert state.revealed_stage == 12
    async with mode.db.factory() as session:
        assert await session.scalar(select(func.count()).select_from(mode.question)) == int(accepted)
    assert len(saved.guesses) == 1
    assert state.points == await expected_points(mode, state)


@pytest.mark.parametrize("failure", ["state", "points"])
async def test_authenticated_persistence_failure_rolls_back_guess_state_and_score(daily_guess_mode, failure):
    mode = daily_guess_mode
    if failure == "points" and mode.spec.family not in {"countrydle", "continental"}:
        pytest.skip("Only these routes currently mutate the aggregate UserPoints ledger")
    await seed_progress(mode)
    before = await snapshot(mode)
    table = mode.state.__tablename__ if failure == "state" else UserPoints.__tablename__
    column = "guesses_made" if failure == "state" else "points"
    initial = 0 if failure == "state" else before.points[0]
    async with mode.db.factory() as session:
        await session.execute(text(f'ALTER TABLE "{table}" ADD CONSTRAINT accounting_reject_update CHECK ({column} = {initial})'))
        await session.commit()
    response = await post_guess(mode, correct=True)
    assert 500 <= response.status_code < 600, response.text
    after = await snapshot(mode)
    assert after.guesses == []
    state = after.states[0]
    assert (state.guesses_made, state.remaining_guesses, state.is_game_over, state.won, state.points) == (0, mode.spec.max_guesses, False, False, 0)
    assert after.points == before.points


async def test_authenticated_completed_game_rejects_replay_without_duplicate_points(daily_guess_mode):
    mode = daily_guess_mode
    accepted = await post_guess(mode, correct=True)
    assert accepted.status_code == 200, accepted.text
    before = await snapshot(mode)
    responses = await asyncio.gather(post_guess(mode, correct=True), post_guess(mode))
    assert [response.status_code for response in responses] == [400, 400]
    after = await snapshot(mode)
    assert [(row.id, row.guess, row.answer) for row in after.guesses] == [(row.id, row.guess, row.answer) for row in before.guesses]
    assert (after.states[0].guesses_made, after.states[0].points, after.points) == (1, before.states[0].points, before.points)
    assert after.states[0].points == await expected_points(mode, after.states[0])


@pytest.mark.parametrize("terminal", ["quota", "won"])
async def test_guest_durable_progress_rejects_without_a_mode_cookie(daily_guess_mode, terminal):
    mode = daily_guess_mode
    identity = await guest_identity(mode)
    count = mode.spec.max_guesses if terminal == "quota" else 1
    await seed_progress(mode, guest_id=identity, guesses=count, won=terminal == "won")
    response = await post_guess(mode, guest=True, correct=True)
    assert response.status_code == 400, response.text
    saved = await snapshot(mode)
    assert len(saved.guesses) == count
    participant = saved.participants[0]
    assert (participant.guesses_made, participant.won) == (count, terminal == "won")
    assert saved.points == (37, 2, 2)


@pytest.mark.parametrize("cookie_action", ["delete", "replay"])
@pytest.mark.parametrize("won", [False, True])
async def test_guest_cookie_deletion_or_replay_cannot_reset_terminal_progress(daily_guess_mode, cookie_action, won):
    mode = daily_guess_mode
    identity = await guest_identity(mode)
    first = await post_guess(mode, guest=True)
    assert first.status_code == 200, first.text
    old_cookie = mode.http.cookies.get(mode.spec.cookie)
    assert old_cookie is not None
    if won:
        winner = await post_guess(mode, guest=True, correct=True)
        assert winner.status_code == 200, winner.text
    if not won:
        async with mode.db.factory() as session:
            participant = await session.scalar(select(GuestParticipation).where(GuestParticipation.guest_id == identity))
            participant.guesses_made = mode.spec.max_guesses - 1
            # Seed prior accepted history directly instead of issuing eleven setup requests.
            for _ in range(mode.spec.max_guesses - 2):
                values = dict(user_id=None, day_id=1, guess=mode.spec.miss, answer=False)
                if mode.spec.entity_field in mode.guess.__table__.columns:
                    values[mode.spec.entity_field] = mode.spec.miss_id
                if "guest_id" in mode.guess.__table__.columns:
                    values["guest_id"] = identity
                session.add(mode.guess(**values))
            await session.commit()
        final = await post_guess(mode, guest=True)
        assert final.status_code == 200, final.text
    identity_token = mode.http.cookies.get(GUEST_IDENTITY_COOKIE)
    cookies = {GUEST_IDENTITY_COOKIE: identity_token}
    if cookie_action == "replay":
        cookies[mode.spec.cookie] = old_cookie
    response = await post_guess(mode, guest=True, cookies=cookies)
    assert response.status_code == 400, response.text
    saved = await snapshot(mode)
    expected = 2 if won else mode.spec.max_guesses
    assert len(saved.guesses) == expected
    assert (saved.participants[0].guesses_made, saved.participants[0].won) == (expected, won)


async def test_guest_concurrent_last_slot_accepts_exactly_one(daily_guess_mode):
    mode = daily_guess_mode
    identity = await guest_identity(mode)
    await seed_progress(mode, guest_id=identity, guesses=mode.spec.max_guesses - 1)
    cookies = {GUEST_IDENTITY_COOKIE: mode.http.cookies.get(GUEST_IDENTITY_COOKIE)}
    responses = await overlap(mode, lambda: post_guess(mode, guest=True, cookies=cookies), lambda: post_guess(mode, guest=True, cookies=cookies))
    assert sorted(response.status_code for response in responses) == [200, 400]
    saved = await snapshot(mode)
    assert len(saved.participants) == 1
    assert saved.participants[0].guesses_made == mode.spec.max_guesses
    assert saved.participants[0].won is False
    assert len(saved.guesses) == mode.spec.max_guesses


async def test_guest_failed_guess_insert_rolls_back_durable_progress(daily_guess_mode):
    mode = daily_guess_mode
    await guest_identity(mode)
    async with mode.db.factory() as session:
        await session.execute(text(f'ALTER TABLE "{mode.guess.__tablename__}" ADD CONSTRAINT accounting_reject_guess CHECK (answer IS NOT FALSE)'))
        await session.commit()
    response = await post_guess(mode, guest=True)
    assert 500 <= response.status_code < 600, response.text
    saved = await snapshot(mode)
    assert saved.guesses == []
    assert saved.participants == []
    assert saved.points == (37, 2, 2)


async def test_guest_other_mode_and_date_progress_do_not_spend_current_quota(daily_guess_mode):
    mode = daily_guess_mode
    identity = await guest_identity(mode)
    previous_date = mode.today - timedelta(days=1)
    day_values = dict(id=2, date=previous_date, **{mode.spec.entity_field: mode.spec.target_id})
    if mode.spec.pool:
        day_values["continent"] = ContinentCode(mode.spec.pool)
    other_mode = "countrydle" if mode.spec.key != "countrydle" else "flagdle"
    async with mode.db.factory() as session:
        session.add(mode.day(**day_values))
        session.add_all([
            GuestParticipation(guest_id=identity, mode=mode.spec.key, day_id=2,
                               guesses_made=mode.spec.max_guesses, won=True),
            GuestParticipation(guest_id=identity, mode=other_mode, day_id=1,
                               guesses_made=12, won=True),
        ])
        await session.commit()
    accepted = await post_guess(mode, guest=True)
    assert accepted.status_code == 200, accepted.text
    saved = await snapshot(mode)
    progress = {(row.mode, row.day_id): (row.guesses_made, row.won) for row in saved.participants}
    assert progress == {(mode.spec.key, 2): (mode.spec.max_guesses, True),
                        (other_mode, 1): (12, True), (mode.spec.key, 1): (1, False)}
    assert [(row.day_id, row.guess, row.answer) for row in saved.guesses] == [(1, mode.spec.miss, False)]


@pytest.mark.parametrize("won", [False, True])
async def test_guest_reload_then_repeated_sync_preserves_accepted_history_once(daily_guess_mode, won):
    mode = daily_guess_mode
    identity = await guest_identity(mode)
    answered = await post_question(mode, guest=True)
    assert answered.status_code == 200, answered.text
    assert answered.json()["valid"] is True
    assert answered.json()["answer"] is (mode.spec.family == "us_statedle")
    question_id = answered.json()["id"]
    first = await post_guess(mode, guest=True)
    assert first.status_code == 200, first.text
    second = await post_guess(mode, guest=True, correct=won)
    assert second.status_code == 200, second.text
    accepted_ids = [first.json()["id"], second.json()["id"]]
    # A reload cannot reset durable progress even if the per-mode snapshot is lost.
    token = mode.http.cookies.get(GUEST_IDENTITY_COOKIE)
    mode.http.cookies.clear()
    mode.http.cookies.set(GUEST_IDENTITY_COOKIE, token, domain="accounting.test", path="/")
    restored = await get_state(mode, guest=True)
    assert (restored["state"]["guesses_made"], restored["state"]["remaining_guesses"],
            restored["state"]["is_game_over"], restored["state"]["won"]) == (2, mode.spec.max_guesses - 2, won or mode.spec.max_guesses == 2, won)
    assert [(row["id"], row["guess"], row["answer"]) for row in restored["guesses"]] == [
        (accepted_ids[0], mode.spec.miss, False),
        (accepted_ids[1], mode.spec.target if won else mode.spec.miss, won),
    ]
    if mode.spec.max_questions is not None:
        assert (restored["state"]["questions_asked"], restored["state"]["remaining_questions"]) == (1, mode.spec.max_questions - 1)
    assert [(row["id"], row["original_question"], row["answer"]) for row in restored["questions"]] == [
        (question_id, mode.spec.question, mode.spec.family == "us_statedle"),
    ]
    sync_state = dict(guesses_made=2, remaining_guesses=mode.spec.max_guesses - 2,
                      questions_asked=1, remaining_questions=(mode.spec.max_questions - 1) if mode.spec.max_questions is not None else 0,
                      is_game_over=won or mode.spec.max_guesses == 2, won=won,
                      revealed_stage=12 if won else 3)
    body = {"date": mode.today.isoformat(), "state": sync_state,
            "questions": [question_id],
            "guesses": [mode.spec.guess(), mode.spec.guess(correct=won)]}
    for _ in range(2):
        response = await mode.http.post(mode.spec.path + "/sync", json=body, headers={"x-accounting-user": "1"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert (result["state"]["guesses_made"], result["state"]["remaining_guesses"], result["state"]["won"]) == (2, mode.spec.max_guesses - 2, won)
        assert [(row["guess"], row["answer"]) for row in result["guesses"]] == [(mode.spec.miss, False), (mode.spec.target if won else mode.spec.miss, won)]
        if mode.spec.max_questions is not None:
            assert (result["state"]["questions_asked"], result["state"]["remaining_questions"]) == (1, mode.spec.max_questions - 1)
        assert [(row["id"], row["original_question"], row["answer"]) for row in result["questions"]] == [
            (question_id, mode.spec.question, mode.spec.family == "us_statedle"),
        ]
    authenticated_reload = await get_state(mode)
    assert authenticated_reload["state"]["guesses_made"] == 2
    saved = await snapshot(mode)
    assert len(saved.states) == 1
    assert saved.states[0].questions_asked == 1
    async with mode.db.factory() as session:
        questions = list((await session.scalars(select(mode.question))).all())
        assert [(row.id, row.user_id, row.original_question) for row in questions] == [(question_id, 1, mode.spec.question)]
    assert [(row.id, row.user_id, row.guess, row.answer) for row in saved.guesses] == [
        (accepted_ids[0], 1, mode.spec.miss, False),
        (accepted_ids[1], 1, mode.spec.target if won else mode.spec.miss, won),
    ]
    assert len(saved.participants) == 1
    assert (saved.participants[0].guest_id, saved.participants[0].user_id,
            saved.participants[0].questions_asked, saved.participants[0].guesses_made,
            saved.participants[0].won) == (identity, 1, 1, 2, won)
    if won:
        assert saved.states[0].points == await expected_points(mode, saved.states[0])


async def test_guest_question_finalizing_after_sync_cannot_create_unowned_history(daily_guess_mode, monkeypatch):
    mode = daily_guess_mode
    original = await post_guess(mode, guest=True)
    assert original.status_code == 200, original.text
    before = await get_state(mode, guest=True)
    module = import_module(mode.spec.family)
    real_finalizer = module.record_guest_action
    arrived, release = asyncio.Event(), asyncio.Event()

    async def delayed_finalizer(*args, **kwargs):
        if kwargs.get("question"):
            arrived.set()
            await release.wait()
        return await real_finalizer(*args, **kwargs)

    monkeypatch.setattr(module, "record_guest_action", delayed_finalizer)
    pending = asyncio.create_task(post_question(mode, guest=True))
    try:
        await asyncio.wait_for(arrived.wait(), timeout=15)
        synced = await mode.http.post(
            mode.spec.path + "/sync",
            json={"date": before["date"], "state": before["state"],
                  "guesses": before["guesses"], "questions": []},
            headers={"x-accounting-user": "1"},
        )
    finally:
        release.set()
        late = await pending
    assert synced.status_code == 200, synced.text
    assert late.status_code == 409, late.text
    saved = await snapshot(mode)
    assert (saved.states[0].questions_asked, saved.states[0].guesses_made) == (0, 1)
    assert (saved.participants[0].user_id, saved.participants[0].questions_asked,
            saved.participants[0].guesses_made) == (1, 0, 1)
    assert [(row.id, row.user_id) for row in saved.guesses] == [(original.json()["id"], 1)]
    async with mode.db.factory() as session:
        assert await session.scalar(select(func.count()).select_from(mode.question)) == 0


async def test_claimed_guest_reload_keeps_originals_without_exposing_later_account_history(daily_guess_mode):
    mode = daily_guess_mode
    original = await post_guess(mode, guest=True)
    assert original.status_code == 200, original.text
    before = await get_state(mode, guest=True)
    synced = await mode.http.post(
        mode.spec.path + "/sync",
        json={"date": before["date"], "state": before["state"],
              "guesses": before["guesses"], "questions": []},
        headers={"x-accounting-user": "1"},
    )
    assert synced.status_code == 200, synced.text
    account_only = await post_guess(mode)
    assert account_only.status_code == 200, account_only.text
    public = await get_state(mode, guest=True)
    assert public["user"] is None
    assert public["state"]["guesses_made"] == 1
    assert public["state"]["is_game_over"] is False
    assert public["country" if mode.spec.family in {"countrydle", "continental", "flagdle"}
                  else {"us_statedle": "us_state", "powiatdle": "powiat", "wojewodztwodle": "wojewodztwo"}[mode.spec.family]] is None
    assert [(row["id"], row["guess"], row["answer"]) for row in public["guesses"]] == [
        (original.json()["id"], mode.spec.miss, False),
    ]


async def test_active_question_explanation_does_not_disclose_secret_entity_name(daily_guess_mode):
    mode = daily_guess_mode
    result = await post_question(mode, guest=True)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["valid"] is True
    assert payload["answer"] is (mode.spec.family == "us_statedle")
    assert mode.spec.target.casefold() not in payload["explanation"].casefold()
    restored = await get_state(mode, guest=True)
    assert [(row["id"], row["answer"]) for row in restored["questions"]] == [
        (payload["id"], payload["answer"]),
    ]
    assert mode.spec.target.casefold() not in restored["questions"][0]["explanation"].casefold()
