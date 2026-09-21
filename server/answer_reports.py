from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import (
    AnswerReport, Country, CountrydleDay, CountrydleQuestion, Powiat,
    PowiatdleDay, PowiatdleQuestion, USState, USStatedleDay, USStatedleQuestion,
    User, Wojewodztwo, WojewodztwodleDay, WojewodztwodleQuestion,
)
from report_tokens import verify_report_token
from schemas.answer_report import (
    AnswerReportCreate, AnswerReportCreated, AnswerReportDetails, AnswerReportDisplay,
    AnswerReportList, AnswerReportMode, AnswerReportReview, AnswerReportStatus,
)
from users.utils import get_admin_user, get_current_or_guest_user


router = APIRouter(tags=["answer reports"])
admin_router = APIRouter(prefix="/admin/answer-reports", tags=["admin"])

# Resolve every piece of diagnostic context from the mode's persisted rows.
MODELS = {
    "countrydle": (CountrydleQuestion, CountrydleDay, Country, CountrydleDay.country_id, Country.name),
    "us_statedle": (USStatedleQuestion, USStatedleDay, USState, USStatedleDay.us_state_id, USState.name),
    "powiatdle": (PowiatdleQuestion, PowiatdleDay, Powiat, PowiatdleDay.powiat_id, Powiat.nazwa),
    "wojewodztwodle": (WojewodztwodleQuestion, WojewodztwodleDay, Wojewodztwo, WojewodztwodleDay.wojewodztwo_id, Wojewodztwo.nazwa),
}


@router.post("/answer-reports", response_model=AnswerReportCreated, status_code=201)
async def submit_answer_report(
    payload: AnswerReportCreate,
    user: User | None = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    question_cls, day_cls, entity_cls, entity_fk, name_column = MODELS[payload.mode]
    result = await session.execute(
        select(question_cls, day_cls.date, name_column)
        .join(day_cls, question_cls.day_id == day_cls.id)
        .join(entity_cls, entity_fk == entity_cls.id)
        .where(question_cls.id == payload.question_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")
    question, game_date, target_name = row
    is_owner = user is not None and question.user_id == user.id
    if not is_owner and not verify_report_token(payload.mode, question.id, payload.report_token):
        raise HTTPException(status_code=404, detail="Question not found")

    details = AnswerReportDetails(
        original_question=question.original_question,
        question=question.question,
        valid=question.valid,
        answer=question.answer,
        explanation=question.explanation,
        context=question.context,
        day_id=question.day_id,
        game_date=game_date.isoformat(),
        target_name=target_name,
        server_version=getattr(question, "server_version", None),
    )
    report = AnswerReport(
        mode=payload.mode,
        question_id=question.id,
        reporter_id=user.id if user is not None else None,
        comment=payload.comment,
        details=details.model_dump(),
    )
    session.add(report)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # The database constraint also protects against concurrent submissions.
        existing = await session.execute(
            select(AnswerReport.id).where(
                AnswerReport.mode == payload.mode,
                AnswerReport.question_id == payload.question_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="This answer has already been reported") from None
        raise
    await session.refresh(report)
    return AnswerReportCreated(id=report.id)


def _report_query():
    return select(AnswerReport, User.username).outerjoin(User, User.id == AnswerReport.reporter_id)


def _display_report(report: AnswerReport, username: str | None) -> AnswerReportDisplay:
    return AnswerReportDisplay(
        id=report.id,
        mode=report.mode,
        question_id=report.question_id,
        comment=report.comment,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
        reporter_username=username,
        details=report.details,
    )


@admin_router.get("", response_model=AnswerReportList)
async def list_answer_reports(
    status: AnswerReportStatus = "open",
    mode: AnswerReportMode | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    filters = []
    if status == "open":
        filters.append(AnswerReport.reviewed_at.is_(None))
    elif status == "reviewed":
        filters.append(AnswerReport.reviewed_at.is_not(None))
    if mode is not None:
        filters.append(AnswerReport.mode == mode)
    count = await session.execute(select(func.count(AnswerReport.id)).where(*filters))
    result = await session.execute(
        _report_query().where(*filters)
        .order_by(AnswerReport.created_at.desc(), AnswerReport.id.desc())
        .offset((page - 1) * limit).limit(limit)
    )
    return AnswerReportList(
        items=[_display_report(report, username) for report, username in result.all()],
        total=count.scalar_one(),
    )


@admin_router.patch("/{report_id}", response_model=AnswerReportDisplay)
async def review_answer_report(
    report_id: int,
    payload: AnswerReportReview,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    # Repeated reviews preserve the first timestamp; reopening clears it.
    result = await session.execute(
        update(AnswerReport)
        .where(AnswerReport.id == report_id)
        .values(reviewed_at=func.coalesce(AnswerReport.reviewed_at, func.now()) if payload.reviewed else None)
        .returning(AnswerReport.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await session.commit()
    result = await session.execute(_report_query().where(AnswerReport.id == report_id))
    report, username = result.one()
    return _display_report(report, username)
