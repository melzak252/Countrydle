from db.models import CountrydleState, CountrydleGuess, CountrydleQuestion
from datetime import UTC, datetime
import logging
import os
from utils.country_cost_metrics import append_metrics
from db.repositories.question_accounting import (
    consume_question, is_answered, unresolved_question, check_question_available,
    get_daily_state, require_guess_available,
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
    create_guest_game_token, record_guest_action, guest_game_over,
    get_guest_identity, check_guest_question_available, get_guest_progress, claim_guest_history,
)
from utils.question_rate_limit import enforce_question_attempt_limit

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
    FactProvenanceUpdate,
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
    update_fact_provenance,
)
from version import SERVER_VERSION

import countrydle.utils as gutils
from game_logic import GameConfig
import json
from utils.geo import enhance_guess_with_hint


load_dotenv()

router = APIRouter(prefix="/countrydle")

router.include_router(statistics.router)

# Konfiguracja zasad gry Countrydle
COUNTRYDLE_CONFIG = GameConfig(max_questions=10, max_guesses=3)

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
            elapsed_seconds=getattr(g, "elapsed_seconds", None),
            distance_km=hint.get("distance_km"),
            bearing_degrees=hint.get("bearing_degrees"),
            bearing_direction=hint.get("bearing_direction"),
            bearing_arrow=hint.get("bearing_arrow"),
        )
        formatted.append(gd)
    return formatted


def _player_question_display(question, *, terminal=False) -> FullQuestionDisplay:
    # Public history needs scalar answer fields, not lazy user/target relationships.
    return FullQuestionDisplay.model_validate(
        {field: getattr(question, field) for field in (
            "id", "original_question", "question", "valid", "answer", "user_id",
            "day_id", "asked_at", "explanation", "fact_provenance",
        )},
        context={"terminal": terminal},
    )


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

    try:
        state = await get_daily_state(
            session, CountrydleState, user.id, day_country.id,
            COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
        )
        imported = await claim_guest_history(
            session, request, state, "countrydle", CountrydleGuess, CountrydleQuestion,
            COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
            validate_original_guess=CountryRepository(session).validate_guess,
        )
        if imported and state.won:
            guesses = await CountrydleGuessRepository(session).get_user_day_guesses(user, day_country)
            streak = (await CountrydleStateRepository(session).get_current_streak(user.id, day_country.date)) + 1
            elapsed = guesses[-1].elapsed_seconds if guesses else None
            state.points = await CountrydleStateRepository(session).calc_points(
                state, elapsed_seconds=elapsed, streak=streak,
            )
        if imported and state.is_game_over:
            from db.repositories.user import UserRepository
            await UserRepository(session).update_points(user.id, state, commit=False)
        await CountrydleStateRepository(session).update_countrydle_state(state, commit=False)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return await get_state(user=user, session=session, request=request)


@router.get("/end/state", response_model=Union[CountrydleEndStateResponse, CountrydleStateResponse])
async def get_end_state(
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    result = await get_state(user=user, session=session, request=request, response=response)
    if not result.state.is_game_over:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target country is only available after the game is over.",
        )
    return result


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

    country_rec = await CountryRepository(session).get(day_country.country_id)
    if user is None:
        participation, guesses, questions = await get_guest_progress(
            session, request, response, "countrydle", day_country.id,
            CountrydleGuess, CountrydleQuestion,
        )
        guesses_made = participation.guesses_made if participation else 0
        questions_asked = participation.questions_asked if participation else 0
        terminal = guest_game_over(participation, COUNTRYDLE_CONFIG.max_guesses)
        guest_state = CountrydleStateSchema(
            remaining_questions=max(0, COUNTRYDLE_CONFIG.max_questions - questions_asked),
            remaining_guesses=max(0, COUNTRYDLE_CONFIG.max_guesses - guesses_made),
            questions_asked=questions_asked, guesses_made=guesses_made,
            is_game_over=terminal, won=bool(participation and participation.won),
        )
        return CountrydleStateResponse(
            user=None, date=str(day_country.date), state=guest_state,
            guesses=format_countrydle_guesses(guesses, day_country.country_id, country_rec.name if country_rec else None),
            questions=[_player_question_display(q, terminal=terminal) for q in questions],
            country=country_rec if terminal else None,
        )

    state = await get_daily_state(
        session, CountrydleState, user.id, day_country.id,
        COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
    )
    await session.commit()
    guesses = await CountrydleGuessRepository(session).get_user_day_guesses(user, day_country)
    questions = await CountrydleQuestionsRepository(session).get_user_day_questions(user, day_country)

    questions_display = [
        (
            _player_question_display(question, terminal=state.is_game_over)
            if question.valid
            else InvalidQuestionDisplay.model_validate(question)
        )
        for question in questions
    ]

    if state.is_game_over:
        return CountrydleEndStateResponse(
            user=user, date=str(day_country.date), country=country_rec,
            state=CountrydleEndStateSchema.model_validate(state),
            guesses=format_countrydle_guesses(guesses, day_country.country_id, country_rec.name if country_rec else None),
            questions=questions_display,
        )
    response_state = CountrydleStateSchema.model_validate(state)

    return CountrydleStateResponse(
        user=user,
        date=str(day_country.date),
        state=response_state,
        guesses=format_countrydle_guesses(guesses, day_country.country_id, country_rec.name if country_rec else None),
        questions=questions_display,
        country=country_rec if state.is_game_over else None,
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
    session: AsyncSession = Depends(get_db),
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


@router.patch("/admin/country-facts/provenance", response_model=CountryFactsResponse)
async def update_admin_fact_provenance(
    payload: FactProvenanceUpdate,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        old, new, operation = update_fact_provenance(
            payload.country_id, payload.relation, payload.value,
            payload.provenance.model_dump(mode="json"),
        )
        await _log_country_fact_change(
            session=session, admin=admin, country_id=payload.country_id,
            relation=payload.relation, operation=operation, old_value=old, new_value=new,
            sqlite_table="country_fact_provenance", sqlite_column="provenance_json", note=payload.note,
        )
        return get_country_facts(payload.country_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.post(
    "/question",
    response_model=Union[FullQuestionDisplay, InvalidQuestionDisplay],
    dependencies=[Depends(enforce_question_attempt_limit)],
)
async def ask_question(
    question: QuestionBase,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    evidence: dict = {}
    handler_started = datetime.now(UTC)
    measurement = {
        "day": handler_started.date().isoformat(),
        "started_at": handler_started.isoformat(),
        "stage": "route",
        "requests": 1,
    }
    accepted_result = None
    failure_status = None
    try:
        accepted_result = await _do_ask_question(
            question, user, session, request, response, evidence
        )
        return accepted_result
    except HTTPException as exc:
        failure_status = exc.status_code
        await session.rollback()
        raise
    except Exception as exc:
        failure_status = status.HTTP_503_SERVICE_UNAVAILABLE
        await session.rollback()
        logging.getLogger("countrydle").error("Handled error in ask_question (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify this question right now. Your turn was not deducted.",
        ) from exc
    finally:
        if accepted_result is not None:
            if getattr(accepted_result, "valid", False) and getattr(accepted_result, "answer", None) in (True, False):
                measurement["answered"] = 1
                if evidence.get("template_answered"):
                    measurement["template_answers"] = 1
            else:
                measurement["invalid"] = 1
        if failure_status == status.HTTP_400_BAD_REQUEST:
            measurement["quota_failures"] = 1
        elif failure_status == status.HTTP_503_SERVICE_UNAVAILABLE:
            measurement["provider_failures"] = 1
        _record_countrydle_cost_measurements(measurement, evidence)


def _record_countrydle_cost_measurements(measurement: dict, evidence: dict) -> None:
    """Write only bounded event labels and observed numeric provider usage."""
    try:
        append_metrics({**measurement, "template_answers": 0})
        if measurement.get("template_answers"):
            append_metrics({
                "day": measurement["day"], "stage": "template",
                "template_answers": measurement["template_answers"],
            })
        for stage in ("planner", "fallback"):
            stage_data = evidence.get(stage) or {}
            attempts = stage_data.get("attempts") or []
            if not attempts:
                if stage_data.get("cache_hit"):
                    append_metrics({
                        "day": measurement["day"], "model": stage_data.get("model"), "stage": stage,
                        "plan_cache_hits": int(stage == "planner"),
                        "fallback_cache_hits": int(stage == "fallback"),
                    })
                continue
            for index, attempt in enumerate(attempts):
                event = {
                    "day": measurement["day"],
                    "model": attempt.get("model") or stage_data.get("model"),
                    "stage": stage,
                    "new_planner_calls": int(stage == "planner" and index == 0),
                    "fallback_model_calls": int(stage == "fallback"),
                    "retries": int(index > 0),
                    "failed_attempts": int(bool(attempt.get("failed"))),
                }
                usage = attempt.get("usage")
                if not isinstance(usage, dict):
                    event["unknown_usage_calls"] = 1
                else:
                    if usage.get("input_tokens") is None or usage.get("total_tokens") is None:
                        event["unknown_usage_calls"] = 1
                    if usage.get("cached_input_tokens") is None and isinstance(usage.get("input_tokens"), int):
                        event["cached_input_unknown_tokens"] = usage["input_tokens"]
                    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "thought_tokens", "total_tokens"):
                        value = usage.get(key)
                        if isinstance(value, int) and value >= 0:
                            event[key] = value
                append_metrics(event)
    except Exception as exc:
        logging.getLogger("countrydle.cost_metrics").warning(
            "Could not persist Countrydle cost measurement (%s)", type(exc).__name__
        )


async def _do_ask_question(
    question: QuestionBase,
    user: User | None,
    session: AsyncSession,
    request: Request,
    response: Response,
    evidence: dict | None = None,
):
    daily_country = await CountrydleRepository(session).get_today_country()
    if not daily_country:
        daily_country = await CountrydleRepository(session).generate_new_day_country()

    if user is not None:
        await check_question_available(
            session, CountrydleState, user.id, daily_country.id, COUNTRYDLE_CONFIG.max_questions,
        )
    else:
        await check_guest_question_available(
            session, request, response, "countrydle", daily_country.id,
            COUNTRYDLE_CONFIG.max_questions, max_guesses=COUNTRYDLE_CONFIG.max_guesses,
        )

    # End the quota/day read transaction before planner or provider work.
    await session.commit()

    question_create, planned_question = await gutils.analyze_and_answer_locally(
        original_question=question.question, day_country=daily_country, user=user, session=session,
        evidence=evidence,
    )
    if (
        question_create is not None
        and question_create.valid
        and question_create.answer in (True, False)
        and (evidence or {}).get("planner", {}).get("provider") == "template"
    ):
        evidence["template_answered"] = True
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
                evidence=evidence,
            )
    if question_create.valid and question_create.answer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify this question right now. Your turn was not deducted.",
        )
    if not is_answered(question_create):
        return unresolved_question(question_create, InvalidQuestionDisplay)
    question_create.user_id = user.id if user else None
    question_create.guest_id = (
        get_guest_identity(request, response) if user is None else None
    )

    question_create.day_id = daily_country.id
    if user is None:
        await record_guest_action(
            session, request, response, "countrydle", daily_country.id,
            question=True, max_questions=COUNTRYDLE_CONFIG.max_questions,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses,
        )
    else:
        await consume_question(
            session, CountrydleState, user.id, daily_country.id,
            COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
        )
    new_question = await CountrydleQuestionsRepository(session).create_question(question_create)
    result = _player_question_display(new_question)
    await session.commit()
    if question_vector:
        # Indexing is auxiliary: an already committed answer remains successful.
        try:
            await add_question_to_qdrant(
                new_question, question_vector, filter_key="country_id",
                filter_value=daily_country.country_id, collection_name="countries_questions",
            )
        except Exception:
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
        state = await get_daily_state(
            session, CountrydleState, user.id, day_country.id,
            COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
        )
        if state and not state.is_game_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reveal country before game is over.",
            )
    else:
        participation, _, _ = await get_guest_progress(
            session, request, None, "countrydle", day_country.id, CountrydleGuess, CountrydleQuestion,
        )
        if not guest_game_over(participation, COUNTRYDLE_CONFIG.max_guesses):
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
    try:
        return await _do_make_guess(guess, request, response, user, session)
    except Exception:
        await session.rollback()
        raise


async def _do_make_guess(guess, request, response, user, session):
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
        participation = await record_guest_action(
            session, request, response, "countrydle", daily_country.id,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses, won=is_correct,
        )
        guess_num = participation.guesses_made
        guest_id = get_guest_identity(request, response)

        guess_create = GuessCreate(
            guess=guess.guess,
            country_id=guess.country_id,
            day_id=daily_country.id,
            user_id=None,
            guest_id=guest_id,
            answer=is_correct,
            elapsed_seconds=guess.elapsed_seconds,
        )
        saved_guess = await CountrydleGuessRepository(session).add_guess(guess_create, commit=False)
        await session.commit()
        token = create_guest_game_token(
            "countrydle", daily_country.id, participation.guesses_made,
            guest_game_over(participation, COUNTRYDLE_CONFIG.max_guesses), participation.won,
        )
        response.set_cookie(
            "guest_countrydle", token, httponly=True, samesite="lax", max_age=86400 * 2,
            secure=request.url.scheme == "https" or os.getenv("FRIEND_COOKIE_SECURE", "").strip().lower() in {"true", "1", "yes"},
        )

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
            elapsed_seconds=getattr(saved_guess, "elapsed_seconds", None),
            **hint,
        )
    state = await get_daily_state(
        session, CountrydleState, user.id, daily_country.id,
        COUNTRYDLE_CONFIG.max_questions, COUNTRYDLE_CONFIG.max_guesses,
    )
    require_guess_available(state, COUNTRYDLE_CONFIG.max_guesses)

    guess_num = state.guesses_made + 1

    # Create Guess entry
    guess_create = GuessCreate(
        guess=guess.guess,
        country_id=guess.country_id,
        day_id=daily_country.id,
        user_id=user.id,
        answer=is_correct,
        elapsed_seconds=guess.elapsed_seconds,
    )

    new_guess = await CountrydleGuessRepository(session).add_guess(guess_create, commit=False)

    # Update State using Repository logic (handles points, game over, etc.)
    await CountrydleStateRepository(session).guess_made(
        state, new_guess, puzzle_date=daily_country.date, elapsed_seconds=guess.elapsed_seconds,
        commit=False,
    )
    await session.commit()

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
        elapsed_seconds=getattr(new_guess, "elapsed_seconds", None),
        distance_km=hint.get("distance_km"),
        bearing_degrees=hint.get("bearing_degrees"),
        bearing_direction=hint.get("bearing_direction"),
        bearing_arrow=hint.get("bearing_arrow"),
    )
