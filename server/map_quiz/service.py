"""Authoritative 10-per-day regional map quiz sessions, scoring, and leaderboards."""

from __future__ import annotations

import hashlib
import math
import random
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, case, func, select
from sqlalchemy.dialects.postgresql import insert

from db.models.map_quiz import MapQuizDailySession
from db.models.user import User, UserPoints
from db.repositories.leaderboard import utc_month_bounds
from game_logic import count_consecutive_daily_wins
from regional_symbols.catalog import load_entities
from schemas.countrydle import LeaderboardEntry
from stats.service import record_mode_result
from utils.guest_session import get_guest_identity, read_guest_identity

MAP_QUIZ_SCOPES = frozenset({"london_boroughs", "england_counties"})
DAILY_ROUND_COUNT = 10
WIN_SCORE_THRESHOLD = 7


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_scope(scope: str) -> str:
    if scope not in MAP_QUIZ_SCOPES:
        raise HTTPException(status_code=404, detail="Unknown map quiz scope.")
    return scope


def select_daily_targets(scope: str, day: date, count: int = DAILY_ROUND_COUNT) -> list[int]:
    """Deterministically select `count` distinct entity IDs for (scope, UTC day)."""
    validate_scope(scope)
    entities = load_entities(scope)
    sorted_ids = sorted(entities.keys())
    if len(sorted_ids) < count:
        raise HTTPException(status_code=503, detail="Insufficient entities for daily map quiz.")
    digest = hashlib.sha256(f"map-quiz:v1:{scope}:{day.isoformat()}".encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    return rng.sample(sorted_ids, count)


def scoring_elapsed(started_at: datetime, finished_at: datetime) -> int:
    return max(1, math.ceil((finished_at - started_at).total_seconds()))


def calculate_map_quiz_points(score: int, elapsed_seconds: int, streak: int = 0) -> int:
    if score <= 0:
        return 0
    clamped_score = min(score, DAILY_ROUND_COUNT)
    base_points = clamped_score * 100
    speed_factor = max(0.0, 1.0 - min(max(elapsed_seconds, 0), 180) / 180.0)
    speed_bonus = int(round(200 * (clamped_score / DAILY_ROUND_COUNT) * speed_factor))
    streak_bonus = min(max(streak, 0) * 25, 250) if clamped_score >= WIN_SCORE_THRESHOLD else 0
    return base_points + speed_bonus + streak_bonus


async def lock_identity(session, identity: str, day: date, scope: str) -> None:
    key = f"map-quiz:{scope}:{identity}:{day.isoformat()}"
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    await session.execute(select(func.pg_advisory_xact_lock(lock_id)))


def owner_filter(user, guest_id):
    if user is not None:
        return MapQuizDailySession.user_id == user.id
    return (MapQuizDailySession.user_id.is_(None)) & (MapQuizDailySession.guest_id == guest_id)


async def add_account_points(session, user_id: int | None, points: int | None) -> None:
    if user_id is None or not points:
        return
    statement = insert(UserPoints).values(user_id=user_id, points=points, streak=0)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[UserPoints.user_id],
            set_={"points": UserPoints.points + statement.excluded.points},
        )
    )


async def streak_for(session, row: MapQuizDailySession) -> int:
    owner = (
        MapQuizDailySession.user_id == row.user_id
        if row.user_id is not None
        else (MapQuizDailySession.user_id.is_(None)) & (MapQuizDailySession.guest_id == row.guest_id)
    )
    previous = (
        await session.execute(
            select(MapQuizDailySession.date, MapQuizDailySession.score >= WIN_SCORE_THRESHOLD)
            .where(
                owner,
                MapQuizDailySession.scope == row.scope,
                MapQuizDailySession.date < row.date,
                MapQuizDailySession.completed_at.is_not(None),
            )
            .order_by(MapQuizDailySession.date.desc())
        )
    ).all()
    return count_consecutive_daily_wins(previous, row.date) + 1


async def get_or_create_daily(session, request, response, user, scope: str, day: date | None = None) -> MapQuizDailySession:
    validate_scope(scope)
    day = day or utcnow().date()
    guest = None if user else get_guest_identity(request, response)
    identity = f"user:{user.id}" if user else f"guest:{guest}"
    await lock_identity(session, identity, day, scope)

    row = await session.scalar(
        select(MapQuizDailySession)
        .where(
            MapQuizDailySession.date == day,
            MapQuizDailySession.scope == scope,
            owner_filter(user, guest),
        )
        .with_for_update()
    )

    if row is None and user is not None:
        guest_cookie = read_guest_identity(request)
        if guest_cookie:
            await lock_identity(session, f"guest:{guest_cookie}", day, scope)
            row = await session.scalar(
                select(MapQuizDailySession)
                .where(
                    MapQuizDailySession.date == day,
                    MapQuizDailySession.scope == scope,
                    owner_filter(None, guest_cookie),
                )
                .with_for_update()
            )

    if row is None:
        targets = select_daily_targets(scope, day)
        row = MapQuizDailySession(
            id=str(uuid4()),
            date=day,
            scope=scope,
            user_id=user.id if user else None,
            guest_id=guest,
            targets=targets,
            answers=[],
            score=0,
            started_at=utcnow(),
        )
        session.add(row)
        await session.flush()

    await session.commit()
    return row


async def submit_answer(
    session,
    request,
    response,
    user,
    scope: str,
    entity_id: int,
    expected_round: int | None = None,
) -> tuple[dict, MapQuizDailySession]:
    validate_scope(scope)
    entities = load_entities(scope)
    clicked = entities.get(entity_id)
    if clicked is None:
        raise HTTPException(status_code=400, detail="Unknown region clicked.")

    day = utcnow().date()
    guest = None if user else get_guest_identity(request, response)
    identity = f"user:{user.id}" if user else f"guest:{guest}"
    await lock_identity(session, identity, day, scope)

    row = await session.scalar(
        select(MapQuizDailySession)
        .where(
            MapQuizDailySession.date == day,
            MapQuizDailySession.scope == scope,
            owner_filter(user, guest),
        )
        .with_for_update()
    )
    if row is None and user is not None:
        guest_cookie = read_guest_identity(request)
        if guest_cookie:
            await lock_identity(session, f"guest:{guest_cookie}", day, scope)
            row = await session.scalar(
                select(MapQuizDailySession)
                .where(
                    MapQuizDailySession.date == day,
                    MapQuizDailySession.scope == scope,
                    owner_filter(None, guest_cookie),
                )
                .with_for_update()
            )
    if row is None:
        targets = select_daily_targets(scope, day)
        row = MapQuizDailySession(
            id=str(uuid4()),
            date=day,
            scope=scope,
            user_id=user.id if user else None,
            guest_id=guest,
            targets=targets,
            answers=[],
            score=0,
            started_at=utcnow(),
        )
        session.add(row)
        await session.flush()

    if row.completed_at is not None or len(row.answers) >= len(row.targets):
        raise HTTPException(status_code=400, detail="Today's map quiz is already completed.")

    round_number = len(row.answers) + 1
    if expected_round is not None and expected_round != round_number:
        raise HTTPException(status_code=409, detail="Round progress changed. Refresh the quiz.")

    target_id = row.targets[round_number - 1]
    target = entities[target_id]
    correct = clicked["id"] == target_id
    now = utcnow()
    entry = {
        "round": round_number,
        "target_id": target_id,
        "target_name": target["name"],
        "clicked_id": clicked["id"],
        "clicked_name": clicked["name"],
        "correct": correct,
        "at": now.isoformat(),
    }
    row.answers = [*row.answers, entry]
    if correct:
        row.score = (row.score or 0) + 1

    completed_elapsed: int | None = None
    if len(row.answers) >= len(row.targets):
        row.completed_at = now
        completed_elapsed = scoring_elapsed(row.started_at, now)
        streak = await streak_for(session, row) if row.score >= WIN_SCORE_THRESHOLD else 0
        row.points = calculate_map_quiz_points(row.score, completed_elapsed, streak)
        await add_account_points(session, row.user_id, row.points)

    await session.commit()
    if completed_elapsed is not None:
        try:
            await record_mode_result(
                session,
                mode=f"map_quiz_{row.scope}",
                record_date=row.date,
                user_id=row.user_id,
                guest_id=row.guest_id,
                completed=True,
                won=row.score >= WIN_SCORE_THRESHOLD,
                points=row.points or 0,
                score=row.score,
                max_score=len(row.targets),
                elapsed_seconds=float(completed_elapsed),
                completed_at=row.completed_at,
            )
        except Exception:
            pass
    return entry, row


async def claim_daily(session, request, user, scope: str) -> MapQuizDailySession:
    validate_scope(scope)
    day = utcnow().date()
    guest = read_guest_identity(request)
    await lock_identity(session, f"user:{user.id}", day, scope)

    existing = await session.scalar(
        select(MapQuizDailySession)
        .where(
            MapQuizDailySession.user_id == user.id,
            MapQuizDailySession.date == day,
            MapQuizDailySession.scope == scope,
        )
        .with_for_update()
    )
    if existing is not None and existing.answers:
        return existing

    if guest is None:
        if existing is not None:
            return existing
        raise HTTPException(status_code=404, detail="No guest daily map quiz session to claim.")

    await lock_identity(session, f"guest:{guest}", day, scope)
    row = await session.scalar(
        select(MapQuizDailySession)
        .where(
            MapQuizDailySession.guest_id == guest,
            MapQuizDailySession.user_id.is_(None),
            MapQuizDailySession.date == day,
            MapQuizDailySession.scope == scope,
        )
        .with_for_update()
    )
    if row is None or not row.answers:
        if existing is not None:
            return existing
        if row is None:
            raise HTTPException(status_code=404, detail="No guest daily map quiz session to claim.")

    if existing is not None:
        row.replaced_session_id = existing.id
        await session.delete(existing)
        await session.flush()

    row.user_id = user.id
    claimed_elapsed: int | None = None
    if row.completed_at is not None:
        claimed_elapsed = scoring_elapsed(row.started_at, row.completed_at)
        streak = await streak_for(session, row) if row.score >= WIN_SCORE_THRESHOLD else 0
        row.points = calculate_map_quiz_points(row.score, claimed_elapsed, streak)
        await add_account_points(session, row.user_id, row.points)

    await session.commit()
    if claimed_elapsed is not None:
        try:
            await record_mode_result(
                session,
                mode=f"map_quiz_{row.scope}",
                record_date=row.date,
                user_id=row.user_id,
                guest_id=None,
                completed=True,
                won=row.score >= WIN_SCORE_THRESHOLD,
                points=row.points or 0,
                score=row.score,
                max_score=len(row.targets),
                elapsed_seconds=float(claimed_elapsed),
                completed_at=row.completed_at,
            )
        except Exception:
            pass
    return row


async def leaderboard(session, scope: str, kind: str = "monthly") -> list[LeaderboardEntry]:
    validate_scope(scope)
    if kind not in {"monthly", "average"}:
        return []
    first, next_month = utc_month_bounds()
    games = func.count(MapQuizDailySession.id).label("games_played")
    points = func.coalesce(func.sum(MapQuizDailySession.points), 0).label("points")
    wins = func.coalesce(
        func.sum(case((MapQuizDailySession.score >= WIN_SCORE_THRESHOLD, 1), else_=0)),
        0,
    ).label("wins")

    statement = (
        select(User.id, User.username, points, wins, games)
        .join(MapQuizDailySession, User.id == MapQuizDailySession.user_id)
        .where(
            MapQuizDailySession.date >= first,
            MapQuizDailySession.date < next_month,
            MapQuizDailySession.scope == scope,
            func.json_array_length(MapQuizDailySession.answers) > 0,
            User.username.not_like("test_%"),
            User.username.not_like("pytest_%"),
            User.username.not_like("guess_c_%"),
            User.username.not_like("ask_q_%"),
        )
        .group_by(User.id, User.username)
    )
    if kind == "average":
        statement = statement.where(MapQuizDailySession.completed_at.is_not(None)).having(games >= 5)

    rows = (await session.execute(statement)).all()
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
    entries.sort(key=lambda e: (-(e.points if kind == "monthly" else e.average_points), -e.wins, e.id))
    return entries


def serialize_state(row: MapQuizDailySession) -> dict:
    entities = load_entities(row.scope)
    total_rounds = len(row.targets)
    answered_count = len(row.answers)
    is_completed = row.completed_at is not None or answered_count >= total_rounds

    current_target = None
    if not is_completed and answered_count < total_rounds:
        target_id = row.targets[answered_count]
        target = entities[target_id]
        current_target = {"id": target_id, "name": target["name"]}

    elapsed_seconds = (
        scoring_elapsed(row.started_at, row.completed_at)
        if row.completed_at is not None
        else None
    )

    return {
        "session_id": row.id,
        "scope": row.scope,
        "date": row.date.isoformat(),
        "total_rounds": total_rounds,
        "current_round": total_rounds if is_completed else answered_count + 1,
        "current_target": current_target,
        "answers": [
            {
                "round": ans["round"],
                "target_id": ans["target_id"],
                "target_name": ans["target_name"],
                "clicked_id": ans["clicked_id"],
                "clicked_name": ans["clicked_name"],
                "correct": ans["correct"],
            }
            for ans in row.answers
        ],
        "score": row.score,
        "is_completed": is_completed,
        "points": row.points,
        "elapsed_seconds": elapsed_seconds,
        "ranked": True,
    }
