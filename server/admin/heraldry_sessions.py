"""Admin views of the separately persisted heraldry games."""
from collections import Counter
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import Integer, String, case, cast, func, select

from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun, QuizSolve
from db.models.user import User
from powiatdle.heraldry_quiz import load_catalog
from schemas.admin import AdminGameSessionItem, AdminGameSessionTimelineEvent, AdminQuizSolve, AdminTargetStrategyStats, AdminTopGuessStat


def _scope(mode, day):
    if mode == "heraldry":
        return HeraldryDailySession, [HeraldryDailySession.date == day]
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return QuizRun, [QuizRun.started_at >= start, QuizRun.started_at < start + timedelta(days=1)]


def _status_filter(mode, status):
    if mode == "heraldry":
        return {
            "won": HeraldryDailySession.won.is_(True),
            "lost": (HeraldryDailySession.won.is_(False)) & HeraldryDailySession.completed_at.is_not(None),
            "in_progress": HeraldryDailySession.completed_at.is_(None),
        }.get(status)
    return {"won": QuizRun.status == "completed", "lost": QuizRun.status == "given_up",
            "in_progress": QuizRun.status == "started"}.get(status)


def _item(row, username, mode, day):
    is_guest = row.user_id is None
    if mode == "heraldry":
        completed_at = row.completed_at
        status = "won" if row.won else "lost" if completed_at else "in_progress"
        timeline = [AdminGameSessionTimelineEvent(
            event_type="guess", id=i + 1, timestamp=datetime.fromisoformat(guess["at"]),
            guess=guess["name"], correct=guess["id"] == row.target_id,
        ) for i, guess in enumerate(row.guesses)]
        target_name = row.target_name
        guesses_made = len(row.guesses)
        points = row.points
        solved_count = quiz_status = active_elapsed_seconds = None
    else:
        completed_at = row.finished_at
        status = {"completed": "won", "given_up": "lost", "started": "in_progress"}[row.status]
        timeline = []
        target_name = "380 Polish counties"
        guesses_made = 0  # Only successful solves are recorded, not failed attempts.
        points = None
        solved_count = row.solved_count if completed_at else None
        quiz_status = row.status
        active_elapsed_seconds = row.elapsed_seconds if completed_at else None
    duration = max(0, int((completed_at - row.started_at).total_seconds())) if completed_at else None
    return AdminGameSessionItem(
        session_id=row.id, mode=mode, day_id=None, game_date=day.isoformat(),
        target_name=target_name, target_subtitle=None, user_id=row.user_id,
        username=(f"Guest {row.guest_id[:8]}" if is_guest else username or f"User #{row.user_id}"),
        is_guest=is_guest, status=status, questions_asked=0, guesses_made=guesses_made,
        started_at=row.started_at, completed_at=completed_at, duration_seconds=duration,
        points=points, solved_count=solved_count, quiz_status=quiz_status,
        active_elapsed_seconds=active_elapsed_seconds, timeline=timeline,
    )


async def query_heraldry_sessions(session, mode, day, status_filter, player_type_filter, page, limit):
    model, filters = _scope(mode, day)
    if status_filter:
        predicate = _status_filter(mode, status_filter.lower().strip())
        if predicate is None:
            return [], 0
        filters.append(predicate)
    if player_type_filter == "guest":
        filters.append(model.user_id.is_(None))
    elif player_type_filter == "registered":
        filters.append(model.user_id.is_not(None))
    total = (await session.execute(select(func.count()).select_from(model).where(*filters))).scalar_one()
    statement = (select(model, User.username).outerjoin(User, model.user_id == User.id)
                 .where(*filters).order_by(model.started_at.desc(), model.id)
                 .offset((page - 1) * limit).limit(limit))
    rows = (await session.execute(statement)).all()
    items = [_item(row, username, mode, day) for row, username in rows]
    if mode == "coats_quiz" and items:
        solves = (await session.execute(
            select(QuizSolve.run_id, QuizSolve.powiat_id, QuizSolve.elapsed_seconds)
            .where(QuizSolve.run_id.in_([item.session_id for item in items]))
            .order_by(QuizSolve.elapsed_seconds, QuizSolve.powiat_id)
        )).all()
        if solves:
            catalog = await load_catalog()
            by_id = {item.session_id: item for item in items}
            for run_id, powiat_id, elapsed in solves:
                by_id[run_id].quiz_solves.append(AdminQuizSolve(
                    powiat_id=powiat_id, name=catalog.get(powiat_id, f"County #{powiat_id}"),
                    active_elapsed_seconds=elapsed,
                ))
    return items, total


async def query_heraldry_stats(session, mode, day):
    model, filters = _scope(mode, day)
    identity = case(
        (model.user_id.is_not(None), 'user:' + cast(model.user_id, String)),
        else_='guest:' + model.guest_id,
    )
    won = model.won if mode == "heraldry" else model.status == "completed"
    total, players, wins = (await session.execute(select(
        func.count(), func.count(func.distinct(identity)),
        func.coalesce(func.sum(cast(won, Integer)), 0),
    ).select_from(model).where(*filters))).one()
    target_name = "380 Polish counties" if mode == "coats_quiz" else "Unknown"
    top_guesses = []
    if mode == "heraldry":
        target = (await session.execute(select(model.target_name).where(*filters).limit(1))).scalar_one_or_none()
        target_name = target or "Unknown"
        rows = (await session.execute(select(model.guesses, model.target_id).where(*filters))).all()
        guesses = Counter(guess['name'] for events, _ in rows for guess in events)
        correct = Counter(guess['name'] for events, target_id in rows for guess in events if guess['id'] == target_id)
        top_guesses = [AdminTopGuessStat(guess=name, count=count, correct_pct=round(correct[name] / count * 100, 1))
                       for name, count in guesses.most_common(10)]
    return AdminTargetStrategyStats(
        target_name=target_name, game_date=day.isoformat(), total_players=players,
        win_rate_pct=round(wins / total * 100, 1) if total else 0.0, top_guesses=top_guesses,
    )
