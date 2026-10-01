from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import Suggestion, User
from schemas.suggestion import SuggestionCreate, SuggestionCreated, SuggestionDisplay, SuggestionList
from users.utils import get_admin_user, get_current_or_guest_user
from utils.question_rate_limit import QuestionAttemptLimiter, client_network_key


router = APIRouter(tags=["suggestions"])
admin_router = APIRouter(prefix="/admin/suggestions", tags=["admin"])
submission_limiter = QuestionAttemptLimiter(max_requests=5)


async def enforce_submission_limit(request: Request) -> None:
    retry_after = submission_limiter.retry_after(client_network_key(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many suggestions. Please wait before submitting again.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post(
    "/suggestions", response_model=SuggestionCreated, status_code=201,
    dependencies=[Depends(enforce_submission_limit)],
)
async def submit_suggestion(
    payload: SuggestionCreate,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    suggestion = Suggestion(
        topic=payload.topic,
        message=payload.message,
        name=payload.name,
        email=payload.email,
        reporter_id=user.id if user is not None else None,
    )
    session.add(suggestion)
    await session.commit()
    await session.refresh(suggestion)
    return SuggestionCreated(id=suggestion.id)


@admin_router.get("", response_model=SuggestionList)
async def list_suggestions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    count = await session.execute(select(func.count(Suggestion.id)))
    result = await session.execute(
        select(Suggestion, User.username)
        .outerjoin(User, User.id == Suggestion.reporter_id)
        .order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = [
        SuggestionDisplay(
            id=suggestion.id,
            topic=suggestion.topic,
            message=suggestion.message,
            name=suggestion.name,
            email=suggestion.email,
            created_at=suggestion.created_at,
            reporter_username=username,
        )
        for suggestion, username in result.all()
    ]
    return SuggestionList(items=items, total=count.scalar_one())
