"""Daily question acceptance and its short, cross-worker finalization transaction."""
import hashlib
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update


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


def require_question_available(state, max_questions):
    if max_questions is not None and state is not None and (
        state.is_game_over or state.questions_asked >= max_questions
    ):
        raise HTTPException(status_code=400, detail="No more questions left or game over!")


async def check_question_available(session, model, user_id, day_id, max_questions):
    state = await session.scalar(
        select(model).where(model.user_id == user_id, model.day_id == day_id).order_by(model.id).limit(1)
    )
    require_question_available(state, max_questions)


async def consume_question(session, model, user_id, day_id, max_questions, max_guesses):
    """Stage one accepted answer; the route commits it with the question or rolls both back."""
    state = await lock_question_state(session, model, user_id, day_id)
    require_question_available(state, max_questions)
    if state is None:
        values = dict(user_id=user_id, day_id=day_id, questions_asked=0,
                      guesses_made=0, remaining_guesses=max_guesses, is_game_over=False, won=False)
        if max_questions is not None:
            values["remaining_questions"] = max_questions
        state = model(**values)
        session.add(state)
    state.questions_asked += 1
    if max_questions is not None:
        state.remaining_questions = max_questions - state.questions_asked
    await session.flush()
    return state


async def claim_guest_questions(session, model, state, question_ids, max_questions):
    """Claim only resolved guest rows, never counters supplied by localStorage."""
    candidates = (
        select(model.id).where(
            model.id.in_(question_ids), model.user_id.is_(None), model.day_id == state.day_id,
            model.valid.is_(True), model.answer.is_not(None),
        ).order_by(model.id).limit(max_questions).with_for_update()
    )
    ids = list((await session.scalars(candidates)).all())
    if ids:
        # Recheck ownership after waiting for another account claiming a row.
        result = await session.execute(
            update(model).where(model.id.in_(ids), model.user_id.is_(None))
            .values(user_id=state.user_id).returning(model.id)
        )
        ids = list(result.scalars())
    state.questions_asked = len(ids)
    state.remaining_questions = max_questions - len(ids)
    await session.flush()
