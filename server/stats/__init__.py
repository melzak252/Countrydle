from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.user import User
from schemas.dashboard_stats import (
    DashboardLeaderboardResponse,
    LeaderboardPeriod,
    ModeStatsSummaryResponse,
)
from stats.registry import MODE_STATS_REGISTRY, resolve_mode_spec
from stats.service import get_mode_leaderboard, get_mode_summary, record_mode_result
from users.utils import get_current_or_guest_user
from utils.guest_session import read_guest_identity

router = APIRouter(prefix="/stats", tags=["stats"])


def _parse_date_param(date_str: Optional[str]) -> date:
    if not date_str:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD.",
        ) from exc


@router.get("/{mode}/summary", response_model=ModeStatsSummaryResponse)
async def get_stats_summary(
    mode: str,
    request: Request,
    date_param: Optional[str] = Query(None, alias="date"),
    period: LeaderboardPeriod = Query("daily"),
    limit: int = Query(10, ge=1, le=100),
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    spec = resolve_mode_spec(mode)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown stats mode: {mode}")

    target_date = _parse_date_param(date_param)
    guest_id = None if user is not None else read_guest_identity(request)

    return await get_mode_summary(
        session,
        spec,
        target_date=target_date,
        period=period,
        limit=limit,
        current_user_id=user.id if user is not None else None,
        guest_id=guest_id,
    )


@router.get("/{mode}/leaderboard", response_model=DashboardLeaderboardResponse)
async def get_stats_leaderboard(
    mode: str,
    period: LeaderboardPeriod = Query("daily"),
    date_param: Optional[str] = Query(None, alias="date"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    spec = resolve_mode_spec(mode)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown stats mode: {mode}")

    target_date = _parse_date_param(date_param)
    return await get_mode_leaderboard(
        session,
        spec,
        period=period,
        target_date=target_date,
        limit=limit,
        offset=offset,
        current_user_id=user.id if user is not None else None,
    )


__all__ = [
    "router",
    "MODE_STATS_REGISTRY",
    "resolve_mode_spec",
    "record_mode_result",
]
