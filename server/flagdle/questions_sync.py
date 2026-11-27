"""Flagdle question answering and guest-to-account sync endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import analyze_question_for_local_plan
from db import get_db
from db.models import User
from db.models.flagdle import FlagdleQuestion, FlagdleState
from db.repositories.country import CountryRepository
from db.repositories.flagdle import (
    FlagdleDayRepository,
    FlagdleGuessRepository,
    FlagdleQuestionRepository,
    FlagdleStateRepository,
)
from db.repositories.question_accounting import consume_question, lock_question_state
from flagdle.gameplay import get_state
from flagdle.shades import flagdle_attr
from flagdle.utils import UNMASK_ORDER, evaluate_flag_clues
from game_logic import FLAGDLE_CONFIG, is_valid_synced_game_state
from schemas.countrydle import InvalidQuestionDisplay, QuestionBase, QuestionCreate
from schemas.flagdle import (
    FlagdleGuessCreate,
    FlagdleQuestionDisplay,
    FlagdleStateResponse,
    FlagdleSyncSchema,
)
from users.utils import get_current_or_guest_user, get_current_user
from utils.explanation_sanitizer import sanitize_explanation_for_player
from utils.guest_session import (
    get_guest_identity,
    get_guest_question_history,
    link_guest_participation,
    record_guest_action,
)
from utils.question_rate_limit import enforce_question_attempt_limit

logger = logging.getLogger("countrydle.flagdle")

router = APIRouter()


@router.post(
    "/question",
    response_model=Union[FlagdleQuestionDisplay, InvalidQuestionDisplay],
    dependencies=[Depends(enforce_question_attempt_limit)],
)
async def ask_flag_question(
    question: QuestionBase,
    request: Request,
    response: Response,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Allows unlimited verified flag questions without counting unresolved attempts."""
    user_id = user.id if user else None
    day_id = 0
    now = datetime.now()
    try:
        day_repo = FlagdleDayRepository(session)
        today_flag = await day_repo.get_today_flag()
        if not today_flag:
            today_flag = await day_repo.generate_new_day_flag()
        day_id = today_flag.id
        target_country = today_flag.country
        if not target_country:
            target_country = await CountryRepository(session).get(today_flag.country_id)

        planner_fn = flagdle_attr("analyze_question_for_local_plan", analyze_question_for_local_plan)
        executor_fn = flagdle_attr("execute_local_plan", execute_local_plan)

        plan = await asyncio.to_thread(planner_fn, question.question)
        answer = None
        explanation = plan.explanation or "Please ask a valid yes/no question about the flag or country."
        if plan.valid:
            if plan.plan and target_country:
                answer = await asyncio.to_thread(
                    executor_fn,
                    plan.plan,
                    target_country.name,
                    plan.improved_question or question.question,
                )
            explanation = (
                "Could not verify this question with local flag facts. "
                "Ask about flag colors, stripes, symbols, or country geography."
            )
        if answer is None or type(answer.answer) is not bool:
            return InvalidQuestionDisplay(
                id=0,
                original_question=question.question,
                valid=False,
                answer=None,
                user_id=user_id,
                day_id=day_id,
                asked_at=now,
                explanation=explanation,
            )

        question_create = QuestionCreate(
            original_question=question.question,
            question=answer.question,
            valid=True,
            answer=answer.answer,
            user_id=user_id,
            day_id=day_id,
            guest_id=get_guest_identity(request, response) if user is None else None,
            explanation=sanitize_explanation_for_player(answer.explanation),
            context=f"flag_kb:{answer.relation}",
            fact_provenance=answer.fact_provenance,
        )
        if user is None:
            record_action_fn = flagdle_attr("record_guest_action", record_guest_action)
            guest_history_fn = flagdle_attr("get_guest_question_history", get_guest_question_history)
            await record_action_fn(session, request, response, "flagdle", day_id, question=True)
            participation, _ = await guest_history_fn(
                session, request, "flagdle", day_id, FlagdleQuestion
            )
            terminal = bool(
                participation
                and (participation.won or participation.guesses_made >= FLAGDLE_CONFIG.max_guesses)
            )
        else:
            state = await consume_question(
                session, FlagdleState, user_id, day_id, None, FLAGDLE_CONFIG.max_guesses
            )
            terminal = state.is_game_over
        saved_question = await FlagdleQuestionRepository(session).create_question(question_create)
        result = FlagdleQuestionDisplay.model_validate(saved_question, context={"terminal": terminal})
        await session.commit()
        return result
    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        logger.exception("Could not answer flag question")
        return InvalidQuestionDisplay(
            id=0,
            original_question=question.question,
            valid=False,
            answer=None,
            user_id=user_id,
            day_id=day_id,
            asked_at=now,
            explanation="Could not verify this question right now. Your turn was not deducted.",
        )


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
        state = await state_repo.create_state(
            user, day_flag, max_guesses=FLAGDLE_CONFIG.max_guesses
        )

    state = await lock_question_state(session, FlagdleState, user.id, day_flag.id) or state
    # Server state takes strict precedence if user already played on server
    link_guest_fn = flagdle_attr("link_guest_participation", link_guest_participation)
    if state.guesses_made > 0:
        linked = await link_guest_fn(session, request, "flagdle", day_flag.id, user.id)
        if linked is not None:
            state.questions_asked = max(state.questions_asked, linked)
            await state_repo.update_state(state)
        return await get_state(request=request, user=user, session=session)

    correct_guesses = [
        (
            guess.country_id == target_country.id
            if guess.country_id is not None
            else bool(
                target_country and guess.guess.strip().casefold() == target_country.name.casefold()
            )
        )
        for guess in sync_data.guesses
    ]
    sync_state = getattr(sync_data, "state", None)
    if sync_state is not None and not is_valid_synced_game_state(
        FLAGDLE_CONFIG,
        guesses_made=sync_state.guesses_made,
        remaining_guesses=sync_state.remaining_guesses,
        is_game_over=sync_state.is_game_over,
        won=sync_state.won,
        correct_guesses=correct_guesses,
    ):
        raise HTTPException(
            status_code=400, detail="Guest game state does not match its saved progress."
        )

    for guess in sync_data.guesses:
        await CountryRepository(session).validate_guess(guess.country_id, guess.guess)

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
            target_country_name=target_country.name if target_country else None,
            guessed_country_name=guessed_country.name,
            all_matched_colors_so_far=all_matched_colors,
        )
        if clues["matched_colors"]:
            all_matched_colors.update(clues["matched_colors"])

        revealed_tile = UNMASK_ORDER[min(idx, 11)]

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
        await guess_repo.add_guess(guess_create, commit=False)

    state.remaining_guesses = sync_data.state.remaining_guesses
    state.guesses_made = sync_data.state.guesses_made
    state.revealed_stage = sync_data.state.revealed_stage
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won

    if state.won:
        streak = (await state_repo.get_current_streak(user.id, day_flag.date)) + 1
        elapsed = sync_data.guesses[-1].elapsed_seconds if sync_data.guesses else None
        state.points = await state_repo.calc_points(state, elapsed_seconds=elapsed, streak=streak)

    linked_questions = await link_guest_fn(
        session, request, "flagdle", day_flag.id, user.id
    )
    if linked_questions is not None:
        state.questions_asked = max(state.questions_asked, linked_questions)
    await state_repo.update_state(state)
    return await get_state(request=request, user=user, session=session)
