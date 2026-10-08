import pytest
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from countrydle.local_answering import DEFAULT_DB_PATH, execute_local_plan
from db.base import Base
from db.models import Country, CountrydleDay
from db.repositories.countrydle import CountrydleRepository

requires_country_facts = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="Countrydle local SQLite KB is missing",
)


@requires_country_facts
def test_flag_color_evaluation():
    p_red = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_color"},
        "right": {"value": "red"},
    }
    p_green = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_color"},
        "right": {"value": "green"},
    }

    # Poland has red, but not green
    assert execute_local_plan(p_red, "Poland", "Is there red on the flag?").answer is True
    assert execute_local_plan(p_green, "Poland", "Is there green on the flag?").answer is False

    # Brazil has green, but not red
    assert execute_local_plan(p_green, "Brazil", "Is there green on the flag?").answer is True
    assert execute_local_plan(p_red, "Brazil", "Is there red on the flag?").answer is False


@requires_country_facts
def test_flag_symbol_evaluation():
    p_star = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_symbol"},
        "right": {"value": "star"},
    }
    p_cross = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_symbol"},
        "right": {"value": "cross"},
    }

    # USA has stars
    assert execute_local_plan(p_star, "United States", "Does the flag have a star?").answer is True
    assert execute_local_plan(p_cross, "United States", "Does the flag have a cross?").answer is False

    # United Kingdom has cross
    assert execute_local_plan(p_cross, "United Kingdom", "Does the flag have a cross?").answer is True
    assert execute_local_plan(p_star, "United Kingdom", "Does the flag have a star?").answer is False


@requires_country_facts
def test_historical_unions_evaluation():
    p_ussr = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "historical_union"},
        "right": {"value": "USSR"},
    }
    p_yugo = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "historical_union"},
        "right": {"value": "Yugoslavia"},
    }

    # Russia was in USSR
    assert execute_local_plan(p_ussr, "Russia", "Was it part of USSR?").answer is True
    # Poland was not in USSR
    assert execute_local_plan(p_ussr, "Poland", "Was it part of USSR?").answer is False

    # Croatia was in Yugoslavia
    assert execute_local_plan(p_yugo, "Croatia", "Was it in Yugoslavia?").answer is True
    # Poland was not in Yugoslavia
    assert execute_local_plan(p_yugo, "Poland", "Was it in Yugoslavia?").answer is False


@pytest.mark.real_database
@pytest.mark.parametrize("requested_date", [None, date(2026, 9, 29)])
@pytest.mark.anyio
async def test_countrydle_cooldown_excludes_recent_entities(tmp_path, monkeypatch, requested_date):
    from db.repositories import countrydle

    today = date(2026, 10, 4)
    target_date = requested_date if requested_date is not None else today
    monkeypatch.setattr(countrydle, "utc_today", lambda: today)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cooldown.sqlite'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda db: Base.metadata.create_all(
                    db, tables=[Country.__table__, CountrydleDay.__table__]
                )
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            session.add_all([
                Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"),
                Country(id=2, name="Germany", official_name="Federal Republic of Germany", md_file="germany.md"),
                Country(id=3, name="France", official_name="French Republic", md_file="france.md"),
                # Insert out of chronological order to exercise the SQL ordering.
                CountrydleDay(country_id=3, date=target_date - timedelta(days=3)),
                CountrydleDay(country_id=1, date=target_date - timedelta(days=1)),
                CountrydleDay(country_id=2, date=target_date - timedelta(days=2)),
            ])
            await session.commit()

            created = await CountrydleRepository(session).generate_new_day_country(
                day_date=requested_date, cooldown_days=2
            )

            # France's older appearance is outside the two most recent puzzles.
            assert created.country_id == 3
            assert created.date == target_date
            persisted = (await session.execute(
                select(CountrydleDay).where(CountrydleDay.date == target_date)
            )).scalar_one()
            assert persisted.id == created.id
            assert persisted.country_id == 3
            days = (await session.execute(select(CountrydleDay))).scalars().all()
            assert len(days) == 4
    finally:
        await engine.dispose()
