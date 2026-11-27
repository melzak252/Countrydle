import hashlib
import hmac
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.powiat import Powiat
from db.models.powiat_map_quiz import PowiatMapQuizSession
from db.models.user import User
from schemas.powiat_map_quiz import (
    DailyMapQuizAnswerRequest,
    DailyMapQuizState,
    MapQuizDailyStats,
    MapQuizHistoryResponse,
)
from users.utils import get_current_or_guest_user, get_current_user
from utils.guest_session import SECRET_KEY, get_guest_identity, read_guest_identity


ROUND_COUNT = 10
MIN_PUBLIC_STATS_COMPLETIONS = 5
DAILY_SET_VERSION = "v1"

router = APIRouter(prefix="/map-quiz", tags=["powiat-map-quiz"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_today() -> date:
    return utc_now().date()


def _lock_key(owner: str, day: date) -> int:
    raw = f"powiat-map-quiz:{day.isoformat()}:{owner}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)


async def _lock_owner(session: AsyncSession, owner: str, day: date) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(_lock_key(owner, day))))


async def _daily_targets(session: AsyncSession, day: date) -> list[dict[str, int | str]]:
    await _lock_owner(session, "shared-sequence", day)
    stored_targets = await session.scalar(
        select(PowiatMapQuizSession.targets)
        .where(PowiatMapQuizSession.date == day)
        .order_by(PowiatMapQuizSession.started_at.asc())
        .limit(1)
    )
    if stored_targets is not None:
        if len(stored_targets) != ROUND_COUNT:
            raise HTTPException(status_code=503, detail="Powiat quiz data is unavailable.")
        return stored_targets

    rows = (await session.execute(select(Powiat.id, Powiat.nazwa))).all()
    if len(rows) < ROUND_COUNT:
        raise HTTPException(status_code=503, detail="Powiat quiz data is unavailable.")

    ordered = sorted(
        rows,
        key=lambda row: hmac.new(
            SECRET_KEY.encode(),
            f"powiat-map-quiz-{DAILY_SET_VERSION}:{day.isoformat()}:{row.id}".encode(),
            hashlib.sha256,
        ).digest(),
    )
    return [{"id": row.id, "name": row.nazwa} for row in ordered[:ROUND_COUNT]]


def _row_for_owner_query(day: date, user: User | None, guest_id: str | None):
    statement = select(PowiatMapQuizSession).where(PowiatMapQuizSession.date == day)
    if user is not None:
        return statement.where(PowiatMapQuizSession.user_id == user.id)
    if guest_id is not None:
        return statement.where(
            PowiatMapQuizSession.user_id.is_(None),
            PowiatMapQuizSession.guest_id == guest_id,
        )
    return None


async def _owned_today(
    session: AsyncSession,
    day: date,
    user: User | None,
    guest_id: str | None,
    *,
    for_update: bool = False,
) -> PowiatMapQuizSession | None:
    if user is not None:
        statement = _row_for_owner_query(day, user, None)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await session.scalar(statement)
        if row is not None:
            return row

    if guest_id is None:
        return None
    statement = _row_for_owner_query(day, None, guest_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(statement)


async def _get_or_create_today(
    session: AsyncSession,
    request: Request,
    response: Response,
    user: User | None,
    day: date,
) -> PowiatMapQuizSession:
    guest_id = read_guest_identity(request)
    if user is None:
        guest_id = get_guest_identity(request, response)

    if user is not None:
        await _lock_owner(session, f"user:{user.id}", day)
        row = await _owned_today(session, day, user, None, for_update=True)
        if row is not None:
            await session.commit()
            return row

    if guest_id is not None:
        if user is not None:
            await _lock_owner(session, f"guest:{guest_id}", day)
        row = await _owned_today(session, day, None, guest_id, for_update=True)
        if row is not None:
            await session.commit()
            return row

    targets = await _daily_targets(session, day)
    row = PowiatMapQuizSession(
        id=str(uuid4()),
        date=day,
        user_id=user.id if user is not None else None,
        guest_id=None if user is not None else guest_id,
        targets=targets,
        answers=[],
        score=0,
        started_at=utc_now(),
    )
    session.add(row)
    await session.commit()
    return row


def _progress_answers(row: PowiatMapQuizSession) -> list[dict]:
    return [
        {
            "round": answer["round"],
            "target_name": row.targets[answer["round"]]["name"],
            "guess_id": answer["guess_id"],
            "correct": answer["correct"],
        }
        for answer in row.answers
    ]


def _answer_result(answer: dict | None) -> dict | None:
    if answer is None:
        return None
    return {
        "round": answer["round"],
        "guess_id": answer["guess_id"],
        "correct": answer["correct"],
    }


def _daily_state(row: PowiatMapQuizSession, last_answer: dict | None = None) -> dict:
    expected_round = len(row.answers)
    current_target = (
        row.targets[expected_round]["name"] if expected_round < ROUND_COUNT else None
    )
    return {
        "date": row.date,
        "round_count": ROUND_COUNT,
        "expected_round": expected_round,
        "current_target": current_target,
        "score": row.score,
        "is_complete": row.completed_at is not None,
        "answers": _progress_answers(row),
        "last_answer": _answer_result(last_answer),
    }


@router.get("/daily", response_model=DailyMapQuizState)
async def get_daily(
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_today(session, request, response, user, utc_today())
    return _daily_state(row)


@router.post("/daily/answer", response_model=DailyMapQuizState)
async def submit_answer(
    body: DailyMapQuizAnswerRequest,
    request: Request,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day = utc_today()
    guest_id = read_guest_identity(request)
    row = await _owned_today(session, day, user, guest_id, for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Start today's quiz before answering.")

    current_round = len(row.answers)
    if body.expected_round < current_round:
        previous = row.answers[body.expected_round]
        if previous["guess_id"] == body.guess_id:
            return _daily_state(row, previous)
        raise HTTPException(status_code=409, detail="That round was already answered differently.")
    if body.expected_round > current_round or current_round >= ROUND_COUNT:
        raise HTTPException(status_code=409, detail="The expected round does not match the current quiz.")

    if await session.get(Powiat, body.guess_id) is None:
        raise HTTPException(status_code=422, detail="guess_id must identify a Powiat.")

    correct = body.guess_id == row.targets[current_round]["id"]
    answer = {"round": current_round, "guess_id": body.guess_id, "correct": correct}
    row.answers = [*row.answers, answer]
    row.score += int(correct)
    if len(row.answers) == ROUND_COUNT:
        row.completed_at = utc_now()

    await session.commit()
    return _daily_state(row, answer)


@router.get("/history", response_model=MapQuizHistoryResponse)
async def get_history(
    request: Request,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    guest_id = read_guest_identity(request)
    if user is None and guest_id is None:
        return {"items": [], "total": 0}

    if user is not None:
        owner_filter = PowiatMapQuizSession.user_id == user.id
        if guest_id is not None:
            owner_filter = or_(
                owner_filter,
                and_(
                    PowiatMapQuizSession.user_id.is_(None),
                    PowiatMapQuizSession.guest_id == guest_id,
                ),
            )
    else:
        owner_filter = and_(
            PowiatMapQuizSession.user_id.is_(None),
            PowiatMapQuizSession.guest_id == guest_id,
        )

    rows = (
        await session.scalars(
            select(PowiatMapQuizSession)
            .where(
                owner_filter,
                PowiatMapQuizSession.date <= utc_today(),
                PowiatMapQuizSession.completed_at.is_not(None),
            )
            .order_by(PowiatMapQuizSession.date.desc())
        )
    ).all()
    items = [
        {
            "date": row.date,
            "score": row.score,
            "round_count": ROUND_COUNT,
            "completed_at": row.completed_at,
            "answers": _progress_answers(row),
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}


@router.get("/daily/stats", response_model=MapQuizDailyStats)
async def get_daily_stats(session: AsyncSession = Depends(get_db)):
    day = utc_today()
    score_rows = (
        await session.execute(
            select(PowiatMapQuizSession.score, func.count())
            .where(
                PowiatMapQuizSession.date == day,
                PowiatMapQuizSession.completed_at.is_not(None),
            )
            .group_by(PowiatMapQuizSession.score)
        )
    ).all()
    completed_count = sum(count for _, count in score_rows)
    if completed_count < MIN_PUBLIC_STATS_COMPLETIONS:
        return {
            "date": day,
            "completed_count": None,
            "average_score": None,
            "score_distribution": None,
        }

    score_distribution = {str(score): 0 for score in range(ROUND_COUNT + 1)}
    total_score = 0
    for score, count in score_rows:
        score_distribution[str(score)] = count
        total_score += score * count
    return {
        "date": day,
        "completed_count": completed_count,
        "average_score": round(total_score / completed_count, 2),
        "score_distribution": score_distribution,
    }


async def _claim_guest_session(
    session: AsyncSession, user: User, guest_id: str | None, day: date
) -> PowiatMapQuizSession:
    await _lock_owner(session, f"user:{user.id}", day)
    account_row = await session.scalar(
        select(PowiatMapQuizSession)
        .where(
            PowiatMapQuizSession.date == day,
            PowiatMapQuizSession.user_id == user.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if account_row is not None and account_row.answers:
        await session.commit()
        return account_row

    if guest_id is None:
        if account_row is not None:
            await session.commit()
            return account_row
        raise HTTPException(status_code=404, detail="No guest quiz session is available to claim.")

    await _lock_owner(session, f"guest:{guest_id}", day)
    guest_row = await session.scalar(
        select(PowiatMapQuizSession)
        .where(
            PowiatMapQuizSession.date == day,
            PowiatMapQuizSession.user_id.is_(None),
            PowiatMapQuizSession.guest_id == guest_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if guest_row is None:
        if account_row is not None:
            await session.commit()
            return account_row
        raise HTTPException(status_code=404, detail="No guest quiz session is available to claim.")

    if account_row is not None:
        await session.delete(account_row)
        await session.flush()
    guest_row.user_id = user.id
    guest_row.guest_id = None
    await session.commit()
    return guest_row


@router.post("/daily/claim", response_model=DailyMapQuizState)
async def claim_daily(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication is required to claim a guest session.")
    row = await _claim_guest_session(session, user, read_guest_identity(request), utc_today())
    return _daily_state(row)
