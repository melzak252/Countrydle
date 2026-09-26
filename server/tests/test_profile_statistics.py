from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import (
    Country,
    CountrydleDay,
    CountrydleState,
    FlagdleDay,
    FlagdleState,
    Powiat,
    PowiatdleDay,
    PowiatdleState,
    USState,
    USStatedleDay,
    USStatedleState,
    User,
    Wojewodztwo,
    WojewodztwodleDay,
    WojewodztwodleState,
)
from db.models.continental import ContinentCode, ContinentalDay, ContinentalState
from db.models.friend_match import FriendMatch, FriendSeat
from db.repositories.user import UserRepository
from users import get_user_stats_by_username


DAILY_MODES = (
    "countrydle",
    "powiatdle",
    "us_statedle",
    "wojewodztwodle",
    "flagdle",
    "europe",
    "asia",
    "africa",
    "americas",
)
DAILY_MODE_TABLES = {
    "countrydle": (CountrydleDay, CountrydleState, "country_id"),
    "powiatdle": (PowiatdleDay, PowiatdleState, "powiat_id"),
    "us_statedle": (USStatedleDay, USStatedleState, "us_state_id"),
    "wojewodztwodle": (WojewodztwodleDay, WojewodztwodleState, "wojewodztwo_id"),
    "flagdle": (FlagdleDay, FlagdleState, "country_id"),
    "europe": (ContinentalDay, ContinentalState, "country_id"),
    "asia": (ContinentalDay, ContinentalState, "country_id"),
    "africa": (ContinentalDay, ContinentalState, "country_id"),
    "americas": (ContinentalDay, ContinentalState, "country_id"),
}
PROFILE_TABLES = [
    model.__table__
    for model in (
        User,
        Country,
        Powiat,
        USState,
        Wojewodztwo,
        CountrydleDay,
        CountrydleState,
        PowiatdleDay,
        PowiatdleState,
        USStatedleDay,
        USStatedleState,
        WojewodztwodleDay,
        WojewodztwodleState,
        FlagdleDay,
        FlagdleState,
        ContinentalDay,
        ContinentalState,
        FriendMatch,
        FriendSeat,
    )
]


@pytest.fixture
async def profile_db():
    url = os.getenv("PROFILE_STATS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PROFILE_STATS_TEST_DATABASE_URL to run profile statistics database regressions")

    schema = f"profile_stats_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    engine = create_async_engine(
        url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection, tables=PROFILE_TABLES, checkfirst=False
                )
            )
        yield factory
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        await bootstrap.dispose()


async def request_profile(session, monkeypatch, username):
    async def get_user(repository, requested_username):
        return await repository.session.scalar(
            select(User).where(User.username == requested_username)
        )

    monkeypatch.setattr(UserRepository, "get_user", get_user)
    return await get_user_stats_by_username(username, session)


async def add_daily_state(
    session,
    user_id,
    mode,
    puzzle_date,
    *,
    won,
    points,
    guesses_made,
    questions_asked=1,
    is_game_over=True,
    target_name=None,
):
    day_model, state_model, target_column = DAILY_MODE_TABLES[mode]
    if target_name is None:
        target_name = f"{mode}-{puzzle_date.isoformat()}"
    if mode in ("powiatdle", "wojewodztwodle"):
        target = Powiat(nazwa=target_name) if mode == "powiatdle" else Wojewodztwo(nazwa=target_name)
    elif mode == "us_statedle":
        target = USState(name=target_name)
    else:
        target = Country(name=target_name, md_file="profile-test")
    session.add(target)
    await session.flush()

    day_values = {target_column: target.id, "date": puzzle_date}
    if mode in ("europe", "asia", "africa", "americas"):
        day_values["continent"] = ContinentCode(mode)
    day = day_model(**day_values)
    session.add(day)
    await session.flush()

    state = state_model(
        user_id=user_id,
        day_id=day.id,
        won=won,
        points=points,
        guesses_made=guesses_made,
        questions_asked=questions_asked,
        is_game_over=is_game_over,
    )
    session.add(state)
    await session.flush()
    return state


async def add_friend_match(
    session,
    user_id,
    *,
    finished_at,
    result,
    mode="countrydle",
    winner_position=0,
    status="finished",
    account_positions=(0,),
):
    match_id = str(uuid4())
    seats = [FriendSeat(
        id=str(uuid4()),
        match_id=match_id,
        position=position,
        name=f"player-{position}",
        credential_hash=uuid4().hex,
        join_request_id=str(uuid4()),
        user_id=user_id if position in account_positions else None,
        last_seen_at=finished_at,
    ) for position in range(2)]
    match = FriendMatch(
        id=match_id,
        invite_code=uuid4().hex,
        create_request_id=str(uuid4()),
        mode=mode,
        status=status,
        phase="finished" if status == "finished" else "thinking",
        version=1,
        turn=1,
        move_ordinal=0,
        created_at=finished_at - timedelta(minutes=5),
        finished_at=finished_at,
        result=result,
        winner_id=seats[winner_position].id if winner_position is not None else None,
    )
    session.add_all([match, *seats])
    await session.flush()
    return match


@pytest.mark.anyio
async def test_profile_stats_count_activity_and_completed_games_in_puzzle_date_order(profile_db, monkeypatch):
    async with profile_db() as session:
        user = User(username="profile-activity", email="profile-activity@example.com", hashed_password="x")
        session.add(user)
        await session.flush()
        today = datetime.now(timezone.utc).date()
        completed_dates_desc = [today - timedelta(days=1), today - timedelta(days=3),
                                today - timedelta(days=8), today - timedelta(days=9),
                                today - timedelta(days=10)]

        for mode_index, mode in enumerate(DAILY_MODES):
            base_points = (mode_index + 1) * 100
            # Insert newest puzzle first: descending state IDs are deliberately not date-descending.
            for index, puzzle_date in enumerate(completed_dates_desc):
                is_loss = puzzle_date == today - timedelta(days=3)
                await add_daily_state(
                    session,
                    user.id,
                    mode,
                    puzzle_date,
                    won=not is_loss,
                    points=base_points + index,
                    guesses_made=3 if is_loss else index + 1,
                )
            await add_daily_state(
                session,
                user.id,
                mode,
                today,
                won=False,
                points=0,
                guesses_made=1,
                is_game_over=False,
            )
            await add_daily_state(
                session,
                user.id,
                mode,
                today - timedelta(days=2),
                won=False,
                points=0,
                guesses_made=0,
                questions_asked=1,
                is_game_over=False,
            )
            await add_daily_state(
                session,
                user.id,
                mode,
                today + timedelta(days=2),
                won=False,
                points=0,
                guesses_made=0,
                questions_asked=0,
                is_game_over=False,
            )
        other_user = User(
            username="profile-other",
            email="profile-other@example.com",
            hashed_password="x",
        )
        session.add(other_user)
        await session.flush()
        countrydle_day_id = await session.scalar(
            select(CountrydleState.day_id)
            .where(CountrydleState.user_id == user.id)
            .order_by(CountrydleState.id)
            .limit(1)
        )
        session.add(
            CountrydleState(
                user_id=other_user.id,
                day_id=countrydle_day_id,
                questions_asked=1,
                guesses_made=1,
                is_game_over=True,
                won=True,
                points=100_000,
            )
        )
        await session.flush()

        profile = await request_profile(session, monkeypatch, user.username)
        for mode_index, mode in enumerate(DAILY_MODES):
            stats = getattr(profile, mode)
            base_points = (mode_index + 1) * 100
            assert (stats.games_played, stats.completed_games, stats.wins) == (7, 5, 4)
            assert stats.win_rate == pytest.approx(0.8)
            assert stats.points == 5 * base_points + 10
            assert stats.average_points == pytest.approx(base_points + 2)
            assert stats.average_winning_guesses == pytest.approx(3.25)
            assert stats.streak == 1
            assert stats.best_streak == 3
            assert [entry.date for entry in stats.history] == [day.isoformat() for day in completed_dates_desc]
            assert stats.history[0].target_name == f"{mode}-{completed_dates_desc[0].isoformat()}"

        assert profile.europe.points != profile.asia.points
        assert profile.asia.points != profile.africa.points
        assert profile.africa.points != profile.americas.points


@pytest.mark.anyio
async def test_profile_history_ties_use_descending_state_id(profile_db, monkeypatch):
    async with profile_db() as session:
        user = User(username="profile-ties", email="profile-ties@example.com", hashed_password="x")
        session.add(user)
        await session.flush()
        puzzle_date = datetime.now(timezone.utc).date() - timedelta(days=1)
        await add_daily_state(
            session, user.id, "countrydle", puzzle_date, won=True, points=10,
            guesses_made=1, target_name="earlier-state",
        )
        await add_daily_state(
            session, user.id, "countrydle", puzzle_date, won=False, points=0,
            guesses_made=3, target_name="later-state",
        )

        profile = await request_profile(session, monkeypatch, user.username)

        assert [entry.target_name for entry in profile.countrydle.history] == [
            "later-state", "earlier-state"
        ]


@pytest.mark.anyio
async def test_profile_public_history_hides_today_and_future_targets(profile_db, monkeypatch):
    async with profile_db() as session:
        user = User(username="profile-hidden", email="profile-hidden@example.com", hashed_password="x")
        session.add(user)
        await session.flush()
        today = datetime.now(timezone.utc).date()
        await add_daily_state(session, user.id, "countrydle", today + timedelta(days=1),
                              won=True, points=90, guesses_made=1)
        await add_daily_state(session, user.id, "countrydle", today,
                              won=True, points=80, guesses_made=2)
        await add_daily_state(session, user.id, "countrydle", today - timedelta(days=1),
                              won=True, points=70, guesses_made=3)

        profile = await request_profile(session, monkeypatch, user.username)
        history = profile.countrydle.history
        assert [entry.date for entry in history] == [
            (today + timedelta(days=1)).isoformat(), today.isoformat(), (today - timedelta(days=1)).isoformat()
        ]
        assert [entry.target_name for entry in history] == ["???", "???", f"countrydle-{(today - timedelta(days=1)).isoformat()}"]


@pytest.mark.anyio
async def test_profile_streak_today_loss_resets_and_missing_dates_break_chains(profile_db, monkeypatch):
    async with profile_db() as session:
        user = User(username="profile-streak", email="profile-streak@example.com", hashed_password="x")
        session.add(user)
        await session.flush()
        today = datetime.now(timezone.utc).date()
        for offset, won in ((0, False), (-1, True), (-2, True), (-4, True), (-5, True), (-6, True)):
            await add_daily_state(session, user.id, "countrydle", today + timedelta(days=offset),
                                  won=won, points=10, guesses_made=2)

        profile = await request_profile(session, monkeypatch, user.username)
        assert profile.countrydle.streak == 0
        assert profile.countrydle.best_streak == 3


@pytest.mark.anyio
async def test_profile_zero_activity_returns_numeric_zeroes_and_empty_histories(profile_db, monkeypatch):
    async with profile_db() as session:
        user = User(username="profile-zero", email="profile-zero@example.com", hashed_password="x")
        session.add(user)
        await session.flush()

        profile = await request_profile(session, monkeypatch, user.username)
        for mode in DAILY_MODES:
            stats = getattr(profile, mode)
            assert stats.points == stats.wins == stats.games_played == stats.completed_games == 0
            assert stats.win_rate == stats.streak == stats.best_streak == 0
            assert stats.average_points == stats.average_winning_guesses == 0
            assert stats.history == []
        assert profile.friend_matches.model_dump() == {
            "games_played": 0, "wins": 0, "losses": 0, "draws": 0, "win_rate": 0, "history": []
        }


@pytest.mark.anyio
async def test_profile_friend_matches_include_only_legitimate_unique_completed_accounts(profile_db, monkeypatch):
    async with profile_db() as session:
        user = User(username="profile-friends", email="profile-friends@example.com", hashed_password="x")
        session.add(user)
        await session.flush()
        now = datetime.now(timezone.utc)
        await add_friend_match(session, user.id, finished_at=now - timedelta(days=3), result="solved",
                               winner_position=0, mode="europe")
        await add_friend_match(session, user.id, finished_at=now - timedelta(days=2), result="forfeit",
                               winner_position=1, mode="countrydle")
        await add_friend_match(session, user.id, finished_at=now - timedelta(days=1), result="draw",
                               winner_position=None, mode="flagdle")
        await add_friend_match(session, user.id, finished_at=now, result="interrupted",
                               winner_position=None)
        await add_friend_match(session, user.id, finished_at=now, result="cancelled",
                               winner_position=None)
        await add_friend_match(session, user.id, finished_at=now, result=None,
                               winner_position=None, status="active")
        await add_friend_match(session, user.id, finished_at=now, result="solved",
                               winner_position=0, account_positions=(0, 1))

        profile = await request_profile(session, monkeypatch, user.username)
        friend_stats = profile.friend_matches
        assert (friend_stats.games_played, friend_stats.wins, friend_stats.losses, friend_stats.draws) == (3, 1, 1, 1)
        assert friend_stats.win_rate == pytest.approx(1 / 3)
        assert [entry.outcome for entry in friend_stats.history] == ["draw", "lost", "won"]
        assert [entry.mode for entry in friend_stats.history] == ["flagdle", "countrydle", "europe"]
        assert all("points" not in entry.model_dump() for entry in friend_stats.history)
        assert "points" not in friend_stats.model_dump()
