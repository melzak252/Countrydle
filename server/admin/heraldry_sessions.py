"""Admin views of the separately persisted heraldry games."""
from collections import Counter
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import Integer, String, case, cast, func, select

from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun, QuizSolve
from db.models.user import User
from powiatdle.heraldry_quiz import load_catalog
from schemas.admin import AdminGameSessionItem, AdminGameSessionTimelineEvent, AdminQuizSolve, AdminTargetStrategyStats, AdminTopGuessStat
from fastapi import HTTPException
from powiatdle.flag_catalog import load_catalog as load_flag_catalog
from regional_symbols.catalog import load_catalog as load_regional_catalog, load_entities as load_regional_entities


REGIONAL_SCOPES = {
    "voivodeships": "Polish voivodeships",
    "london_boroughs": "London boroughs",
    "england_counties": "English counties",
}


def heraldry_mode(mode):
    legacy = {
        "heraldry": ("county", "coat", False),
        "county_flags": ("county", "flag", False),
        "coats_quiz": ("county", "coat", True),
        "county_flags_quiz": ("county", "flag", True),
    }
    if mode in legacy:
        return legacy[mode]
    parts = mode.split(":")
    if (len(parts) in (3, 4) and parts[0] == "regional_symbols"
            and parts[1] in REGIONAL_SCOPES and parts[2] in {"coat", "flag"}
            and (len(parts) == 3 or parts[3] == "quiz")):
        return parts[1], parts[2], len(parts) == 4
    return None


def quiz_target(mode):
    scope, symbol, _ = heraldry_mode(mode)
    if scope == "county":
        return flag_quiz_target() if symbol == "flag" else "380 Polish counties"
    try:
        return f"{len(load_regional_catalog(scope, symbol))} {REGIONAL_SCOPES[scope]}"
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        return "Catalog unavailable"


def flag_quiz_target():
    try:
        count = len(load_flag_catalog())
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        return "Catalog unavailable"
    return f"{count} Polish counties"


def _scope(mode, day):
    entity_scope, symbol_mode, is_quiz = heraldry_mode(mode)
    if not is_quiz:
        return HeraldryDailySession, [HeraldryDailySession.date == day,
                                     HeraldryDailySession.symbol_mode == symbol_mode,
                                     HeraldryDailySession.entity_scope == entity_scope]
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return QuizRun, [QuizRun.started_at >= start, QuizRun.started_at < start + timedelta(days=1),
                     QuizRun.symbol_mode == symbol_mode, QuizRun.entity_scope == entity_scope]


def _status_filter(mode, status):
    if not heraldry_mode(mode)[2]:
        return {
            "won": HeraldryDailySession.won.is_(True),
            "lost": (HeraldryDailySession.won.is_(False)) & HeraldryDailySession.completed_at.is_not(None),
            "in_progress": HeraldryDailySession.completed_at.is_(None),
        }.get(status)
    return {"won": QuizRun.status == "completed", "lost": QuizRun.status == "given_up",
            "in_progress": QuizRun.status == "started"}.get(status)


def _item(row, username, mode, day, quiz_target=None):
    is_guest = row.user_id is None
    if not heraldry_mode(mode)[2]:
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
        target_name = quiz_target
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
    entity_scope, _, is_quiz = heraldry_mode(mode)
    target = quiz_target(mode) if is_quiz else None
    items = [_item(row, username, mode, day, target) for row, username in rows]
    if is_quiz and items:
        solves = (await session.execute(
            select(QuizSolve.run_id, QuizSolve.powiat_id, QuizSolve.elapsed_seconds)
            .where(QuizSolve.run_id.in_([item.session_id for item in items]))
            .order_by(QuizSolve.elapsed_seconds, QuizSolve.powiat_id)
        )).all()
        if solves:
            catalog = await load_catalog() if entity_scope == "county" else {
                entity_id: entity["name"] for entity_id, entity in load_regional_entities(entity_scope).items()
            }
            by_id = {item.session_id: item for item in items}
            for run_id, powiat_id, elapsed in solves:
                by_id[run_id].quiz_solves.append(AdminQuizSolve(
                    powiat_id=powiat_id, name=catalog.get(powiat_id, f"{'County' if entity_scope == 'county' else 'Entity'} #{powiat_id}"),
                    active_elapsed_seconds=elapsed,
                ))
    return items, total


async def query_heraldry_stats(session, mode, day):
    model, filters = _scope(mode, day)
    identity = case(
        (model.user_id.is_not(None), 'user:' + cast(model.user_id, String)),
        else_='guest:' + model.guest_id,
    )
    is_quiz = heraldry_mode(mode)[2]
    won = model.status == "completed" if is_quiz else model.won
    total, players, wins = (await session.execute(select(
        func.count(), func.count(func.distinct(identity)),
        func.coalesce(func.sum(cast(won, Integer)), 0),
    ).select_from(model).where(*filters))).one()
    target_name = quiz_target(mode) if is_quiz else "Unknown"
    top_guesses = []
    if not is_quiz:
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
