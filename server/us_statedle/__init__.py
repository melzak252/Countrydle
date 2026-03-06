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
    DayUSStateDisplay,
    USStatedleSyncSchema,
)
from users.utils import get_current_or_guest_user, get_current_user
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
        is_lost=db_state.is_game_over and not db_state.won,
    )


@router.post("/sync", response_model=USStatedleStateResponse)
async def sync_guest_data(
    sync_data: USStatedleSyncSchema,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    from sqlalchemy import update
    
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    day_state = await USStatedleDayRepository(session).get_day_us_state_by_date(game_date)
    if not day_state:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    state = await USStatedleStateRepository(session).get_state(user, day_state)
    if state is None:
        state = await USStatedleStateRepository(session).create_state(
            user,
            day_state,
            max_questions=USSTATEDLE_CONFIG.max_questions,
            max_guesses=USSTATEDLE_CONFIG.max_guesses,
        )
    
    if state.questions_asked > 0 or state.guesses_made > 0:
        return await get_state(user, session)

    if sync_data.questions:
        from db.models import USStatedleQuestion
        await session.execute(
            update(USStatedleQuestion)
            .where(
                USStatedleQuestion.id.in_(sync_data.questions), 
                USStatedleQuestion.user_id == None,
                USStatedleQuestion.day_id == day_state.id
            )
            .values(user_id=user.id)
        )

    for guess in sync_data.guesses:
        is_correct = False
        if guess.us_state_id:
            is_correct = guess.us_state_id == day_state.us_state_id
            
        guess_create = USStateGuessCreate(
            guess=guess.guess,
            us_state_id=guess.us_state_id,
            day_id=day_state.id,
            user_id=user.id,
            answer=is_correct,
        )
        await USStatedleGuessRepository(session).add_guess(guess_create)

    state.remaining_questions = sync_data.state.remaining_questions
    state.remaining_guesses = sync_data.state.remaining_guesses
    state.questions_asked = sync_data.state.questions_asked
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won
    
    if state.won:
        state.points = await USStatedleStateRepository(session).calc_points(state)
        
    await USStatedleStateRepository(session).update_state(state)
    
    return await get_state(user, session)


@router.get("/history", response_model=List[DayUSStateDisplay])
async def get_history(session: AsyncSession = Depends(get_db)):
    return await USStatedleDayRepository(session).get_history()


@router.get(
    "/state", response_model=Union[USStatedleStateResponse, USStatedleEndStateResponse]
)
async def get_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    if not day_state:
        day_state = await USStatedleDayRepository(session).generate_new_day_us_state()

    if user is None:
        return USStatedleStateResponse(
            user=None,
            date=str(day_state.date),
            state=USStatedleStateSchema(
                id=0,
                user_id=0,
                day_id=day_state.id,
                remaining_questions=USSTATEDLE_CONFIG.max_questions,
                remaining_guesses=USSTATEDLE_CONFIG.max_guesses,
                questions_asked=0,
                guesses_made=0,
                is_game_over=False,
                won=False,
                points=0,
            ),
            guesses=[],
            questions=[],
            us_state=None,
        )

    state = await USStatedleStateRepository(session).get_state(user, day_state)

    if state is None:
        state = await USStatedleStateRepository(session).create_state(
            user,
            day_state,
            max_questions=USSTATEDLE_CONFIG.max_questions,
            max_guesses=USSTATEDLE_CONFIG.max_guesses,
        )

    guesses = await USStatedleGuessRepository(session).get_user_day_guesses(
        user, day_state
    )
    questions = await USStatedleQuestionRepository(session).get_user_day_questions(
        user, day_state
    )

    if state.is_game_over:
        us_state = await USStateRepository(session).get(day_state.us_state_id)
        return USStatedleEndStateResponse(
            user=user,
            date=str(day_state.date),
            state=USStatedleStateSchema.model_validate(state),
            guesses=guesses,
            questions=questions,
            us_state=us_state,
        )

    return USStatedleStateResponse(
        user=user,
        date=str(day_state.date),
        state=USStatedleStateSchema.model_validate(state),
        guesses=guesses,
        questions=questions,
        us_state=None,
    )


from schemas.countrydle import LeaderboardEntry


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(session: AsyncSession = Depends(get_db)):
    return await USStatedleStateRepository(session).get_leaderboard()


@router.get("/states", response_model=List[USStateDisplay])
async def get_us_states(
    session: AsyncSession = Depends(get_db),
):
    return await USStateRepository(session).get_all()


@router.post("/question", response_model=USStateQuestionDisplay)
async def ask_question(
    question: USStateQuestionBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    
    from qdrant.utils import add_question_to_qdrant

    if user is None:
        enh_question = await uutils.enhance_question(question.question)
        if not enh_question.valid:
            question_create = USStateQuestionCreate(
                user_id=None,
                day_id=day_state.id,
                original_question=enh_question.original_question,
                valid=enh_question.valid,
                question=enh_question.question,
                answer=None,
                explanation=enh_question.explanation or "No explanation provided.",
                context=None,
            )
            new_quest = await USStatedleQuestionRepository(session).create_question(
                question_create
            )
            return new_quest

        question_create, question_vector = await uutils.ask_question(
            enh_question,
            day_state,
            None,
            session,
        )

        new_quest = await USStatedleQuestionRepository(session).create_question(
            question_create
        )

        if question_vector:
            await add_question_to_qdrant(
                new_quest,
                question_vector,
                filter_key="us_state_id",
                filter_value=day_state.us_state_id,
                collection_name="us_states_questions",
            )

        return new_quest


        question_create, question_vector = await uutils.ask_question(
            enh_question,
            day_state,
            None,
            session,
        )

        new_quest = await USStatedleQuestionRepository(session).create_question(
            question_create
        )

        await add_question_to_qdrant(
            new_quest,
            question_vector,
            filter_key="us_state_id",
            filter_value=day_state.us_state_id,
            collection_name="us_states_questions",
        )

        return new_quest

    state = await USStatedleStateRepository(session).get_state(user, day_state)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_ask_question(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more questions left or game over!",
        )

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
        new_quest = await USStatedleQuestionRepository(session).create_question(
            question_create
        )

        # Update state
        new_game_state = game_rules.process_question(current_game_state)
        state.remaining_questions = (
            USSTATEDLE_CONFIG.max_questions - new_game_state.questions_used
        )
        state.questions_asked += 1
        await USStatedleStateRepository(session).update_state(state)

        return new_quest

    question_create, question_vector = await uutils.ask_question(
        enh_question,
        day_state,
        user,
        session,
    )

    new_quest = await USStatedleQuestionRepository(session).create_question(
        question_create
    )

    await add_question_to_qdrant(
        new_quest,
        question_vector,
        filter_key="us_state_id",
        filter_value=day_state.us_state_id,
        collection_name="us_states_questions",
    )

    # Update state
    new_game_state = game_rules.process_question(current_game_state)
    state.remaining_questions = (
        USSTATEDLE_CONFIG.max_questions - new_game_state.questions_used
    )
    state.questions_asked += 1
    await USStatedleStateRepository(session).update_state(state)

    return new_quest


@router.get("/reveal", response_model=USStateDisplay)
async def reveal_us_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    if not day_state:
        raise HTTPException(status_code=404, detail="No game today")
        
    if user is not None:
        state = await USStatedleStateRepository(session).get_state(user, day_state)
        if state and not state.is_game_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal state before game is over.",
            )
            
    us_state = await USStateRepository(session).get(day_state.us_state_id)
    return us_state

@router.post("/guess", response_model=USStateGuessDisplay)
async def make_guess(
    guess: USStateGuessBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await USStatedleDayRepository(session).get_today_us_state()
    
    if user is None:
        is_correct = False
        if guess.us_state_id:
            is_correct = guess.us_state_id == day_state.us_state_id
            
        from datetime import datetime
        return USStateGuessDisplay(
            id=0,
            guess=guess.guess,
            us_state_id=guess.us_state_id,
            answer=is_correct,
            guessed_at=datetime.now()
        )

    state = await USStatedleStateRepository(session).get_state(user, day_state)

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more guesses left or game over!",
        )

    is_correct = False
    if guess.us_state_id:
        is_correct = guess.us_state_id == day_state.us_state_id

    guess_create = USStateGuessCreate(
        guess=guess.guess,
        us_state_id=guess.us_state_id,
        day_id=day_state.id,
        user_id=user.id,
        answer=is_correct,
    )

    new_guess = await USStatedleGuessRepository(session).add_guess(guess_create)

    # Update state
    new_game_state = game_rules.process_guess(current_game_state, is_correct)
    state.remaining_guesses = (
        USSTATEDLE_CONFIG.max_guesses - new_game_state.guesses_used
    )
    state.guesses_made += 1
    state.won = new_game_state.is_won
    state.is_game_over = new_game_state.is_game_over

    if state.won:
        state.points = await USStatedleStateRepository(session).calc_points(state)

    await USStatedleStateRepository(session).update_state(state)

    return new_guess
