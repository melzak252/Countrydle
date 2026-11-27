"""Flag SVG caching and Flag Shades grayscale challenge endpoints."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import hashlib
import logging
import os
import sys
import tempfile
from typing import Optional, TypeVar
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import Response as RawResponse
from sqlalchemy.ext.asyncio import AsyncSession

from country_eligibility import is_country_eligible
from db import get_db
from db.models import User
from db.repositories.country import CountryRepository
from db.repositories.flagdle import FlagdleDayRepository
from flagdle.utils import (
    FACTS_DB_PATH,
    evaluate_flag_clues,
    generate_shades_token,
    get_country_iso2,
    normalize_svg_for_grid,
    verify_shades_token,
)
from game_logic import calculate_flagdle_points
from schemas.flagdle import (
    FlagShadesChallenge,
    FlagShadesGuessRequest,
    FlagShadesGuessResult,
    FlagShadesTargetCountry,
)
from users.utils import get_current_or_guest_user
from utils.guest_session import get_guest_identity

logger = logging.getLogger("countrydle.flagdle")

router = APIRouter()

FLAG_SVG_CACHE_DIR = FACTS_DB_PATH.parent / "flag_svg_cache"

T = TypeVar("T")


def flagdle_attr(name: str, default: T) -> T:
    """Resolve an attribute through ``flagdle`` when loaded for test monkeypatch compatibility."""
    mod = sys.modules.get("flagdle")
    if mod is not None and hasattr(mod, name):
        return getattr(mod, name)
    return default


def _get_or_fetch_flag_svg(iso2: str) -> bytes:
    code = iso2.lower()
    cache_dir = flagdle_attr("FLAG_SVG_CACHE_DIR", FLAG_SVG_CACHE_DIR)
    try:
        if len(code) != 2 or not all("a" <= char <= "z" for char in code):
            raise ValueError("Flag asset requires a two-letter ASCII ISO2 code")

        cache_path = cache_dir / f"{code}.svg"
        try:
            return cache_path.read_bytes()
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("Failed to read cached SVG for %s: %s", code, exc)

        url = f"https://flagcdn.com/{code}.svg"
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "flagcdn.com":
            raise ValueError("Invalid flag SVG URL")
        req = urllib.request.Request(url, headers={"User-Agent": "Countrydle/1.0"})
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read()
    except Exception as exc:
        logger.warning("Failed to fetch SVG for %s from flagcdn: %s", code, exc)
        fallback = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600">'
            '<rect width="900" height="600" fill="#1e293b"/>'
            '<text x="450" y="300" fill="#94a3b8" font-size="40" font-family="sans-serif" '
            f'text-anchor="middle">Flag of {code.upper()}</text></svg>'
        )
        return fallback.encode("utf-8")

    temporary_path = None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=cache_dir, prefix=f".{code}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = temporary.name
            temporary.write(content)
        os.replace(temporary_path, cache_path)
        temporary_path = None
    except OSError as exc:
        logger.warning("Failed to cache SVG for %s: %s", code, exc)
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning("Failed to remove temporary SVG for %s: %s", code, exc)
    return content


@router.get("/shades/challenge", response_model=FlagShadesChallenge)
async def get_shades_challenge(
    seed: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Generates or fetches a Flag Shades challenge round (daily or custom seed)."""
    all_countries = await CountryRepository(session).get_all_countries()
    eligible_countries = [c for c in all_countries if is_country_eligible(c.name, "flagdle")]
    if not eligible_countries:
        eligible_countries = all_countries
    eligible_countries.sort(key=lambda c: c.id)
    if not eligible_countries:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No eligible countries found.",
        )

    today_str = datetime.now(timezone.utc).date().isoformat()
    if not seed or seed.strip() == "daily":
        is_daily = True
        effective_seed = f"daily-{today_str}"
    else:
        is_daily = False
        effective_seed = seed.strip()[:64]

    seed_hash_int = int(
        hashlib.sha256(f"flag-shades:{effective_seed}".encode("utf-8")).hexdigest(),
        16,
    )
    target_idx = seed_hash_int % len(eligible_countries)
    target_country = eligible_countries[target_idx]

    if is_daily:
        today_flag = await FlagdleDayRepository(session).get_today_flag()
        if today_flag and today_flag.country_id == target_country.id and len(eligible_countries) > 1:
            target_idx = (target_idx + 1) % len(eligible_countries)
            target_country = eligible_countries[target_idx]

    token = generate_shades_token(effective_seed, target_country.id)
    return FlagShadesChallenge(
        seed=effective_seed,
        is_daily=is_daily,
        date=today_str,
        max_guesses=12,
        hint_unlock_guesses=3,
        token=token,
        flag_asset_url=f"/flagdle/shades/flag-asset?token={token}",
    )


@router.get("/shades/flag-asset")
async def get_shades_flag_asset(
    token: str = Query(...),
    fit: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Securely streams the grayscale/color flag SVG for shades challenge without leaking country in URL."""
    verified = verify_shades_token(token)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid shades token.",
        )

    _seed, country_id = verified
    target_country = await CountryRepository(session).get(country_id)
    if not target_country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target country not found.",
        )

    iso2 = get_country_iso2(target_country.name)
    fetch_svg = flagdle_attr("_get_or_fetch_flag_svg", _get_or_fetch_flag_svg)
    svg_bytes = await asyncio.to_thread(fetch_svg, iso2)
    if fit == "grid":
        svg_bytes = normalize_svg_for_grid(svg_bytes, iso2)
    return RawResponse(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/shades/guess", response_model=FlagShadesGuessResult)
async def make_shades_guess(
    body: FlagShadesGuessRequest,
    request: Request,
    response: Response,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Evaluates a guess in Flag Shades challenge mode."""
    verified = verify_shades_token(body.token)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid shades token.",
        )

    seed_str, target_country_id = verified
    target_country = await CountryRepository(session).get(target_country_id)
    if not target_country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target country not found.",
        )

    all_countries = await CountryRepository(session).get_all_countries()
    guessed_country = None
    if body.country_id:
        guessed_country = next((c for c in all_countries if c.id == body.country_id), None)
    if not guessed_country and body.guess:
        clean_guess = body.guess.strip().casefold()
        guessed_country = next(
            (
                c
                for c in all_countries
                if c.name.strip().casefold() == clean_guess
                or (
                    getattr(c, "official_name", None)
                    and c.official_name.strip().casefold() == clean_guess
                )
            ),
            None,
        )
    if not guessed_country:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guessed country not found.",
        )

    is_correct = guessed_country.id == target_country.id
    clues = await asyncio.to_thread(
        evaluate_flag_clues,
        target_country_id=target_country.id,
        guessed_country_id=guessed_country.id,
        target_country_name=target_country.name,
        guessed_country_name=guessed_country.name,
    )

    is_game_over = is_correct or (body.guesses_made >= 12)
    target_info = (
        FlagShadesTargetCountry(id=target_country.id, name=target_country.name)
        if is_game_over
        else None
    )

    if is_game_over and seed_str.startswith("daily-"):
        try:
            challenge_date = date.fromisoformat(seed_str[len("daily-") :])
            from stats.service import record_mode_result

            user_id = user.id if user is not None else None
            guest_id = None if user is not None else get_guest_identity(request, response)
            points = calculate_flagdle_points(is_correct, body.guesses_made)
            await record_mode_result(
                session,
                mode="flag_shades",
                record_date=challenge_date,
                user_id=user_id,
                guest_id=guest_id,
                completed=True,
                won=is_correct,
                points=points,
                guesses_used=body.guesses_made,
                elapsed_seconds=getattr(body, "elapsed_seconds", None),
            )
        except Exception as exc:
            logger.warning("Could not record flag_shades daily result: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass

    return FlagShadesGuessResult(
        answer=is_correct,
        guess=guessed_country.name,
        country_id=guessed_country.id,
        iso2=get_country_iso2(guessed_country.name),
        distance_km=clues.get("distance_km"),
        bearing_degrees=clues.get("bearing_degrees"),
        bearing_direction=clues.get("bearing_direction"),
        bearing_arrow=clues.get("bearing_arrow"),
        matched_colors=clues.get("matched_colors") or [],
        missed_colors=clues.get("missed_colors") or [],
        remaining_colors_count=clues.get("remaining_colors_count"),
        matched_symbols=clues.get("matched_symbols") or [],
        is_game_over=is_game_over,
        won=is_correct,
        target_country=target_info,
    )
