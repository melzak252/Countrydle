from datetime import datetime, timezone

from sqlalchemy import Integer, and_, cast, func, or_, select

from db.models.user import User
from schemas.countrydle import LeaderboardEntry


def utc_month_bounds():
    first_day = datetime.now(timezone.utc).date().replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_month = first_day.replace(month=first_day.month + 1)
    return first_day, next_month

async def get_leaderboard(session, state_model, day_model, kind, *, minimum_average_games=5, day_filters=()):
    if kind not in {"monthly", "average"}:
        return []

    state = state_model
    activity = or_(state.questions_asked > 0, state.guesses_made > 0)
    filters = [
        User.username.not_like("test_%"),
        User.username.not_like("pytest_%"),
        User.username.not_like("guess_c_%"),
        User.username.not_like("ask_q_%"),
        activity,
        *day_filters,
    ]
    if kind == "monthly":
        month_start, next_month = utc_month_bounds()
        filters.extend((day_model.date >= month_start, day_model.date < next_month))
    else:
        filters.append(state.is_game_over.is_(True))

    games_played = func.count(state.id).label("games_played")
    points = func.coalesce(func.sum(state.points), 0).label("points")
    wins = func.coalesce(func.sum(cast(state.won, Integer)), 0).label("wins")
    statement = (
        select(User.id, User.username, points, wins, games_played)
        .join(state, User.id == state.user_id)
        .join(day_model, state.day_id == day_model.id)
        .where(and_(*filters))
        .group_by(User.id, User.username)
    )
    if kind == "average":
        statement = statement.having(games_played >= minimum_average_games)

    result = await session.execute(statement)
    rows = result.all()
    entries = [
        LeaderboardEntry(
            id=row.id,
            username=row.username,
            points=row.points,
            wins=row.wins,
            games_played=row.games_played,
            average_points=round(row.points / row.games_played, 2),
        )
        for row in rows
    ]
    if kind == "monthly":
        entries.sort(key=lambda entry: (-entry.points, -entry.wins, entry.id))
    else:
        entries.sort(key=lambda entry: (-entry.average_points, -entry.wins, entry.id))
    return entries
