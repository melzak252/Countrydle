import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.guest_participation import GuestParticipation
from db.repositories.question_accounting import lock_question_state
from jose import JWTError, jwt

from runtime_configuration import ALGORITHM, SECRET_KEY

GUEST_IDENTITY_COOKIE = "guest_identity"
GUEST_IDENTITY_MAX_AGE = 2 * 86400


def read_guest_identity(request: Request) -> str | None:
    cached = getattr(request.state, "guest_identity", None)
    if cached is not None:
        return cached
    token = request.cookies.get(GUEST_IDENTITY_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "guest_identity":
            return None
        return str(UUID(payload["sub"]))
    except (JWTError, KeyError, ValueError, TypeError, AttributeError):
        return None


def get_guest_identity(request: Request, response: Response) -> str:
    identity = read_guest_identity(request)
    if identity is None:
        identity = str(uuid4())
        token = jwt.encode(
            {
                "sub": identity,
                "purpose": "guest_identity",
                "exp": datetime.now(UTC) + timedelta(seconds=GUEST_IDENTITY_MAX_AGE),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        response.set_cookie(
            GUEST_IDENTITY_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https" or os.getenv("FRIEND_COOKIE_SECURE", "").lower() in {"true", "1", "yes"},
            max_age=GUEST_IDENTITY_MAX_AGE,
        )
    request.state.guest_identity = identity
    return identity


async def lock_guest_participation(
    session: AsyncSession, identity: str, mode: str, day_id: int, *, create: bool = True
) -> GuestParticipation | None:
    """The unique identity/mode/day row serializes guest actions, including first creation."""
    if create:
        await session.execute(
            insert(GuestParticipation).values(
                guest_id=identity, mode=mode, day_id=day_id,
                questions_asked=0, guesses_made=0, won=False,
            ).on_conflict_do_nothing(constraint="uq_guest_participation_mode_day_identity")
        )
    return await session.scalar(
        select(GuestParticipation).where(
            GuestParticipation.guest_id == identity,
            GuestParticipation.mode == mode,
            GuestParticipation.day_id == day_id,
        ).with_for_update().execution_options(populate_existing=True)
    )


def guest_game_over(participation: GuestParticipation | None, max_guesses: int) -> bool:
    # Existing excessive counters stay intact and are terminal, without a lossy backfill.
    return participation is not None and (
        participation.won or participation.guesses_made >= max_guesses
    )


def _require_unclaimed_guest(participation):
    if participation is not None and participation.user_id is not None:
        raise HTTPException(
            status_code=409,
            detail="This guest game was synchronized to an account. Sign in to continue.",
        )


def require_guest_question_available(participation, max_questions, max_guesses):
    _require_unclaimed_guest(participation)
    if max_questions is not None and participation is not None and (
        guest_game_over(participation, max_guesses)
        or participation.questions_asked >= max_questions
    ):
        raise HTTPException(status_code=400, detail="No more questions left or game over!")


async def check_guest_question_available(
    session: AsyncSession,
    request: Request,
    response: Response,
    mode: str,
    day_id: int,
    max_questions: int | None,
    *,
    max_guesses: int,
) -> None:
    """Cheap preflight; finalization repeats the authoritative guard under the row lock."""
    identity = get_guest_identity(request, response)
    participation = await session.scalar(
        select(GuestParticipation).where(
            GuestParticipation.guest_id == identity,
            GuestParticipation.mode == mode,
            GuestParticipation.day_id == day_id,
        )
    )
    require_guest_question_available(participation, max_questions, max_guesses)


async def record_guest_action(
    session: AsyncSession,
    request: Request,
    response: Response,
    mode: str,
    day_id: int,
    *,
    max_guesses: int,
    question: bool = False,
    won: bool | None = None,
    max_questions: int | None = None,
) -> GuestParticipation:
    """Guard and stage durable progress; commit once with its identity-bound history."""
    identity = get_guest_identity(request, response)
    participation = await lock_guest_participation(session, identity, mode, day_id)
    if question:
        require_guest_question_available(participation, max_questions, max_guesses)
        participation.questions_asked += 1
    else:
        _require_unclaimed_guest(participation)
        if guest_game_over(participation, max_guesses):
            raise HTTPException(status_code=400, detail="No more guesses left or game over!")
        participation.guesses_made += 1
        participation.won = participation.won or bool(won)
    await session.flush()
    return participation


async def get_guest_progress(
    session: AsyncSession, request: Request, response: Response | None, mode: str, day_id: int,
    guess_model, question_model=None,
):
    """Reload only this signed identity's originals, never per-mode cookie counters."""
    identity = get_guest_identity(request, response) if response is not None else read_guest_identity(request)
    if identity is None:
        return None, [], []
    participation = await lock_guest_participation(session, identity, mode, day_id, create=False)
    guesses = list((await session.scalars(
        select(guess_model).where(
            guess_model.guest_id == identity, guess_model.day_id == day_id,
        ).order_by(guess_model.guessed_at, guess_model.id)
    )).all())
    questions = []
    if question_model is not None:
        questions = list((await session.scalars(
            select(question_model).where(
                question_model.guest_id == identity, question_model.day_id == day_id,
                question_model.valid.is_(True), question_model.answer.is_not(None),
            ).order_by(question_model.asked_at, question_model.id)
        )).all())
    return participation, guesses, questions


async def claim_guest_history(
    session: AsyncSession, request: Request, state, mode: str, guess_model, question_model,
    max_questions: int | None, max_guesses: int, *, validate_original_guess=None,
) -> bool:
    """Account-before-guest locking; import once from original durable, identified records."""
    state = await lock_question_state(session, type(state), state.user_id, state.day_id)
    identity = read_guest_identity(request)
    if identity is None:
        return False
    participation = await lock_guest_participation(
        session, identity, mode, state.day_id, create=False,
    )
    if participation is None or participation.user_id is not None:
        return False
    if not (participation.questions_asked or participation.guesses_made):
        return False
    # Do not overwrite or merge account progress, even if a client submits a newer snapshot.
    if state.questions_asked or state.guesses_made or state.is_game_over or state.won:
        participation.user_id = state.user_id
        await session.flush()
        return False
    if validate_original_guess is not None:
        originals = (await session.scalars(
            select(guess_model).where(
                guess_model.guest_id == identity, guess_model.day_id == state.day_id,
                guess_model.user_id.is_(None),
            )
        )).all()
        for original in originals:
            await validate_original_guess(getattr(original, "country_id", None), original.guess)
    participation.user_id = state.user_id
    for model in (guess_model, question_model):
        if model is not None:
            await session.execute(
                update(model).where(
                    model.guest_id == identity, model.day_id == state.day_id,
                    model.user_id.is_(None),
                ).values(user_id=state.user_id)
            )
    state.questions_asked = participation.questions_asked
    state.guesses_made = participation.guesses_made
    state.remaining_guesses = max(0, max_guesses - state.guesses_made)
    if max_questions is not None:
        state.remaining_questions = max(0, max_questions - state.questions_asked)
    state.won = participation.won
    state.is_game_over = guest_game_over(participation, max_guesses)
    if mode == "flagdle":
        state.revealed_stage = 12 if state.is_game_over else min(12, state.guesses_made + 1)
    await session.flush()
    return True

def create_guest_game_token(
    game_mode: str,
    day_id: int,
    guesses_count: int,
    is_game_over: bool,
    won: bool,
) -> str:
    payload = {
        "mode": game_mode,
        "day_id": day_id,
        "guesses_count": guesses_count,
        "is_game_over": is_game_over,
        "won": won,
        "exp": datetime.now(UTC) + timedelta(days=2),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def read_guest_game_token(
    token: str | None, game_mode: str, day_id: int
) -> dict:
    default_state = {
        "mode": game_mode,
        "day_id": day_id,
        "guesses_count": 0,
        "is_game_over": False,
        "won": False,
    }
    if not token:
        return default_state

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("mode") != game_mode or payload.get("day_id") != day_id:
            return default_state
        return {
            "mode": game_mode,
            "day_id": day_id,
            "guesses_count": int(payload.get("guesses_count", 0)),
            "is_game_over": bool(payload.get("is_game_over", False)),
            "won": bool(payload.get("won", False)),
        }
    except JWTError:
        return default_state
