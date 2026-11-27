"""Authoritative 10-per-day regional map quiz sessions, scoring, and leaderboards."""

from __future__ import annotations

import hashlib
import math
import random
import sqlite3
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, case, func, select
from sqlalchemy.dialects.postgresql import insert

from db.models.map_quiz import MapQuizDailySession
from db.models.user import User, UserPoints
from db.repositories.leaderboard import utc_month_bounds
from game_logic import count_consecutive_daily_wins
from regional_symbols.catalog import load_entities as _load_regional_entities
from schemas.countrydle import LeaderboardEntry
from stats.service import record_mode_result
from utils.guest_session import get_guest_identity, read_guest_identity

MAP_QUIZ_SCOPES = frozenset({"london_boroughs", "england_counties", "us_states"})
DAILY_ROUND_COUNT = 10
WIN_SCORE_THRESHOLD = 7

_FALLBACK_US_STATES: tuple[tuple[int, str, float, float], ...] = (
    (1, "Alabama", 32.5917, -86.675),
    (2, "Alaska", 64.2008, -149.4937),
    (3, "Arizona", 34.1667, -111.9333),
    (4, "Arkansas", 34.7519, -92.1314),
    (5, "California", 36.7783, -119.4179),
    (6, "Colorado", 39.5501, -105.7821),
    (7, "Connecticut", 41.6032, -73.0877),
    (8, "Delaware", 38.9108, -75.5277),
    (9, "Florida", 27.6648, -81.5158),
    (10, "Georgia", 32.1656, -82.9001),
    (11, "Hawaii", 19.8968, -155.5828),
    (12, "Idaho", 44.0682, -114.742),
    (13, "Illinois", 40.6331, -89.3985),
    (14, "Indiana", 40.2672, -86.1349),
    (15, "Iowa", 41.878, -93.0977),
    (16, "Kansas", 39.0119, -98.4842),
    (17, "Kentucky", 37.8393, -84.27),
    (18, "Louisiana", 30.9843, -91.9623),
    (19, "Maine", 45.2538, -69.4455),
    (20, "Maryland", 39.0458, -76.6413),
    (21, "Massachusetts", 42.4072, -71.3824),
    (22, "Michigan", 44.3148, -85.6024),
    (23, "Minnesota", 46.7296, -94.6859),
    (24, "Mississippi", 32.3547, -89.3985),
    (25, "Missouri", 37.9643, -91.8318),
    (26, "Montana", 46.8797, -110.3626),
    (27, "Nebraska", 41.4925, -99.9018),
    (28, "Nevada", 38.8026, -116.4194),
    (29, "New Hampshire", 43.1939, -71.5724),
    (30, "New Jersey", 40.0583, -74.4057),
    (31, "New Mexico", 34.5199, -105.8701),
    (32, "New York", 43.2994, -74.2179),
    (33, "North Carolina", 35.7596, -79.0193),
    (34, "North Dakota", 47.5515, -101.002),
    (35, "Ohio", 40.4173, -82.9071),
    (36, "Oklahoma", 35.0078, -97.0929),
    (37, "Oregon", 43.8041, -120.5542),
    (38, "Pennsylvania", 41.2033, -77.1945),
    (39, "Rhode Island", 41.5801, -71.4774),
    (40, "South Carolina", 33.8361, -81.1637),
    (41, "South Dakota", 43.9695, -99.9018),
    (42, "Tennessee", 35.5175, -86.5804),
    (43, "Texas", 31.9686, -99.9018),
    (44, "Utah", 39.321, -111.0937),
    (45, "Vermont", 44.5588, -72.5778),
    (46, "Virginia", 37.4316, -78.6569),
    (47, "Washington", 47.7511, -120.7401),
    (48, "West Virginia", 38.5976, -80.4549),
    (49, "Wisconsin", 43.7844, -88.7879),
    (50, "Wyoming", 43.076, -107.2903),
)


@lru_cache(maxsize=1)
def _load_us_state_entities() -> dict[int, dict]:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "data" / "us_state_facts.sqlite",
        here.parents[2] / "data" / "us_state_facts.sqlite",
    ]
    for db_path in candidates:
        if db_path.is_file():
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                try:
                    rows = conn.execute(
                        "SELECT id, name, latitude, longitude FROM us_states ORDER BY id"
                    ).fetchall()
                finally:
                    conn.close()
                if len(rows) >= 50:
                    return {
                        int(row[0]): {
                            "id": int(row[0]),
                            "name": str(row[1]),
                            "aliases": [],
                            "latitude": float(row[2] if row[2] is not None else 0.0),
                            "longitude": float(row[3] if row[3] is not None else 0.0),
                        }
                        for row in rows
                    }
            except sqlite3.Error:
                pass

    return {
        state_id: {
            "id": state_id,
            "name": name,
            "aliases": [],
            "latitude": lat,
            "longitude": lon,
        }
        for state_id, name, lat, lon in _FALLBACK_US_STATES
    }


def load_map_quiz_entities(scope: str) -> dict[int, dict]:
    validate_scope(scope)
    if scope == "us_states":
        return _load_us_state_entities()
    return _load_regional_entities(scope)


def load_entities(scope: str) -> dict[int, dict]:
    return load_map_quiz_entities(scope)


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
