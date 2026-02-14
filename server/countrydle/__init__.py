from typing import Union

from db import get_db
from db.models import User
from db.repositories.countrydle import CountrydleRepository, CountrydleStateRepository
from schemas.countrydle import (
    CountrydleEndStateResponse,
    CountrydleEndStateSchema,
    CountrydleStateResponse,
    CountrydleStateSchema,
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
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from countrydle import statistics
from db.repositories.guess import GuessRepository
from db.repositories.question import QuestionsRepository
from qdrant.utils import add_question_to_qdrant
from db.repositories.country import CountryRepository
from users.utils import get_current_user

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
        is_lost=db_state.is_game_over and not db_state.won
    )


@router.get("/state", response_model=CountrydleStateResponse)
async def get_state(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    day_country = await CountrydleRepository(session).get_today_country()
    state = await CountrydleStateRepository(session).get_state(user, day_country)
    guesses = await GuessRepository(session).get_user_day_guesses(user, day_country)
    questions = await QuestionsRepository(session).get_user_day_questions(
        user, day_country
    )

    if state is None:
        return await CountrydleStateRepository(session).add_countrydle_state(
            user, day_country
        )

    questions = [
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
        questions=questions,
    )


@router.get("/end/state", response_model=CountrydleEndStateResponse)
async def get_end_state(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    day_country = await CountrydleRepository(session).get_today_country()
    state = await CountrydleStateRepository(session).get_state(user, day_country)
    guesses = await GuessRepository(session).get_user_day_guesses(user, day_country)
    questions = await QuestionsRepository(session).get_user_day_questions(
        user, day_country
    )

    if not state.is_game_over:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The player is still playing the game!",
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


@router.get("/countries", response_model=list[CountryDisplay])
async def get_countries(
    session: AsyncSession = Depends(get_db),
):
    return await CountryRepository(session).get_all_countries()


@router.post("/question", response_model=Union[QuestionDisplay, InvalidQuestionDisplay])
async def ask_question(
    question: QuestionBase,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
         daily_country = await CountrydleRepository(session).generate_new_day_country()

    state = await CountrydleStateRepository(session).get_player_countrydle_state(
        user, daily_country
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
        new_quest = await QuestionsRepository(session).create_question(question_create)

        # Update Logic State
        try:
            new_game_state = game_rules.process_question(current_game_state)
        except ValueError as e:
             raise HTTPException(status_code=400, detail=str(e))

        state.remaining_questions = COUNTRYDLE_CONFIG.max_questions - new_game_state.questions_used
        state.questions_asked += 1
        state = await CountrydleStateRepository(session).update_countrydle_state(state)

        return InvalidQuestionDisplay.model_validate(new_quest)

    question_create, question_vector = await gutils.ask_question(
        question=enh_question,
        day_country=daily_country,
        user=user,
        session=session,
    )

    new_quest = await QuestionsRepository(session).create_question(question_create)

    await add_question_to_qdrant(new_quest, question_vector, daily_country.country_id)

    # Update Logic State
    try:
        new_game_state = game_rules.process_question(current_game_state)
    except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    state.remaining_questions = COUNTRYDLE_CONFIG.max_questions - new_game_state.questions_used
    state.questions_asked += 1
    state = await CountrydleStateRepository(session).update_countrydle_state(state)

    return QuestionDisplay.model_validate(new_quest)


@router.post("/guess", response_model=GuessDisplay)
async def make_guess(
    guess: GuessBase,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
         daily_country = await CountrydleRepository(session).generate_new_day_country()

    state = await CountrydleStateRepository(session).get_player_countrydle_state(
        user, daily_country
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
        is_correct = (guess.country_id == daily_country.country_id)
    
    # Create Guess entry
    guess_create = GuessCreate(
        guess=guess.guess,
        country_id=guess.country_id, 
        day_id=daily_country.id,
        user_id=user.id,
        answer=is_correct
    )
    
    new_guess = await GuessRepository(session).add_guess(guess_create)

    # Update State using Repository logic (handles points, game over, etc.)
    # Note: guess_made expects a Guess model instance, which add_guess returns.
    # However, guess_made modifies state based on remaining_guesses logic.
    # We should ensure our GameRules logic matches what guess_made does, 
    # or rely on guess_made entirely for state updates.
    # The original code seemed to rely on manual updates. 
    # Let's use guess_made as it encapsulates the business logic for scoring/winning.
    
    await CountrydleStateRepository(session).guess_made(state, new_guess)

    return GuessDisplay.model_validate(new_guess)
