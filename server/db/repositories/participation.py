from datetime import date
from typing import Optional

from sqlalchemy import String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.continental import ContinentalDay, ContinentalState
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.guest_participation import GuestParticipation
from db.models.powiatdle import PowiatdleDay, PowiatdleState
from db.models.us_statedle import USStatedleDay, USStatedleState
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState


MODE_MODELS = (
    ("countrydle", CountrydleState, CountrydleDay),
    ("us_statedle", USStatedleState, USStatedleDay),
    ("powiatdle", PowiatdleState, PowiatdleDay),
    ("wojewodztwodle", WojewodztwodleState, WojewodztwodleDay),
    ("flagdle", FlagdleState, FlagdleDay),
    ("continental", ContinentalState, ContinentalDay),
)


def _participants(start_date=None, end_date=None, mode=None):
    """One active account/browser per puzzle; anonymous legacy events cannot identify people."""
    branches = []
    for key, state, day in MODE_MODELS:
        if mode is not None and key != mode and not (key == "continental" and mode.startswith("continental:")):
            continue
        mode_value = (
            literal("continental:") + cast(day.continent, String)
            if key == "continental" else literal(key)
        )
        day_filters = []
        if start_date is not None:
            day_filters.append(day.date >= start_date)
        if end_date is not None:
            day_filters.append(day.date <= end_date)
        if mode is not None:
            day_filters.append(mode_value == mode)

        branches.append(
            select(
                day.date.label("date"), mode_value.label("mode"), day.id.label("day_id"),
                (literal("user:") + cast(state.user_id, String)).label("identity"),
                state.questions_asked.label("questions"), state.guesses_made.label("guesses"),
                case((state.won.is_(True), 1), else_=0).label("won"),
            )
            .join(day, day.id == state.day_id)
            .where(state.user_id.is_not(None), or_(state.questions_asked > 0, state.guesses_made > 0), *day_filters)
        )
        guest = GuestParticipation
        branches.append(
            select(
                day.date.label("date"), mode_value.label("mode"), day.id.label("day_id"),
                (literal("guest:") + guest.guest_id).label("identity"),
                guest.questions_asked.label("questions"), guest.guesses_made.label("guesses"),
                case((guest.won.is_(True), 1), else_=0).label("won"),
            )
            .join(day, day.id == guest.day_id)
            .where(
                guest.mode == mode_value, guest.user_id.is_(None),
                or_(guest.questions_asked > 0, guest.guesses_made > 0), *day_filters,
            )
        )
    if not branches:
        raise ValueError(f"Unsupported participation mode: {mode}")
    rows = union_all(*branches).subquery()
    # Older state tables lack a unique user/day constraint; duplicate snapshots
    # must not multiply participants, wins or cumulative action counters.
    return select(
        rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity,
        func.max(rows.c.questions).label("questions"),
        func.max(rows.c.guesses).label("guesses"),
        func.max(rows.c.won).label("won"),
    ).group_by(rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity).subquery()


def _aggregate(participants):
    p = participants.c
    return select(
        func.count(func.distinct(p.identity)).label("total_players"),
        func.count().label("total_games"),
        func.coalesce(func.sum(p.won), 0).label("winners_count"),
        func.coalesce(func.sum(p.questions), 0).label("total_questions"),
        func.coalesce(func.sum(p.guesses), 0).label("total_guesses"),
        func.avg(case((p.won == 1, p.questions))).label("avg_questions_won"),
        func.avg(case((p.won == 1, p.guesses))).label("avg_guesses_won"),
    ).select_from(participants)


def _stats(row):
    games = int(row.total_games)
    winners = int(row.winners_count)
    return {
        "total_players": int(row.total_players),
        "total_games": games,
        "winners_count": winners,
        # Players are unique across modes; wins and rate refer to puzzle plays.
        "win_rate_pct": round(winners / games * 100, 1) if games else 0.0,
        "total_questions": int(row.total_questions),
        "total_guesses": int(row.total_guesses),
        "avg_questions_won": round(float(row.avg_questions_won or 0), 1),
        "avg_guesses_won": round(float(row.avg_guesses_won or 0), 1),
    }


class ParticipationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_stats(self, target_date: Optional[date] = None, mode: Optional[str] = None):
        participants = _participants(target_date, target_date, mode)
        result = await self.session.execute(_aggregate(participants))
        return _stats(result.one())

    async def get_mode_stats(self, target_date: date):
        participants = _participants(target_date, target_date)
        result = await self.session.execute(
            _aggregate(participants).add_columns(participants.c.mode).group_by(participants.c.mode)
        )
        return {row.mode: _stats(row) for row in result}

    async def get_daily_stats(self, start_date: date, end_date: date):
        participants = _participants(start_date, end_date)
        result = await self.session.execute(
            _aggregate(participants).add_columns(participants.c.date).group_by(participants.c.date)
        )
        return {row.date: _stats(row) for row in result}
