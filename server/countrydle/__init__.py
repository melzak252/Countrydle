from db.models import CountrydleState
from db.repositories.question_accounting import (
    consume_question, is_answered, unresolved_question, check_question_available,
    lock_question_state, claim_guest_questions,
)
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
from schemas.countrydle import FullQuestionDisplay
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response
from utils.guest_session import (
    create_guest_game_token, read_guest_game_token, record_guest_action, link_guest_participation,
)
from sqlalchemy.ext.asyncio import AsyncSession
from countrydle import statistics
from db.repositories.guess import (
    CountrydleGuessRepository,
)
from db.repositories.question import (
    CountrydleQuestionsRepository,
)
from db.repositories.country_fact_change_log import CountryFactChangeLogRepository
from qdrant.utils import add_question_to_qdrant
from db.repositories.country import CountryRepository
from users.utils import get_current_or_guest_user, get_current_user, get_admin_user
from schemas.country_facts import (
    CountryFactChangeLogDisplay,
    CountryFactsResponse,
    ListFactCreate,
    ListFactDelete,
    ScalarFactUpdate,
)
from countrydle.fact_editor import (
    add_list_fact,
    add_local_list_fact,
    delete_list_fact,
    delete_local_list_fact,
    get_country_facts,
    get_country_facts_by_name,
    get_local_facts,
    get_local_relation_storage,
    get_relation_storage,
    update_local_scalar_fact,
    update_scalar_fact,
)
from version import SERVER_VERSION

import countrydle.utils as gutils
from game_logic import GameConfig, GameRules, GameState
import json
from utils.geo import enhance_guess_with_hint


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

def format_countrydle_guesses(guesses: list, target_country_id: int, target_name: str | None = None) -> list[GuessDisplay]:
    from datetime import datetime
    formatted = []
    for idx, g in enumerate(guesses):
        hint = enhance_guess_with_hint(
            mode="countrydle",
            guess_record=g,
            guess_number=idx + 1,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses,
            target_id=target_country_id,
            target_name=target_name,
        )
        gd = GuessDisplay(
            id=int(getattr(g, "id", 0) or 0),
            guess=str(getattr(g, "guess", "") or ""),
            country_id=getattr(g, "country_id", None) if isinstance(getattr(g, "country_id", None), int) else None,
            answer=getattr(g, "answer", None) if isinstance(getattr(g, "answer", None), bool) else None,
            guessed_at=getattr(g, "guessed_at", None) or datetime.now(),
            distance_km=hint.get("distance_km"),
            bearing_degrees=hint.get("bearing_degrees"),
            bearing_direction=hint.get("bearing_direction"),
            bearing_arrow=hint.get("bearing_arrow"),
        )
        formatted.append(gd)
    return formatted


@router.post("/sync", response_model=CountrydleStateResponse)
async def sync_guest_data(
    sync_data: CountrydleSyncSchema,
    request: Request,
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
    state = await lock_question_state(session, CountrydleState, user.id, day_country.id)
    
    # BEST SOLUTION: Prioritize Server State
    # If the user already has any progress on the server (at least 1 question or guess),
    # we ignore the guest sync to prevent merging conflicts or exceeding game limits.
    if state.questions_asked > 0 or state.guesses_made > 0:
        linked = await link_guest_participation(session, request, "countrydle", day_country.id, user.id)
        if linked is not None:
            await session.commit()
        return await get_state(user, session)

    country_repo = CountryRepository(session)
    for guess in sync_data.guesses:
        await country_repo.validate_guess(guess.country_id, guess.guess)

    from db.models import CountrydleQuestion
    await claim_guest_questions(
        session, CountrydleQuestion, state, sync_data.questions, COUNTRYDLE_CONFIG.max_questions,
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
        await CountrydleGuessRepository(session).add_guess(guess_create, commit=False)

    # 5. Update state
    state.remaining_guesses = sync_data.state.remaining_guesses
    state.guesses_made = sync_data.state.guesses_made
    state.is_game_over = sync_data.state.is_game_over
    state.won = sync_data.state.won
    
    if state.won:
        from db.repositories.user import UserRepository
        user_points = await UserRepository(session).get_user_points(user.id)
        current_streak = ((user_points.streak if user_points else 0) + 1)
        elapsed = None
        for g in sync_data.guesses:
            if g.elapsed_seconds is not None:
                elapsed = g.elapsed_seconds
                break
        state.points = await CountrydleStateRepository(session).calc_points(
            state, elapsed_seconds=elapsed, streak=current_streak
        )
        
    if state.is_game_over:
        from db.repositories.user import UserRepository
        await UserRepository(session).update_points(user.id, state)
    if state.questions_asked > 0 or state.guesses_made > 0:
        await link_guest_participation(session, request, "countrydle", day_country.id, user.id)
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
        guesses=format_countrydle_guesses(guesses, day_country.country_id, country.name if country else None),
        questions=questions,
    )


@router.get(
    "/state", response_model=Union[CountrydleStateResponse, CountrydleEndStateResponse]
)
async def get_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    day_country = await CountrydleRepository(session).get_today_country()
    if not day_country:
        day_country = await CountrydleRepository(session).generate_new_day_country()

    if user is None:
        if request is not None and response is not None:
            from utils.guest_session import get_guest_identity
            get_guest_identity(request, response)
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
            FullQuestionDisplay.model_validate(question)
            if question.valid
            else InvalidQuestionDisplay.model_validate(question)
        )
        for question in questions
    ]

    country_rec = await CountryRepository(session).get(day_country.country_id)
    response_state = CountrydleStateSchema.model_validate(state)

    return CountrydleStateResponse(
        user=user,
        date=str(day_country.date),
        state=response_state,
        guesses=format_countrydle_guesses(guesses, day_country.country_id, country_rec.name if country_rec else None),
        questions=questions_display,
        country=None,
    )


@router.get("/countries", response_model=list[CountryDisplay])
async def get_countries(
    session: AsyncSession = Depends(get_db),
):
    return await CountryRepository(session).get_all_countries()


@router.get("/admin/questions")
async def get_admin_questions(
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    repository = CountrydleQuestionsRepository(session)
    if limit is None:
        return await repository.get_all_questions()
    items = await repository.get_all_questions(limit=limit, offset=offset)
    total = await repository.count_questions()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _json_value(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


async def _log_country_fact_change(
    *,
    session: AsyncSession,
    admin: User,
    country_id: int,
    relation: str,
    operation: str,
    old_value,
    new_value,
    sqlite_table: str,
    sqlite_column: str,
    note: str | None,
):
    facts = get_country_facts(country_id)
    await CountryFactChangeLogRepository(session).create(
        user_id=admin.id,
        game_type="countrydle",
        entity_id=country_id,
        entity_name=facts["country"]["name"],
        country_id=country_id,
        country_name=facts["country"]["name"],
        relation=relation,
        operation=operation,
        old_value=_json_value(old_value),
        new_value=_json_value(new_value),
        sqlite_table=sqlite_table,
        sqlite_column=sqlite_column,
        note=note,
        server_version=SERVER_VERSION,
    )


async def _log_local_fact_change(
    *,
    session: AsyncSession,
    admin: User,
    game_type: str,
    entity_id: int,
    relation: str,
    operation: str,
    old_value,
    new_value,
    sqlite_table: str,
    sqlite_column: str,
    note: str | None,
):
    facts = get_local_facts(game_type, entity_id=entity_id)
    entity_name = facts["entity"]["name"]
    await CountryFactChangeLogRepository(session).create(
        user_id=admin.id,
        game_type=game_type,
        entity_id=entity_id,
        entity_name=entity_name,
        country_id=entity_id,
        country_name=entity_name,
        relation=relation,
        operation=operation,
        old_value=_json_value(old_value),
        new_value=_json_value(new_value),
        sqlite_table=sqlite_table,
        sqlite_column=sqlite_column,
        note=note,
        server_version=SERVER_VERSION,
    )


@router.get("/admin/country-facts", response_model=CountryFactsResponse)
async def get_admin_country_facts(
    game_type: str = Query("countrydle"),
    entity_id: int | None = Query(None, ge=1),
    entity_name: str | None = Query(None, min_length=1),
    country_id: int | None = Query(None, ge=1),
    country_name: str | None = Query(None, min_length=1),
    admin: User = Depends(get_admin_user),
):
    try:
        resolved_name = country_name or entity_name
        target_id = country_id or entity_id

        if not resolved_name and target_id:
            if game_type == "countrydle":
                c = await CountryRepository(session).get(target_id)
                if c:
                    resolved_name = c.name
            elif game_type == "us_statedle":
                from db.repositories.us_state import USStateRepository
                s = await USStateRepository(session).get(target_id)
                if s:
                    resolved_name = s.name
            elif game_type == "powiatdle":
                from db.repositories.powiatdle import PowiatRepository
                p = await PowiatRepository(session).get(target_id)
                if p:
                    resolved_name = p.nazwa
            elif game_type == "wojewodztwodle":
                from db.repositories.wojewodztwo import WojewodztwoRepository
                w = await WojewodztwoRepository(session).get(target_id)
                if w:
                    resolved_name = w.nazwa

        if game_type != "countrydle":
            return get_local_facts(game_type, entity_id=target_id, entity_name=resolved_name)
        if resolved_name:
            return get_country_facts_by_name(resolved_name)
        if target_id is None:
            raise HTTPException(status_code=400, detail="country_id or country_name is required")
        return get_country_facts(target_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/admin/country-facts/scalar", response_model=CountryFactsResponse)
async def update_admin_country_scalar_fact(
    payload: ScalarFactUpdate,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        if payload.game_type != "countrydle":
            target_id = payload.entity_id or payload.country_id
            if target_id is None:
                raise HTTPException(status_code=400, detail="entity_id or country_id is required")
            old_value, new_value, operation = update_local_scalar_fact(
                payload.game_type,
                target_id,
                payload.relation,
                payload.value,
            )
            sqlite_table, sqlite_column = get_local_relation_storage(payload.game_type, payload.relation, list_relation=False)
            await _log_local_fact_change(
                session=session,
                admin=admin,
                game_type=payload.game_type,
                entity_id=target_id,
                relation=payload.relation,
                operation=operation,
                old_value=old_value,
                new_value=new_value,
                sqlite_table=sqlite_table,
                sqlite_column=sqlite_column,
                note=payload.note,
            )
            return get_local_facts(payload.game_type, entity_id=target_id)
        if payload.country_id is None:
            raise HTTPException(status_code=400, detail="country_id is required")
        old_value, new_value, operation = update_scalar_fact(
            payload.country_id,
            payload.relation,
            payload.value,
        )
        sqlite_table, sqlite_column = get_relation_storage(payload.relation, list_relation=False)
        await _log_country_fact_change(
            session=session,
            admin=admin,
            country_id=payload.country_id,
            relation=payload.relation,
            operation=operation,
            old_value=old_value,
            new_value=new_value,
            sqlite_table=sqlite_table,
            sqlite_column=sqlite_column,
            note=payload.note,
        )
        return get_country_facts(payload.country_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/admin/country-facts/list-values", response_model=CountryFactsResponse)
async def add_admin_country_list_fact(
    payload: ListFactCreate,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        if payload.game_type != "countrydle":
            target_id = payload.entity_id or payload.country_id
            if target_id is None:
                raise HTTPException(status_code=400, detail="entity_id or country_id is required")
            old_value, new_value, operation = add_local_list_fact(
                payload.game_type,
                target_id,
                payload.relation,
                payload.value,
                payload.metadata,
            )
            sqlite_table, sqlite_column = get_local_relation_storage(payload.game_type, payload.relation, list_relation=True)
            await _log_local_fact_change(
                session=session,
                admin=admin,
                game_type=payload.game_type,
                entity_id=target_id,
                relation=payload.relation,
                operation=operation,
                old_value=old_value,
                new_value=new_value,
                sqlite_table=sqlite_table,
                sqlite_column=sqlite_column,
                note=payload.note,
            )
            return get_local_facts(payload.game_type, entity_id=target_id)
        if payload.country_id is None:
            raise HTTPException(status_code=400, detail="country_id is required")
        old_value, new_value, operation = add_list_fact(
            payload.country_id,
            payload.relation,
            payload.value,
            payload.metadata,
        )
        sqlite_table, sqlite_column = get_relation_storage(payload.relation, list_relation=True)
        await _log_country_fact_change(
            session=session,
            admin=admin,
            country_id=payload.country_id,
            relation=payload.relation,
            operation=operation,
            old_value=old_value,
            new_value=new_value,
            sqlite_table=sqlite_table,
            sqlite_column=sqlite_column,
            note=payload.note,
        )
        return get_country_facts(payload.country_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/admin/country-facts/list-values", response_model=CountryFactsResponse)
async def delete_admin_country_list_fact(
    payload: ListFactDelete,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        if payload.game_type != "countrydle":
            target_id = payload.entity_id or payload.country_id
            if target_id is None:
                raise HTTPException(status_code=400, detail="entity_id or country_id is required")
            old_value, new_value, operation = delete_local_list_fact(
                payload.game_type,
                target_id,
                payload.relation,
                payload.value,
            )
            sqlite_table, sqlite_column = get_local_relation_storage(payload.game_type, payload.relation, list_relation=True)
            await _log_local_fact_change(
                session=session,
                admin=admin,
                game_type=payload.game_type,
                entity_id=target_id,
                relation=payload.relation,
                operation=operation,
                old_value=old_value,
                new_value=new_value,
                sqlite_table=sqlite_table,
                sqlite_column=sqlite_column,
                note=payload.note,
            )
            return get_local_facts(payload.game_type, entity_id=target_id)
        if payload.country_id is None:
            raise HTTPException(status_code=400, detail="country_id is required")
        old_value, new_value, operation = delete_list_fact(
            payload.country_id,
            payload.relation,
            payload.value,
        )
        sqlite_table, sqlite_column = get_relation_storage(payload.relation, list_relation=True)
        await _log_country_fact_change(
            session=session,
            admin=admin,
            country_id=payload.country_id,
            relation=payload.relation,
            operation=operation,
            old_value=old_value,
            new_value=new_value,
            sqlite_table=sqlite_table,
            sqlite_column=sqlite_column,
            note=payload.note,
        )
        return get_country_facts(payload.country_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/admin/country-facts/change-log", response_model=list[CountryFactChangeLogDisplay])
async def get_admin_country_fact_change_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    return await CountryFactChangeLogRepository(session).get_recent(limit=limit, offset=offset)


@router.post("/question", response_model=Union[FullQuestionDisplay, InvalidQuestionDisplay])
async def ask_question(
    question: QuestionBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await _do_ask_question(question, user, session, request, response)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        import logging, traceback
        logging.getLogger("countrydle").error("Handled error in ask_question: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify this question right now. Your turn was not deducted.",
        ) from exc


async def _do_ask_question(
    question: QuestionBase,
    user: User | None,
    session: AsyncSession,
    request: Request,
    response: Response,
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
        daily_country = await CountrydleRepository(session).generate_new_day_country()

    if user is not None:
        await check_question_available(
            session, CountrydleState, user.id, daily_country.id, COUNTRYDLE_CONFIG.max_questions,
        )

    # End the quota/day read transaction before planner or provider work.
    await session.commit()

    question_create, planned_question = await gutils.analyze_and_answer_locally(
        original_question=question.question, day_country=daily_country, user=user, session=session,
    )
    question_vector = None
    if question_create is None:
        enhanced = gutils.question_enhanced_from_plan(question.question, planned_question)
        if not enhanced.valid:
            question_create = QuestionCreate(
                user_id=user.id if user else None,
                day_id=daily_country.id,
                original_question=question.question,
                question=enhanced.question,
                valid=False,
                answer=None,
                explanation=enhanced.explanation,
                context=None,
            )
        else:
            question_create, question_vector = await gutils.ask_question(
                question=enhanced, day_country=daily_country, user=user, session=session,
            )
    if question_create.valid and question_create.answer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify this question right now. Your turn was not deducted.",
        )

    if not is_answered(question_create):
        return unresolved_question(question_create, InvalidQuestionDisplay)

    question_create.user_id = user.id if user else None
    question_create.day_id = daily_country.id
    if user is None:
        await record_guest_action(
            session, request, response, "countrydle", daily_country.id,
            question=True, max_questions=COUNTRYDLE_CONFIG.max_questions,
        )
    else:
        await consume_question(
            session, CountrydleState, user.id, daily_country.id,
            COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
        )
    new_question = await CountrydleQuestionsRepository(session).create_question(question_create)
    result = FullQuestionDisplay.model_validate(new_question)
    await session.commit()
    if question_vector:
        # Indexing is auxiliary: an already committed answer remains successful.
        try:
            await add_question_to_qdrant(
                new_question, question_vector, filter_key="country_id",
                filter_value=daily_country.country_id, collection_name="countries_questions",
            )
        except Exception:
            import logging
            logging.getLogger("countrydle").exception("Could not index accepted countrydle question")
    return result


@router.get("/reveal", response_model=CountryDisplay)
async def reveal_country(
    request: Request,
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
    else:
        cookie = request.cookies.get("guest_countrydle")
        guest_state = read_guest_game_token(cookie, "countrydle", day_country.id)
        if not guest_state["is_game_over"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal country before game is over.",
            )
            
    country = await CountryRepository(session).get(day_country.country_id)
    return country

@router.post("/guess", response_model=GuessDisplay)
async def make_guess(
    guess: GuessBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    await CountryRepository(session).validate_guess(guess.country_id, guess.guess)
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
        daily_country = await CountrydleRepository(session).generate_new_day_country()
    target_country = await CountryRepository(session).get(daily_country.country_id)

    # Check if guess is correct (by ID or by case-insensitive name match)
    is_correct = False
    if guess.country_id is not None and guess.country_id > 0:
        is_correct = guess.country_id == daily_country.country_id
    if not is_correct and guess.guess and target_country:
        guessed_clean = guess.guess.strip().lower()
        target_clean = target_country.name.strip().lower()
        official_clean = (target_country.official_name or "").strip().lower()
        is_correct = (guessed_clean == target_clean) or (guessed_clean == official_clean)
        if is_correct:
            guess.country_id = daily_country.country_id

    guess_num = 1
    if user is None:
        cookie = request.cookies.get("guest_countrydle")
        guest_state = read_guest_game_token(cookie, "countrydle", daily_country.id)
        guesses_count = guest_state["guesses_count"] + 1
        guess_num = guesses_count
        won = is_correct
        is_game_over = is_correct or (guesses_count >= COUNTRYDLE_CONFIG.max_guesses)
        token = create_guest_game_token("countrydle", daily_country.id, guesses_count, is_game_over, won)
        response.set_cookie("guest_countrydle", token, httponly=True, samesite="lax", max_age=86400 * 2)

        guess_create = GuessCreate(
            guess=guess.guess,
            country_id=guess.country_id,
            day_id=daily_country.id,
            user_id=None,
            answer=is_correct,
            elapsed_seconds=guess.elapsed_seconds,
        )
        await record_guest_action(session, request, response, "countrydle", daily_country.id, won=is_correct)
        saved_guess = await CountrydleGuessRepository(session).add_guess(guess_create)

        hint = enhance_guess_with_hint(
            mode="countrydle",
            guess_record=saved_guess,
            guess_number=guess_num,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses,
            target_id=daily_country.country_id,
            target_name=target_country.name if target_country else None,
        )

        from datetime import datetime
        return GuessDisplay(
            id=int(getattr(saved_guess, "id", 0) or 0),
            guess=str(getattr(saved_guess, "guess", guess.guess) or guess.guess),
            country_id=guess.country_id,
            answer=saved_guess.answer,
            guessed_at=getattr(saved_guess, "guessed_at", None) or datetime.now(),
            **hint,
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

    guess_num = state.guesses_made + 1

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
    await CountrydleStateRepository(session).guess_made(
        state, new_guess, elapsed_seconds=guess.elapsed_seconds
    )

    hint = enhance_guess_with_hint(
        mode="countrydle",
        guess_record=new_guess,
        guess_number=guess_num,
        max_guesses=COUNTRYDLE_CONFIG.max_guesses,
        target_id=daily_country.country_id,
        target_name=target_country.name if target_country else None,
    )

    from datetime import datetime
    return GuessDisplay(
        id=int(getattr(new_guess, "id", 0) or 0),
        guess=str(getattr(new_guess, "guess", guess.guess) or guess.guess),
        country_id=getattr(new_guess, "country_id", guess.country_id) if isinstance(getattr(new_guess, "country_id", guess.country_id), int) else guess.country_id,
        answer=is_correct,
        guessed_at=getattr(new_guess, "guessed_at", None) or datetime.now(),
        distance_km=hint.get("distance_km"),
        bearing_degrees=hint.get("bearing_degrees"),
        bearing_direction=hint.get("bearing_direction"),
        bearing_arrow=hint.get("bearing_arrow"),
    )
