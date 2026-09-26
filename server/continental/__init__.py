from db.models.continental import ContinentalState
from db.repositories.question_accounting import (
    consume_question, is_answered, unresolved_question, check_question_available,
    lock_question_state, claim_guest_questions,
)
from datetime import date, datetime
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
from game_logic import CONTINENTAL_CONFIG, GameRules, GameState, is_valid_synced_game_state
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
from utils.guest_session import (
    create_guest_game_token, read_guest_game_token, record_guest_action, link_guest_participation,
)


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

    state = await state_repo.get_state(
        user,
        day,
        max_questions=CONTINENTAL_CONFIG.max_questions,
        max_guesses=CONTINENTAL_CONFIG.max_guesses,
    )
    state = await lock_question_state(session, ContinentalState, user.id, day.id) or state

    # If user already has progress on server, ignore guest sync
    if state.questions_asked > 0 or state.guesses_made > 0:
        linked = await link_guest_participation(session, request, f"continental:{continent.value}", day.id, user.id)
        if linked is not None:
            await session.commit()
        return await get_state(continent, user, session)

    sync_state = getattr(sync_data, "state", None)
    if sync_state is not None and not is_valid_synced_game_state(
        CONTINENTAL_CONFIG,
        guesses_made=sync_state.guesses_made,
        remaining_guesses=sync_state.remaining_guesses,
        is_game_over=sync_state.is_game_over,
        won=sync_state.won,
        correct_guesses=[
            guess.country_id == day.country_id for guess in sync_data.guesses
        ],
        questions_asked=sync_state.questions_asked,
        remaining_questions=sync_state.remaining_questions,
        synced_questions=len(sync_data.questions),
    ):
        raise HTTPException(status_code=400, detail="Guest game state does not match its saved progress.")

    country_repo = CountryRepository(session)
    for guess in sync_data.guesses:
        await country_repo.validate_guess(guess.country_id, guess.guess, continent.value)
        if not is_eligible_candidate(guess.guess, continent):
            raise HTTPException(status_code=400, detail="Country is not eligible for this game.")

    await claim_guest_questions(
        session, ContinentalQuestion, state, sync_data.questions, CONTINENTAL_CONFIG.max_questions,
    )

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
        await guess_repo.add_guess(guess_create, commit=False)

    state.remaining_guesses = sync_data.state.remaining_guesses
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won

    if state.won:
        current_streak = (await state_repo.get_current_streak(user.id, day.date, continent)) + 1
        elapsed = sync_data.guesses[-1].elapsed_seconds if sync_data.guesses else None
        state.points = await state_repo.calc_points(
            state, elapsed_seconds=elapsed, streak=current_streak
        )

    if state.is_game_over:
        await UserRepository(session).update_points(user.id, state)

    if state.questions_asked > 0 or state.guesses_made > 0:
        await link_guest_participation(session, request, f"continental:{continent.value}", day.id, user.id)
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
    request: Request = None,
    response: Response = None,
):
    day_repo = ContinentalDayRepository(session)
    day = await day_repo.get_today_day(continent)
    if not day:
        day = await day_repo.generate_new_day(continent)

    target_country = await CountryRepository(session).get(day.country_id)

    if user is None:
        if request is not None and response is not None:
            from utils.guest_session import get_guest_identity
            get_guest_identity(request, response)
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
        )
    else:
        await consume_question(
            session, ContinentalState, user.id, day.id,
            CONTINENTAL_CONFIG.max_questions, CONTINENTAL_CONFIG.max_guesses,
        )
    new_question = await ContinentalQuestionRepository(session).create_question(question_create)
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
    await CountryRepository(session).validate_guess(guess.country_id, guess.guess, continent.value)
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
        await record_guest_action(session, request, response, f"continental:{continent.value}", day.id, won=is_correct)
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
        state, new_guess, elapsed_seconds=guess.elapsed_seconds, continent=continent, puzzle_date=day.date
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
