import os
from datetime import UTC, datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "fallback_countrydle_secret")
ALGORITHM = os.getenv("ALGORITHM", "HS256")


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
