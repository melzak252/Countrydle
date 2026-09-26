from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.base import Base
from db.models import (
    CountrydleDay, CountrydleState, ContinentalDay, ContinentalState, ContinentCode,
    FlagdleDay, FlagdleState, PowiatdleDay, PowiatdleState,
    USStatedleDay, USStatedleState, WojewodztwodleDay, WojewodztwodleState, User,
)
from db.repositories.countrydle import CountrydleStateRepository
from db.repositories.continental import ContinentalStateRepository
from db.repositories.flagdle import FlagdleStateRepository
from db.repositories.powiatdle import PowiatdleDayRepository, PowiatdleStateRepository
from db.repositories.us_statedle import USStatedleDayRepository, USStatedleStateRepository
from db.repositories.wojewodztwodle import WojewodztwodleDayRepository, WojewodztwodleStateRepository


CASES = [
    (CountrydleDay, CountrydleState, CountrydleStateRepository, None),
    (PowiatdleDay, PowiatdleState, PowiatdleStateRepository, None),
    (USStatedleDay, USStatedleState, USStatedleStateRepository, None),
    (WojewodztwodleDay, WojewodztwodleState, WojewodztwodleStateRepository, None),
    (FlagdleDay, FlagdleState, FlagdleStateRepository, None),
    *[(ContinentalDay, ContinentalState, ContinentalStateRepository, continent) for continent in ContinentCode],
]


class AsyncQuerySession:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


@pytest.mark.anyio
@pytest.mark.parametrize("day_model,state_model,repository,continent", CASES,
                         ids=["country", "powiat", "us-state", "wojewodztwo", "flagdle", "europe", "asia", "africa", "americas"])
@pytest.mark.parametrize("history,expected", [
    ([], 0),
    ([(-1, True), (-2, True)], 2),
    ([(-1, True), (-3, True)], 1),
    ([(-1, False), (-2, True)], 0),
    ([(-2, True)], 0),
], ids=["first-win", "consecutive", "gap-after-win", "previous-loss", "missed-yesterday"])
async def test_score_streak_excludes_current_win_and_stops_at_gap_or_loss(
    day_model, state_model, repository, continent, history, expected
):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, day_model.__table__, state_model.__table__])
    today = date(2026, 9, 26)
    try:
        with Session(engine) as session:
            for day_id, (offset, won) in enumerate([(0, True), *history], start=1):
                values = {"id": day_id, "date": today + timedelta(days=offset)}
                if day_model in (ContinentalDay, FlagdleDay):
                    values["country_id"] = 1
                if continent is not None:
                    values["continent"] = continent
                session.add(day_model(**values))
                session.flush()
                session.add(state_model(user_id=1, day_id=day_id, won=won,
                                        is_game_over=True, guesses_made=1))
            # A different account's win must not contribute to this player's streak.
            session.add(state_model(user_id=2, day_id=1, won=True, is_game_over=True, guesses_made=1))
            session.flush()
            repo = repository(AsyncQuerySession(session))
            if continent is None:
                streak = await repo.get_current_streak(1, today)
            else:
                streak = await repo.get_current_streak(1, today, continent)
            assert streak == expected
    finally:
        engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("day_model,repository,lookup", [
    (PowiatdleDay, PowiatdleDayRepository, "get_day_powiat_by_date"),
    (USStatedleDay, USStatedleDayRepository, "get_day_us_state_by_date"),
    (WojewodztwodleDay, WojewodztwodleDayRepository, "get_day_wojewodztwo_by_date"),
], ids=["powiat", "us-state", "wojewodztwo"])
async def test_guest_sync_resolves_requested_puzzle_date(day_model, repository, lookup):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[day_model.__table__])
    requested = date(2026, 9, 25)
    try:
        with Session(engine) as session:
            session.add_all([
                day_model(id=1, date=requested),
                day_model(id=2, date=requested + timedelta(days=1)),
            ])
            session.flush()
            find_day = getattr(repository(AsyncQuerySession(session)), lookup)
            assert (await find_day(requested)).id == 1
            assert await find_day(requested - timedelta(days=1)) is None
    finally:
        engine.dispose()
