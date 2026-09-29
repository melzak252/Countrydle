from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import TemplateDivergence, User
from schemas.template_divergence import (
    TemplateDivergenceDisplay,
    TemplateDivergenceList,
    TemplateDivergenceReview,
    TemplateDivergenceStatus,
)
from users.utils import get_admin_user

router = APIRouter(prefix="/admin/template-divergences", tags=["admin"])


@router.get("", response_model=TemplateDivergenceList)
async def list_template_divergences(
    status: TemplateDivergenceStatus = "open",
    mode: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    filters = []
    if status == "open":
        filters.append(TemplateDivergence.reviewed_at.is_(None))
    elif status == "reviewed":
        filters.append(TemplateDivergence.reviewed_at.is_not(None))
    if mode is not None and mode.strip():
        filters.append(TemplateDivergence.mode == mode.strip())

    count = await session.execute(select(func.count(TemplateDivergence.id)).where(*filters))
    total = count.scalar_one()

    query = (
        select(TemplateDivergence)
        .where(*filters)
        .order_by(TemplateDivergence.created_at.desc(), TemplateDivergence.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await session.execute(query)
    rows = result.scalars().all()

    items = [
        TemplateDivergenceDisplay(
            id=row.id,
            mode=row.mode,
            question=row.question,
            template_plan=row.template_plan,
            gemini_plan=row.gemini_plan,
            divergence_type=row.divergence_type,
            details=row.details,
            created_at=row.created_at,
            reviewed_at=row.reviewed_at,
        )
        for row in rows
    ]
    return TemplateDivergenceList(items=items, total=total)


@router.patch("/{divergence_id}", response_model=TemplateDivergenceDisplay)
async def review_template_divergence(
    divergence_id: int,
    body: TemplateDivergenceReview,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    timestamp = func.now() if body.reviewed else None
    result = await session.execute(
        update(TemplateDivergence)
        .where(TemplateDivergence.id == divergence_id)
        .values(reviewed_at=timestamp)
        .returning(TemplateDivergence)
    )
    divergence = result.scalar_one_or_none()
    if divergence is None:
        raise HTTPException(status_code=404, detail="Template divergence not found")
    await session.commit()
    await session.refresh(divergence)

    return TemplateDivergenceDisplay(
        id=divergence.id,
        mode=divergence.mode,
        question=divergence.question,
        template_plan=divergence.template_plan,
        gemini_plan=divergence.gemini_plan,
        divergence_type=divergence.divergence_type,
        details=divergence.details,
        created_at=divergence.created_at,
        reviewed_at=divergence.reviewed_at,
    )
