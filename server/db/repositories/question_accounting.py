"""Shared daily accounting locks and short action-finalization transactions."""
import hashlib
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select


def is_answered(question) -> bool:
    return question.valid is True and type(question.answer) is bool


def unresolved_question(question, display):
    return display.model_validate({
        **question.model_dump(),
        "id": 0,
        "asked_at": datetime.now(),
        "valid": False,
        "answer": None,
        "explanation": question.explanation or "Could not verify this question. Your turn was not deducted.",
    })


async def lock_question_state(session, model, user_id, day_id):
    # State tables predate unique user/day constraints. Lock the logical key even
    # when there is no row yet, using the same PostgreSQL pattern as friend matches.
    key = f"daily-question:{model.__tablename__}:{user_id}:{day_id}"
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    await session.execute(select(func.pg_advisory_xact_lock(lock_id)))
    return await session.scalar(
        select(model).where(model.user_id == user_id, model.day_id == day_id)
        .order_by(model.id).limit(1).with_for_update().execution_options(populate_existing=True)
    )


async def get_daily_state(session, model, user_id, day_id, max_questions, max_guesses):
    """Lock/read/create authoritative state; never release the lock with a commit."""
    state = await lock_question_state(session, model, user_id, day_id)
    if state is None:
        values = dict(
            user_id=user_id, day_id=day_id, questions_asked=0, guesses_made=0,
            remaining_guesses=max_guesses, is_game_over=False, won=False, points=0,
        )
        if max_questions is not None:
            values["remaining_questions"] = max_questions
        state = model(**values)
        session.add(state)
        await session.flush()
    return state


def require_guess_available(state, max_guesses):
    if state is not None and (
        state.is_game_over or state.won or state.guesses_made >= max_guesses
        or state.remaining_guesses <= 0
    ):
        raise HTTPException(status_code=400, detail="No more guesses left or game over!")


def require_question_available(state, max_questions):
    if max_questions is not None and state is not None and (
        state.is_game_over or state.won or state.remaining_guesses <= 0
        or state.questions_asked >= max_questions
    ):
        raise HTTPException(status_code=400, detail="No more questions left or game over!")


async def check_question_available(session, model, user_id, day_id, max_questions):
    state = await session.scalar(
        select(model).where(model.user_id == user_id, model.day_id == day_id).order_by(model.id).limit(1)
    )
    require_question_available(state, max_questions)


async def consume_question(session, model, user_id, day_id, max_questions, max_guesses):
    """Stage one accepted answer; the route commits it with the question or rolls both back."""
    state = await get_daily_state(session, model, user_id, day_id, max_questions, max_guesses)
    require_question_available(state, max_questions)
    state.questions_asked += 1
    if max_questions is not None:
        state.remaining_questions = max_questions - state.questions_asked
    await session.flush()
    return state

