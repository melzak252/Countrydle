from datetime import date, timedelta
import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from continental.utils import get_continent_country_names
from db.models import Country, CountrydleDay
from db.models.continental import ContinentCode
from db.models.flagdle import FlagdleDay
from db.repositories.country import CountryRepository
from db.repositories.countrydle import CountrydleRepository
from db.repositories.flagdle import FlagdleDayRepository
from friend_matches import providers


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
    country_session.add(CountrydleDay(country_id=1, date=date.today()))
    country_session.add(CountrydleDay(country_id=1, date=date.today() - timedelta(days=1)))
    await country_session.commit()
    repo = CountrydleRepository(country_session)
    with pytest.raises(HTTPException) as exc:
        await repo.get_today_country()
    assert exc.value.status_code == 503
    yesterday = await repo.get_day_country_by_date(date.today() - timedelta(days=1))
    assert yesterday.country_id == 1


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/countrydle/guess", "/flagdle/guess", "/continental/asia/guess",
                                 "/continental/europe/guess"])
async def test_guess_endpoints_reject_disabled_id_even_with_eligible_name(async_client, monkeypatch, path):
    monkeypatch.setattr(CountryRepository, "get", AsyncMock(
        return_value=SimpleNamespace(id=1, name="Israel", official_name="State of Israel")))
    response = await async_client.post(path, json={"country_id": 1, "guess": "Poland"})
    assert response.status_code == 400


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["countrydle", "flagdle", "continental"])
async def test_guest_sync_rejects_disabled_country_before_importing_progress(monkeypatch, mode):
    import importlib
    from db.repositories.countrydle import CountrydleStateRepository
    from db.repositories.flagdle import FlagdleDayRepository, FlagdleStateRepository
    from db.repositories.continental import ContinentalDayRepository, ContinentalStateRepository

    day = SimpleNamespace(id=9, country_id=3, country=SimpleNamespace(id=3, name="Kosovo"))
    state = SimpleNamespace(questions_asked=0, guesses_made=0)
    repositories = {
        "countrydle": (CountrydleRepository, "get_day_country_by_date", CountrydleStateRepository),
        "flagdle": (FlagdleDayRepository, "get_day_flag_by_date", FlagdleStateRepository),
        "continental": (ContinentalDayRepository, "get_day_by_date", ContinentalStateRepository),
    }
    day_repo, method, state_repo = repositories[mode]
    monkeypatch.setattr(day_repo, method, AsyncMock(return_value=day))
    monkeypatch.setattr(state_repo, "get_state", AsyncMock(return_value=state))
    monkeypatch.setattr(CountryRepository, "get", AsyncMock(
        return_value=SimpleNamespace(id=1, name="Israel", official_name="State of Israel")))
    data = SimpleNamespace(date=date.today().isoformat(), questions=[],
                           guesses=[SimpleNamespace(country_id=1, guess="Kosovo")])
    kwargs = {"sync_data": data, "user": SimpleNamespace(id=1), "session": AsyncMock(),
              "request": Request({"type": "http", "headers": []})}
    if mode == "continental":
        kwargs["continent"] = ContinentCode.EUROPE
    with pytest.raises(HTTPException) as exc:
        await importlib.import_module(mode).sync_guest_data(**kwargs)
    assert exc.value.status_code == 400
    assert state.guesses_made == 0


@pytest.mark.real_database
@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["world", "flagdle"])
async def test_generation_cooldown_fallback_still_excludes_israel(country_session, monkeypatch, mode):
    model = CountrydleDay if mode == "world" else FlagdleDay
    for cid in (2, 3):
        country_session.add(model(country_id=cid, date=date.today() - timedelta(days=cid)))
    await country_session.commit()
    monkeypatch.setattr("db.repositories.countrydle.random.choice", lambda pool: pool[0])
    if mode == "world":
        day = await CountrydleRepository(country_session).generate_new_day_country(day_date=date.today())
    else:
        day = await FlagdleDayRepository(country_session).generate_new_day_flag(target_date=date.today())
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
