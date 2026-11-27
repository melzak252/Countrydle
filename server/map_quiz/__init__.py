from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.user import User
from regional_symbols.catalog import load_entities
from schemas.countrydle import LeaderboardEntry
from users.utils import get_current_or_guest_user, get_current_user

from .schemas import (
    MapQuizAnswerRequest,
    MapQuizAnswerResponse,
    MapQuizDailyState,
    MapQuizEntity,
)
from .service import (
    claim_daily,
    get_or_create_daily,
    leaderboard,
    serialize_state,
    submit_answer,
    validate_scope,
)

router = APIRouter(prefix="/map-quiz", tags=["map_quiz"])


@router.get("/{scope}/entities", response_model=List[MapQuizEntity])
async def get_map_quiz_entities(scope: str):
    validate_scope(scope)
    entities = load_entities(scope)
    return sorted(
        (
            {
                "id": e["id"],
                "name": e["name"],
                "aliases": e.get("aliases", []),
                "latitude": e["latitude"],
                "longitude": e["longitude"],
            }
            for e in entities.values()
        ),
        key=lambda item: item["name"],
    )


@router.get("/{scope}/daily", response_model=MapQuizDailyState)
async def get_daily_map_quiz(
    scope: str,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_or_guest_user),
):
    row = await get_or_create_daily(session, request, response, current_user, scope)
    return serialize_state(row)


@router.post("/{scope}/answer", response_model=MapQuizAnswerResponse)
async def post_map_quiz_answer(
    scope: str,
    payload: MapQuizAnswerRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_or_guest_user),
):
    entry, row = await submit_answer(
        session,
        request,
        response,
        current_user,
        scope,
        payload.entity_id,
        expected_round=payload.round,
    )
    return {
        "result": {
            "round": entry["round"],
            "target_id": entry["target_id"],
            "target_name": entry["target_name"],
            "clicked_id": entry["clicked_id"],
            "clicked_name": entry["clicked_name"],
            "correct": entry["correct"],
        },
        "state": serialize_state(row),
    }


@router.post("/{scope}/sync", response_model=MapQuizDailyState)
async def sync_map_quiz_daily(
    scope: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await claim_daily(session, request, current_user, scope)
    return serialize_state(row)


@router.get("/{scope}/leaderboard", response_model=List[LeaderboardEntry])
async def get_map_quiz_leaderboard(
    scope: str,
    type: str = Query("monthly"),
    session: AsyncSession = Depends(get_db),
):
    return await leaderboard(session, scope, type)
