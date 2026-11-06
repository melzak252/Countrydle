"""Authoritative ranked daily heraldry sessions and account claims."""
import hashlib
import math
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from db.models.heraldry_daily import HeraldryDailySession
from db.models.user import User, UserPoints
from db.repositories.leaderboard import utc_month_bounds
from game_logic import calculate_flagdle_points, count_consecutive_daily_wins
from schemas.countrydle import LeaderboardEntry
from utils.guest_session import get_guest_identity, read_guest_identity


def utcnow():
    return datetime.now(timezone.utc)


async def lock_identity(session, identity, day, symbol_mode="coat"):
    key = f"heraldry-daily:{symbol_mode}:{identity}:{day.isoformat()}"
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    await session.execute(select(func.pg_advisory_xact_lock(lock_id)))


def owner_filter(user, guest_id):
    if user is not None:
        return HeraldryDailySession.user_id == user.id
    return (HeraldryDailySession.user_id.is_(None)) & (HeraldryDailySession.guest_id == guest_id)


async def get_or_create_daily(session, request, response, user, day, target, symbol_mode="coat"):
    guest = None if user else get_guest_identity(request, response)
    identity = f"user:{user.id}" if user else f"guest:{guest}"
    await lock_identity(session, identity, day, symbol_mode)
    row = await session.scalar(select(HeraldryDailySession).where(
        HeraldryDailySession.date == day, HeraldryDailySession.symbol_mode == symbol_mode, owner_filter(user, guest)
    ).with_for_update())
    if row is None and user is not None:
        guest = read_guest_identity(request)
        if guest:
            await lock_identity(session, f"guest:{guest}", day, symbol_mode)
            row = await session.scalar(select(HeraldryDailySession).where(
                HeraldryDailySession.date == day, HeraldryDailySession.symbol_mode == symbol_mode, owner_filter(None, guest)
            ).with_for_update())
    if row is None:
        row = HeraldryDailySession(
            id=str(uuid4()), date=day, symbol_mode=symbol_mode, user_id=user.id if user else None, guest_id=guest,
            target_id=target["id"], target_name=target["name"], guesses=[], started_at=utcnow(), won=False,
        )
        session.add(row)
        await session.flush()
    await session.commit()
    return row


async def get_owned_daily(session, request, user, session_id, *, lock=False, symbol_mode="coat"):
    guest = read_guest_identity(request)
    if user is None and guest is None:
        raise HTTPException(status_code=403, detail="Daily session does not belong to this player.")
    ownership = owner_filter(user, guest)
    if user is not None and guest is not None:
        ownership = or_(ownership, owner_filter(None, guest))
    stmt = select(HeraldryDailySession).where(
        or_(HeraldryDailySession.id == session_id, HeraldryDailySession.replaced_session_id == session_id),
        HeraldryDailySession.symbol_mode == symbol_mode,
        ownership,
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(stmt)
    if row is None:
        raise HTTPException(status_code=403, detail="Daily session does not belong to this player.")
    return row


def token_payload(row):
    return {"session_id": row.id, "seed": f"daily-{row.date.isoformat()}", "is_daily": True,
            "date": row.date.isoformat(), "target_id": row.target_id, "symbol_mode": row.symbol_mode,
            "guesses": [guess["id"] for guess in row.guesses]}


async def streak_for(session, row):
    owner = (HeraldryDailySession.user_id == row.user_id if row.user_id is not None else
             (HeraldryDailySession.user_id.is_(None)) & (HeraldryDailySession.guest_id == row.guest_id))
    previous = (await session.execute(select(HeraldryDailySession.date, HeraldryDailySession.won).where(
        owner, HeraldryDailySession.symbol_mode == row.symbol_mode, HeraldryDailySession.date < row.date, HeraldryDailySession.completed_at.is_not(None)
    ).order_by(HeraldryDailySession.date.desc()))).all()
    return count_consecutive_daily_wins(previous, row.date) + 1


def scoring_elapsed(started_at, finished_at):
    # Flagdle treats zero as unknown; round positive server durations up so
    # sub-second solves retain the speed bonus and cannot score below slower ones.
    return max(1, math.ceil((finished_at - started_at).total_seconds()))


async def add_account_points(session, user_id, points):
    if user_id is None or not points:
        return
    statement = insert(UserPoints).values(user_id=user_id, points=points, streak=0)
    await session.execute(statement.on_conflict_do_update(
        index_elements=[UserPoints.user_id],
        set_={"points": UserPoints.points + statement.excluded.points},
    ))


async def record_guess(session, request, user, payload, county, symbol_mode="coat"):
    row = await get_owned_daily(session, request, user, payload["session_id"], lock=True, symbol_mode=symbol_mode)
    if row.date != utcnow().date():
        raise HTTPException(status_code=400, detail="This daily challenge has expired.")
    current_ids = [g["id"] for g in row.guesses]
    if payload.get("guesses") != current_ids or payload.get("target_id") != row.target_id:
        raise HTTPException(status_code=409, detail="Daily progress changed. Refresh the challenge.")
    if row.completed_at is not None:
        raise HTTPException(status_code=400, detail="The game is already over.")
    if county["id"] in current_ids:
        raise HTTPException(status_code=400, detail="This county has already been checked.")
    now = utcnow()
    row.guesses = [*row.guesses, {"id": county["id"], "name": county["name"], "at": now.isoformat()}]
    row.won = county["id"] == row.target_id
    if row.won or len(row.guesses) >= 8:
        row.completed_at = now
        elapsed = scoring_elapsed(row.started_at, now)
        row.points = calculate_flagdle_points(row.won, len(row.guesses), elapsed, await streak_for(session, row) if row.won else 0)
        await add_account_points(session, row.user_id, row.points)
    await session.commit()
    return row


async def claim_daily(session, request, user, symbol_mode="coat"):
    day = utcnow().date()
    guest = read_guest_identity(request)
    await lock_identity(session, f"user:{user.id}", day, symbol_mode)
    existing = await session.scalar(select(HeraldryDailySession).where(
        HeraldryDailySession.user_id == user.id, HeraldryDailySession.date == day, HeraldryDailySession.symbol_mode == symbol_mode
    ).with_for_update())
    if existing is not None and existing.guesses:
        return existing
    if guest is None:
        if existing is not None:
            return existing
        raise HTTPException(status_code=404, detail="No guest daily session to claim.")
    await lock_identity(session, f"guest:{guest}", day, symbol_mode)
    row = await session.scalar(select(HeraldryDailySession).where(
        HeraldryDailySession.guest_id == guest, HeraldryDailySession.user_id.is_(None),
        HeraldryDailySession.date == day, HeraldryDailySession.symbol_mode == symbol_mode,
    ).with_for_update())
    if row is None or not row.guesses:
        if existing is not None:
            return existing
        if row is None:
            raise HTTPException(status_code=404, detail="No guest daily session to claim.")
    if existing is not None:
        # This row has no moves; keep the guest's actual history as canonical.
        row.replaced_session_id = existing.id
        await session.delete(existing)
        await session.flush()
    row.user_id = user.id
    if row.won and row.completed_at is not None:
        elapsed = scoring_elapsed(row.started_at, row.completed_at)
        row.points = calculate_flagdle_points(True, len(row.guesses), elapsed, await streak_for(session, row))
        await add_account_points(session, row.user_id, row.points)
    await session.commit()
    return row


async def leaderboard(session, kind, symbol_mode="coat"):
    if kind not in {"monthly", "average"}:
        return []
    first, next_month = utc_month_bounds()
    games = func.count(HeraldryDailySession.id).label("games_played")
    points = func.coalesce(func.sum(HeraldryDailySession.points), 0).label("points")
    wins = func.coalesce(func.sum(cast(HeraldryDailySession.won, Integer)), 0).label("wins")
    statement = select(User.id, User.username, points, wins, games).join(
        HeraldryDailySession, User.id == HeraldryDailySession.user_id
    ).where(
        HeraldryDailySession.date >= first, HeraldryDailySession.date < next_month,
        HeraldryDailySession.symbol_mode == symbol_mode,
        func.json_array_length(HeraldryDailySession.guesses) > 0,
        User.username.not_like("test_%"), User.username.not_like("pytest_%"),
        User.username.not_like("guess_c_%"), User.username.not_like("ask_q_%"),
    ).group_by(User.id, User.username)
    if kind == "average":
        statement = statement.where(HeraldryDailySession.completed_at.is_not(None)).having(games >= 5)
    rows = (await session.execute(statement)).all()
    entries = [LeaderboardEntry(
        id=row.id, username=row.username, points=row.points, wins=row.wins,
        games_played=row.games_played, average_points=round(row.points / row.games_played, 2),
    ) for row in rows]
    entries.sort(key=lambda e: (-(e.points if kind == "monthly" else e.average_points), -e.wins, e.id))
    return entries
