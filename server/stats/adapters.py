from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.guest_participation import GuestParticipation
from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun
from db.models.mode_result import ModeResultRecord
from db.models.user import User
from stats.registry import ModeStatsSpec


@dataclass
class _PlayRow:
    identity: str
    user_id: Optional[int]
    guest_id: Optional[str]
    completed: bool
    won: bool
    points: Optional[int] = None
    questions_used: Optional[int] = None
    guesses_used: Optional[int] = None
    score: Optional[int] = None
    max_score: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    played_date: Optional[date] = None


def _month_bounds(target_date: date) -> Tuple[date, date]:
    first_day = target_date.replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_month = first_day.replace(month=first_day.month + 1)
    return first_day, next_month


def _utc_date(dt: Optional[datetime]) -> Optional[date]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).date()
    return dt.date()


def _non_test_user_filters():
    return (
        User.username.not_like("test_%"),
        User.username.not_like("pytest_%"),
        User.username.not_like("guess_c_%"),
        User.username.not_like("ask_q_%"),
    )


def _is_test_username(username: Optional[str]) -> bool:
    if not username:
        return True
    lowered = username.lower()
    return (
        lowered.startswith("test_")
        or lowered.startswith("pytest_")
        or lowered.startswith("guess_c_")
        or lowered.startswith("ask_q_")
    )


def _dedupe_plays(rows: List[_PlayRow]) -> List[_PlayRow]:
    by_identity: Dict[str, _PlayRow] = {}
    for row in rows:
        existing = by_identity.get(row.identity)
        if existing is None:
            by_identity[row.identity] = row
            continue
        new_key = (
            1 if row.completed else 0,
            1 if row.won else 0,
            row.points if row.points is not None else -1,
            row.guesses_used if row.guesses_used is not None else -1,
            row.questions_used if row.questions_used is not None else -1,
        )
        old_key = (
            1 if existing.completed else 0,
            1 if existing.won else 0,
            existing.points if existing.points is not None else -1,
            existing.guesses_used if existing.guesses_used is not None else -1,
            existing.questions_used if existing.questions_used is not None else -1,
        )
        if new_key > old_key:
            by_identity[row.identity] = row
    return list(by_identity.values())


async def _fetch_qa_or_guess_daily_rows(
    session: AsyncSession,
    spec: ModeStatsSpec,
    target_date: date,
) -> Tuple[List[_PlayRow], List[_PlayRow]]:
    state_model = spec.state_model
    day_model = spec.day_model
    day_filters = [day_model.date == target_date]
    if spec.continent is not None:
        day_filters.append(day_model.continent == spec.continent)

    auth_stmt = (
        select(
            state_model.user_id,
            state_model.questions_asked,
            state_model.guesses_made,
            state_model.is_game_over,
            state_model.won,
            state_model.points,
        )
        .join(day_model, day_model.id == state_model.day_id)
        .where(
            state_model.user_id.is_not(None),
            or_(state_model.questions_asked > 0, state_model.guesses_made > 0),
            *day_filters,
        )
    )
    auth_rows = (await session.execute(auth_stmt)).all()

    guest_stmt = (
        select(
            GuestParticipation.guest_id,
            GuestParticipation.questions_asked,
            GuestParticipation.guesses_made,
            GuestParticipation.won,
        )
        .join(day_model, day_model.id == GuestParticipation.day_id)
        .where(
            GuestParticipation.mode == spec.guest_mode_key,
            GuestParticipation.user_id.is_(None),
            or_(
                GuestParticipation.questions_asked > 0,
                GuestParticipation.guesses_made > 0,
            ),
            *day_filters,
        )
    )
    guest_rows = (await session.execute(guest_stmt)).all()

    plays: List[_PlayRow] = []
    for r in auth_rows:
        plays.append(
            _PlayRow(
                identity=f"user:{r.user_id}",
                user_id=r.user_id,
                guest_id=None,
                completed=bool(r.is_game_over),
                won=bool(r.won),
                points=int(r.points or 0),
                questions_used=int(r.questions_asked or 0) if spec.adapter == "qa_daily" else None,
                guesses_used=int(r.guesses_made or 0),
                played_date=target_date,
            )
        )
    for r in guest_rows:
        g_used = int(r.guesses_made or 0)
        is_won = bool(r.won)
        is_completed = is_won or (spec.max_guesses is not None and g_used >= spec.max_guesses)
        plays.append(
            _PlayRow(
                identity=f"guest:{r.guest_id}",
                user_id=None,
                guest_id=r.guest_id,
                completed=is_completed,
                won=is_won,
                points=None,
                questions_used=int(r.questions_asked or 0) if spec.adapter == "qa_daily" else None,
                guesses_used=g_used,
                played_date=target_date,
            )
        )
    deduped = _dedupe_plays(plays)
    return deduped, deduped


async def _fetch_heraldry_daily_rows(
    session: AsyncSession,
    spec: ModeStatsSpec,
    target_date: date,
) -> Tuple[List[_PlayRow], List[_PlayRow]]:
    stmt = select(HeraldryDailySession).where(
        HeraldryDailySession.date == target_date,
        HeraldryDailySession.symbol_mode == spec.symbol_mode,
        HeraldryDailySession.entity_scope == spec.entity_scope,
    )
    sessions = (await session.execute(stmt)).scalars().all()
    plays: List[_PlayRow] = []
    for s in sessions:
        guesses_len = len(s.guesses or [])
        if guesses_len == 0:
            continue
        identity = f"user:{s.user_id}" if s.user_id is not None else f"guest:{s.guest_id}"
        elapsed = None
        if s.started_at is not None and s.completed_at is not None:
            elapsed = max(0.0, (s.completed_at - s.started_at).total_seconds())
        plays.append(
            _PlayRow(
                identity=identity,
                user_id=s.user_id,
                guest_id=None if s.user_id is not None else s.guest_id,
                completed=s.completed_at is not None,
                won=bool(s.won),
                points=int(s.points or 0) if s.points is not None else None,
                guesses_used=guesses_len,
                elapsed_seconds=elapsed,
                played_date=s.date,
            )
        )
    deduped = _dedupe_plays(plays)
    return deduped, deduped


async def _fetch_quiz_run_rows(
    session: AsyncSession,
    spec: ModeStatsSpec,
    target_date: date,
) -> Tuple[List[_PlayRow], List[_PlayRow]]:
    stmt = select(QuizRun).where(
        QuizRun.symbol_mode == spec.symbol_mode,
        QuizRun.entity_scope == spec.entity_scope,
    )
    runs = (await session.execute(stmt)).scalars().all()
    all_rows: List[_PlayRow] = []
    today_rows: List[_PlayRow] = []
    for run in runs:
        identity = f"user:{run.user_id}" if run.user_id is not None else f"guest:{run.guest_id}"
        run_date = _utc_date(run.started_at)
        is_completed = run.status in ("completed", "given_up")
        is_won = run.status == "completed"
        row = _PlayRow(
            identity=identity,
            user_id=run.user_id,
            guest_id=None if run.user_id is not None else run.guest_id,
            completed=is_completed,
            won=is_won,
            points=int(run.solved_count or 0),
            score=int(run.solved_count or 0),
            max_score=spec.max_score,
            elapsed_seconds=float(run.elapsed_seconds) if run.elapsed_seconds is not None else None,
            played_date=run_date,
        )
        all_rows.append(row)
        if run_date == target_date:
            today_rows.append(row)
    return today_rows, all_rows


async def _fetch_mode_result_rows(
    session: AsyncSession,
    spec: ModeStatsSpec,
    target_date: date,
) -> Tuple[List[_PlayRow], List[_PlayRow]]:
    record_mode = spec.record_mode or spec.mode
    stmt = select(ModeResultRecord).where(ModeResultRecord.mode == record_mode)
    if spec.is_daily:
        stmt = stmt.where(ModeResultRecord.date == target_date)
    records = (await session.execute(stmt)).scalars().all()

    all_rows: List[_PlayRow] = []
    today_rows: List[_PlayRow] = []
    for rec in records:
        identity = f"user:{rec.user_id}" if rec.user_id is not None else f"guest:{rec.guest_id}"
        rec_date = rec.date or _utc_date(rec.completed_at)
        row = _PlayRow(
            identity=identity,
            user_id=rec.user_id,
            guest_id=None if rec.user_id is not None else rec.guest_id,
            completed=bool(rec.completed),
            won=bool(rec.won),
            points=int(rec.points or 0),
            questions_used=rec.questions_used,
            guesses_used=rec.guesses_used,
            score=rec.score,
            max_score=rec.max_score if rec.max_score is not None else spec.max_score,
            elapsed_seconds=float(rec.elapsed_seconds) if rec.elapsed_seconds is not None else None,
            played_date=rec_date,
        )
        all_rows.append(row)
        if rec_date == target_date:
            today_rows.append(row)

    if spec.is_daily:
        deduped = _dedupe_plays(today_rows)
        return deduped, deduped
    return today_rows, all_rows


async def _fetch_summary_rows(
    session: AsyncSession,
    spec: ModeStatsSpec,
    target_date: date,
) -> Tuple[List[_PlayRow], List[_PlayRow]]:
    """Return (today_rows, distribution_rows) for the given mode spec and date."""
    if spec.adapter in ("qa_daily", "guess_daily"):
        return await _fetch_qa_or_guess_daily_rows(session, spec, target_date)
    if spec.adapter == "heraldry_daily":
        return await _fetch_heraldry_daily_rows(session, spec, target_date)
    if spec.adapter == "quiz_run":
        return await _fetch_quiz_run_rows(session, spec, target_date)
    return await _fetch_mode_result_rows(session, spec, target_date)
