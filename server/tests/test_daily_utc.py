"""H08: UTC puzzle identity, rollover, generation, streak and expiry contracts.

These exercise existing application functions, not a proposed clock API. SQLite
executes the real ORM queries; its current_date/current_timestamp functions model
an independently timezone-configured database at the same controlled instant.
No lifespan, scheduler execution, providers, or application database are used.
"""

from contextlib import asynccontextmanager
import builtins
import datetime as datetime_module
from datetime import date, datetime, timedelta, timezone
import importlib
import os
from pathlib import Path
import random
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

import app as app_module
import utils
from db import get_db
from db.models import Country, CountrydleDay, CountrydleState, CountrydleGuess, CountrydleQuestion, User
from db.models.continental import ContinentCode, ContinentalDay, ContinentalState, ContinentalGuess, ContinentalQuestion
from db.models.fallback_answer import FallbackAnswer, FallbackAnswerBlock
from db.models.flagdle import FlagdleDay, FlagdleState, FlagdleGuess, FlagdleQuestion
from db.models.guest_participation import GuestParticipation
from db.models.powiat import Powiat
from db.models.powiatdle import PowiatdleDay, PowiatdleState, PowiatdleGuess, PowiatdleQuestion
from db.models.us_state import USState
from db.models.us_statedle import USStatedleDay, USStatedleState, USStatedleGuess, USStatedleQuestion
from db.models.user import UserPoints
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState, WojewodztwodleGuess, WojewodztwodleQuestion
from db.repositories.continental import ContinentalDayRepository
from db.repositories.countrydle import CountrydleRepository, CountrydleStateRepository
from db.repositories.flagdle import FlagdleDayRepository
from db.repositories.powiatdle import PowiatdleDayRepository
from db.repositories.us_statedle import USStatedleDayRepository
from db.repositories.wojewodztwodle import WojewodztwodleDayRepository
from users.utils import get_current_or_guest_user


pytestmark = [pytest.mark.real_database, pytest.mark.anyio]
UTC = timezone.utc
SERVER_ROOT = Path(__file__).resolve().parents[1]
INSTANTS = [
    "2026-01-31T23:59:59+00:00",
    "2026-02-01T00:00:00+00:00",
    "2026-03-28T23:30:00+00:00",
    "2026-03-29T00:59:59+00:00",
    "2026-03-29T01:00:00+00:00",
    "2026-10-24T22:30:00+00:00",
    "2026-10-25T00:59:59+00:00",
    "2026-10-25T01:00:00+00:00",
]

# Continental is four separate daily puzzles, not one representative continent.
MODES = [
    ("countrydle", CountrydleDay, "country_id", CountrydleRepository,
     "get_today_country", "get_countrydle_history", "generate_new_day_country"),
    ("flagdle", FlagdleDay, "country_id", FlagdleDayRepository,
     "get_today_flag", "get_history", "generate_new_day_flag"),
    ("powiatdle", PowiatdleDay, "powiat_id", PowiatdleDayRepository,
     "get_today_powiat", "get_history", "generate_new_day_powiat"),
    ("us_statedle", USStatedleDay, "us_state_id", USStatedleDayRepository,
     "get_today_us_state", "get_history", "generate_new_day_us_state"),
    ("wojewodztwodle", WojewodztwodleDay, "wojewodztwo_id", WojewodztwodleDayRepository,
     "get_today_wojewodztwo", "get_history", "generate_new_day_wojewodztwo"),
    *[(f"continental/{continent.value}", ContinentalDay, "country_id", ContinentalDayRepository,
       "get_today_day", "get_history", "generate_new_day") for continent in ContinentCode],
]
STATE_MODELS = {
    "countrydle": CountrydleState, "flagdle": FlagdleState,
    "powiatdle": PowiatdleState, "us_statedle": USStatedleState,
    "wojewodztwodle": WojewodztwodleState,
    **{f"continental/{continent.value}": ContinentalState for continent in ContinentCode},
}


def continent_args(mode):
    return (ContinentCode(mode.split("/")[1]),) if mode.startswith("continental/") else ()


def day_kwargs(mode):
    args = continent_args(mode)
    return {"continent": args[0]} if args else {}


@pytest.fixture(params=INSTANTS, ids=lambda value: value.replace("+00:00", "Z"))
def instant(request):
    return datetime.fromisoformat(request.param)


@pytest.fixture(params=["UTC", "Europe/Warsaw"])
def host_zone(request, monkeypatch):
    original = os.environ.get("TZ")
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    try:
        yield ZoneInfo(request.param)
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


@pytest.fixture
def clock(monkeypatch, instant, host_zone):
    """Control application clocks without changing stdlib/ORM date identities."""
    real_date = date
    real_datetime = datetime
    # Load lazy scheduler consumers before replacing imported aliases; otherwise
    # the first controlled date survives subsequent parametrized test cases.
    importlib.import_module("continental.scheduler")
    importlib.import_module("flagdle.scheduler")


    class ControlledDate(real_date):
        @classmethod
        def today(cls):
            return instant.astimezone(host_zone).date()

    class ControlledDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return instant.astimezone(host_zone).replace(tzinfo=None)
            return instant.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return instant.replace(tzinfo=None)

    controlled_module = ModuleType("datetime")
    controlled_module.__dict__.update(vars(datetime_module))
    controlled_module.date = ControlledDate
    controlled_module.datetime = ControlledDatetime

    def application_module(module):
        filename = getattr(module, "__file__", None)
        return bool(filename and Path(filename).is_relative_to(SERVER_ROOT)
                    and not Path(filename).is_relative_to(SERVER_ROOT / "tests"))

    # Load the shared clock before patching aliases imported by consumers. Until
    # the UTC cutover exists, legacy local reads retain their host-zone semantics.
    shared_clock = (importlib.import_module("daily_clock")
                    if importlib.util.find_spec("daily_clock") is not None else None)
    clock_functions = {}
    if shared_clock is not None:
        clock_functions = {
            shared_clock.utc_now: lambda: instant,
            shared_clock.utc_today: lambda: instant.date(),
        }

    for module in list(sys.modules.values()):
        if not application_module(module):
            continue
        for name, value in list(vars(module).items()):
            if value is real_date:
                monkeypatch.setattr(module, name, ControlledDate)
            elif value is real_datetime:
                monkeypatch.setattr(module, name, ControlledDatetime)
            elif value is datetime_module:
                monkeypatch.setattr(module, name, controlled_module)
            else:
                for original, replacement in clock_functions.items():
                    if value is original:
                        monkeypatch.setattr(module, name, replacement)
                        break

    # Function-local imports bypass module bindings. Scope their replacement to
    # application callers; SQLAlchemy, JWT and the test itself import real types.
    # In particular, SQLite's lazy bind processors must capture datetime.date,
    # not ControlledDate, so seeded base-date objects remain valid ORM values.
    real_import = builtins.__import__

    def application_import(name, globals=None, locals=None, fromlist=(), level=0):
        imported = real_import(name, globals, locals, fromlist, level)
        filename = (globals or {}).get("__file__")
        if (name == "datetime" and level == 0 and filename
                and Path(filename).is_relative_to(SERVER_ROOT)
                and not Path(filename).is_relative_to(SERVER_ROOT / "tests")):
            return controlled_module
        return imported

    monkeypatch.setattr(builtins, "__import__", application_import)
    monkeypatch.setattr(random, "choice", lambda values: sorted(values, key=lambda v: getattr(v, "id", v))[0])
    return SimpleNamespace(now=instant, today=instant.date(), local_date=instant.astimezone(host_zone).date())


@pytest.fixture
def daily_db(clock):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def controlled_database_date(connection, _):
        # Deliberately distinguish DB-local identity from UTC application time.
        # Date defaults use current_timestamp in these models; returning a date
        # string gives SQLite's Date columns the same value as PostgreSQL NOW()
        # coerced to DATE in the configured database/session timezone.
        connection.create_function("current_date", 0, lambda: clock.local_date.isoformat())
        connection.create_function("current_timestamp", 0, lambda: clock.local_date.isoformat())
        # This date oracle does not establish PostgreSQL lock semantics; the
        # separate real-PostgreSQL accounting suite covers those transactions.
        connection.create_function("pg_advisory_xact_lock", 1, lambda _: None)

    models = [Country, User, UserPoints, CountrydleDay, CountrydleState,
              FlagdleDay, FlagdleState, ContinentalDay, ContinentalState,
              Powiat, PowiatdleDay, PowiatdleState, USState, USStatedleDay, USStatedleState,
              Wojewodztwo, WojewodztwodleDay, WojewodztwodleState, FallbackAnswer, FallbackAnswerBlock,
              GuestParticipation,
              CountrydleGuess, CountrydleQuestion, ContinentalGuess, ContinentalQuestion,
              FlagdleGuess, FlagdleQuestion, PowiatdleGuess, PowiatdleQuestion,
              USStatedleGuess, USStatedleQuestion, WojewodztwodleGuess, WojewodztwodleQuestion]
    for model in models:
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([
            Country(id=1, name="Poland", md_file="Poland.md"),
            Country(id=2, name="Japan", md_file="Japan.md"),
            Country(id=3, name="Kenya", md_file="Kenya.md"),
            Country(id=4, name="Canada", md_file="Canada.md"),
            Country(id=5, name="Germany", md_file="Germany.md"),
            Powiat(id=1, nazwa="powiat krakowski"),
            Powiat(id=2, nazwa="powiat warszawski zachodni"),
            USState(id=1, name="Texas", code="TX"),
            USState(id=2, name="Ohio", code="OH"),
            Wojewodztwo(id=1, nazwa="małopolskie"),
            Wojewodztwo(id=2, nazwa="mazowieckie"),
        ])
        session.commit()
        async_session = SimpleNamespace(
            execute=AsyncMock(side_effect=session.execute),
            scalar=AsyncMock(side_effect=session.scalar),
            scalars=AsyncMock(side_effect=session.scalars),
            flush=AsyncMock(side_effect=session.flush),
            add=session.add, add_all=session.add_all,
            commit=AsyncMock(side_effect=session.commit),
            refresh=AsyncMock(side_effect=session.refresh),
            rollback=AsyncMock(side_effect=session.rollback),
            get_bind=session.get_bind,
        )
        yield SimpleNamespace(sync=session, async_session=async_session)
    engine.dispose()


@pytest.fixture
def daily_session_factory(monkeypatch, daily_db):
    @asynccontextmanager
    async def factory():
        yield daily_db.async_session

    monkeypatch.setattr(utils, "AsyncSessionLocal", factory)
    flag_scheduler = importlib.import_module("flagdle.scheduler")
    monkeypatch.setattr(flag_scheduler, "AsyncSessionLocal", factory)
    return factory


@pytest.mark.parametrize("mode,model,target,repo_type,today_method,history_method,generation_method",
                         MODES, ids=[row[0] for row in MODES])
async def test_today_and_history_choose_utc_puzzle_not_host_or_database_date(
    clock, daily_db, mode, model, target, repo_type, today_method, history_method, generation_method,
):
    rows = [model(date=clock.today + timedelta(days=offset), **{target: 1}, **day_kwargs(mode))
            for offset in (-1, 0, 1)]
    daily_db.sync.add_all(rows)
    daily_db.sync.commit()
    repository = repo_type(daily_db.async_session)
    today = await getattr(repository, today_method)(*continent_args(mode))
    history = await getattr(repository, history_method)(*continent_args(mode))
    assert today is not None
    assert (today.id, today.date) == (rows[1].id, clock.today)
    assert [(entry.id, entry.date) for entry in history] == [(rows[0].id, clock.today - timedelta(days=1))]


@pytest.mark.parametrize("mode,model,target,repo_type,today_method,history_method,generation_method",
                         MODES, ids=[row[0] for row in MODES])
async def test_default_generation_assigns_explicit_utc_puzzle_date(
    clock, daily_db, monkeypatch, mode, model, target, repo_type, today_method, history_method, generation_method,
):
    if continent_args(mode):
        # Candidate enumeration is the only fact boundary replaced. The actual
        # generation/cooldown/date choice and persistence execute unchanged.
        monkeypatch.setattr("db.repositories.continental.get_continent_country_ids",
                            AsyncMock(return_value=[1]))
    generated = await getattr(repo_type(daily_db.async_session), generation_method)(*continent_args(mode))
    assert generated.date == clock.today
    stored = daily_db.sync.scalar(select(model).where(model.id == generated.id))
    assert (stored.id, stored.date, getattr(stored, target)) == (generated.id, clock.today, 1)


@pytest.mark.parametrize("mode,model,target,repo_type,today_method,history_method,generation_method",
                         MODES, ids=[row[0] for row in MODES])
async def test_time_http_and_each_state_http_agree_on_utc_identity(
    clock, daily_db, monkeypatch, mode, model, target, repo_type, today_method, history_method, generation_method,
):
    today = model(date=clock.today, **{target: 1}, **day_kwargs(mode))
    tomorrow = model(date=clock.today + timedelta(days=1), **{target: 2}, **day_kwargs(mode))
    daily_db.sync.add_all([today, tomorrow, User(id=1, email="played@example.test", verified=True)])
    daily_db.sync.flush()
    played_state = STATE_MODELS[mode](
        user_id=1, day_id=today.id, is_game_over=True, won=True,
        questions_asked=2, guesses_made=1, points=17,
    )
    daily_db.sync.add(played_state)
    daily_db.sync.commit()

    async def database():
        yield daily_db.async_session

    async def guest():
        return None

    monkeypatch.setitem(app_module.app.dependency_overrides, get_db, database)
    monkeypatch.setitem(app_module.app.dependency_overrides, get_current_or_guest_user, guest)
    async with AsyncClient(transport=ASGITransport(app=app_module.app), base_url="http://daily.test") as client:
        time_response = await client.get("/time")
        state_response = await client.get(f"/{mode}/state")
    assert time_response.status_code == 200
    assert state_response.status_code == 200, state_response.text
    time_data = time_response.json()
    now = datetime.fromisoformat(time_data["server_time"])
    rollover = datetime.fromisoformat(time_data["next_game_at"])
    assert now == clock.now
    assert rollover == datetime.combine(clock.today + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    assert 0 < (rollover - now).total_seconds() <= 86400
    state_data = state_response.json()
    assert state_data["date"] == now.date().isoformat()
    daily_db.sync.expire_all()
    assert (today.date, getattr(today, target)) == (clock.today, 1)
    assert (tomorrow.date, getattr(tomorrow, target)) == (clock.today + timedelta(days=1), 2)
    assert (played_state.day_id, played_state.is_game_over, played_state.won,
            played_state.questions_asked, played_state.guesses_made, played_state.points) == (
        today.id, True, True, 2, 1, 17)


@pytest.mark.parametrize("function_name,minute", [
    ("generate_day_countries", 0), ("check_streaks", 0),
    ("generate_yesterday_blog_post", 5), ("run_generate_continental_days", 0),
    ("generate_day_flags", 0), ("purge_old_fallback_answers", 10),
])
async def test_actual_scheduled_jobs_fire_at_utc_rollover_even_through_dst(
    monkeypatch, instant, host_zone, function_name, minute,
):
    # conftest imports app/utils before test fixtures set TZ. Re-evaluate the
    # actual scheduler registration with a controlled OS timezone resolver;
    # explicit UTC CronTriggers must ignore that resolver.
    monkeypatch.setattr("apscheduler.triggers.cron.get_localzone", lambda: host_zone)
    original_bindings = vars(utils).copy()
    try:
        importlib.reload(utils)
        job = next(job for job in utils.scheduler.get_jobs() if job.func.__name__ == function_name)
        trigger = job.trigger
        expected = datetime.combine(instant.date(), datetime.min.time(), tzinfo=UTC) + timedelta(minutes=minute)
        if expected < instant:
            expected += timedelta(days=1)
        first = trigger.get_next_fire_time(None, instant)
        second = trigger.get_next_fire_time(first, first + timedelta(microseconds=1))
        assert first.astimezone(UTC) == expected
        assert second.astimezone(UTC) == expected + timedelta(days=1)
    finally:
        # Do not replace the process-wide scheduler for unrelated tests.
        vars(utils).clear()
        vars(utils).update(original_bindings)


@pytest.mark.parametrize("generator", ["countrydle", "flagdle", "continental"])
async def test_generation_window_is_utc_and_existing_played_targets_are_unchanged(
    clock, daily_db, daily_session_factory, monkeypatch, generator,
):
    user = User(id=1, email="utc-player@example.test", verified=True)
    daily_db.sync.add(user)
    if generator == "continental":
        model, state_model = ContinentalDay, ContinentalState
        played_days = [model(continent=continent, country_id=index + 1, date=clock.today)
                       for index, continent in enumerate(ContinentCode)]
    else:
        model, state_model = ((CountrydleDay, CountrydleState) if generator == "countrydle"
                              else (FlagdleDay, FlagdleState))
        played_days = [model(country_id=1, date=clock.today)]
    daily_db.sync.add_all(played_days)
    daily_db.sync.flush()
    states = [state_model(user_id=user.id, day_id=day.id, is_game_over=True, won=True,
                          questions_asked=2, guesses_made=1,
                          **({"remaining_questions": 0} if generator != "flagdle" else {}),
                          remaining_guesses=0, points=17) for day in played_days]
    daily_db.sync.add_all(states)
    daily_db.sync.commit()
    before = [(day.id, day.date, day.country_id) for day in played_days]

    if generator == "countrydle":
        await utils.generate_day_countries()
        await utils.generate_day_countries()
    elif generator == "flagdle":
        await utils.generate_day_flags()
        await utils.generate_day_flags()
    else:
        continental_scheduler = importlib.import_module("continental.scheduler")
        monkeypatch.setattr(continental_scheduler, "get_continent_country_ids", AsyncMock(return_value=[1, 2, 3, 4]))
        await continental_scheduler.generate_continental_days(daily_db.async_session)
        await continental_scheduler.generate_continental_days(daily_db.async_session)
    daily_db.sync.expire_all()
    rows = daily_db.sync.scalars(select(model)).all()
    assert {day.date for day in rows} == {clock.today + timedelta(days=n) for n in range(5)}
    assert len(rows) == (20 if generator == "continental" else 5)
    assert [(day.id, day.date, day.country_id) for day in played_days] == before
    assert [(state.day_id, state.is_game_over, state.won, state.questions_asked,
             state.guesses_made, state.points) for state in states] == [
        (day.id, True, True, 2, 1, 17) for day in played_days]


async def test_streak_check_uses_completed_utc_yesterday_not_in_progress_host_yesterday(
    clock, daily_db, daily_session_factory,
):
    user = User(id=1, email="streak@example.test", verified=True)
    points = UserPoints(user_id=1, streak=7)
    yesterday = CountrydleDay(country_id=1, date=clock.today - timedelta(days=1))
    today = CountrydleDay(country_id=2, date=clock.today)
    daily_db.sync.add_all([user, points, yesterday, today])
    daily_db.sync.flush()
    daily_db.sync.add_all([
        CountrydleState(user_id=1, day_id=yesterday.id, is_game_over=True, won=True),
        CountrydleState(user_id=1, day_id=today.id, is_game_over=False, won=False),
    ])
    daily_db.sync.commit()
    await utils.check_streaks()
    daily_db.sync.refresh(points)
    assert points.streak == 7


async def test_profile_hides_current_utc_target_but_keeps_yesterdays_completed_target(clock, daily_db):
    user = User(id=1, email="history@example.test", verified=True)
    yesterday = CountrydleDay(country_id=1, date=clock.today - timedelta(days=1))
    today = CountrydleDay(country_id=2, date=clock.today)
    daily_db.sync.add_all([user, yesterday, today])
    daily_db.sync.flush()
    daily_db.sync.add_all([CountrydleState(user_id=1, day_id=day.id, is_game_over=True, won=True)
                           for day in (yesterday, today)])
    daily_db.sync.commit()
    states = await CountrydleStateRepository(daily_db.async_session).get_player_countrydle_states(user, show_today=False)
    by_date = {state.day.date: state for state in states}
    assert by_date[clock.today].day.country is None
    assert by_date[clock.today - timedelta(days=1)].day.country.id == 1
    # The disclosure operation is not a target reassignment in the database.
    daily_db.sync.rollback()
    assert daily_db.sync.get(CountrydleDay, today.id).country_id == 2


async def test_country_frequency_counts_exclude_the_current_utc_puzzle(clock, daily_db):
    daily_db.sync.add_all([
        CountrydleDay(country_id=1, date=clock.today - timedelta(days=1)),
        CountrydleDay(country_id=2, date=clock.today),
    ])
    daily_db.sync.commit()
    counts = await CountrydleRepository(daily_db.async_session).get_countries_count()
    assert [(row[0], row[2], row[3]) for row in counts] == [
        (1, 1, clock.today - timedelta(days=1))]


async def test_fallback_expiry_removes_only_days_before_utc_today(clock, daily_db, daily_session_factory):
    for offset in (-1, 0, 1):
        puzzle_date = clock.today + timedelta(days=offset)
        daily_db.sync.add(FallbackAnswer(key=f"answer-{offset}", signature=f"signature-{offset}",
                                         game_date=puzzle_date, answer=True, explanation="Fixture evidence"))
        daily_db.sync.add(FallbackAnswerBlock(signature=f"block-{offset}", game_date=puzzle_date))
    daily_db.sync.commit()
    await utils.purge_old_fallback_answers()
    assert [(entry.key, entry.game_date) for entry in daily_db.sync.scalars(
        select(FallbackAnswer).order_by(FallbackAnswer.game_date))] == [
        ("answer-0", clock.today), ("answer-1", clock.today + timedelta(days=1))]
    assert [(entry.signature, entry.game_date) for entry in daily_db.sync.scalars(
        select(FallbackAnswerBlock).order_by(FallbackAnswerBlock.game_date))] == [
        ("block-0", clock.today), ("block-1", clock.today + timedelta(days=1))]
