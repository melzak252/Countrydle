import os

from db.models import PowiatdleState, PowiatdleGuess, PowiatdleQuestion
from db.repositories.question_accounting import (
    consume_question, is_answered, unresolved_question, require_question_available,
    get_daily_state, require_guess_available,
)
from typing import Union, List

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response
from utils.guest_session import (
    create_guest_game_token, record_guest_action, get_guest_progress, guest_game_over,
    check_guest_question_available, claim_guest_history,
)
from utils.question_rate_limit import enforce_question_attempt_limit

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
from utils.geo import enhance_guess_with_hint


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

def format_powiat_guesses(guesses: list, target_powiat_id: int, target_name: str | None = None) -> list[PowiatGuessDisplay]:
    from datetime import datetime
    formatted = []
    for idx, g in enumerate(guesses):
        hint = enhance_guess_with_hint(
            mode="powiatdle",
            guess_record=g,
            guess_number=idx + 1,
            max_guesses=POWIATDLE_CONFIG.max_guesses,
            target_id=target_powiat_id,
            target_name=target_name,
        )
        gd = PowiatGuessDisplay(
            id=int(getattr(g, "id", 0) or 0),
            guess=str(getattr(g, "guess", "") or ""),
            powiat_id=getattr(g, "powiat_id", None) if isinstance(getattr(g, "powiat_id", None), int) else None,
            answer=bool(getattr(g, "answer", False) if isinstance(getattr(g, "answer", False), bool) else False),
            guessed_at=getattr(g, "guessed_at", None) or datetime.now(),
            elapsed_seconds=getattr(g, "elapsed_seconds", None),
            distance_km=hint.get("distance_km"),
            bearing_degrees=hint.get("bearing_degrees"),
            bearing_direction=hint.get("bearing_direction"),
            bearing_arrow=hint.get("bearing_arrow"),
        )
        formatted.append(gd)
    return formatted




@router.post("/sync", response_model=PowiatdleStateResponse)
async def sync_guest_data(
    sync_data: PowiatdleSyncSchema,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    day_powiat = await PowiatdleDayRepository(session).get_day_powiat_by_date(game_date)
    if not day_powiat:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    try:
        state = await get_daily_state(
            session, PowiatdleState, user.id, day_powiat.id,
            POWIATDLE_CONFIG.max_questions, POWIATDLE_CONFIG.max_guesses,
        )
        imported = await claim_guest_history(
            session, request, state, "powiatdle", PowiatdleGuess, PowiatdleQuestion,
            POWIATDLE_CONFIG.max_questions, POWIATDLE_CONFIG.max_guesses,
        )
        if imported and state.won:
            guesses = await PowiatdleGuessRepository(session).get_user_day_guesses(user, day_powiat)
            elapsed = guesses[-1].elapsed_seconds if guesses else None
            streak = (await PowiatdleStateRepository(session).get_current_streak(user.id, day_powiat.date)) + 1
            state.points = await PowiatdleStateRepository(session).calc_points(
                state, elapsed_seconds=elapsed, streak=streak,
            )
        await PowiatdleStateRepository(session).update_state(state, commit=False)
        result = await _state_response(user, session, day_powiat)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


@router.get("/history", response_model=List[DayPowiatDisplay])
async def get_history(session: AsyncSession = Depends(get_db)):
    return await PowiatdleDayRepository(session).get_history()


@router.get(
    "/state", response_model=Union[PowiatdleStateResponse, PowiatdleEndStateResponse]
)
async def get_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    if not day_powiat:
        day_powiat = await PowiatdleDayRepository(session).generate_new_day_powiat()

    try:
        result = await _state_response(user, session, day_powiat, request, response)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


async def _state_response(user, session, day_powiat, request=None, response=None):
    powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
    if user is None:
        participation, guesses, questions = await get_guest_progress(
            session, request, response, "powiatdle", day_powiat.id,
            PowiatdleGuess, PowiatdleQuestion,
        )
        questions_asked = participation.questions_asked if participation else 0
        guesses_made = participation.guesses_made if participation else 0
        is_game_over = guest_game_over(participation, POWIATDLE_CONFIG.max_guesses)
        state_display = PowiatdleStateSchema(
            id=0, user_id=0, day_id=day_powiat.id,
            remaining_questions=max(0, POWIATDLE_CONFIG.max_questions - questions_asked),
            remaining_guesses=max(0, POWIATDLE_CONFIG.max_guesses - guesses_made),
            questions_asked=questions_asked, guesses_made=guesses_made,
            is_game_over=is_game_over, won=participation.won if participation else False,
            points=0,
        )
    else:
        state = await get_daily_state(
            session, PowiatdleState, user.id, day_powiat.id,
            POWIATDLE_CONFIG.max_questions, POWIATDLE_CONFIG.max_guesses,
        )
        state.remaining_questions = max(0, POWIATDLE_CONFIG.max_questions - state.questions_asked)
        state.remaining_guesses = max(0, POWIATDLE_CONFIG.max_guesses - state.guesses_made)
        state.is_game_over = state.is_game_over or state.won or state.guesses_made >= POWIATDLE_CONFIG.max_guesses
        guesses = await PowiatdleGuessRepository(session).get_user_day_guesses(user, day_powiat)
        questions = await PowiatdleQuestionRepository(session).get_user_day_questions(user, day_powiat)
        state_display = PowiatdleStateSchema.model_validate(state)
        is_game_over = state.is_game_over
    return PowiatdleStateResponse(
        user=user, date=str(day_powiat.date), state=state_display,
        guesses=format_powiat_guesses(guesses, day_powiat.powiat_id, powiat.nazwa if powiat else None),
        questions=[PowiatQuestionDisplay.model_validate(question) for question in questions],
        powiat=powiat if is_game_over else None,
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


@router.get("/admin/questions")
async def get_admin_questions(
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    repository = PowiatdleQuestionRepository(session)
    if limit is None:
        return await repository.get_all_questions()
    items = await repository.get_all_questions(limit=limit, offset=offset)
    total = await repository.count_questions()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post(
    "/question",
    response_model=PowiatQuestionDisplay,
    dependencies=[Depends(enforce_question_attempt_limit)],
)
async def ask_question(
    question: PowiatQuestionBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    user_id = user.id if user else None
    try:
        return await _do_ask_question(question, user, session, request, response)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        import logging, traceback
        logging.getLogger("countrydle").error("Handled error in powiatdle ask_question: %s\n%s", exc, traceback.format_exc())
        from datetime import datetime
        return PowiatQuestionDisplay(
            id=0,
            original_question=question.question,
            question=question.question,
            valid=False,
            answer=None,
            explanation="Nie udało się zweryfikować tego pytania w tym momencie. Twoja próba nie została zużyta.",
            asked_at=datetime.now(),
            user_id=user_id,
            day_id=0,
        )


async def _do_ask_question(
    question: PowiatQuestionBase,
    user: User | None,
    session: AsyncSession,
    request: Request,
    response: Response,
):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    if not day_powiat:
        day_powiat = await PowiatdleDayRepository(session).generate_new_day_powiat()
    if user is not None:
        state = await PowiatdleStateRepository(session).get_state(user, day_powiat)
        require_question_available(state, POWIATDLE_CONFIG.max_questions)
    else:
        await check_guest_question_available(
            session, request, response, "powiatdle", day_powiat.id,
            POWIATDLE_CONFIG.max_questions, max_guesses=POWIATDLE_CONFIG.max_guesses,
        )

    # End the day/quota read transaction before planner or provider work.
    await session.commit()

    question_create, planned_question = await putils.analyze_and_answer_locally(
        question.question, day_powiat, user, session
    )
    question_vector = None
    if question_create is None:
        enhanced = putils.question_enhanced_from_plan(question.question, planned_question)
        if not enhanced.valid:
            question_create = PowiatQuestionCreate(
                user_id=user.id if user else None, day_id=day_powiat.id,
                original_question=question.question, question=enhanced.question,
                valid=False, answer=None, explanation=enhanced.explanation, context=None,
            )
        else:
            question_create, question_vector = await putils.ask_question(
                enhanced, day_powiat, user, session
            )

    if not is_answered(question_create):
        return unresolved_question(question_create, PowiatQuestionDisplay)
    question_create.user_id = user.id if user else None
    question_create.day_id = day_powiat.id
    guest_id = None
    if user is None:
        participation = await record_guest_action(
            session, request, response, "powiatdle", day_powiat.id,
            max_guesses=POWIATDLE_CONFIG.max_guesses,
            question=True, max_questions=POWIATDLE_CONFIG.max_questions,
        )
        guest_id = participation.guest_id
    else:
        await consume_question(
            session, PowiatdleState, user.id, day_powiat.id,
            POWIATDLE_CONFIG.max_questions, POWIATDLE_CONFIG.max_guesses,
        )
    new_question = await PowiatdleQuestionRepository(session).create_question(
        question_create, guest_id=guest_id,
    )
    result = PowiatQuestionDisplay.model_validate(new_question)
    await session.commit()
    if question_vector:
        # Indexing is auxiliary: an already committed answer remains successful.
        try:
            from qdrant.utils import add_question_to_qdrant
            await add_question_to_qdrant(
                new_question, question_vector, filter_key="powiat_id",
                filter_value=day_powiat.powiat_id, collection_name="powiaty_questions",
            )
        except Exception:
            import logging
            logging.getLogger("countrydle").exception("Could not index accepted powiatdle question")
    return result


@router.get("/reveal", response_model=PowiatDisplay)
async def reveal_powiat(
    request: Request,
    response: Response,
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
        if state is None or not (state.is_game_over or state.won or state.guesses_made >= POWIATDLE_CONFIG.max_guesses):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal powiat before game is over.",
            )
    else:
        participation, _, _ = await get_guest_progress(
            session, request, response, "powiatdle", day_powiat.id,
            PowiatdleGuess, PowiatdleQuestion,
        )
        if not guest_game_over(participation, POWIATDLE_CONFIG.max_guesses):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal powiat before game is over.",
            )
            
    powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
    await session.commit()
    return powiat

@router.post("/guess", response_model=PowiatGuessDisplay)
async def make_guess(
    guess: PowiatGuessBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await _do_make_guess(guess, request, response, user, session)
    except Exception:
        await session.rollback()
        raise


async def _do_make_guess(guess, request, response, user, session):
    day_powiat = await PowiatdleDayRepository(session).get_today_powiat()
    if not day_powiat:
        day_powiat = await PowiatdleDayRepository(session).generate_new_day_powiat()

    from db.repositories.powiatdle import PowiatRepository
    target_powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
    is_correct = False
    if guess.powiat_id:
        is_correct = guess.powiat_id == day_powiat.powiat_id
    if not is_correct and guess.guess and target_powiat:
        is_correct = guess.guess.strip().lower() == target_powiat.nazwa.strip().lower()
        if is_correct:
            guess.powiat_id = day_powiat.powiat_id

    if user is None:
        participation = await record_guest_action(
            session, request, response, "powiatdle", day_powiat.id,
            max_guesses=POWIATDLE_CONFIG.max_guesses, won=is_correct,
        )
        guess_create = PowiatGuessCreate(
            guess=guess.guess, powiat_id=guess.powiat_id, day_id=day_powiat.id,
            user_id=None, answer=is_correct, elapsed_seconds=guess.elapsed_seconds,
        )
        saved_guess = await PowiatdleGuessRepository(session).add_guess(
            guess_create, guest_id=participation.guest_id, commit=False,
        )
        hint = enhance_guess_with_hint(
            mode="powiatdle", guess_record=saved_guess,
            guess_number=participation.guesses_made,
            max_guesses=POWIATDLE_CONFIG.max_guesses,
            target_id=day_powiat.powiat_id,
            target_name=target_powiat.nazwa if target_powiat else None,
        )
        result = PowiatGuessDisplay(
            id=saved_guess.id, guess=saved_guess.guess, powiat_id=saved_guess.powiat_id,
            elapsed_seconds=getattr(saved_guess, "elapsed_seconds", None),
            answer=saved_guess.answer, guessed_at=saved_guess.guessed_at, **hint,
        )
        token = create_guest_game_token(
            "powiatdle", day_powiat.id, participation.guesses_made,
            guest_game_over(participation, POWIATDLE_CONFIG.max_guesses), participation.won,
        )
        await session.commit()
        response.set_cookie(
            "guest_powiatdle", token, httponly=True, samesite="lax",
            secure=request.url.scheme == "https" or os.getenv("FRIEND_COOKIE_SECURE", "").lower() in {"true", "1", "yes"}, max_age=86400 * 2,
        )
        return result

    state = await get_daily_state(
        session, PowiatdleState, user.id, day_powiat.id,
        POWIATDLE_CONFIG.max_questions, POWIATDLE_CONFIG.max_guesses,
    )
    require_guess_available(state, POWIATDLE_CONFIG.max_guesses)
    current_game_state = db_state_to_game_state(state)

    guess_create = PowiatGuessCreate(
        guess=guess.guess,
        powiat_id=guess.powiat_id,
        day_id=day_powiat.id,
        user_id=user.id,
        answer=is_correct,
        elapsed_seconds=guess.elapsed_seconds,
    )

    new_guess = await PowiatdleGuessRepository(session).add_guess(guess_create, commit=False)

    # Update state
    new_game_state = game_rules.process_guess(current_game_state, is_correct)
    state.remaining_guesses = POWIATDLE_CONFIG.max_guesses - new_game_state.guesses_used
    state.guesses_made += 1
    state.won = new_game_state.is_won
    state.is_game_over = new_game_state.is_game_over

    if state.won:
        streak = (await PowiatdleStateRepository(session).get_current_streak(user.id, day_powiat.date)) + 1
        state.points = await PowiatdleStateRepository(session).calc_points(
            state, elapsed_seconds=guess.elapsed_seconds, streak=streak
        )
    await PowiatdleStateRepository(session).update_state(state, commit=False)

    hint = enhance_guess_with_hint(
        mode="powiatdle",
        guess_record=new_guess,
        guess_number=state.guesses_made,
        max_guesses=POWIATDLE_CONFIG.max_guesses,
        target_id=day_powiat.powiat_id,
        target_name=target_powiat.nazwa if target_powiat else None,
    )
    from datetime import datetime
    result = PowiatGuessDisplay(
        id=int(getattr(new_guess, "id", 0) or 0),
        guess=str(getattr(new_guess, "guess", guess.guess) or guess.guess),
        powiat_id=getattr(new_guess, "powiat_id", guess.powiat_id) if isinstance(getattr(new_guess, "powiat_id", guess.powiat_id), int) else guess.powiat_id,
        answer=is_correct,
        guessed_at=getattr(new_guess, "guessed_at", None) or datetime.now(),
        elapsed_seconds=getattr(new_guess, "elapsed_seconds", None),
        distance_km=hint.get("distance_km"),
        bearing_degrees=hint.get("bearing_degrees"),
        bearing_direction=hint.get("bearing_direction"),
        bearing_arrow=hint.get("bearing_arrow"),
    )
    await session.commit()
    return result
