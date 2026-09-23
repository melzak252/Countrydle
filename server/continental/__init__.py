from datetime import date, datetime
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, update
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
from game_logic import CONTINENTAL_CONFIG, GameRules, GameState
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
from users.utils import get_current_or_guest_user, get_current_user
from utils.geo import enhance_guess_with_hint
from utils.guest_session import create_guest_game_token, read_guest_game_token


router = APIRouter(prefix="/continental")

game_rules = GameRules(CONTINENTAL_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    """Convert DB state to logic GameState."""
    return GameState(
        questions_used=db_state.questions_asked,
        guesses_used=db_state.guesses_made,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won,
    )


@router.post("/{continent}/sync", response_model=ContinentalStateResponse)
async def sync_guest_data(
    continent: ContinentCode,
    sync_data: ContinentalSyncSchema,
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

    state = await state_repo.get_state(
        user,
        day,
        max_questions=CONTINENTAL_CONFIG.max_questions,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
    )

    # If user already has progress on server, ignore guest sync
    if state.questions_asked > 0 or state.guesses_made > 0:
        return await get_state(continent, user, session)

    # Claim questions belonging to this day that have no user assigned
    if sync_data.questions:
        question_repo = ContinentalQuestionRepository(session)
        await question_repo.claim_guest_questions(user.id, day.id, sync_data.questions)

    # Add guesses
    guess_repo = ContinentalGuessRepository(session)
    for g in sync_data.guesses:
        is_correct = False
        if g.country_id is not None:
            is_correct = (g.country_id == day.country_id)

        guess_create = ContinentalGuessCreate(
            guess=g.guess,
            country_id=g.country_id,
            day_id=day.id,
            user_id=user.id,
            answer=is_correct,
            elapsed_seconds=g.elapsed_seconds,
        )
        await guess_repo.add_guess(guess_create)

    state.remaining_questions = sync_data.state.remaining_questions
    state.remaining_guesses = sync_data.state.remaining_guesses
    state.questions_asked = sync_data.state.questions_asked
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won

    if state.won:
        user_points = await UserRepository(session).get_user_points(user.id)
        current_streak = ((user_points.streak if user_points else 0) + 1)
        elapsed = None
        for g in sync_data.guesses:
            if g.elapsed_seconds is not None:
                elapsed = g.elapsed_seconds
                break
        state.points = await state_repo.calc_points(
            state, elapsed_seconds=elapsed, streak=current_streak
        )

    if state.is_game_over:
        await UserRepository(session).update_points(user.id, state)

    await state_repo.update_state(state)
    return await get_state(continent, user, session)


@router.get(
    "/{continent}/state",
    response_model=Union[ContinentalStateResponse, ContinentalEndStateResponse],
)
async def get_state(
    continent: ContinentCode,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    target_country = await CountryRepository(session).get(day.country_id)

    if user is None:
        guest_state = ContinentalStateSchema(
            remaining_questions=CONTINENTAL_CONFIG.max_questions,
            remaining_guesses=CONTINENTAL_CONFIG.max_guesses,
            questions_asked=0,
            guesses_made=0,
            is_game_over=False,
            won=False,
            points=0,
        )
        return ContinentalStateResponse(
            user=None,
            date=str(day.date),
            state=guest_state,
            questions=[],
            guesses=[],
            country=None,
        )

    state_repo = ContinentalStateRepository(session)
    state = await state_repo.get_state(
        user,
        day,
        max_questions=CONTINENTAL_CONFIG.max_questions,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
    )

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
        questions=[ContinentalQuestionDisplay.model_validate(q) for q in questions_db],
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
    session: AsyncSession = Depends(get_db),
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    target_country = await CountryRepository(session).get(day.country_id)
    if not target_country:
        raise HTTPException(status_code=404, detail="Target country not found.")

    return CountryDisplay.model_validate(target_country)


@router.post(
    "/{continent}/question",
    response_model=Union[ContinentalQuestionDisplay, InvalidContinentalQuestionDisplay],
)
async def ask_question(
    continent: ContinentCode,
    question: ContinentalQuestionBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await _do_ask_question(continent, question, user, session)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {exc}") from exc


async def _do_ask_question(
    continent: ContinentCode,
    question: ContinentalQuestionBase,
    user: User | None,
    session: AsyncSession,
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    question_repo = ContinentalQuestionRepository(session)

    # Guest user flow (unauthenticated)
    if user is None:
        local_question_create, planned_question = await gutils.analyze_and_answer_locally(
            original_question=question.question,
            day_country=day,
            user=None,
            session=session,
        )
        if local_question_create is not None:
            new_quest = await question_repo.create_question(local_question_create)
            if not local_question_create.valid:
                return InvalidContinentalQuestionDisplay.model_validate(new_quest)
            return ContinentalQuestionDisplay.model_validate(new_quest)

        enh_question = gutils.question_enhanced_from_plan(question.question, planned_question)
        if not enh_question.valid:
            question_create = QuestionCreate(
                user_id=None,
                day_id=day.id,
                original_question=enh_question.original_question,
                valid=enh_question.valid,
                question=enh_question.question,
                answer=None,
                explanation=enh_question.explanation or "No explanation provided.",
                context=None,
            )
            new_quest = await question_repo.create_question(question_create)
            return InvalidContinentalQuestionDisplay.model_validate(new_quest)

        question_create, question_vector = await gutils.ask_question(
            question=enh_question,
            day_country=day,
            user=None,
            session=session,
        )
        new_quest = await question_repo.create_question(question_create)
        if question_vector:
            await add_question_to_qdrant(
                new_quest,
                question_vector,
                filter_key="country_id",
                filter_value=day.country_id,
                collection_name="countries_questions",
            )
        return ContinentalQuestionDisplay.model_validate(new_quest)

    # Authenticated user flow
    state_repo = ContinentalStateRepository(session)
    state = await state_repo.get_state(
        user,
        day,
        max_questions=CONTINENTAL_CONFIG.max_questions,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
    )

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_ask_question(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no more questions left or game is over!",
        )

    local_question_create, planned_question = await gutils.analyze_and_answer_locally(
        original_question=question.question,
        day_country=day,
        user=user,
        session=session,
    )
    if local_question_create is not None:
        new_quest = await question_repo.create_question(local_question_create)
        if not local_question_create.valid:
            return InvalidContinentalQuestionDisplay.model_validate(new_quest)

        new_game_state = game_rules.process_question(current_game_state)
        state.remaining_questions = CONTINENTAL_CONFIG.max_questions - new_game_state.questions_used
        state.questions_asked += 1
        await state_repo.update_state(state)
        return ContinentalQuestionDisplay.model_validate(new_quest)

    enh_question = gutils.question_enhanced_from_plan(question.question, planned_question)
    if not enh_question.valid:
        question_create = QuestionCreate(
            user_id=user.id,
            day_id=day.id,
            original_question=enh_question.original_question,
            valid=enh_question.valid,
            question=enh_question.question,
            answer=None,
            explanation=enh_question.explanation or "No explanation provided.",
            context=None,
        )
        new_quest = await question_repo.create_question(question_create)
        return InvalidContinentalQuestionDisplay.model_validate(new_quest)

    question_create, question_vector = await gutils.ask_question(
        question=enh_question,
        day_country=day,
        user=user,
        session=session,
    )
    new_quest = await question_repo.create_question(question_create)
    if question_vector:
        await add_question_to_qdrant(
            new_quest,
            question_vector,
            filter_key="country_id",
            filter_value=day.country_id,
            collection_name="countries_questions",
        )

    new_game_state = game_rules.process_question(current_game_state)
    state.remaining_questions = CONTINENTAL_CONFIG.max_questions - new_game_state.questions_used
    state.questions_asked += 1
    await state_repo.update_state(state)
    return ContinentalQuestionDisplay.model_validate(new_quest)


@router.post("/{continent}/guess", response_model=ContinentalGuessDisplay)
async def make_guess(
    continent: ContinentCode,
    guess: ContinentalGuessBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    # Rule 2: Whitelist enforcement
    candidate_name = guess.guess.strip()
    if not is_eligible_candidate(candidate_name, continent):
        mode_title = CONTINENT_TITLE_MAP.get(continent, continent.value.title() + "dle")
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
        cookie_name = f"guest_continental_{continent.value}"
        cookie = request.cookies.get(cookie_name)
        guest_state = read_guest_game_token(cookie, f"continental_{continent.value}", day.id)
        guesses_count = guest_state["guesses_count"] + 1
        won = is_correct
        is_game_over = is_correct or (guesses_count >= CONTINENTAL_CONFIG.max_guesses)
        token = create_guest_game_token(
            f"continental_{continent.value}", day.id, guesses_count, is_game_over, won
        )
        response.set_cookie(
            cookie_name, token, httponly=True, samesite="lax", max_age=86400 * 2
        )

        guess_create = ContinentalGuessCreate(
            guess=candidate_name,
            country_id=guess.country_id,
            day_id=day.id,
            user_id=None,
            answer=is_correct,
            elapsed_seconds=guess.elapsed_seconds,
        )
        saved_guess = await ContinentalGuessRepository(session).add_guess(guess_create)

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
    state = await state_repo.get_state(
        user,
        day,
        max_questions=CONTINENTAL_CONFIG.max_questions,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
    )

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no more guesses left or game is over!",
        )

    guess_num = state.guesses_made + 1

    guess_create = ContinentalGuessCreate(
        guess=guess.guess,
        country_id=guess.country_id,
        day_id=day.id,
        user_id=user.id,
        answer=is_correct,
        elapsed_seconds=guess.elapsed_seconds,
    )
    new_guess = await ContinentalGuessRepository(session).add_guess(guess_create)

    state = await state_repo.guess_made(
        state, new_guess, elapsed_seconds=guess.elapsed_seconds, continent=continent
    )

    if state.is_game_over:
        await UserRepository(session).update_points(user.id, state)

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
