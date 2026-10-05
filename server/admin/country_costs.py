"""Admin-only Countrydle AI cost reporting endpoint."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.user import User
from users.utils import get_admin_user
from utils.country_cost_report import build_country_cost_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/countrydle-costs", tags=["admin"])


@router.get("")
async def get_countrydle_costs(
    days: int = Query(default=7, ge=1, le=366),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await build_country_cost_report(session, days)
    except Exception as exc:
        logger.exception("Admin Countrydle cost report failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load Countrydle cost report. Please try again.",
        ) from exc
