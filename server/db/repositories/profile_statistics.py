from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.friend_match import FriendMatch, FriendSeat
from db.models.powiat import Powiat
from db.models.powiatdle import PowiatdleDay, PowiatdleState
from db.models.continental import ContinentCode, ContinentalDay, ContinentalState
from db.models.us_state import USState
from db.models.us_statedle import USStatedleDay, USStatedleState
from db.models.user import User
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState
from schemas.statistics import (
    FriendMatchStatistics,
    GameHistoryEntry,
    GameStatistics,
    FriendMatchHistoryEntry,
    UserProfileStatistics,
)


# Each profile mode reads its points, progress counters, and terminal status from
# its own state table. Continental modes additionally scope the shared tables.
DAILY_GAME_TABLES = {
    "countrydle": (CountrydleState, CountrydleDay, Country, CountrydleDay.country_id, Country.name, None),
    "powiatdle": (PowiatdleState, PowiatdleDay, Powiat, PowiatdleDay.powiat_id, Powiat.nazwa, None),
    "us_statedle": (USStatedleState, USStatedleDay, USState, USStatedleDay.us_state_id, USState.name, None),
    "wojewodztwodle": (
        WojewodztwodleState,
        WojewodztwodleDay,
        Wojewodztwo,
        WojewodztwodleDay.wojewodztwo_id,
        Wojewodztwo.nazwa,
        None,
    ),
    "flagdle": (FlagdleState, FlagdleDay, Country, FlagdleDay.country_id, Country.name, None),
    "europe": (ContinentalState, ContinentalDay, Country, ContinentalDay.country_id, Country.name, ContinentCode.EUROPE),
    "asia": (ContinentalState, ContinentalDay, Country, ContinentalDay.country_id, Country.name, ContinentCode.ASIA),
    "africa": (ContinentalState, ContinentalDay, Country, ContinentalDay.country_id, Country.name, ContinentCode.AFRICA),
    "americas": (ContinentalState, ContinentalDay, Country, ContinentalDay.country_id, Country.name, ContinentCode.AMERICAS),
}


class ProfileStatisticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_profile_statistics(self, user: User) -> UserProfileStatistics:
        daily_statistics = {
            mode: await self._get_daily_statistics(user, mode)
            for mode in DAILY_GAME_TABLES
        }
        return UserProfileStatistics(
            user=user,
            friend_matches=await self._get_friend_match_statistics(user),
            **daily_statistics,
        )

    async def _get_daily_statistics(self, user: User, mode: str) -> GameStatistics:
        state_model, day_model, target_model, target_id, target_name, continent = DAILY_GAME_TABLES[mode]
        statement = (
            select(
                state_model.id.label("id"),
                state_model.is_game_over.label("is_game_over"),
                state_model.won.label("won"),
                state_model.points.label("points"),
                state_model.guesses_made.label("guesses_made"),
                day_model.date.label("date"),
                target_name.label("target_name"),
            )
            .join(day_model, state_model.day_id == day_model.id)
            .join(target_model, target_id == target_model.id)
            .where(
                state_model.user_id == user.id,
                or_(state_model.questions_asked > 0, state_model.guesses_made > 0),
            )
            .order_by(day_model.date.desc(), state_model.id.desc())
        )
        if continent is not None:
            statement = statement.where(day_model.continent == continent)

        rows = (await self.session.execute(statement)).all()
        completed = [row for row in rows if row.is_game_over]
        wins = sum(bool(row.won) for row in completed)
        completed_games = len(completed)
        points = sum(row.points or 0 for row in rows)
        completed_points = sum(row.points or 0 for row in completed)
        winning_guesses = sum(row.guesses_made or 0 for row in completed if row.won)

        today = datetime.now(timezone.utc).date()
        history = [
            GameHistoryEntry(
                date=row.date.isoformat(),
                won=bool(row.won),
                points=row.points or 0,
                attempts=row.guesses_made or 0,
                target_name="???" if row.date >= today else row.target_name or "???",
            )
            for row in completed
        ]

        # Duplicate states for a puzzle date can exist in older data. They remain
        # visible in history, but count as one result when deriving date streaks.
        completed_by_date: dict[date, Any] = {}
        for row in completed:
            completed_by_date.setdefault(row.date, row)
        daily_results = list(completed_by_date.items())

        current_streak = 0
        if daily_results and daily_results[0][0] in (today, today - timedelta(days=1)):
            latest_date, latest_result = daily_results[0]
            if latest_result.won:
                current_streak = 1
                previous_date = latest_date
                for puzzle_date, result in daily_results[1:]:
                    if not result.won or puzzle_date != previous_date - timedelta(days=1):
                        break
                    current_streak += 1
                    previous_date = puzzle_date

        best_streak = 0
        run_streak = 0
        newer_date = None
        for puzzle_date, result in daily_results:
            if result.won:
                run_streak = run_streak + 1 if newer_date == puzzle_date + timedelta(days=1) else 1
                best_streak = max(best_streak, run_streak)
            else:
                run_streak = 0
            newer_date = puzzle_date

        return GameStatistics(
            points=points,
            wins=wins,
            games_played=len(rows),
            completed_games=completed_games,
            win_rate=wins / completed_games if completed_games else 0,
            streak=current_streak,
            best_streak=best_streak,
            average_points=completed_points / completed_games if completed_games else 0,
            average_winning_guesses=winning_guesses / wins if wins else 0,
            history=history,
        )

    async def _get_friend_match_statistics(self, user: User) -> FriendMatchStatistics:
        statement = (
            select(FriendMatch, FriendSeat)
            .join(FriendSeat, FriendSeat.match_id == FriendMatch.id)
            .where(
                FriendSeat.user_id == user.id,
                FriendMatch.status == "finished",
                FriendMatch.finished_at.is_not(None),
                FriendMatch.result.in_(("solved", "forfeit", "draw")),
            )
            .order_by(FriendMatch.finished_at.desc(), FriendMatch.id.desc(), FriendSeat.id.desc())
        )
        rows = (await self.session.execute(statement)).all()
        seats_by_match: dict[str, tuple[FriendMatch, list[FriendSeat]]] = {}
        for match, seat in rows:
            if match.id not in seats_by_match:
                seats_by_match[match.id] = (match, [])
            seats_by_match[match.id][1].append(seat)

        history = []
        for match, user_seats in seats_by_match.values():
            # More than one seat for an account is self-play, not a friend match.
            if len(user_seats) != 1:
                continue
            if match.result == "draw":
                outcome = "draw"
            elif match.result in ("solved", "forfeit") and match.winner_id:
                outcome = "won" if match.winner_id == user_seats[0].id else "lost"
            else:
                continue
            history.append(
                FriendMatchHistoryEntry(
                    id=match.id,
                    finished_at=match.finished_at,
                    mode=match.mode,
                    outcome=outcome,
                )
            )

        wins = sum(entry.outcome == "won" for entry in history)
        losses = sum(entry.outcome == "lost" for entry in history)
        draws = sum(entry.outcome == "draw" for entry in history)
        games_played = len(history)
        return FriendMatchStatistics(
            games_played=games_played,
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=wins / games_played if games_played else 0,
            history=history,
        )
