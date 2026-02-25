from typing import Union, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import User
from db.repositories.wojewodztwodle import (
    WojewodztwodleDayRepository,
    WojewodztwodleStateRepository,
    WojewodztwodleGuessRepository,
    WojewodztwodleQuestionRepository,
)
from db.repositories.wojewodztwo import WojewodztwoRepository
from schemas.wojewodztwodle import (
    WojewodztwoDisplay,
    WojewodztwodleStateResponse,
    WojewodztwodleEndStateResponse,
    WojewodztwodleStateSchema,
    WojewodztwoGuessBase,
    WojewodztwoGuessCreate,
    WojewodztwoGuessDisplay,
    WojewodztwoQuestionBase,
    WojewodztwoQuestionCreate,
    WojewodztwoQuestionDisplay,
    DayWojewodztwoDisplay,
)
from users.utils import get_current_or_guest_user, is_guest_user
import wojewodztwodle.utils as wutils
from game_logic import GameConfig, GameRules, GameState

router = APIRouter(prefix="/wojewodztwodle")

WOJEWODZTWDLE_CONFIG = GameConfig(max_questions=5, max_guesses=2)
game_rules = GameRules(WOJEWODZTWDLE_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    return GameState(
        questions_used=WOJEWODZTWDLE_CONFIG.max_questions
        - db_state.remaining_questions,
        guesses_used=WOJEWODZTWDLE_CONFIG.max_guesses - db_state.remaining_guesses,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won,
    )


@router.get("/history", response_model=List[DayWojewodztwoDisplay])
async def get_history(session: AsyncSession = Depends(get_db)):
    return await WojewodztwodleDayRepository(session).get_history()


@router.get(
    "/state",
    response_model=Union[WojewodztwodleStateResponse, WojewodztwodleEndStateResponse],
)
async def get_state(
    user: User = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await WojewodztwodleDayRepository(session).get_today_wojewodztwo()
    if not day_state:
        day_state = await WojewodztwodleDayRepository(
            session
        ).generate_new_day_wojewodztwo()

    state = await WojewodztwodleStateRepository(session).get_state(user, day_state)

    if state is None:
        state = await WojewodztwodleStateRepository(session).create_state(
            user,
            day_state,
            max_questions=WOJEWODZTWDLE_CONFIG.max_questions,
            max_guesses=WOJEWODZTWDLE_CONFIG.max_guesses,
        )

    guesses = await WojewodztwodleGuessRepository(session).get_user_day_guesses(
        user, day_state
    )
    questions = await WojewodztwodleQuestionRepository(session).get_user_day_questions(
        user, day_state
    )

    if state.is_game_over and state.won:
        wojewodztwo = await WojewodztwoRepository(session).get(day_state.wojewodztwo_id)
        return WojewodztwodleEndStateResponse(
            user=user,
            date=str(day_state.date),
            state=WojewodztwodleStateSchema.model_validate(state),
            guesses=guesses,
            questions=questions,
            wojewodztwo=wojewodztwo,
        )

    return WojewodztwodleStateResponse(
        user=user,
        date=str(day_state.date),
        state=WojewodztwodleStateSchema.model_validate(state),
        guesses=guesses,
        questions=questions,
        wojewodztwo=None,
    )


from schemas.countrydle import LeaderboardEntry


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(session: AsyncSession = Depends(get_db)):
    return await WojewodztwodleStateRepository(session).get_leaderboard()


@router.get("/wojewodztwa", response_model=List[WojewodztwoDisplay])
async def get_wojewodztwa(
    session: AsyncSession = Depends(get_db),
):
    return await WojewodztwoRepository(session).get_all()


@router.post("/question", response_model=WojewodztwoQuestionDisplay)
async def ask_question(
    question: WojewodztwoQuestionBase,
    user: User = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await WojewodztwodleDayRepository(session).get_today_wojewodztwo()
    state = await WojewodztwodleStateRepository(session).get_state(user, day_state)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_ask_question(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more questions left or game over!",
        )

    from qdrant.utils import add_question_to_qdrant

    enh_question = await wutils.enhance_question(question.question)
    if not enh_question.valid:
        question_create = WojewodztwoQuestionCreate(
            user_id=None if is_guest_user(user) else user.id,
            day_id=day_state.id,
            original_question=enh_question.original_question,
            valid=enh_question.valid,
            question=enh_question.question,
            answer=None,
            explanation=enh_question.explanation,
            context=None,
        )
        new_quest = await WojewodztwodleQuestionRepository(session).create_question(
            question_create
        )

        # Update state
        new_game_state = game_rules.process_question(current_game_state)
        state.remaining_questions = (
            WOJEWODZTWDLE_CONFIG.max_questions - new_game_state.questions_used
        )
        state.questions_asked += 1
        await WojewodztwodleStateRepository(session).update_state(state)

        return new_quest

    question_create, question_vector = await wutils.ask_question(
        enh_question,
        day_state,
        None if is_guest_user(user) else user,
        session,
    )

    new_quest = await WojewodztwodleQuestionRepository(session).create_question(
        question_create
    )

    await add_question_to_qdrant(
        new_quest,
        question_vector,
        filter_key="wojewodztwo_id",
        filter_value=day_state.wojewodztwo_id,
        collection_name="wojewodztwa_questions",
    )

    # Update state
    new_game_state = game_rules.process_question(current_game_state)
    state.remaining_questions = (
        WOJEWODZTWDLE_CONFIG.max_questions - new_game_state.questions_used
    )
    state.questions_asked += 1
    await WojewodztwodleStateRepository(session).update_state(state)

    return new_quest


@router.post("/guess", response_model=WojewodztwoGuessDisplay)
async def make_guess(
    guess: WojewodztwoGuessBase,
    user: User = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await WojewodztwodleDayRepository(session).get_today_wojewodztwo()
    state = await WojewodztwodleStateRepository(session).get_state(user, day_state)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more guesses left or game over!",
        )

    is_correct = False
    if guess.wojewodztwo_id:
        is_correct = guess.wojewodztwo_id == day_state.wojewodztwo_id

    guess_create = WojewodztwoGuessCreate(
        guess=guess.guess,
        wojewodztwo_id=guess.wojewodztwo_id,
        day_id=day_state.id,
        user_id=user.id,
        answer=is_correct,
    )

    new_guess = await WojewodztwodleGuessRepository(session).add_guess(guess_create)

    # Update state
    new_game_state = game_rules.process_guess(current_game_state, is_correct)
    state.remaining_guesses = (
        WOJEWODZTWDLE_CONFIG.max_guesses - new_game_state.guesses_used
    )
    state.guesses_made += 1
    state.won = new_game_state.is_won
    state.is_game_over = new_game_state.is_game_over

    if state.won:
        state.points = await WojewodztwodleStateRepository(session).calc_points(state)

    await WojewodztwodleStateRepository(session).update_state(state)

    return new_guess
