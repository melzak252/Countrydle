from typing import Union, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import User
from db.repositories.powiatdle import (
    PowiatRepository,
    PowiatdleDayRepository,
    PowiatdleStateRepository,
    PowiatdleGuessRepository,
    PowiatdleQuestionRepository,
)
from schemas.powiatdle import (
    PowiatDisplay,
    PowiatdleStateResponse,
    PowiatdleEndStateResponse,
    PowiatdleStateSchema,
    PowiatGuessBase,
    PowiatGuessCreate,
    PowiatGuessDisplay,
    PowiatQuestionBase,
    PowiatQuestionCreate,
    PowiatQuestionDisplay,
    DayPowiatDisplay,
)
from users.utils import get_current_or_guest_user
import powiatdle.utils as putils
from game_logic import GameConfig, GameRules, GameState

router = APIRouter(prefix="/powiatdle")

POWIATDLE_CONFIG = GameConfig(max_questions=15, max_guesses=3)
game_rules = GameRules(POWIATDLE_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    return GameState(
        questions_used=POWIATDLE_CONFIG.max_questions - db_state.remaining_questions,
        guesses_used=POWIATDLE_CONFIG.max_guesses - db_state.remaining_guesses,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won,
    )


@router.get("/history", response_model=List[DayPowiatDisplay])
async def get_history(session: AsyncSession = Depends(get_db)):
    return await PowiatdleDayRepository(session).get_history()


@router.get(
    "/state", response_model=Union[PowiatdleStateResponse, PowiatdleEndStateResponse]
)
async def get_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    if not day_powiat:
        day_powiat = await PowiatdleDayRepository(session).generate_new_day_powiat()

    if user is None:
        return PowiatdleStateResponse(
            user=None,
            date=str(day_powiat.date),
            state=PowiatdleStateSchema(
                id=0,
                user_id=0,
                day_id=day_powiat.id,
                remaining_questions=POWIATDLE_CONFIG.max_questions,
                remaining_guesses=POWIATDLE_CONFIG.max_guesses,
                questions_asked=0,
                guesses_made=0,
                is_game_over=False,
                won=False,
                points=0,
            ),
            guesses=[],
            questions=[],
            powiat=None,
        )

    state = await PowiatdleStateRepository(session).get_state(user, day_powiat)

    if state is None:
        state = await PowiatdleStateRepository(session).create_state(
            user,
            day_powiat,
            max_questions=POWIATDLE_CONFIG.max_questions,
            max_guesses=POWIATDLE_CONFIG.max_guesses,
        )

    guesses = await PowiatdleGuessRepository(session).get_user_day_guesses(
        user, day_powiat
    )
    questions = await PowiatdleQuestionRepository(session).get_user_day_questions(
        user, day_powiat
    )

    if state.is_game_over:
        powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
        return PowiatdleEndStateResponse(
            user=user,
            date=str(day_powiat.date),
            state=PowiatdleStateSchema.model_validate(state),
            guesses=guesses,
            questions=questions,
            powiat=powiat,
        )

    return PowiatdleStateResponse(
        user=user,
        date=str(day_powiat.date),
        state=PowiatdleStateSchema.model_validate(state),
        guesses=guesses,
        questions=questions,
        powiat=None,
    )


from schemas.countrydle import LeaderboardEntry


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(session: AsyncSession = Depends(get_db)):
    return await PowiatdleStateRepository(session).get_leaderboard()


@router.get("/powiaty", response_model=List[PowiatDisplay])
async def get_powiaty(
    session: AsyncSession = Depends(get_db),
):
    return await PowiatRepository(session).get_all()


@router.post("/question", response_model=PowiatQuestionDisplay)
async def ask_question(
    question: PowiatQuestionBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    
    from qdrant.utils import add_question_to_qdrant

    if user is None:
        enh_question = await putils.enhance_question(question.question)
        if not enh_question.valid:
            question_create = PowiatQuestionCreate(
                user_id=None,
                day_id=day_powiat.id,
                original_question=enh_question.original_question,
                valid=enh_question.valid,
                question=enh_question.question,
                answer=None,
                explanation=enh_question.explanation,
                context=None,
            )
            new_quest = await PowiatdleQuestionRepository(session).create_question(
                question_create
            )
            return new_quest

        question_create, question_vector = await putils.ask_question(
            enh_question,
            day_powiat,
            None,
            session,
        )

        new_quest = await PowiatdleQuestionRepository(session).create_question(
            question_create
        )

        await add_question_to_qdrant(
            new_quest,
            question_vector,
            filter_key="powiat_id",
            filter_value=day_powiat.powiat_id,
            collection_name="powiaty_questions",
        )

        return new_quest

    state = await PowiatdleStateRepository(session).get_state(user, day_powiat)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_ask_question(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more questions left or game over!",
        )

    enh_question = await putils.enhance_question(question.question)
    if not enh_question.valid:
        question_create = PowiatQuestionCreate(
            user_id=user.id,
            day_id=day_powiat.id,
            original_question=enh_question.original_question,
            valid=enh_question.valid,
            question=enh_question.question,
            answer=None,
            explanation=enh_question.explanation,
            context=None,
        )
        new_quest = await PowiatdleQuestionRepository(session).create_question(
            question_create
        )

        # Update state
        new_game_state = game_rules.process_question(current_game_state)
        state.remaining_questions = (
            POWIATDLE_CONFIG.max_questions - new_game_state.questions_used
        )
        state.questions_asked += 1
        await PowiatdleStateRepository(session).update_state(state)

        return new_quest

    question_create, question_vector = await putils.ask_question(
        enh_question,
        day_powiat,
        user,
        session,
    )

    new_quest = await PowiatdleQuestionRepository(session).create_question(
        question_create
    )

    await add_question_to_qdrant(
        new_quest,
        question_vector,
        filter_key="powiat_id",
        filter_value=day_powiat.powiat_id,
        collection_name="powiaty_questions",
    )

    # Update state
    new_game_state = game_rules.process_question(current_game_state)
    state.remaining_questions = (
        POWIATDLE_CONFIG.max_questions - new_game_state.questions_used
    )
    state.questions_asked += 1
    await PowiatdleStateRepository(session).update_state(state)

    return new_quest


@router.post("/guess", response_model=PowiatGuessDisplay)
async def make_guess(
    guess: PowiatGuessBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    
    if user is None:
        is_correct = False
        if guess.powiat_id:
            is_correct = guess.powiat_id == day_powiat.powiat_id
            
        from datetime import datetime
        return PowiatGuessDisplay(
            id=0,
            guess=guess.guess,
            powiat_id=guess.powiat_id,
            answer=is_correct,
            guessed_at=datetime.now()
        )

    state = await PowiatdleStateRepository(session).get_state(user, day_powiat)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more guesses left or game over!",
        )

    is_correct = False
    if guess.powiat_id:
        is_correct = guess.powiat_id == day_powiat.powiat_id

    guess_create = PowiatGuessCreate(
        guess=guess.guess,
        powiat_id=guess.powiat_id,
        day_id=day_powiat.id,
        user_id=user.id,
        answer=is_correct,
    )

    new_guess = await PowiatdleGuessRepository(session).add_guess(guess_create)

    # Update state
    new_game_state = game_rules.process_guess(current_game_state, is_correct)
    state.remaining_guesses = POWIATDLE_CONFIG.max_guesses - new_game_state.guesses_used
    state.guesses_made += 1
    state.won = new_game_state.is_won
    state.is_game_over = new_game_state.is_game_over

    if state.won:
        state.points = await PowiatdleStateRepository(session).calc_points(state)

    await PowiatdleStateRepository(session).update_state(state)

    return new_guess
