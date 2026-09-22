from __future__ import annotations

from datetime import date, datetime
import logging
from typing import List, Optional
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import Response as RawResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import Country, User
from db.repositories.country import CountryRepository
from db.repositories.flagdle import (
    FlagdleDayRepository,
    FlagdleGuessRepository,
    FlagdleStateRepository,
)
from game_logic import FLAGDLE_CONFIG, GameRules, GameState
from schemas.country import CountryDisplay
from schemas.flagdle import (
    FlagdleCountryDisplay,
    FlagdleGuessBase,
    FlagdleGuessCreate,
    FlagdleGuessDisplay,
    FlagdleStateResponse,
    FlagdleStateSchema,
    FlagdleSyncSchema,
)
from users.utils import get_current_or_guest_user, get_current_user
from utils.guest_session import create_guest_game_token, read_guest_game_token
from flagdle.utils import (
    UNMASK_ORDER,
    evaluate_flag_clues,
    generate_asset_token,
    get_country_iso2,
    verify_asset_token,
)

logger = logging.getLogger("countrydle.flagdle")

router = APIRouter(prefix="/flagdle", tags=["flagdle"])

_FLAG_SVG_CACHE: dict[str, bytes] = {}


def _get_or_fetch_flag_svg(iso2: str) -> bytes:
    code = iso2.lower()
    if code in _FLAG_SVG_CACHE:
        return _FLAG_SVG_CACHE[code]

    url = f"https://flagcdn.com/{code}.svg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Countrydle/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read()
            _FLAG_SVG_CACHE[code] = content
            return content
    except Exception as exc:
        logger.warning("Failed to fetch SVG for %s from flagcdn: %s", code, exc)
        # Simple generic fallback SVG
        fallback = f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600"><rect width="900" height="600" fill="#1e293b"/><text x="450" y="300" fill="#94a3b8" font-size="40" font-family="sans-serif" text-anchor="middle">Flag of {code.upper()}</text></svg>'
        return fallback.encode("utf-8")


@router.get("/countries", response_model=List[FlagdleCountryDisplay])
async def get_countries(session: AsyncSession = Depends(get_db)):
    """Returns all available countries for Flagdle guess autocomplete, including iso2 codes."""
    country_repo = CountryRepository(session)
    countries = await country_repo.get_all_countries()
    result = []
    for c in countries:
        c_name = getattr(c, "name", "") or ""
        c_official = getattr(c, "official_name", "") or None
        c_id = int(getattr(c, "id", 0))
        iso2 = get_country_iso2(c_name)
        result.append(
            FlagdleCountryDisplay(
                id=c_id,
                name=c_name,
                official_name=c_official,
                iso2=iso2,
            )
        )
    return result


@router.get("/flag-asset")
async def get_flag_asset(
    token: str = Query(...),
    session: AsyncSession = Depends(get_db),
):
    """Securely streams the daily secret flag SVG without leaking the country name in URL."""
    day_repo = FlagdleDayRepository(session)
    today_flag = await day_repo.get_today_flag()
    if not today_flag:
        today_flag = await day_repo.generate_new_day_flag()

    if not verify_asset_token(today_flag.id, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid flag asset token.")

    target_country = today_flag.country
    if not target_country:
        target_country = await CountryRepository(session).get(today_flag.country_id)

    if not target_country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target country not found.")

    iso2 = get_country_iso2(target_country.name)
    svg_bytes = _get_or_fetch_flag_svg(iso2)
    return RawResponse(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/state", response_model=FlagdleStateResponse)
async def get_state(
    request: Request,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Fetches or initializes the daily Flagdle state (anti-cheat protected)."""
    day_repo = FlagdleDayRepository(session)
    today_flag = await day_repo.get_today_flag()
    if not today_flag:
        today_flag = await day_repo.generate_new_day_flag()

    target_country = today_flag.country
    if not target_country:
        target_country = await CountryRepository(session).get(today_flag.country_id)

    today_str = today_flag.date.strftime("%Y-%m-%d") if today_flag.date else date.today().strftime("%Y-%m-%d")
    asset_token = generate_asset_token(today_flag.id)
    flag_asset_url = f"/flagdle/flag-asset?token={asset_token}"

    if user:
        state_repo = FlagdleStateRepository(session)
        state = await state_repo.get_state(user, today_flag)
        if not state:
            state = await state_repo.create_state(user, today_flag, max_guesses=FLAGDLE_CONFIG.max_guesses)

        guess_repo = FlagdleGuessRepository(session)
        db_guesses = await guess_repo.get_user_day_guesses(user, today_flag.id)

        guesses_display = []
        for g in db_guesses:
            guesses_display.append(
                FlagdleGuessDisplay(
                    id=g.id,
                    guess=g.guess,
                    country_id=g.country_id,
                    answer=g.answer,
                    distance_km=g.distance_km,
                    bearing_degrees=g.bearing_degrees,
                    bearing_direction=g.bearing_direction,
                    bearing_arrow=g.bearing_arrow,
                    matched_colors=g.matched_colors or [],
                    missed_colors=g.missed_colors or [],
                    remaining_colors_count=g.remaining_colors_count,
                    matched_symbols=g.matched_symbols or [],
                    revealed_tile=g.revealed_tile,
                    guessed_at=g.guessed_at or datetime.now(),
                )
            )

        revealed_country = None
        if state.is_game_over:
            revealed_country = CountryDisplay.model_validate(target_country) if target_country else None

        return FlagdleStateResponse(
            user=user,
            date=today_str,
            state=FlagdleStateSchema.model_validate(state),
            guesses=guesses_display,
            flag_asset_url=flag_asset_url,
            country=revealed_country,
        )
    else:
        # Guest session
        cookie = request.cookies.get("guest_flagdle")
        guest_state = read_guest_game_token(cookie, "flagdle", today_flag.id)

        guesses_made = guest_state["guesses_count"]
        is_won = guest_state["won"]
        is_game_over = guest_state["is_game_over"]
        remaining_guesses = max(0, FLAGDLE_CONFIG.max_guesses - guesses_made)
        revealed_stage = 6 if is_game_over else min(6, guesses_made + 1)

        state_schema = FlagdleStateSchema(
            remaining_guesses=remaining_guesses,
            guesses_made=guesses_made,
            revealed_stage=revealed_stage,
            is_game_over=is_game_over,
            won=is_won,
            points=0,
        )

        revealed_country = None
        if is_game_over:
            revealed_country = CountryDisplay.model_validate(target_country) if target_country else None

        return FlagdleStateResponse(
            user=None,
            date=today_str,
            state=state_schema,
            guesses=[],
            flag_asset_url=flag_asset_url,
            country=revealed_country,
        )


@router.post("/guess", response_model=FlagdleGuessDisplay)
async def make_guess(
    guess_in: FlagdleGuessBase,
    request: Request,
    response: Response,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Processes a Flagdle guess and returns tile reveal, color match, symbol match, and geo clues."""
    day_repo = FlagdleDayRepository(session)
    today_flag = await day_repo.get_today_flag()
    if not today_flag:
        today_flag = await day_repo.generate_new_day_flag()

    target_country = today_flag.country
    if not target_country:
        target_country = await CountryRepository(session).get(today_flag.country_id)

    if not target_country:
        raise HTTPException(status_code=500, detail="Target country not configured.")

    # Resolve guessed country
    country_repo = CountryRepository(session)
    guessed_country = None
    if guess_in.country_id:
        guessed_country = await country_repo.get(guess_in.country_id)
    if not guessed_country and guess_in.guess:
        all_countries = await country_repo.get_all_countries()
        for c in all_countries:
            if c.name.lower() == guess_in.guess.strip().lower() or (
                c.official_name and c.official_name.lower() == guess_in.guess.strip().lower()
            ):
                guessed_country = c
                break

    if not guessed_country:
        raise HTTPException(status_code=400, detail="Invalid country guess.")

    # Determine current guess index and check game status
    if user:
        state_repo = FlagdleStateRepository(session)
        state = await state_repo.get_state(user, today_flag)
        if not state:
            state = await state_repo.create_state(user, today_flag, max_guesses=FLAGDLE_CONFIG.max_guesses)

        if state.is_game_over or state.remaining_guesses <= 0:
            raise HTTPException(status_code=400, detail="Game is already over.")

        current_guess_idx = state.guesses_made
        existing_guesses = await FlagdleGuessRepository(session).get_user_day_guesses(user, today_flag.id)
    else:
        cookie = request.cookies.get("guest_flagdle")
        guest_state = read_guest_game_token(cookie, "flagdle", today_flag.id)
        if guest_state["is_game_over"] or guest_state["guesses_count"] >= FLAGDLE_CONFIG.max_guesses:
            raise HTTPException(status_code=400, detail="Game is already over.")

        current_guess_idx = guest_state["guesses_count"]
        existing_guesses = []

    # Gather prior matched colors for cumulative remaining count
    all_matched_colors = set()
    for eg in existing_guesses:
        if eg.matched_colors:
            all_matched_colors.update(eg.matched_colors)

    # Clue Evaluation
    clues = evaluate_flag_clues(
        target_country_id=target_country.id,
        guessed_country_id=guessed_country.id,
        target_country_name=target_country.name,
        guessed_country_name=guessed_country.name,
        all_matched_colors_so_far=all_matched_colors,
    )

    is_correct = guessed_country.id == target_country.id
    new_guesses_made = current_guess_idx + 1
    new_remaining = max(0, FLAGDLE_CONFIG.max_guesses - new_guesses_made)
    is_game_over = is_correct or (new_remaining == 0)
    won = is_correct
    new_stage = 6 if is_game_over else min(6, new_guesses_made + 1)
    revealed_tile = UNMASK_ORDER[min(current_guess_idx, 5)]

    now = datetime.now()

    if user:
        guess_repo = FlagdleGuessRepository(session)
        guess_create = FlagdleGuessCreate(
            guess=guessed_country.name,
            country_id=guessed_country.id,
            day_id=today_flag.id,
            user_id=user.id,
            answer=is_correct,
            distance_km=clues["distance_km"],
            bearing_degrees=clues["bearing_degrees"],
            bearing_direction=clues["bearing_direction"],
            bearing_arrow=clues["bearing_arrow"],
            matched_colors=clues["matched_colors"],
            missed_colors=clues["missed_colors"],
            remaining_colors_count=clues["remaining_colors_count"],
            matched_symbols=clues["matched_symbols"],
            revealed_tile=revealed_tile,
            elapsed_seconds=guess_in.elapsed_seconds,
        )
        saved_guess = await guess_repo.add_guess(guess_create)

        state.guesses_made = new_guesses_made
        state.remaining_guesses = new_remaining
        state.revealed_stage = new_stage
        state.is_game_over = is_game_over
        state.won = won

        if won:
            streak = (await state_repo.get_current_streak(user.id)) + 1
            state.points = await state_repo.calc_points(
                state, elapsed_seconds=guess_in.elapsed_seconds, streak=streak
            )

        await state_repo.update_state(state)

        return FlagdleGuessDisplay(
            id=saved_guess.id,
            guess=saved_guess.guess,
            country_id=saved_guess.country_id,
            answer=saved_guess.answer,
            distance_km=saved_guess.distance_km,
            bearing_degrees=saved_guess.bearing_degrees,
            bearing_direction=saved_guess.bearing_direction,
            bearing_arrow=saved_guess.bearing_arrow,
            matched_colors=saved_guess.matched_colors or [],
            missed_colors=saved_guess.missed_colors or [],
            remaining_colors_count=saved_guess.remaining_colors_count,
            matched_symbols=saved_guess.matched_symbols or [],
            revealed_tile=saved_guess.revealed_tile,
            guessed_at=saved_guess.guessed_at or now,
        )
    else:
        # Guest update
        token = create_guest_game_token("flagdle", today_flag.id, new_guesses_made, is_game_over, won)
        response.set_cookie("guest_flagdle", token, httponly=True, samesite="lax", max_age=86400 * 2)

        return FlagdleGuessDisplay(
            id=new_guesses_made,
            guess=guessed_country.name,
            country_id=guessed_country.id,
            answer=is_correct,
            distance_km=clues["distance_km"],
            bearing_degrees=clues["bearing_degrees"],
            bearing_direction=clues["bearing_direction"],
            bearing_arrow=clues["bearing_arrow"],
            matched_colors=clues["matched_colors"],
            missed_colors=clues["missed_colors"],
            remaining_colors_count=clues["remaining_colors_count"],
            matched_symbols=clues["matched_symbols"],
            revealed_tile=revealed_tile,
            guessed_at=now,
        )


@router.get("/reveal", response_model=CountryDisplay)
async def reveal_country(
    request: Request,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Reveals the secret target country only when the game is over."""
    day_repo = FlagdleDayRepository(session)
    today_flag = await day_repo.get_today_flag()
    if not today_flag:
        raise HTTPException(status_code=404, detail="No game today.")

    if user:
        state = await FlagdleStateRepository(session).get_state(user, today_flag)
        if state and not state.is_game_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal country before game is over.",
            )
    else:
        cookie = request.cookies.get("guest_flagdle")
        guest_state = read_guest_game_token(cookie, "flagdle", today_flag.id)
        if not guest_state["is_game_over"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal country before game is over.",
            )

    country = today_flag.country
    if not country:
        country = await CountryRepository(session).get(today_flag.country_id)

    if not country:
        raise HTTPException(status_code=404, detail="Country not found.")

    return CountryDisplay.model_validate(country)


@router.get("/end/state", response_model=FlagdleStateResponse)
async def get_end_state(
    request: Request,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Returns the final state with revealed country details upon game over."""
    state_response = await get_state(request=request, user=user, session=session)
    if not state_response.state.is_game_over:
        raise HTTPException(status_code=400, detail="Cannot access end state before game is over.")
    return state_response


@router.post("/sync", response_model=FlagdleStateResponse)
async def sync_guest_data(
    sync_data: FlagdleSyncSchema,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Reconciles guest localStorage progress into user profile upon authentication."""
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    day_repo = FlagdleDayRepository(session)
    day_flag = await day_repo.get_day_flag_by_date(game_date)
    if not day_flag:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    target_country = day_flag.country
    if not target_country:
        target_country = await CountryRepository(session).get(day_flag.country_id)

    state_repo = FlagdleStateRepository(session)
    state = await state_repo.get_state(user, day_flag)
    if state is None:
        state = await state_repo.create_state(user, day_flag, max_guesses=FLAGDLE_CONFIG.max_guesses)

    # Server state takes strict precedence if user already played on server
    if state.guesses_made > 0:
        return await get_state(request=request, user=user, session=session)

    guess_repo = FlagdleGuessRepository(session)
    country_repo = CountryRepository(session)

    all_matched_colors = set()
    for idx, g in enumerate(sync_data.guesses):
        guessed_country = None
        if g.country_id:
            guessed_country = await country_repo.get(g.country_id)
        if not guessed_country and g.guess:
            all_countries = await country_repo.get_all_countries()
            for c in all_countries:
                if c.name.lower() == g.guess.strip().lower():
                    guessed_country = c
                    break

        if not guessed_country:
            continue

        is_correct = target_country and (guessed_country.id == target_country.id)
        clues = evaluate_flag_clues(
            target_country_id=target_country.id if target_country else 0,
            guessed_country_id=guessed_country.id,
            all_matched_colors_so_far=all_matched_colors,
        )
        if clues["matched_colors"]:
            all_matched_colors.update(clues["matched_colors"])

        revealed_tile = UNMASK_ORDER[min(idx, 5)]

        guess_create = FlagdleGuessCreate(
            guess=guessed_country.name,
            country_id=guessed_country.id,
            day_id=day_flag.id,
            user_id=user.id,
            answer=is_correct,
            distance_km=clues["distance_km"],
            bearing_degrees=clues["bearing_degrees"],
            bearing_direction=clues["bearing_direction"],
            bearing_arrow=clues["bearing_arrow"],
            matched_colors=clues["matched_colors"],
            missed_colors=clues["missed_colors"],
            remaining_colors_count=clues["remaining_colors_count"],
            matched_symbols=clues["matched_symbols"],
            revealed_tile=revealed_tile,
            elapsed_seconds=g.elapsed_seconds,
        )
        await guess_repo.add_guess(guess_create)

    state.remaining_guesses = sync_data.state.remaining_guesses
    state.guesses_made = sync_data.state.guesses_made
    state.revealed_stage = sync_data.state.revealed_stage
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won

    if state.won:
        streak = (await state_repo.get_current_streak(user.id)) + 1
        elapsed = None
        for g in sync_data.guesses:
            if g.elapsed_seconds is not None:
                elapsed = g.elapsed_seconds
                break
        state.points = await state_repo.calc_points(state, elapsed_seconds=elapsed, streak=streak)

    await state_repo.update_state(state)
    return await get_state(request=request, user=user, session=session)
