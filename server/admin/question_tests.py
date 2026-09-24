"""Admin-only evaluation of explicit targets, without daily/player persistence."""
import logging
from time import perf_counter
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from continental.utils import get_continent_country_names
from countrydle import local_answering as country_facts
from countrydle import utils as country_utils
from db import get_db
from db.models import Country, Powiat, USState, User, Wojewodztwo
from db.models.continental import ContinentCode
import flagdle
from powiatdle import utils as powiat_utils
from schemas.admin import (
    AdminQuestionTestEntity,
    AdminQuestionTestMode,
    AdminQuestionTestRequest,
    AdminQuestionTestResponse,
)
from us_statedle import utils as state_utils
from users.utils import get_admin_user
from version import SERVER_VERSION
from wojewodztwodle import utils as voivodeship_utils

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/question-tests")

# Reuse the daily utilities, including their retrieval, prompts and provider fallback.
_MODE_PIPELINES = {
    "us_statedle": (USState, USState.name, state_utils, "us_state_id"),
    "powiatdle": (Powiat, Powiat.nazwa, powiat_utils, "powiat_id"),
    "wojewodztwodle": (Wojewodztwo, Wojewodztwo.nazwa, voivodeship_utils, "wojewodztwo_id"),
}
_COUNTRY_PIPELINE = (Country, Country.name, country_utils, "country_id")
_CONTINENT_MODES = {continent.value for continent in ContinentCode}


def _entity_query(mode: AdminQuestionTestMode):
    model, name, _, _ = _MODE_PIPELINES.get(mode, _COUNTRY_PIPELINE)
    statement = select(model)
    if mode in _CONTINENT_MODES:
        statement = statement.where(
            Country.name.in_(get_continent_country_names(ContinentCode(mode)))
        )
    return statement.order_by(name, model.id)


def _entity_display(entity) -> AdminQuestionTestEntity:
    return AdminQuestionTestEntity(
        id=entity.id,
        name=entity.nazwa if isinstance(entity, (Powiat, Wojewodztwo)) else entity.name,
    )


def _plan_diagnostics(plan) -> dict:
    # Only structured planner output, never prompts, credentials or provider metadata.
    return {
        "valid": plan.valid,
        "supported": plan.supported,
        "improved_question": plan.improved_question,
        "explanation": plan.explanation,
        "plan": plan.plan,
        "fallback_reason": plan.fallback_reason,
    }


def _evaluate_flag(question: str, entity):
    plan = flagdle.analyze_question_for_local_plan(
        question, strict_errors=True, use_cache=False,
    )
    if not plan.valid:
        return SimpleNamespace(
            valid=False, answer=None, question=plan.improved_question,
            explanation=plan.explanation or "Please ask a valid yes/no question about the flag or country.",
            context="local_planner:invalid",
        ), plan, "local_planner"

    answer = None
    if plan.plan:
        if not country_facts.DEFAULT_DB_PATH.is_file():
            raise RuntimeError("Local flag facts are unavailable")
        answer = flagdle.execute_local_plan(
            plan.plan, entity.name, plan.improved_question or question,
            plan.explanation, original_question=question,
        )
    if answer is None:
        return SimpleNamespace(
            valid=False, answer=None, question=plan.improved_question,
            explanation="Could not verify this question with local flag facts. Ask about flag colors, stripes, symbols, or country geography.",
            context=None,
        ), plan, "flag_kb"
    return SimpleNamespace(
        valid=True, answer=answer.answer, question=answer.question,
        explanation=answer.explanation, context=f"flag_kb:{answer.relation}",
    ), plan, "flag_kb"


@router.get("/entities", response_model=list[AdminQuestionTestEntity])
async def list_question_test_entities(
    mode: AdminQuestionTestMode,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        with session.no_autoflush:
            result = await session.execute(_entity_query(mode))
            return [_entity_display(entity) for entity in result.scalars().all()]
    except Exception as exc:
        logger.exception("Admin question-test entity lookup failed for %s", mode)
        raise HTTPException(status_code=503, detail="Could not load question-test entities. Please try again.") from exc


@router.post("", response_model=AdminQuestionTestResponse)
async def evaluate_question_test(
    request: AdminQuestionTestRequest,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    started = perf_counter()
    model, _, utilities, entity_fk = _MODE_PIPELINES.get(request.mode, _COUNTRY_PIPELINE)
    try:
        with session.no_autoflush:
            result = await session.execute(_entity_query(request.mode).where(model.id == request.entity_id))
            entity = result.scalars().first()
            if entity is None:
                raise HTTPException(status_code=404, detail="Entity not found for this game mode.")

            if request.mode == "flagdle":
                answer, plan, source = _evaluate_flag(request.question, entity)
            else:
                # Daily question schemas require an integer day_id. This is a plain,
                # unattached adapter, never an ORM record or a returned game/day ID.
                target = SimpleNamespace(id=0, **{entity_fk: entity.id})
                answer, plan = await utilities.analyze_and_answer_locally(
                    request.question, target, None, session, strict_errors=True,
                )
                source = "local_kb" if answer is not None and answer.valid else "local_planner"
                if answer is None:
                    enhanced = utilities.question_enhanced_from_plan(request.question, plan)
                    answer, _ = await utilities.ask_question(enhanced, target, None, session)
                    source = "fallback"

            if answer.valid and type(answer.answer) is not bool:
                raise RuntimeError("Answer provider did not return a yes/no answer")
            return AdminQuestionTestResponse(
                mode=request.mode, entity=_entity_display(entity),
                original_question=request.question, question=answer.question,
                valid=answer.valid, answer=answer.answer, explanation=answer.explanation,
                context=answer.context, source=source,
                server_version=SERVER_VERSION,
                duration_ms=round((perf_counter() - started) * 1000),
                plan=_plan_diagnostics(plan),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Admin question-test evaluation failed for %s entity %s", request.mode, request.entity_id)
        raise HTTPException(
            status_code=503,
            detail="Question evaluation failed because the answering service or facts are unavailable. No answer was recorded; please try again.",
        ) from exc
