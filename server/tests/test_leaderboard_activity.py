from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.base import Base
from db.models.continental import ContinentalDay, ContinentalState, ContinentCode
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.powiatdle import PowiatdleDay, PowiatdleState
from db.models.us_statedle import USStatedleDay, USStatedleState
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.user import User, UserPoints
from db.repositories.countrydle import CountrydleRepository
from db.repositories.continental import ContinentalStateRepository
from db.repositories.flagdle import FlagdleStateRepository
from db.repositories.powiatdle import PowiatdleStateRepository
from db.repositories.us_statedle import USStatedleStateRepository
from db.repositories.wojewodztwodle import WojewodztwodleStateRepository


CASES = [
    (CountrydleDay, CountrydleState, CountrydleRepository, 5),
    (USStatedleDay, USStatedleState, USStatedleStateRepository, 5),
    (PowiatdleDay, PowiatdleState, PowiatdleStateRepository, 5),
    (WojewodztwodleDay, WojewodztwodleState, WojewodztwodleStateRepository, 5),
    (ContinentalDay, ContinentalState, ContinentalStateRepository, 3),
    (FlagdleDay, FlagdleState, FlagdleStateRepository, 5),
]


class AsyncReportingSession:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


@pytest.fixture(params=CASES, ids=['country', 'us_states', 'powiaty', 'wojewodztwa', 'continental', 'flagdle'])
def leaderboard_db(request):
    day_cls, state_cls, repo_cls, minimum = request.param
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine, tables=[User.__table__, UserPoints.__table__, day_cls.__table__, state_cls.__table__])
    with Session(engine) as session:
        session.add_all([User(id=i, username=f'player{i}', email=f'player{i}@example.com') for i in range(1, 7)])
        session.flush()
        yield session, day_cls, state_cls, repo_cls(AsyncReportingSession(session)), minimum
    engine.dispose()


def add_day(session, day_cls, day_id, puzzle_date, continent=ContinentCode.EUROPE):
    values = {'id': day_id, 'date': puzzle_date}
    if day_cls is ContinentalDay:
        values.update(continent=continent, country_id=1)
    elif day_cls is FlagdleDay:
        values.update(country_id=1)
    session.add(day_cls(**values))
    session.flush()

async def rankings(repo, kind):
    if isinstance(repo, ContinentalStateRepository):
        return await repo.get_leaderboard(ContinentCode.EUROPE, type=kind)
    return await repo.get_leaderboard(kind)


@pytest.mark.anyio
async def test_monthly_rankings_exclude_idle_accounts_but_keep_zero_point_players(leaderboard_db):
    session, day_cls, state_cls, repo, _ = leaderboard_db
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)
    next_month = month_start.replace(year=month_start.year + (month_start.month == 12), month=(month_start.month % 12) + 1)
    add_day(session, day_cls, 1, today)
    add_day(session, day_cls, 2, month_start - timedelta(days=1))
    add_day(session, day_cls, 3, next_month)
    if day_cls is ContinentalDay:
        add_day(session, day_cls, 4, today, continent=ContinentCode.ASIA)
    session.add_all([
        state_cls(user_id=1, day_id=1),
        state_cls(user_id=2, day_id=1, questions_asked=1),
        state_cls(user_id=3, day_id=1, guesses_made=1),
        state_cls(user_id=4, day_id=1),
        state_cls(user_id=4, day_id=2, guesses_made=1, won=True, points=1000),
        state_cls(user_id=5, day_id=1, guesses_made=1, won=True, points=2000),
        state_cls(user_id=6, day_id=3, guesses_made=1, won=True, points=9999),
    ])
    if day_cls is ContinentalDay:
        session.add(state_cls(user_id=5, day_id=4, guesses_made=1, won=True, points=50000))
    session.flush()

    result = await rankings(repo, 'monthly')

    assert [entry.id for entry in result] == [5, 2, 3]
    assert (result[0].points, result[0].wins, result[0].games_played, result[0].average_points) == (2000, 1, 1, 2000.0)
    assert {entry.points for entry in result if entry.id in {2, 3}} == {0}
    assert result[1].id < result[2].id


@pytest.mark.anyio
async def test_average_rankings_do_not_use_idle_rows_to_meet_minimum_games(leaderboard_db):
    session, day_cls, state_cls, repo, minimum = leaderboard_db
    for i in range(minimum):
        add_day(session, day_cls, i + 1, datetime.now(timezone.utc).date() - timedelta(days=i * 20))
        session.add_all([
            state_cls(user_id=1, day_id=i + 1, is_game_over=True),
            state_cls(user_id=2, day_id=i + 1, questions_asked=1, guesses_made=1, is_game_over=True, won=True, points=100),
            state_cls(user_id=3, day_id=i + 1, guesses_made=int(i < minimum - 1), is_game_over=True),
            state_cls(user_id=4, day_id=i + 1, questions_asked=1, is_game_over=True, won=True, points=100),
        ])
    session.flush()

    result = await rankings(repo, 'average')

    assert [entry.id for entry in result] == [2, 4]
    for entry in result:
        assert (entry.points, entry.wins, entry.games_played, entry.average_points) == (minimum * 100, minimum, minimum, 100.0)
