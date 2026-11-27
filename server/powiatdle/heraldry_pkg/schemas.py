"""Pydantic schemas, session token cryptography, and facade lookup helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from typing import Any, List, Optional, TypeVar

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

T = TypeVar("T")


def facade_attr(name: str, default: T) -> T:
    """Resolve an attribute through ``powiatdle.heraldry`` when loaded.

    Preserves backwards compatibility for tests that monkeypatch symbols
    directly on ``powiatdle.heraldry``.
    """
    mod = sys.modules.get("powiatdle.heraldry")
    if mod is not None and hasattr(mod, name):
        return getattr(mod, name)
    return default


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PowiatHeraldrySourceAttribution(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    license_url: Optional[str] = None
    source_url: Optional[str] = None
    description: Optional[str] = None


class RegionalComponentCredit(BaseModel):
    title: str
    url: str
    author: str
    license: str
    license_url: Optional[str] = None


class RegionalSourceAttribution(PowiatHeraldrySourceAttribution):
    context: Optional[str] = None
    component_credits: List[RegionalComponentCredit] = Field(default_factory=list)


class PowiatHeraldryTarget(BaseModel):
    id: int
    name: str
    voivodeship: str


class PowiatHeraldryItem(BaseModel):
    id: int
    name: str
    voivodeship: str
    is_city_county: bool


class RegionalSymbolItem(PowiatHeraldryItem):
    aliases: List[str] = Field(default_factory=list)


class PowiatHeraldryGuessRequest(BaseModel):
    token: str
    guess: str
    powiat_id: Optional[int] = None


class PowiatHeraldryGuessResult(BaseModel):
    answer: bool
    guess: str
    powiat_id: int
    voivodeship: str
    distance_km: Optional[int | float] = None
    bearing_degrees: Optional[int] = None
    bearing_direction: Optional[str] = None
    bearing_arrow: Optional[str] = None
    same_voivodeship: bool
    guesses_made: int
    remaining_guesses: int
    is_game_over: bool
    won: bool
    registration_plates: Optional[List[str]] = None
    target_powiat: Optional[PowiatHeraldryTarget] = None
    source_attribution: Optional[RegionalSourceAttribution | PowiatHeraldrySourceAttribution] = None
    token: Optional[str] = None
    ranked: bool = False
    points: Optional[int] = None


class PowiatHeraldryChallenge(BaseModel):
    seed: str
    is_daily: bool
    date: str
    max_guesses: int = 8
    hint_unlock_guesses: int = 5
    token: str
    coat_asset_url: str
    source_attribution: Optional[RegionalSourceAttribution | PowiatHeraldrySourceAttribution] = None
    guesses: Optional[List[PowiatHeraldryGuessResult]] = None
    is_game_over: Optional[bool] = False
    won: Optional[bool] = False
    registration_plates: Optional[List[str]] = None
    target_powiat: Optional[PowiatHeraldryTarget] = None
    ranked: bool = False
    points: Optional[int] = None


# ---------------------------------------------------------------------------
# Security & Crypto
# ---------------------------------------------------------------------------


def get_fernet() -> Fernet:
    secret_key = os.getenv("SECRET_KEY", "fallback_countrydle_secret")
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode("utf-8")).digest())
    return Fernet(fernet_key)


def encrypt_session_token(payload: dict[str, Any]) -> str:
    f = get_fernet()
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return f.encrypt(data).decode("utf-8")


def decrypt_session_token(token: str) -> dict[str, Any]:
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid session token.",
        )
    f = get_fernet()
    try:
        data = f.decrypt(token.encode("utf-8"))
        return json.loads(data.decode("utf-8"))
    except (InvalidToken, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired heraldry session token.",
        ) from exc
