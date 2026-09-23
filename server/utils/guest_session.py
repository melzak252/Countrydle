import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Request, Response
from sqlalchemy import or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.guest_participation import GuestParticipation
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "fallback_countrydle_secret")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

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
            secure=request.url.scheme == "https",
            max_age=GUEST_IDENTITY_MAX_AGE,
        )
    request.state.guest_identity = identity
    return identity


async def record_guest_action(
    session: AsyncSession,
    request: Request,
    response: Response,
    mode: str,
    day_id: int,
    *,
    question: bool = False,
    won: bool | None = None,
) -> None:
    """Stage an accepted action in the action repository's transaction, without committing."""
    identity = get_guest_identity(request, response)
    statement = insert(GuestParticipation).values(
        guest_id=identity,
        mode=mode,
        day_id=day_id,
        questions_asked=int(question),
        guesses_made=int(not question),
        won=bool(won),
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_guest_participation_mode_day_identity",
            set_={
                "questions_asked": GuestParticipation.questions_asked + statement.excluded.questions_asked,
                "guesses_made": GuestParticipation.guesses_made + statement.excluded.guesses_made,
                "won": or_(GuestParticipation.won, statement.excluded.won),
            },
        )
    )


async def link_guest_participation(
    session: AsyncSession, request: Request, mode: str, day_id: int, user_id: int
) -> int | None:
    """Link only this browser's puzzle; repeated sync cannot steal another account's link."""
    identity = read_guest_identity(request)
    if identity is None:
        return None
    result = await session.execute(
        update(GuestParticipation)
        .where(
            GuestParticipation.guest_id == identity,
            GuestParticipation.mode == mode,
            GuestParticipation.day_id == day_id,
            or_(GuestParticipation.user_id.is_(None), GuestParticipation.user_id == user_id),
        )
        .values(user_id=user_id)
        .returning(GuestParticipation.questions_asked)
    )
    return result.scalar_one_or_none()


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
