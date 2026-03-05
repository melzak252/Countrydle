from typing import Union

from db import get_db
from db.models import User
from db.repositories.countrydle import CountrydleRepository, CountrydleStateRepository
from schemas.countrydle import (
    CountrydleEndStateResponse,
    CountrydleEndStateSchema,
    CountrydleStateResponse,
    CountrydleStateSchema,
    CountrydleSyncSchema,
    FullUserHistory,
    GuessBase,
    GuessCreate,
    GuessDisplay,
    InvalidQuestionDisplay,
    QuestionBase,
    QuestionCreate,
    QuestionDisplay,
)
from schemas.country import CountryDisplay
from schemas.user import UserDisplay
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from countrydle import statistics
from db.repositories.guess import (
    CountrydleGuessRepository,
)
from db.repositories.question import (
    CountrydleQuestionsRepository,
)
from qdrant.utils import add_question_to_qdrant
from db.repositories.country import CountryRepository
from users.utils import get_current_or_guest_user, get_current_user

import countrydle.utils as gutils
from game_logic import GameConfig, GameRules, GameState

load_dotenv()

router = APIRouter(prefix="/countrydle")

router.include_router(statistics.router)

# Konfiguracja zasad gry Countrydle
COUNTRYDLE_CONFIG = GameConfig(max_questions=10, max_guesses=3)
game_rules = GameRules(COUNTRYDLE_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    """Helper to convert DB state to Logic GameState"""
    return GameState(
        questions_used=COUNTRYDLE_CONFIG.max_questions - db_state.remaining_questions,
        guesses_used=COUNTRYDLE_CONFIG.max_guesses - db_state.remaining_guesses,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won,
    )


@router.post("/sync", response_model=CountrydleStateResponse)
async def sync_guest_data(
    sync_data: CountrydleSyncSchema,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    
    # 1. Get the day country
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    day_country = await CountrydleRepository(session).get_day_country_by_date(game_date)
    if not day_country:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    # 2. Get or create user state
    state = await CountrydleStateRepository(session).get_state(
        user,
        day_country,
        max_questions=COUNTRYDLE_CONFIG.max_questions,
        max_guesses=COUNTRYDLE_CONFIG.max_guesses,
    )
    
    # BEST SOLUTION: Prioritize Server State
    # If the user already has any progress on the server (at least 1 question or guess),
    # we ignore the guest sync to prevent merging conflicts or exceeding game limits.
    if state.questions_asked > 0 or state.guesses_made > 0:
        return await get_state(user, session)

    # 3. Update questions - only claim those that belong to this day and have no user assigned
    if sync_data.questions:
        from db.models import CountrydleQuestion
        await session.execute(
            update(CountrydleQuestion)
            .where(
                CountrydleQuestion.id.in_(sync_data.questions), 
                CountrydleQuestion.user_id == None,
                CountrydleQuestion.day_id == day_country.id
            )
            .values(user_id=user.id)
        )

    # 4. Create guesses
    for guess in sync_data.guesses:
        is_correct = False
        if guess.country_id is not None:
            is_correct = guess.country_id == day_country.country_id
            
        guess_create = GuessCreate(
            guess=guess.guess,
            country_id=guess.country_id,
            day_id=day_country.id,
            user_id=user.id,
            answer=is_correct,
        )
        await CountrydleGuessRepository(session).add_guess(guess_create)

    # 5. Update state
    state.remaining_questions = sync_data.state.remaining_questions
    state.remaining_guesses = sync_data.state.remaining_guesses
    state.questions_asked = sync_data.state.questions_asked
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won
    
    if state.won:
        state.points = await CountrydleStateRepository(session).calc_points(state)
        
    if state.is_game_over:
        from db.repositories.user import UserRepository
        await UserRepository(session).update_points(user.id, state)

    await CountrydleStateRepository(session).update_countrydle_state(state)
    
    return await get_state(user, session)


@router.get("/end/state", response_model=CountrydleEndStateResponse)
async def get_end_state(
    user: User = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_country = await CountrydleRepository(session).get_today_country()
    state = await CountrydleStateRepository(session).get_state(
        user,
        day_country,
        max_questions=COUNTRYDLE_CONFIG.max_questions,
        max_guesses=COUNTRYDLE_CONFIG.max_guesses,
    )
    guesses = await CountrydleGuessRepository(session).get_user_day_guesses(
        user, day_country
    )
    questions = await CountrydleQuestionsRepository(session).get_user_day_questions(
        user, day_country
    )

    if not state.is_game_over:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target country is only available after the game is over.",
        )

    country = await CountryRepository(session).get(day_country.country_id)
    return CountrydleEndStateResponse(
        user=user,
        date=str(day_country.date),
        country=country,
        state=CountrydleEndStateSchema.model_validate(state),
        guesses=guesses,
        questions=questions,
    )


@router.get(
    "/state", response_model=Union[CountrydleStateResponse, CountrydleEndStateResponse]
)
async def get_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_country = await CountrydleRepository(session).get_today_country()
    if not day_country:
        day_country = await CountrydleRepository(session).generate_new_day_country()

    if user is None:
        return CountrydleStateResponse(
            user=None,
            date=str(day_country.date),
            state=CountrydleStateSchema(
                remaining_questions=COUNTRYDLE_CONFIG.max_questions,
                remaining_guesses=COUNTRYDLE_CONFIG.max_guesses,
                questions_asked=0,
                guesses_made=0,
                is_game_over=False,
                won=False,
            ),
            guesses=[],
            questions=[],
            country=None,
        )

    state = await CountrydleStateRepository(session).get_state(
        user,
        day_country,
        max_questions=COUNTRYDLE_CONFIG.max_questions,
        max_guesses=COUNTRYDLE_CONFIG.max_guesses,
    )

    if state and state.is_game_over:
        return await get_end_state(user, session)

    guesses = await CountrydleGuessRepository(session).get_user_day_guesses(
        user, day_country
    )
    questions = await CountrydleQuestionsRepository(session).get_user_day_questions(
        user, day_country
    )

    if state is None:
        new_state = await CountrydleStateRepository(session).add_countrydle_state(
            user,
            day_country,
            max_questions=COUNTRYDLE_CONFIG.max_questions,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses,
        )
        return CountrydleStateResponse(
            user=user,
            date=str(day_country.date),
            state=CountrydleStateSchema.model_validate(new_state),
            guesses=[],
            questions=[],
            country=None,
        )

    questions_display = [
        (
            QuestionDisplay.model_validate(question)
            if question.valid
            else InvalidQuestionDisplay.model_validate(question)
        )
        for question in questions
    ]

    response_state = CountrydleStateSchema.model_validate(state)

    return CountrydleStateResponse(
        user=user,
        date=str(day_country.date),
        state=response_state,
        guesses=guesses,
        questions=questions_display,
        country=None,
    )


@router.get("/countries", response_model=list[CountryDisplay])
async def get_countries(
    session: AsyncSession = Depends(get_db),
):
    return await CountryRepository(session).get_all_countries()


@router.post("/question", response_model=Union[QuestionDisplay, InvalidQuestionDisplay])
async def ask_question(
    question: QuestionBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
        daily_country = await CountrydleRepository(session).generate_new_day_country()

    if user is None:
        enh_question = await gutils.enhance_question(question.question)
        if not enh_question.valid:
            question_create = QuestionCreate(
                user_id=None,
                day_id=daily_country.id,
                original_question=enh_question.original_question,
                valid=enh_question.valid,
                question=enh_question.question,
                answer=None,
                explanation=enh_question.explanation,
                context=None,
            )
            new_quest = await CountrydleQuestionsRepository(session).create_question(
                question_create
            )
            return InvalidQuestionDisplay.model_validate(new_quest)

        question_create, question_vector = await gutils.ask_question(
            question=enh_question,
            day_country=daily_country,
            user=None,
            session=session,
        )

        new_quest = await CountrydleQuestionsRepository(session).create_question(
            question_create
        )

        await add_question_to_qdrant(
            new_quest,
            question_vector,
            filter_key="country_id",
            filter_value=daily_country.country_id,
            collection_name="countries_questions",
        )

        return QuestionDisplay.model_validate(new_quest)

    state = await CountrydleStateRepository(session).get_player_countrydle_state(
        user,
        daily_country,
        max_questions=COUNTRYDLE_CONFIG.max_questions,
        max_guesses=COUNTRYDLE_CONFIG.max_guesses,
    )

    # Use Game Logic
    current_game_state = db_state_to_game_state(state)

    if not game_rules.can_ask_question(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no more questions left or game is over!",
        )

    enh_question = await gutils.enhance_question(question.question)
    if not enh_question.valid:
        question_create = QuestionCreate(
            user_id=user.id,
            day_id=daily_country.id,
            original_question=enh_question.original_question,
            valid=enh_question.valid,
            question=enh_question.question,
            answer=None,
            explanation=enh_question.explanation,
            context=None,
        )
        new_quest = await CountrydleQuestionsRepository(session).create_question(
            question_create
        )

        # Update Logic State
        try:
            new_game_state = game_rules.process_question(current_game_state)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        state.remaining_questions = (
            COUNTRYDLE_CONFIG.max_questions - new_game_state.questions_used
        )
        state.questions_asked += 1
        state = await CountrydleStateRepository(session).update_countrydle_state(state)

        return InvalidQuestionDisplay.model_validate(new_quest)

    question_create, question_vector = await gutils.ask_question(
        question=enh_question,
        day_country=daily_country,
        user=user,
        session=session,
    )

    new_quest = await CountrydleQuestionsRepository(session).create_question(
        question_create
    )

    await add_question_to_qdrant(
        new_quest,
        question_vector,
        filter_key="country_id",
        filter_value=daily_country.country_id,
        collection_name="countries_questions",
    )

    # Update Logic State
    try:
        new_game_state = game_rules.process_question(current_game_state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    state.remaining_questions = (
        COUNTRYDLE_CONFIG.max_questions - new_game_state.questions_used
    )
    state.questions_asked += 1
    state = await CountrydleStateRepository(session).update_countrydle_state(state)

    return QuestionDisplay.model_validate(new_quest)


@router.get("/reveal", response_model=CountryDisplay)
async def reveal_country(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_country = await CountrydleRepository(session).get_today_country()
    if not day_country:
        raise HTTPException(status_code=404, detail="No game today")
        
    if user is not None:
        state = await CountrydleStateRepository(session).get_state(
            user,
            day_country,
            max_questions=COUNTRYDLE_CONFIG.max_questions,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses,
        )
        if state and not state.is_game_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal country before game is over.",
            )
            
    country = await CountryRepository(session).get(day_country.country_id)
    return country

@router.post("/guess", response_model=GuessDisplay)
async def make_guess(
    guess: GuessBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
        daily_country = await CountrydleRepository(session).generate_new_day_country()

    if user is None:
        is_correct = False
        if guess.country_id is not None:
            is_correct = guess.country_id == daily_country.country_id
            
        from datetime import datetime
        return GuessDisplay(
            id=0,
            guess=guess.guess,
            country_id=guess.country_id,
            answer=is_correct,
            guessed_at=datetime.now()
        )

    state = await CountrydleStateRepository(session).get_player_countrydle_state(
        user,
        daily_country,
        max_questions=COUNTRYDLE_CONFIG.max_questions,
        max_guesses=COUNTRYDLE_CONFIG.max_guesses,
    )

    # Use Game Logic
    current_game_state = db_state_to_game_state(state)

    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no more guesses left or game is over!",
        )

    # Check if guess is correct
    is_correct = False

    if guess.country_id is not None:
        is_correct = guess.country_id == daily_country.country_id

    # Create Guess entry
    guess_create = GuessCreate(
        guess=guess.guess,
        country_id=guess.country_id,
        day_id=daily_country.id,
        user_id=user.id,
        answer=is_correct,
    )

    new_guess = await CountrydleGuessRepository(session).add_guess(guess_create)

    # Update State using Repository logic (handles points, game over, etc.)
    await CountrydleStateRepository(session).guess_made(state, new_guess)

    return GuessDisplay.model_validate(new_guess)
