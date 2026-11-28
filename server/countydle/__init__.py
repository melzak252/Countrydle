from datetime import datetime
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import countydle.utils as cutils
from db import get_db
from db.models import CountydleQuestion, CountydleState, User
from db.repositories.countydle import (
    CountydleDayRepository,
    CountydleGuessRepository,
    CountydleQuestionRepository,
    CountydleStateRepository,
)
from db.repositories.english_county import EnglishCountyRepository
from db.repositories.question_accounting import (
    claim_guest_questions,
    consume_question,
    is_answered,
    lock_question_state,
    require_question_available,
    unresolved_question,
)
from game_logic import COUNTYDLE_CONFIG, GameRules, GameState, is_valid_synced_game_state
from local_kb_question import _build_local_kb_clarification
from schemas.countrydle import LeaderboardEntry
from schemas.countydle import (
    CountydleEndStateResponse,
    CountydleStateResponse,
    CountydleStateSchema,
    CountydleSyncSchema,
    DayEnglishCountyDisplay,
    EnglishCountyDisplay,
    EnglishCountyGuessBase,
    EnglishCountyGuessCreate,
    EnglishCountyGuessDisplay,
    EnglishCountyQuestionBase,
    EnglishCountyQuestionCreate,
    EnglishCountyQuestionDisplay,
)
from users.utils import get_admin_user, get_current_or_guest_user, get_current_user
from utils.geo import enhance_guess_with_hint
from utils.guest_session import (
    create_guest_game_token,
    get_guest_identity,
    link_guest_participation,
    read_guest_game_token,
    record_guest_action,
)
from utils.question_rate_limit import enforce_question_attempt_limit

router = APIRouter(prefix="/countydle")

game_rules = GameRules(COUNTYDLE_CONFIG)


def db_state_to_game_state(db_state) -> GameState:
    return GameState(
        questions_used=db_state.questions_asked,
        guesses_used=db_state.guesses_made,
        is_won=db_state.won,
        is_lost=db_state.is_game_over and not db_state.won,
    )


def _player_question_display(
    question, *, terminal: bool = False, clarification: str | None = None
) -> EnglishCountyQuestionDisplay:
    # Serialize scalar fields only and redact factual explanations until game over.
    payload = {
        field: getattr(question, field, None)
        for field in (
            "id",
            "original_question",
            "question",
            "valid",
            "answer",
            "clarification",
            "user_id",
            "day_id",
            "asked_at",
            "explanation",
        )
    }
    if payload.get("asked_at") is None:
        payload["asked_at"] = datetime.now()
    if clarification is not None:
        payload["clarification"] = clarification
    return EnglishCountyQuestionDisplay.model_validate(
        payload,
        context={"terminal": terminal},
    )


def format_county_guesses(
    guesses: list, target_county_id: int, target_name: str | None = None
) -> list[EnglishCountyGuessDisplay]:
    formatted = []
    for idx, g in enumerate(guesses):
        hint = enhance_guess_with_hint(
            mode="countydle",
            guess_record=g,
            guess_number=idx + 1,
            max_guesses=COUNTYDLE_CONFIG.max_guesses,
            target_id=target_county_id,
            target_name=target_name,
        )
        gd = EnglishCountyGuessDisplay(
            id=int(getattr(g, "id", 0) or 0),
            guess=str(getattr(g, "guess", "") or ""),
            county_id=(
                getattr(g, "county_id", None)
                if isinstance(getattr(g, "county_id", None), int)
                else None
            ),
            answer=bool(
                getattr(g, "answer", False)
                if isinstance(getattr(g, "answer", False), bool)
                else False
            ),
            guessed_at=getattr(g, "guessed_at", None) or datetime.now(),
            distance_km=hint.get("distance_km"),
            bearing_degrees=hint.get("bearing_degrees"),
            bearing_direction=hint.get("bearing_direction"),
            bearing_arrow=hint.get("bearing_arrow"),
        )
        formatted.append(gd)
    return formatted


async def normalize_state_limits(state, session: AsyncSession):
    expected_questions = max(0, COUNTYDLE_CONFIG.max_questions - state.questions_asked)
    expected_guesses = max(0, COUNTYDLE_CONFIG.max_guesses - state.guesses_made)
    if (
        state.remaining_questions != expected_questions
        or state.remaining_guesses != expected_guesses
    ):
        state = await lock_question_state(session, CountydleState, state.user_id, state.day_id)
        state.remaining_questions = max(0, COUNTYDLE_CONFIG.max_questions - state.questions_asked)
        state.remaining_guesses = max(0, COUNTYDLE_CONFIG.max_guesses - state.guesses_made)
        await CountydleStateRepository(session).update_state(state)
    return state


@router.post("/sync", response_model=CountydleStateResponse)
async def sync_guest_data(
    sync_data: CountydleSyncSchema,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        game_date = datetime.strptime(sync_data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    day_state = await CountydleDayRepository(session).get_day_county_by_date(game_date)
    if not day_state:
        raise HTTPException(status_code=404, detail="Game for this date not found.")

    state = await CountydleStateRepository(session).get_state(user, day_state)
    if state is None:
        state = await CountydleStateRepository(session).create_state(
            user,
            day_state,
            max_questions=COUNTYDLE_CONFIG.max_questions,
            max_guesses=COUNTYDLE_CONFIG.max_guesses,
        )
    state = await lock_question_state(session, CountydleState, user.id, day_state.id) or state

    if state.questions_asked > 0 or state.guesses_made > 0:
        linked = await link_guest_participation(session, request, "countydle", day_state.id, user.id)
        if linked is not None:
            await session.commit()
        return await get_state(user, session)

    sync_state = getattr(sync_data, "state", None)
    if sync_state is not None and not is_valid_synced_game_state(
        COUNTYDLE_CONFIG,
        guesses_made=sync_state.guesses_made,
        remaining_guesses=sync_state.remaining_guesses,
        is_game_over=sync_state.is_game_over,
        won=sync_state.won,
        correct_guesses=[
            guess.county_id == day_state.county_id for guess in sync_data.guesses
        ],
        questions_asked=sync_state.questions_asked,
        remaining_questions=sync_state.remaining_questions,
        synced_questions=len(sync_data.questions),
    ):
        raise HTTPException(
            status_code=400, detail="Guest game state does not match its saved progress."
        )

    from db.models import CountydleGuess
    from db.repositories.question_accounting import claim_guest_guesses
    from utils.guest_session import read_guest_identity
    await claim_guest_questions(
        session,
        CountydleQuestion,
        state,
        sync_data.questions,
        COUNTYDLE_CONFIG.max_questions,
    )

    claimed_guess_ids = await claim_guest_guesses(
        session, CountydleGuess, user.id, day_state.id, read_guest_identity(request), COUNTYDLE_CONFIG.max_guesses,
    )
    for guess in sync_data.guesses[len(claimed_guess_ids):]:
        is_correct = False
        if guess.county_id:
            is_correct = guess.county_id == day_state.county_id

        guess_create = EnglishCountyGuessCreate(
            guess=guess.guess,
            county_id=guess.county_id,
            day_id=day_state.id,
            user_id=user.id,
            answer=is_correct,
        )
        await CountydleGuessRepository(session).add_guess(guess_create, commit=False)

    state.remaining_guesses = sync_data.state.remaining_guesses
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won

    if state.won:
        streak = (
            await CountydleStateRepository(session).get_current_streak(user.id, day_state.date)
        ) + 1
        elapsed = sync_data.guesses[-1].elapsed_seconds if sync_data.guesses else None
        state.points = await CountydleStateRepository(session).calc_points(
            state, elapsed_seconds=elapsed, streak=streak
        )
    if state.questions_asked > 0 or state.guesses_made > 0:
        await link_guest_participation(session, request, "countydle", day_state.id, user.id)
    await CountydleStateRepository(session).update_state(state)

    return await get_state(user, session)


@router.get("/history", response_model=List[DayEnglishCountyDisplay])
async def get_history(session: AsyncSession = Depends(get_db)):
    return await CountydleDayRepository(session).get_history()


@router.get(
    "/state",
    response_model=Union[CountydleStateResponse, CountydleEndStateResponse],
)
async def get_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    day_state = await CountydleDayRepository(session).get_today_county()
    if not day_state:
        day_state = await CountydleDayRepository(session).generate_new_day_county()

    if user is None:
        if request is not None and response is not None:
            get_guest_identity(request, response)
        return CountydleStateResponse(
            user=None,
            date=str(day_state.date),
            state=CountydleStateSchema(
                id=0,
                user_id=0,
                day_id=day_state.id,
                remaining_questions=COUNTYDLE_CONFIG.max_questions,
                remaining_guesses=COUNTYDLE_CONFIG.max_guesses,
                questions_asked=0,
                guesses_made=0,
                is_game_over=False,
                won=False,
                points=0,
            ),
            guesses=[],
            questions=[],
            county=None,
        )

    state = await CountydleStateRepository(session).get_state(user, day_state)
    if state is None:
        state = await CountydleStateRepository(session).create_state(
            user,
            day_state,
            max_questions=COUNTYDLE_CONFIG.max_questions,
            max_guesses=COUNTYDLE_CONFIG.max_guesses,
        )

    state = await normalize_state_limits(state, session)

    guesses = await CountydleGuessRepository(session).get_user_day_guesses(user, day_state)
    questions = await CountydleQuestionRepository(session).get_user_day_questions(user, day_state)
    county_rec = await EnglishCountyRepository(session).get(day_state.county_id)

    if state.is_game_over:
        return CountydleEndStateResponse(
            user=user,
            date=str(day_state.date),
            state=CountydleStateSchema.model_validate(state),
            guesses=format_county_guesses(
                guesses, day_state.county_id, county_rec.name if county_rec else None
            ),
            questions=[_player_question_display(q, terminal=True) for q in questions],
            county=county_rec,
        )

    questions_display = [
        _player_question_display(question, terminal=False) for question in questions
    ]

    return CountydleStateResponse(
        user=user,
        date=str(day_state.date),
        state=CountydleStateSchema.model_validate(state),
        guesses=format_county_guesses(
            guesses, day_state.county_id, county_rec.name if county_rec else None
        ),
        questions=questions_display,
        county=None,
    )


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(type: str = "monthly", session: AsyncSession = Depends(get_db)):
    return await CountydleStateRepository(session).get_leaderboard(type)


@router.get("/counties", response_model=List[EnglishCountyDisplay])
async def get_counties(session: AsyncSession = Depends(get_db)):
    return await EnglishCountyRepository(session).get_all()


@router.get("/admin/questions")
async def get_admin_questions(
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    repository = CountydleQuestionRepository(session)
    if limit is None:
        return await repository.get_all_questions()
    items = await repository.get_all_questions(limit=limit, offset=offset)
    total = await repository.count_questions()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post(
    "/question",
    response_model=EnglishCountyQuestionDisplay,
    dependencies=[Depends(enforce_question_attempt_limit)],
)
async def ask_question(
    question: EnglishCountyQuestionBase,
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
        import logging
        import traceback

        logging.getLogger("countrydle").error(
            "Handled error in countydle ask_question: %s\n%s",
            exc,
            traceback.format_exc(),
        )
        return EnglishCountyQuestionDisplay(
            id=0,
            original_question=question.question,
            question=question.question,
            valid=False,
            answer=None,
            explanation="This question could not be verified right now. Your attempt was not used.",
            asked_at=datetime.now(),
            user_id=user_id,
            day_id=0,
        )


async def _do_ask_question(
    question: EnglishCountyQuestionBase,
    user: User | None,
    session: AsyncSession,
    request: Request,
    response: Response,
):
    day_state = await CountydleDayRepository(session).get_today_county()
    if not day_state:
        day_state = await CountydleDayRepository(session).generate_new_day_county()
    if user is not None:
        state = await CountydleStateRepository(session).get_state(user, day_state)
        require_question_available(state, COUNTYDLE_CONFIG.max_questions)

    await session.commit()

    question_create, planned_question = await cutils.analyze_and_answer_locally(
        question.question, day_state, user, session
    )
    if question_create is None:
        enhanced = cutils.question_enhanced_from_plan(question.question, planned_question)
        if not enhanced.valid:
            question_create = EnglishCountyQuestionCreate(
                user_id=user.id if user else None,
                day_id=day_state.id,
                original_question=question.question,
                question=enhanced.question,
                valid=False,
                answer=None,
                explanation=enhanced.explanation,
                context=None,
            )
        else:
            question_create, _ = await cutils.ask_question(enhanced, day_state, user, session)

    if not is_answered(question_create):
        return unresolved_question(question_create, EnglishCountyQuestionDisplay)

    question_create.user_id = user.id if user else None
    question_create.day_id = day_state.id
    if user is None:
        await record_guest_action(
            session,
            request,
            response,
            "countydle",
            day_state.id,
            question=True,
            max_questions=COUNTYDLE_CONFIG.max_questions,
        )
    else:
        await consume_question(
            session,
            CountydleState,
            user.id,
            day_state.id,
            COUNTYDLE_CONFIG.max_questions,
            COUNTYDLE_CONFIG.max_guesses,
        )
    new_question = await CountydleQuestionRepository(session).create_question(question_create)
    clarification = None
    if (
        planned_question is not None
        and getattr(planned_question, "valid", False)
        and getattr(planned_question, "supported", False)
        and isinstance(question_create.answer, bool)
    ):
        clarification = _build_local_kb_clarification(
            cutils.LOCAL_CONFIG, planned_question, question_create.answer
        )
    result = _player_question_display(new_question, terminal=False, clarification=clarification)
    map_highlight = question_create.map_highlight
    if map_highlight is None and question_create.valid and question_create.answer in (True, False):
        from schemas.countrydle import MapHighlight
        map_highlight = MapHighlight(
            supported=False,
            note="Couldn't auto-color all matching counties for this question; mark the map manually.",
        )
    result.map_highlight = map_highlight
    await session.commit()
    return result


@router.get("/reveal", response_model=EnglishCountyDisplay)
async def reveal_county(
    request: Request,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await CountydleDayRepository(session).get_today_county()
    if not day_state:
        day_state = await CountydleDayRepository(session).generate_new_day_county()
    if not day_state:
        raise HTTPException(status_code=404, detail="No game today")

    if user is not None:
        state = await CountydleStateRepository(session).get_state(user, day_state)
        if state and not state.is_game_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal county before game is over.",
            )
    else:
        cookie = request.cookies.get("guest_countydle")
        guest_state = read_guest_game_token(cookie, "countydle", day_state.id)
        if not guest_state["is_game_over"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal county before game is over.",
            )

    county = await EnglishCountyRepository(session).get(day_state.county_id)
    return county


@router.post("/guess", response_model=EnglishCountyGuessDisplay)
async def make_guess(
    guess: EnglishCountyGuessBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    day_state = await CountydleDayRepository(session).get_today_county()
    if not day_state:
        day_state = await CountydleDayRepository(session).generate_new_day_county()

    target_county = await EnglishCountyRepository(session).get(day_state.county_id)

    is_correct = False
    if guess.county_id:
        is_correct = guess.county_id == day_state.county_id
    if not is_correct and guess.guess and target_county:
        is_correct = guess.guess.strip().lower() == target_county.name.strip().lower()
        if is_correct:
            guess.county_id = day_state.county_id

    if user is None:
        cookie = request.cookies.get("guest_countydle")
        guest_state = read_guest_game_token(cookie, "countydle", day_state.id)
        guesses_count = guest_state["guesses_count"] + 1
        won = is_correct
        is_game_over = is_correct or (guesses_count >= COUNTYDLE_CONFIG.max_guesses)
        token = create_guest_game_token(
            "countydle", day_state.id, guesses_count, is_game_over, won
        )
        response.set_cookie(
            "guest_countydle", token, httponly=True, samesite="lax", max_age=86400 * 2
        )

        guess_create = EnglishCountyGuessCreate(
            guess=guess.guess,
            county_id=guess.county_id,
            day_id=day_state.id,
            user_id=None,
            answer=is_correct,
            elapsed_seconds=guess.elapsed_seconds,
        )
        await record_guest_action(
            session, request, response, "countydle", day_state.id, won=is_correct
        )
        saved_guess = await CountydleGuessRepository(session).add_guess(guess_create)

        hint = enhance_guess_with_hint(
            mode="countydle",
            guess_record=saved_guess,
            guess_number=guesses_count,
            max_guesses=COUNTYDLE_CONFIG.max_guesses,
            target_id=day_state.county_id,
            target_name=target_county.name if target_county else None,
        )

        return EnglishCountyGuessDisplay(
            id=saved_guess.id,
            guess=saved_guess.guess,
            county_id=saved_guess.county_id,
            answer=saved_guess.answer,
            guessed_at=saved_guess.guessed_at,
            **hint,
        )

    state = await CountydleStateRepository(session).get_state(user, day_state)
    if state is None:
        state = await CountydleStateRepository(session).create_state(
            user,
            day_state,
            max_questions=COUNTYDLE_CONFIG.max_questions,
            max_guesses=COUNTYDLE_CONFIG.max_guesses,
        )

    current_game_state = db_state_to_game_state(state)
    if not game_rules.can_make_guess(current_game_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more guesses left or game over!",
        )

    guess_create = EnglishCountyGuessCreate(
        guess=guess.guess,
        county_id=guess.county_id,
        day_id=day_state.id,
        user_id=user.id,
        answer=is_correct,
    )
    new_guess = await CountydleGuessRepository(session).add_guess(guess_create)

    new_game_state = game_rules.process_guess(current_game_state, is_correct)
    state.remaining_guesses = COUNTYDLE_CONFIG.max_guesses - new_game_state.guesses_used
    state.guesses_made += 1
    state.won = new_game_state.is_won
    state.is_game_over = new_game_state.is_game_over

    if state.won:
        streak = (
            await CountydleStateRepository(session).get_current_streak(user.id, day_state.date)
        ) + 1
        state.points = await CountydleStateRepository(session).calc_points(
            state, elapsed_seconds=guess.elapsed_seconds, streak=streak
        )
    await CountydleStateRepository(session).update_state(state)

    hint = enhance_guess_with_hint(
        mode="countydle",
        guess_record=new_guess,
        guess_number=state.guesses_made,
        max_guesses=COUNTYDLE_CONFIG.max_guesses,
        target_id=day_state.county_id,
        target_name=target_county.name if target_county else None,
    )
    return EnglishCountyGuessDisplay(
        id=int(getattr(new_guess, "id", 0) or 0),
        guess=str(getattr(new_guess, "guess", guess.guess) or guess.guess),
        county_id=(
            getattr(new_guess, "county_id", guess.county_id)
            if isinstance(getattr(new_guess, "county_id", guess.county_id), int)
            else guess.county_id
        ),
        answer=is_correct,
        guessed_at=getattr(new_guess, "guessed_at", None) or datetime.now(),
        distance_km=hint.get("distance_km"),
        bearing_degrees=hint.get("bearing_degrees"),
        bearing_direction=hint.get("bearing_direction"),
        bearing_arrow=hint.get("bearing_arrow"),
    )
