from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models.us_statedle import USStatedleDay
from db.repositories.us_statedle import USStatedleDayRepository


@pytest.mark.anyio
async def test_get_today_us_state_selects_one_deterministic_row_when_duplicates_exist():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(USStatedleDay.__table__.create)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            current_date = await session.scalar(select(func.current_date()))
            today = current_date
            first = USStatedleDay(date=today)
            duplicate = USStatedleDay(date=today)
            session.add_all([first, duplicate])
            await session.commit()

            selected = await USStatedleDayRepository(session).get_today_us_state()

            assert selected.id == first.id
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_generate_new_day_reuses_day_created_while_waiting_for_lock():
    existing_day = SimpleNamespace(id=14, date=date.today(), us_state_id=23)
    state = SimpleNamespace(id=7)
    statements = []

    def rows_result(rows):
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        return result

    day_result = MagicMock()
    day_result.scalar_one_or_none.return_value = existing_day

    async def execute(statement):
        sql = str(statement).lower()
        statements.append(sql)
        if "pg_advisory_xact_lock" in sql:
            return MagicMock()
        if "select us_statedle_days.us_state_id" in sql:
            return rows_result([])
        if "from us_states" in sql:
            return rows_result([state])
        if "from us_statedle_days" in sql:
            return day_result
        raise AssertionError(f"Unexpected statement: {statement}")

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    repository = USStatedleDayRepository(session)

    selected = await repository.generate_new_day_us_state()

    assert selected is existing_day
    assert "pg_advisory_xact_lock" in statements[0]
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
