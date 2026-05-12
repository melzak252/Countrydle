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
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import update
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
            FullQuestionDisplay.model_validate(question)
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
        if game_type != "countrydle":
            return get_local_facts(game_type, entity_id=entity_id or country_id, entity_name=entity_name or country_name)
        if country_name:
            return get_country_facts_by_name(country_name)
        if country_id is None:
            raise HTTPException(status_code=400, detail="country_id or country_name is required")
        return get_country_facts(country_id)
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
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
        daily_country = await CountrydleRepository(session).generate_new_day_country()

    if user is None:
        local_question_create, planned_question = await gutils.analyze_and_answer_locally(
            original_question=question.question,
            day_country=daily_country,
            user=None,
            session=session,
        )
        if local_question_create is not None:
            new_quest = await CountrydleQuestionsRepository(session).create_question(
                local_question_create
            )
            if not local_question_create.valid:
                return InvalidQuestionDisplay.model_validate(new_quest)
            return FullQuestionDisplay.model_validate(new_quest)

        enh_question = gutils.question_enhanced_from_plan(question.question, planned_question)
        if not enh_question.valid:
            question_create = QuestionCreate(
                user_id=None,
                day_id=daily_country.id,
                original_question=enh_question.original_question,
                valid=enh_question.valid,
                question=enh_question.question,
                answer=None,
                explanation=enh_question.explanation or "No explanation provided.",
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

        if question_vector:
            await add_question_to_qdrant(
                new_quest,
                question_vector,
                filter_key="country_id",
                filter_value=daily_country.country_id,
                collection_name="countries_questions",
            )


        return FullQuestionDisplay.model_validate(new_quest)

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

    local_question_create, planned_question = await gutils.analyze_and_answer_locally(
        original_question=question.question,
        day_country=daily_country,
        user=user,
        session=session,
    )
    if local_question_create is not None:
        new_quest = await CountrydleQuestionsRepository(session).create_question(
            local_question_create
        )

        try:
            new_game_state = game_rules.process_question(current_game_state)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        state.remaining_questions = (
            COUNTRYDLE_CONFIG.max_questions - new_game_state.questions_used
        )
        state.questions_asked += 1
        state = await CountrydleStateRepository(session).update_countrydle_state(state)

        if not local_question_create.valid:
            return InvalidQuestionDisplay.model_validate(new_quest)
        return FullQuestionDisplay.model_validate(new_quest)

    enh_question = gutils.question_enhanced_from_plan(question.question, planned_question)
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

    return FullQuestionDisplay.model_validate(new_quest)


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
