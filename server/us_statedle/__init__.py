from typing import Union, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import User
from db.repositories.us_statedle import (
    USStatedleDayRepository,
    USStatedleStateRepository,
    USStatedleGuessRepository,
    USStatedleQuestionRepository,
)
from db.repositories.us_state import USStateRepository
from schemas.us_statedle import (
    USStateDisplay,
    USStatedleStateResponse,
    USStatedleEndStateResponse,
    USStatedleStateSchema,
    USStateGuessBase,
    USStateGuessCreate,
    USStateGuessDisplay,
    USStateQuestionBase,
    USStateQuestionCreate,
    USStateQuestionDisplay,
)
from users.utils import get_current_user
import us_statedle.utils as uutils
from game_logic import GameConfig, GameRules, GameState

router = APIRouter(prefix="/us_statedle")

USSTATEDLE_CONFIG = GameConfig(max_questions=8, max_guesses=3)
game_rules = GameRules(USSTATEDLE_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    return GameState(
        questions_used=USSTATEDLE_CONFIG.max_questions - db_state.remaining_questions,
        guesses_used=USSTATEDLE_CONFIG.max_guesses - db_state.remaining_guesses,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won
    )


@router.get("/state", response_model=Union[USStatedleStateResponse, USStatedleEndStateResponse])
async def get_state(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    if not day_state:
        day_state = await USStatedleDayRepository(session).generate_new_day_us_state()

    state = await USStatedleStateRepository(session).get_state(user, day_state)
    
    if state is None:
        state = await USStatedleStateRepository(session).create_state(user, day_state)

    guesses = await USStatedleGuessRepository(session).get_user_day_guesses(user, day_state)
    questions = await USStatedleQuestionRepository(session).get_user_day_questions(user, day_state)

    if state.is_game_over:
        us_state = await USStateRepository(session).get(day_state.us_state_id)
        return USStatedleEndStateResponse(
            user=user,
            date=str(day_state.date),
            state=USStatedleStateSchema.model_validate(state),
            guesses=guesses,
            questions=questions,
            us_state=us_state
        )

    return USStatedleStateResponse(
        user=user,
        date=str(day_state.date),
        state=USStatedleStateSchema.model_validate(state),
        guesses=guesses,
        questions=questions,
        us_state=None
    )


@router.get("/states", response_model=List[USStateDisplay])
async def get_us_states(
    session: AsyncSession = Depends(get_db),
):
    return await USStateRepository(session).get_all()


@router.post("/question", response_model=USStateQuestionDisplay)
async def ask_question(
    question: USStateQuestionBase,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    state = await USStatedleStateRepository(session).get_state(user, day_state)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_ask_question(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more questions left or game over!"
        )

    from qdrant.utils import add_question_to_qdrant
    enh_question = await uutils.enhance_question(question.question)
    if not enh_question.valid:
        question_create = USStateQuestionCreate(
            user_id=user.id,
            day_id=day_state.id,
            original_question=enh_question.original_question,
            valid=enh_question.valid,
            question=enh_question.question,
            answer=None,
            explanation=enh_question.explanation,
            context=None,
        )
        new_quest = await USStatedleQuestionRepository(session).create_question(question_create)

        # Update state
        new_game_state = game_rules.process_question(current_game_state)
        state.remaining_questions = USSTATEDLE_CONFIG.max_questions - new_game_state.questions_used
        state.questions_asked += 1
        await USStatedleStateRepository(session).update_state(state)

        return new_quest

    question_create, question_vector = await uutils.ask_question(enh_question, day_state, user, session)
    
    new_quest = await USStatedleQuestionRepository(session).create_question(question_create)

    await add_question_to_qdrant(
        new_quest,
        question_vector,
        filter_key="us_state_id",
        filter_value=day_state.us_state_id,
        collection_name="us_states_questions",
    )

    # Update state
    new_game_state = game_rules.process_question(current_game_state)
    state.remaining_questions = USSTATEDLE_CONFIG.max_questions - new_game_state.questions_used
    state.questions_asked += 1
    await USStatedleStateRepository(session).update_state(state)

    return new_quest


@router.post("/guess", response_model=USStateGuessDisplay)
async def make_guess(
    guess: USStateGuessBase,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    state = await USStatedleStateRepository(session).get_state(user, day_state)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more guesses left or game over!"
        )

    is_correct = False
    if guess.us_state_id:
        is_correct = (guess.us_state_id == day_state.us_state_id)
    
    guess_create = USStateGuessCreate(
        guess=guess.guess,
        us_state_id=guess.us_state_id,
        day_id=day_state.id,
        user_id=user.id,
        answer=is_correct
    )
    
    new_guess = await USStatedleGuessRepository(session).add_guess(guess_create)

    # Update state
    new_game_state = game_rules.process_guess(current_game_state, is_correct)
    state.remaining_guesses = USSTATEDLE_CONFIG.max_guesses - new_game_state.guesses_used
    state.guesses_made += 1
    state.won = new_game_state.is_won
    state.is_game_over = new_game_state.is_game_over
    
    if state.won:
        state.points = 100 # Simple points for now
        
    await USStatedleStateRepository(session).update_state(state)

    return new_guess
