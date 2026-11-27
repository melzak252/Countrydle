from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.mode_result import ModeResultRecord


async def record_mode_result(
    session: AsyncSession,
    *,
    mode: str,
    record_date: Optional[date],
    user_id: Optional[int],
    guest_id: Optional[str],
    completed: bool = True,
    won: bool = False,
    points: int = 0,
    questions_used: Optional[int] = None,
    guesses_used: Optional[int] = None,
    score: Optional[int] = None,
    max_score: Optional[int] = None,
    elapsed_seconds: Optional[float] = None,
    completed_at: Optional[datetime] = None,
) -> Optional[ModeResultRecord]:
    """Persist a mode completion into mode_result_records (idempotent for daily modes)."""
    if user_id is None and not guest_id:
        return None

    now = completed_at or datetime.now(timezone.utc)
    effective_guest_id = None if user_id is not None else guest_id

    if record_date is not None:
        if user_id is not None:
            owner_clause = ModeResultRecord.user_id == user_id
        else:
            owner_clause = and_(
                ModeResultRecord.user_id.is_(None),
                ModeResultRecord.guest_id == effective_guest_id,
            )

        existing = (
            await session.execute(
                select(ModeResultRecord).where(
                    ModeResultRecord.mode == mode,
                    ModeResultRecord.date == record_date,
                    owner_clause,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            if existing.completed:
                return existing
            existing.completed = completed
            existing.won = won
            existing.points = points
            existing.questions_used = questions_used
            existing.guesses_used = guesses_used
            existing.score = score
            existing.max_score = max_score
            existing.elapsed_seconds = elapsed_seconds
            existing.completed_at = now
            await session.commit()
            return existing

    record = ModeResultRecord(
        id=str(uuid4()),
        mode=mode,
        date=record_date,
        user_id=user_id,
        guest_id=effective_guest_id,
        completed=completed,
        won=won,
        points=points,
        questions_used=questions_used,
        guesses_used=guesses_used,
        score=score,
        max_score=max_score,
        elapsed_seconds=elapsed_seconds,
        completed_at=now,
    )
    session.add(record)
    await session.commit()
    return record
