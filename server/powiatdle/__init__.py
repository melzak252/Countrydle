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
    PowiatdleSyncSchema,
)
from users.utils import get_current_or_guest_user, get_current_user, get_admin_user
import powiatdle.utils as putils
from game_logic import GameConfig, GameRules, GameState

router = APIRouter(prefix="/powiatdle")

POWIATDLE_CONFIG = GameConfig(max_questions=15, max_guesses=3)
game_rules = GameRules(POWIATDLE_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    return GameState(
        questions_used=db_state.questions_asked,
        guesses_used=db_state.guesses_made,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won,
    )


async def normalize_state_limits(state, session: AsyncSession):
    expected_questions = max(0, POWIATDLE_CONFIG.max_questions - state.questions_asked)
    expected_guesses = max(0, POWIATDLE_CONFIG.max_guesses - state.guesses_made)
    if (
        state.remaining_questions != expected_questions
        or state.remaining_guesses != expected_guesses
    ):
        state.remaining_questions = expected_questions
        state.remaining_guesses = expected_guesses
        await PowiatdleStateRepository(session).update_state(state)
    return state


@router.post("/sync", response_model=PowiatdleStateResponse)
async def sync_guest_data(
    sync_data: PowiatdleSyncSchema,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    from sqlalchemy import update
    
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    day_powiat = await PowiatdleDayRepository(session).get_day_powiat_by_date(game_date)
    if not day_powiat:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    state = await PowiatdleStateRepository(session).get_state(user, day_powiat)
    if state is None:
        state = await PowiatdleStateRepository(session).create_state(
            user,
            day_powiat,
            max_questions=POWIATDLE_CONFIG.max_questions,
            max_guesses=POWIATDLE_CONFIG.max_guesses,
        )
    
    if state.questions_asked > 0 or state.guesses_made > 0:
        return await get_state(user, session)

    if sync_data.questions:
        from db.models import PowiatdleQuestion
        await session.execute(
            update(PowiatdleQuestion)
            .where(
                PowiatdleQuestion.id.in_(sync_data.questions), 
                PowiatdleQuestion.user_id == None,
                PowiatdleQuestion.day_id == day_powiat.id
            )
            .values(user_id=user.id)
        )

    for guess in sync_data.guesses:
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
        await PowiatdleGuessRepository(session).add_guess(guess_create)

    state.remaining_questions = sync_data.state.remaining_questions
    state.remaining_guesses = sync_data.state.remaining_guesses
    state.questions_asked = sync_data.state.questions_asked
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won
    
    if state.won:
        state.points = await PowiatdleStateRepository(session).calc_points(state)
        
    await PowiatdleStateRepository(session).update_state(state)
    
    return await get_state(user, session)


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

    state = await normalize_state_limits(state, session)

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

    questions_display = [
        PowiatQuestionDisplay.model_validate(question)
        for question in questions
    ]

    return PowiatdleStateResponse(
        user=user,
        date=str(day_powiat.date),
        state=PowiatdleStateSchema.model_validate(state),
        guesses=guesses,
        questions=questions_display,
        powiat=None,
    )


from schemas.countrydle import LeaderboardEntry


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(type: str = "monthly", session: AsyncSession = Depends(get_db)):
    return await PowiatdleStateRepository(session).get_leaderboard(type)


@router.get("/powiaty", response_model=List[PowiatDisplay])
async def get_powiaty(
    session: AsyncSession = Depends(get_db),
):
    return await PowiatRepository(session).get_all()


@router.get("/admin/questions", response_model=List[PowiatQuestionDisplay])
async def get_admin_questions(
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    return await PowiatdleQuestionRepository(session).get_all_questions()


@router.post("/question", response_model=PowiatQuestionDisplay)
async def ask_question(
    question: PowiatQuestionBase,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    
    from qdrant.utils import add_question_to_qdrant

    if user is None:
        question_create, planned_question = await putils.analyze_and_answer_locally(
            question.question, day_powiat, None, session
        )

        if question_create is None:
            enh_question = putils.question_enhanced_from_plan(
                question.question, planned_question
            )
            question_create, question_vector = await putils.ask_question(
                enh_question,
                day_powiat,
                None,
                session,
            )
        else:
            question_vector = None

        new_quest = await PowiatdleQuestionRepository(session).create_question(
            question_create
        )

        if question_vector:
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

    question_create, planned_question = await putils.analyze_and_answer_locally(
        question.question, day_powiat, user, session
    )

    if question_create is None:
        enh_question = putils.question_enhanced_from_plan(question.question, planned_question)
        question_create, question_vector = await putils.ask_question(
            enh_question,
            day_powiat,
            user,
            session,
        )
    else:
        question_vector = None

    new_quest = await PowiatdleQuestionRepository(session).create_question(
        question_create
    )

    if question_vector:
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


@router.get("/reveal", response_model=PowiatDisplay)
async def reveal_powiat(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    if not day_powiat:
        day_powiat = await PowiatdleDayRepository(session).generate_new_day_powiat()
    if not day_powiat:
        raise HTTPException(status_code=404, detail="No game today")
        
    if user is not None:
        state = await PowiatdleStateRepository(session).get_state(user, day_powiat)
        if state and not state.is_game_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal powiat before game is over.",
            )
            
    powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
    return powiat

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
