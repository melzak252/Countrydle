"""Flagdle daily gameplay endpoints: state, guess, reveal, end/state, flag-asset, history, leaderboard."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import Response as RawResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import User
from db.models.flagdle import FlagdleQuestion
from db.repositories.country import CountryRepository
from db.repositories.flagdle import (
    FlagdleDayRepository,
    FlagdleGuessRepository,
    FlagdleQuestionRepository,
    FlagdleStateRepository,
)
from flagdle.shades import _get_or_fetch_flag_svg, flagdle_attr
from flagdle.utils import (
    UNMASK_ORDER,
    evaluate_flag_clues,
    generate_asset_token,
    get_country_iso2,
    normalize_svg_for_grid,
    verify_asset_token,
)
from game_logic import FLAGDLE_CONFIG
from schemas.country import CountryDisplay
from schemas.countrydle import LeaderboardEntry
from schemas.flagdle import (
    DayFlagdleDisplay,
    FlagdleCountryDisplay,
    FlagdleGuessBase,
    FlagdleGuessCreate,
    FlagdleGuessDisplay,
    FlagdleQuestionDisplay,
    FlagdleStateResponse,
    FlagdleStateSchema,
)
from users.utils import get_current_or_guest_user
from utils.guest_session import (
    create_guest_game_token,
    get_guest_identity,
    get_guest_question_history,
    read_guest_game_token,
    record_guest_action,
)

router = APIRouter()


def _to_guess_display(g, fallback_now: Optional[datetime] = None) -> FlagdleGuessDisplay:
    return FlagdleGuessDisplay(
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
        guessed_at=g.guessed_at or fallback_now or datetime.now(),
    )


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    type: str = Query("monthly", pattern="^(monthly|average)$"),
    session: AsyncSession = Depends(get_db),
):
    return await FlagdleStateRepository(session).get_leaderboard(type)


@router.get("/history", response_model=List[DayFlagdleDisplay])
async def get_history(session: AsyncSession = Depends(get_db)):
    days = await FlagdleDayRepository(session).get_history()
    return [DayFlagdleDisplay.model_validate(d) for d in days]


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
    fit: Optional[str] = Query(None),
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
    fetch_svg = flagdle_attr("_get_or_fetch_flag_svg", _get_or_fetch_flag_svg)
    svg_bytes = await asyncio.to_thread(fetch_svg, iso2)
    if fit == "grid":
        svg_bytes = normalize_svg_for_grid(svg_bytes, iso2)
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
    response: Response = None,
):
    """Fetches or initializes the daily Flagdle state (anti-cheat protected)."""
    day_repo = FlagdleDayRepository(session)
    today_flag = await day_repo.get_today_flag()
    if not today_flag:
        today_flag = await day_repo.generate_new_day_flag()

    target_country = today_flag.country
    if not target_country:
        target_country = await CountryRepository(session).get(today_flag.country_id)

    today_str = (
        today_flag.date.strftime("%Y-%m-%d")
        if today_flag.date
        else date.today().strftime("%Y-%m-%d")
    )
    asset_token = generate_asset_token(today_flag.id)
    flag_asset_url = f"/flagdle/flag-asset?token={asset_token}"

    if user:
        state_repo = FlagdleStateRepository(session)
        state = await state_repo.get_state(user, today_flag)
        if not state:
            state = await state_repo.create_state(
                user, today_flag, max_guesses=FLAGDLE_CONFIG.max_guesses
            )

        guess_repo = FlagdleGuessRepository(session)
        db_guesses = await guess_repo.get_user_day_guesses(user, today_flag.id)
        questions = await FlagdleQuestionRepository(session).get_user_day_questions(
            user.id, today_flag.id
        )

        guesses_display = [_to_guess_display(g) for g in db_guesses]
        revealed_country = (
            CountryDisplay.model_validate(target_country)
            if state.is_game_over and target_country
            else None
        )

        return FlagdleStateResponse(
            user=user,
            date=today_str,
            state=FlagdleStateSchema.model_validate(state),
            guesses=guesses_display,
            questions=[
                FlagdleQuestionDisplay.model_validate(q, context={"terminal": state.is_game_over})
                for q in questions
            ],
            flag_asset_url=flag_asset_url,
            country=revealed_country,
        )

    # Guest session
    if response is not None:
        get_guest_identity(request, response)
    cookie = request.cookies.get("guest_flagdle")
    guest_state = read_guest_game_token(cookie, "flagdle", today_flag.id)

    guesses_made = guest_state["guesses_count"]
    is_won = guest_state["won"]
    guest_history_fn = flagdle_attr("get_guest_question_history", get_guest_question_history)
    participation, questions = await guest_history_fn(
        session, request, "flagdle", today_flag.id, FlagdleQuestion
    )
    terminal = bool(
        participation and (participation.won or participation.guesses_made >= FLAGDLE_CONFIG.max_guesses)
    )
    is_game_over = terminal
    if participation is not None:
        guesses_made = participation.guesses_made
        is_won = participation.won
    remaining_guesses = max(0, FLAGDLE_CONFIG.max_guesses - guesses_made)
    revealed_stage = 12 if is_game_over else min(12, guesses_made + 1)

    state_schema = FlagdleStateSchema(
        remaining_guesses=remaining_guesses,
        guesses_made=guesses_made,
        revealed_stage=revealed_stage,
        is_game_over=is_game_over,
        won=is_won,
        points=0,
    )

    revealed_country = (
        CountryDisplay.model_validate(target_country)
        if is_game_over and target_country
        else None
    )

    return FlagdleStateResponse(
        user=None,
        date=today_str,
        state=state_schema,
        guesses=[],
        questions=[
            FlagdleQuestionDisplay.model_validate(q, context={"terminal": terminal})
            for q in questions
        ],
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
    await CountryRepository(session).validate_guess(guess_in.country_id, guess_in.guess)
    day_repo = FlagdleDayRepository(session)
    today_flag = await day_repo.get_today_flag()
    if not today_flag:
        today_flag = await day_repo.generate_new_day_flag()

    target_country = today_flag.country
    if not target_country:
        target_country = await CountryRepository(session).get(today_flag.country_id)

    if not target_country:
        raise HTTPException(status_code=500, detail="Target country not configured.")

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

    if user:
        state_repo = FlagdleStateRepository(session)
        state = await state_repo.get_state(user, today_flag)
        if not state:
            state = await state_repo.create_state(
                user, today_flag, max_guesses=FLAGDLE_CONFIG.max_guesses
            )
        if state.is_game_over or state.remaining_guesses <= 0:
            raise HTTPException(status_code=400, detail="Game is already over.")
        current_guess_idx = state.guesses_made
        existing_guesses = await FlagdleGuessRepository(session).get_user_day_guesses(
            user, today_flag.id
        )
    else:
        cookie = request.cookies.get("guest_flagdle")
        guest_state = read_guest_game_token(cookie, "flagdle", today_flag.id)
        if guest_state["is_game_over"] or guest_state["guesses_count"] >= FLAGDLE_CONFIG.max_guesses:
            raise HTTPException(status_code=400, detail="Game is already over.")
        current_guess_idx = guest_state["guesses_count"]
        existing_guesses = []

    all_matched_colors = set()
    for eg in existing_guesses:
        if eg.matched_colors:
            all_matched_colors.update(eg.matched_colors)

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
    new_stage = 12 if is_game_over else min(12, new_guesses_made + 1)
    revealed_tile = UNMASK_ORDER[min(current_guess_idx, 11)]
    now = datetime.now()

    # Progressive distance & direction disclosure:
    # Guesses 1-2: visual cards only; 3-4: distance only; 5-12: distance + direction
    effective_dist: Optional[int] = 0 if is_correct else (clues["distance_km"] if new_guesses_made >= 3 else None)
    effective_bearing_deg: Optional[int] = None if is_correct or new_guesses_made < 5 else clues["bearing_degrees"]
    effective_compass: Optional[str] = None if is_correct or new_guesses_made < 5 else clues["bearing_direction"]
    effective_arrow: Optional[str] = None if is_correct or new_guesses_made < 5 else clues["bearing_arrow"]

    guess_create = FlagdleGuessCreate(
        guess=guessed_country.name,
        country_id=guessed_country.id,
        day_id=today_flag.id,
        user_id=user.id if user else None,
        answer=is_correct,
        distance_km=effective_dist,
        bearing_degrees=effective_bearing_deg,
        bearing_direction=effective_compass,
        bearing_arrow=effective_arrow,
        matched_colors=clues["matched_colors"],
        missed_colors=clues["missed_colors"],
        remaining_colors_count=clues["remaining_colors_count"],
        matched_symbols=clues["matched_symbols"],
        revealed_tile=revealed_tile,
        elapsed_seconds=guess_in.elapsed_seconds,
    )

    if user:
        saved_guess = await FlagdleGuessRepository(session).add_guess(guess_create)
        state.guesses_made = new_guesses_made
        state.remaining_guesses = new_remaining
        state.revealed_stage = new_stage
        state.is_game_over = is_game_over
        state.won = won
        if won:
            streak = (await state_repo.get_current_streak(user.id, today_flag.date)) + 1
            state.points = await state_repo.calc_points(
                state, elapsed_seconds=guess_in.elapsed_seconds, streak=streak
            )
        await state_repo.update_state(state)
        return _to_guess_display(saved_guess, now)

    token = create_guest_game_token("flagdle", today_flag.id, new_guesses_made, is_game_over, won)
    response.set_cookie("guest_flagdle", token, httponly=True, samesite="lax", max_age=86400 * 2)
    record_action_fn = flagdle_attr("record_guest_action", record_guest_action)
    await record_action_fn(session, request, response, "flagdle", today_flag.id, won=is_correct)
    saved_guess = await FlagdleGuessRepository(session).add_guess(guess_create)
    return _to_guess_display(saved_guess, now)


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
