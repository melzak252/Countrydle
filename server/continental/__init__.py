from db.models.continental import ContinentalState
from db.repositories.question_accounting import (
    consume_question, is_answered, unresolved_question, check_question_available,
    get_daily_state, require_guess_available,
)
from datetime import datetime
import os
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import countrydle.utils as gutils
from continental.utils import (
    CONTINENT_TITLE_MAP,
    format_continental_guesses,
    get_continent_countries,
    is_eligible_candidate,
)
from db import get_db
from db.models import Country, User
from db.models.continental import (
    ContinentCode,
    ContinentalDay,
    ContinentalGuess,
    ContinentalQuestion,
)
from db.repositories.continental import (
    ContinentalDayRepository,
    ContinentalGuessRepository,
    ContinentalQuestionRepository,
    ContinentalStateRepository,
)
from db.repositories.country import CountryRepository
from db.repositories.user import UserRepository
from game_logic import CONTINENTAL_CONFIG
from qdrant.utils import add_question_to_qdrant
from schemas.continental import (
    ContinentalEndStateResponse,
    ContinentalGuessBase,
    ContinentalGuessCreate,
    ContinentalGuessDisplay,
    ContinentalQuestionBase,
    ContinentalQuestionDisplay,
    ContinentalStateResponse,
    ContinentalStateSchema,
    ContinentalSyncSchema,
    DayContinentalDisplay,
    InvalidContinentalQuestionDisplay,
)
from schemas.country import CountryDisplay
from schemas.countrydle import LeaderboardEntry, QuestionCreate
from schemas.user import UserDisplay
from users.utils import get_admin_user, get_current_or_guest_user, get_current_user
from utils.geo import enhance_guess_with_hint
from utils.guest_session import (
    create_guest_game_token, record_guest_action, get_guest_identity, guest_game_over,
    get_guest_progress, claim_guest_history, check_guest_question_available,
)
from utils.question_rate_limit import enforce_question_attempt_limit



router = APIRouter(prefix="/continental")



@router.get("/admin/questions")
async def get_admin_questions(
    continent: ContinentCode | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    repository = ContinentalQuestionRepository(session)
    if limit is None:
        return await repository.get_all_questions(continent=continent)
    items = await repository.get_all_questions(limit=limit, offset=offset, continent=continent)
    total = await repository.count_questions(continent=continent)
    return {"items": items, "total": total, "limit": limit, "offset": offset}

@router.post("/{continent}/sync", response_model=ContinentalStateResponse)
async def sync_guest_data(
    continent: ContinentCode,
    sync_data: ContinentalSyncSchema,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    day_repo = ContinentalDayRepository(session)
    state_repo = ContinentalStateRepository(session)

    day = await day_repo.get_day_by_date(continent, game_date)
    if not day:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    try:
        state = await get_daily_state(
            session, ContinentalState, user.id, day.id,
            CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
        )
        imported = await claim_guest_history(
            session, request, state, f"continental:{continent.value}",
            ContinentalGuess, ContinentalQuestion,
            CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
            validate_original_guess=lambda country_id, name: CountryRepository(session).validate_guess(
                country_id, name, continent.value,
            ),
        )
        if imported and state.won:
            guesses = await ContinentalGuessRepository(session).get_user_guesses(user.id, day.id)
            streak = (await state_repo.get_current_streak(user.id, day.date, continent)) + 1
            elapsed = guesses[-1].elapsed_seconds if guesses else None
            state.points = await state_repo.calc_points(state, elapsed_seconds=elapsed, streak=streak)
        if imported and state.is_game_over:
            await UserRepository(session).update_points(user.id, state, commit=False)
        await state_repo.update_state(state, commit=False)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return await get_state(continent=continent, user=user, session=session, request=request)


@router.get(
    "/{continent}/state",
    response_model=Union[ContinentalStateResponse, ContinentalEndStateResponse],
)
async def get_state(
    continent: ContinentCode,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    target_country = await CountryRepository(session).get(day.country_id)

    if user is None:
        participation, guesses, questions = await get_guest_progress(
            session, request, response, f"continental:{continent.value}", day.id,
            ContinentalGuess, ContinentalQuestion,
        )
        guesses_made = participation.guesses_made if participation else 0
        questions_asked = participation.questions_asked if participation else 0
        terminal = guest_game_over(participation, CONTINENTAL_CONFIG.max_guesses)
        guest_state = ContinentalStateSchema(
            remaining_questions=max(0, CONTINENTAL_CONFIG.max_questions - questions_asked),
            remaining_guesses=max(0, CONTINENTAL_CONFIG.max_guesses - guesses_made),
            questions_asked=questions_asked, guesses_made=guesses_made,
            is_game_over=terminal, won=bool(participation and participation.won), points=0,
        )
        return ContinentalStateResponse(
            user=None, date=str(day.date), state=guest_state,
            questions=[ContinentalQuestionDisplay.model_validate(q, context={"terminal": terminal}) for q in questions],
            guesses=format_continental_guesses(
                guesses, day.country_id, target_country.name if target_country else None,
                max_guesses=CONTINENTAL_CONFIG.max_guesses,
            ),
            country=CountryDisplay.model_validate(target_country) if terminal and target_country else None,
        )

    state = await get_daily_state(
        session, ContinentalState, user.id, day.id,
        CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
    )
    await session.commit()

    questions_db = await ContinentalQuestionRepository(session).get_user_questions(
        user.id, day.id
    )
    guesses_db = await ContinentalGuessRepository(session).get_user_guesses(user.id, day.id)

    formatted_guesses = format_continental_guesses(
        guesses_db,
        day.country_id,
        target_country.name if target_country else None,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
    )

    country_display = (
        CountryDisplay.model_validate(target_country)
        if state.is_game_over and target_country
        else None
    )

    return ContinentalStateResponse(
        user=UserDisplay.model_validate(user),
        date=str(day.date),
        state=ContinentalStateSchema.model_validate(state),
        questions=[ContinentalQuestionDisplay.model_validate(q, context={"terminal": state.is_game_over}) for q in questions_db],
        guesses=formatted_guesses,
        country=country_display,
    )


@router.get("/{continent}/countries", response_model=List[CountryDisplay])
async def get_countries(
    continent: ContinentCode,
    session: AsyncSession = Depends(get_db),
):
    countries = await get_continent_countries(continent, session)
    return [CountryDisplay.model_validate(c) for c in countries]


@router.get("/{continent}/reveal", response_model=CountryDisplay)
async def reveal_country(
    continent: ContinentCode,
    request: Request,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    if user is not None:
        state = await get_daily_state(
            session, ContinentalState, user.id, day.id,
            CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
        )
        terminal = state.is_game_over
    else:
        participation, _, _ = await get_guest_progress(
            session, request, None, f"continental:{continent.value}", day.id,
            ContinentalGuess, ContinentalQuestion,
        )
        terminal = guest_game_over(participation, CONTINENTAL_CONFIG.max_guesses)
    if not terminal:
        raise HTTPException(status_code=400, detail="Cannot reveal country before game is over.")

    target_country = await CountryRepository(session).get(day.country_id)
    if not target_country:
        raise HTTPException(status_code=404, detail="Target country not found.")

    return CountryDisplay.model_validate(target_country)


@router.post(
    "/{continent}/question",
    response_model=Union[ContinentalQuestionDisplay, InvalidContinentalQuestionDisplay],
    dependencies=[Depends(enforce_question_attempt_limit)],
)
async def ask_question(
    continent: ContinentCode,
    question: ContinentalQuestionBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    user_id = user.id if user else None
    try:
        return await _do_ask_question(continent, question, user, session, request, response)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        import logging
        logging.getLogger("countrydle").exception("Could not answer continental question")
        return InvalidContinentalQuestionDisplay(
            id=0, original_question=question.question, valid=False, answer=None,
            user_id=user_id, day_id=0, asked_at=datetime.now(),
            explanation="Could not verify this question right now. Your turn was not deducted.",
        )


async def _do_ask_question(
    continent: ContinentCode,
    question: ContinentalQuestionBase,
    user: User | None,
    session: AsyncSession,
    request: Request,
    response: Response,
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    if user is not None:
        await check_question_available(
            session, ContinentalState, user.id, day.id, CONTINENTAL_CONFIG.max_questions,
        )
    else:
        await check_guest_question_available(
            session, request, response, f"continental:{continent.value}", day.id,
            CONTINENTAL_CONFIG.max_questions, max_guesses=CONTINENTAL_CONFIG.max_guesses,
        )
    await session.commit()

    question_create, planned_question = await gutils.analyze_and_answer_locally(
        original_question=question.question, day_country=day, user=user, session=session,
    )
    question_vector = None
    if question_create is None:
        enhanced = gutils.question_enhanced_from_plan(question.question, planned_question)
        if not enhanced.valid:
            question_create = QuestionCreate(
                user_id=user.id if user else None, day_id=day.id,
                original_question=question.question, question=enhanced.question,
                valid=False, answer=None, explanation=enhanced.explanation, context=None,
            )
        else:
            question_create, question_vector = await gutils.ask_question(
                question=enhanced, day_country=day, user=user, session=session,
            )

    if not is_answered(question_create):
        return unresolved_question(question_create, InvalidContinentalQuestionDisplay)
    question_create.user_id = user.id if user else None
    question_create.day_id = day.id
    if user is None:
        await record_guest_action(
            session, request, response, f"continental:{continent.value}", day.id,
            question=True, max_questions=CONTINENTAL_CONFIG.max_questions,
            max_guesses=CONTINENTAL_CONFIG.max_guesses,
        )
    else:
        await consume_question(
            session, ContinentalState, user.id, day.id,
            CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
        )
    new_question = await ContinentalQuestionRepository(session).create_question(
        question_create,
        guest_id=get_guest_identity(request, response) if user is None else None,
    )
    result = ContinentalQuestionDisplay.model_validate(new_question)
    await session.commit()
    if question_vector:
        # Indexing is auxiliary: an already committed answer remains successful.
        try:
            await add_question_to_qdrant(
                new_question, question_vector, filter_key="country_id",
                filter_value=day.country_id, collection_name="countries_questions",
            )
        except Exception:
            import logging
            logging.getLogger("countrydle").exception("Could not index accepted continental question")
    return result


@router.post("/{continent}/guess", response_model=ContinentalGuessDisplay)
async def make_guess(
    continent: ContinentCode,
    guess: ContinentalGuessBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await _do_make_guess(continent, guess, request, response, user, session)
    except Exception:
        await session.rollback()
        raise


async def _do_make_guess(continent, guess, request, response, user, session):
    await CountryRepository(session).validate_guess(guess.country_id, guess.guess, continent.value)
    # Rule 2: Whitelist enforcement
    candidate_name = guess.guess.strip()
    if not is_eligible_candidate(candidate_name, continent):
        mode_title = CONTINENT_TITLE_MAP.get(continent, continent.value.title() + "dle")
        if candidate_name.endswith("?") or any(candidate_name.lower().startswith(w) for w in ("is ", "czy ", "does ", "what ", "which ", "are ", "can ", "has ")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{guess.guess}' looks like a question. Please use the Question input to ask questions, or select an eligible country in {mode_title} to make a guess.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate '{guess.guess}' is not an eligible country in {mode_title}.",
        )

    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    target_country = await CountryRepository(session).get(day.country_id)

    # Determine if guess is correct
    is_correct = False
    if guess.country_id is not None and guess.country_id > 0:
        is_correct = (guess.country_id == day.country_id)
    if not is_correct and guess.guess and target_country:
        guessed_clean = guess.guess.strip().lower()
        target_clean = target_country.name.strip().lower()
        official_clean = (target_country.official_name or "").strip().lower()
        is_correct = (guessed_clean == target_clean) or (guessed_clean == official_clean)
        if is_correct:
            guess.country_id = day.country_id

    # Guest player
    if user is None:
        participation = await record_guest_action(
            session, request, response, f"continental:{continent.value}", day.id,
            max_guesses=CONTINENTAL_CONFIG.max_guesses, won=is_correct,
        )
        guesses_count = participation.guesses_made
        won = participation.won
        is_game_over = guest_game_over(participation, CONTINENTAL_CONFIG.max_guesses)

        guess_create = ContinentalGuessCreate(
            guess=candidate_name,
            country_id=guess.country_id,
            day_id=day.id,
            user_id=None,
            answer=is_correct,
            elapsed_seconds=guess.elapsed_seconds,
        )
        saved_guess = await ContinentalGuessRepository(session).add_guess(
            guess_create, commit=False, guest_id=get_guest_identity(request, response),
        )
        await session.commit()
        token = create_guest_game_token(
            f"continental_{continent.value}", day.id, participation.guesses_made,
            guest_game_over(participation, CONTINENTAL_CONFIG.max_guesses), participation.won,
        )
        response.set_cookie(
            f"guest_continental_{continent.value}", token, httponly=True, samesite="lax", max_age=86400 * 2,
            secure=request.url.scheme == "https" or os.getenv("FRIEND_COOKIE_SECURE", "").strip().lower() in {"true", "1", "yes"},
        )

        hint = enhance_guess_with_hint(
            mode="countrydle",
            guess_record=saved_guess,
            guess_number=guesses_count,
            max_guesses=CONTINENTAL_CONFIG.max_guesses,
            target_id=day.country_id,
            target_name=target_country.name if target_country else None,
        )

        return ContinentalGuessDisplay(
            id=saved_guess.id,
            guess=saved_guess.guess,
            country_id=saved_guess.country_id,
            answer=saved_guess.answer,
            guessed_at=saved_guess.guessed_at,
            elapsed_seconds=saved_guess.elapsed_seconds,
            is_game_over=is_game_over,
            won=won,
            points=0,
            **hint,
        )

    # Authenticated player
    state_repo = ContinentalStateRepository(session)
    state = await get_daily_state(
        session, ContinentalState, user.id, day.id,
        CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
    )
    require_guess_available(state, CONTINENTAL_CONFIG.max_guesses)

    guess_num = state.guesses_made + 1

    guess_create = ContinentalGuessCreate(
        guess=guess.guess,
        country_id=guess.country_id,
        day_id=day.id,
        user_id=user.id,
        answer=is_correct,
        elapsed_seconds=guess.elapsed_seconds,
    )
    new_guess = await ContinentalGuessRepository(session).add_guess(guess_create, commit=False)

    state = await state_repo.guess_made(
        state, new_guess, elapsed_seconds=guess.elapsed_seconds, continent=continent,
        puzzle_date=day.date, commit=False,
    )

    if state.is_game_over:
        await UserRepository(session).update_points(user.id, state, commit=False)
    await session.commit()

    hint = enhance_guess_with_hint(
        mode="countrydle",
        guess_record=new_guess,
        guess_number=guess_num,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
        target_id=day.country_id,
        target_name=target_country.name if target_country else None,
    )

    return ContinentalGuessDisplay(
        id=new_guess.id,
        guess=new_guess.guess,
        country_id=new_guess.country_id,
        answer=is_correct,
        guessed_at=new_guess.guessed_at or datetime.now(),
        elapsed_seconds=new_guess.elapsed_seconds,
        is_game_over=state.is_game_over,
        won=state.won,
        points=state.points,
        distance_km=hint.get("distance_km"),
        bearing_degrees=hint.get("bearing_degrees"),
        bearing_direction=hint.get("bearing_direction"),
        bearing_arrow=hint.get("bearing_arrow"),
    )

@router.get("/{continent}/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    continent: ContinentCode,
    type: str = Query("monthly", pattern="^(monthly|average)$"),
    session: AsyncSession = Depends(get_db),
):
    state_repo = ContinentalStateRepository(session)
    return await state_repo.get_leaderboard(continent, type=type)


@router.get("/{continent}/history", response_model=List[DayContinentalDisplay])
async def get_history(
    continent: ContinentCode,
    session: AsyncSession = Depends(get_db),
):
    day_repo = ContinentalDayRepository(session)
    days = await day_repo.get_history(continent)
    return [DayContinentalDisplay.model_validate(d) for d in days]
