import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, case, desc, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import get_db
from db.models.blog import DailyBlogPost
from db.models.continental import ContinentCode, ContinentalDay, ContinentalGuess, ContinentalQuestion
from db.models.country import Country
from db.models.countrydle import CountrydleState
from db.models.flagdle import FlagdleDay
from db.models.guess import CountrydleGuess
from db.models.question import CountrydleQuestion
from db.models.user import User, UserPoints
from db.models.powiatdle import PowiatdleQuestion, PowiatdleGuess
from db.models.us_statedle import USStatedleQuestion, USStatedleGuess
from db.models.wojewodztwodle import WojewodztwodleQuestion, WojewodztwodleGuess
from db.models.heraldry_daily import HeraldryDailySession
from admin.heraldry_sessions import (
    REGIONAL_SCOPES, flag_quiz_target, heraldry_mode, query_heraldry_sessions,
    query_heraldry_stats, quiz_target,
)
from powiatdle.heraldry import get_all_counties, select_target
from db.repositories.participation import ParticipationRepository
from db.repositories.country import CountryRepository
from db.repositories.countrydle import CountrydleRepository
from db.repositories.powiatdle import PowiatRepository, PowiatdleDayRepository
from db.repositories.us_state import USStateRepository
from db.repositories.us_statedle import USStatedleDayRepository
from db.repositories.wojewodztwo import WojewodztwoRepository
from db.repositories.wojewodztwodle import WojewodztwodleDayRepository
from schemas.admin import (
    AdminDaySummary,
    AdminGameSessionsResponse,
    AdminInvalidateFallbackRequest,
    AdminInvalidateFallbackResponse,
    AdminLiveFeedResponse,
    AdminLiveGuess,
    AdminLiveQuestion,
    AdminModeToday,
    AdminOverviewResponse,
    AdminOverviewToday,
    AdminPlatformTotals,
    AdminQuestionsListResponse,
    AdminTargetStrategyStats,
    AdminUserItem,
    AdminUsersResponse,
)
from admin.resolver import (
    ADMIN_MODE_CONFIGS,
    _resolve_day_and_target,
    classify_question_source,
    invalidate_question_fallback,
    query_admin_game_sessions,
    query_admin_questions,
    query_admin_target_stats,
)
from admin.participation import admin_counts
from users.utils import get_admin_user
from admin.question_tests import router as question_tests_router
from admin.country_costs import router as country_costs_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(question_tests_router)
router.include_router(country_costs_router)


def get_today_date() -> date:
    if not isinstance(date, type):
        return date.today()
    return datetime.now(timezone.utc).date()


def _mode_today(stats, mode_key: str, mode_label: str, target_name: str) -> AdminModeToday:
    return AdminModeToday(
        mode_key=mode_key,
        mode_label=mode_label,
        target_name=target_name,
        players=stats.get("total_players", 0),
        sessions=stats.get("total_games", 0),
        winners=stats.get("winners_count", 0),
        win_rate_pct=stats.get("win_rate_pct", 0.0),
        questions=stats.get("total_questions", 0),
        guesses=stats.get("total_guesses", 0),
        avg_questions_won=stats.get("avg_questions_won", 0.0),
        avg_guesses_won=stats.get("avg_guesses_won", 0.0),
    )


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    today = get_today_date()

    # Use the same UTC date and day resolution as the drilldown endpoints.
    c_target = (await _resolve_day_and_target(session, ADMIN_MODE_CONFIGS["countrydle"], today, "countrydle"))[1]
    us_target = (await _resolve_day_and_target(session, ADMIN_MODE_CONFIGS["us_statedle"], today, "us_statedle"))[1]
    p_target = (await _resolve_day_and_target(session, ADMIN_MODE_CONFIGS["powiatdle"], today, "powiatdle"))[1]
    w_target = (await _resolve_day_and_target(session, ADMIN_MODE_CONFIGS["wojewodztwodle"], today, "wojewodztwodle"))[1]

    flag_target = (await session.execute(
        select(Country.name).join(FlagdleDay, FlagdleDay.country_id == Country.id)
        .where(FlagdleDay.date == today)
    )).scalar()
    continental_targets = dict((await session.execute(
        select(ContinentalDay.continent, Country.name)
        .join(Country, Country.id == ContinentalDay.country_id)
        .where(ContinentalDay.date == today)
    )).all())
    heraldry_targets = {(scope, symbol): name for scope, symbol, name in (await session.execute(
        select(HeraldryDailySession.entity_scope, HeraldryDailySession.symbol_mode, HeraldryDailySession.target_name)
        .where(HeraldryDailySession.date == today)
    )).all()}
    flag_target_name = heraldry_targets.get(("county", "flag"))
    if not flag_target_name:
        try:
            flag_target_name = select_target(get_all_counties(), f"daily-{today.isoformat()}", "flag")["name"]
        except HTTPException as exc:
            if exc.status_code != 503:
                raise

    targets = [
        ("countrydle", "World Countries", c_target),
        ("us_statedle", "US States", us_target),
        ("powiatdle", "Polish Counties", p_target),
        ("wojewodztwodle", "Polish Voivodeships", w_target),
        ("flagdle", "Flags", flag_target or "Unknown"),
        ("heraldry", "County Coats of Arms", heraldry_targets.get(("county", "coat")) or "Unknown"),
        ("coats_quiz", "All County Coats Quiz", "380 Polish counties"),
        ("county_flags", "County Flags", flag_target_name or "Unknown"),
        ("county_flags_quiz", "All County Flags Quiz", flag_quiz_target()),
        *[
            (f"regional_symbols:{scope}:{symbol}{':quiz' if is_quiz else ''}",
             f"{label.title()} {'Flags' if symbol == 'flag' else 'Coats of Arms'}{' Quiz' if is_quiz else ''}",
             quiz_target(f"regional_symbols:{scope}:{symbol}:quiz") if is_quiz
             else heraldry_targets.get((scope, symbol), "Unknown"))
            for scope, label in REGIONAL_SCOPES.items()
            for symbol in ("coat", "flag")
            for is_quiz in (False, True)
        ],
        *[
            (f"continental:{continent.value}", f"Continental: {continent.value.title()}",
             continental_targets.get(continent, "Unknown"))
            for continent in ContinentCode
        ],
    ]
    participation = ParticipationRepository(session)
    mode_stats = await participation.get_mode_stats(today)
    _, admin_days, admin_modes = await admin_counts(session, today - timedelta(days=13), today)
    modes_today = []
    for key, label, target in targets:
        stats = dict(mode_stats.get(key, {}))
        count = admin_modes.get((today, key))
        stats["total_players"] = count.players if count else 0
        stats["total_games"] = count.sessions if count else 0
        stats["win_rate_pct"] = round(stats.get("winners_count", 0) / count.sessions * 100, 1) if count and count.sessions else 0.0
        modes_today.append(_mode_today(stats, key, label, target))

    # Unique players across challenges; wins and win rate remain per-game metrics.
    daily_stats = await participation.get_daily_stats(today - timedelta(days=13), today)
    current = await participation.get_stats(today)
    today_count = admin_days.get(today)
    today_overview = AdminOverviewToday(
        total_players=today_count.players if today_count else 0,
        total_sessions=today_count.sessions if today_count else 0,
        total_winners=current.get("winners_count", 0),
        win_rate_pct=round(current.get("winners_count", 0) / today_count.sessions * 100, 1) if today_count and today_count.sessions else 0.0,
        total_questions=current.get("total_questions", 0),
        total_guesses=current.get("total_guesses", 0),
        avg_questions_won=current.get("avg_questions_won", 0.0),
        avg_guesses_won=current.get("avg_guesses_won", 0.0),
    )

    history_14d = []
    for i in range(14):
        hist_date = today - timedelta(days=i)
        stats = daily_stats.get(hist_date, {})
        count = admin_days.get(hist_date)
        history_14d.append(
            AdminDaySummary(
                date=hist_date,
                total_players=count.players if count else 0,
                total_winners=stats.get("winners_count", 0),
                win_rate_pct=round(stats.get("winners_count", 0) / count.sessions * 100, 1) if count and count.sessions else 0.0,
                total_questions=stats.get("total_questions", 0),
                total_guesses=stats.get("total_guesses", 0),
                avg_questions_won=stats.get("avg_questions_won", 0.0),
                avg_guesses_won=stats.get("avg_guesses_won", 0.0),
            )
        )

    # All-time tracked participation; legacy anonymous guesses are not people.
    platform = await participation.get_stats()
    admin_all_time, _, _ = await admin_counts(session, include_breakdown=False)
    u_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    b_total = (await session.execute(select(func.count(DailyBlogPost.id)))).scalar() or 0

    totals = AdminPlatformTotals(
        total_users=u_count,
        total_games=admin_all_time.sessions,
        total_questions=platform["total_questions"],
        total_guesses=platform["total_guesses"],
        total_blog_posts=b_total,
    )

    return AdminOverviewResponse(
        date=today,
        today=today_overview,
        modes_today=modes_today,
        history_14d=history_14d,
        totals=totals,
    )


@router.get("/users", response_model=AdminUsersResponse)
async def list_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    base_query = (
        select(
            User.id,
            User.username,
            User.email,
            User.created_at,
            User.is_admin,
            func.coalesce(UserPoints.points, 0).label("points"),
            func.coalesce(UserPoints.streak, 0).label("streak"),
            func.coalesce(func.sum(case((CountrydleState.won == True, 1))), 0).label("wins"),
            func.count(CountrydleState.id).label("games_played"),
        )
        .outerjoin(UserPoints, UserPoints.user_id == User.id)
        .outerjoin(CountrydleState, CountrydleState.user_id == User.id)
        .group_by(User.id, User.username, User.email, User.created_at, User.is_admin, UserPoints.points, UserPoints.streak)
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        base_query = base_query.where(
            or_(User.username.ilike(term), User.email.ilike(term))
        )

    # Count total
    count_stmt = select(func.count(User.id))
    if search and search.strip():
        count_stmt = count_stmt.where(
            or_(User.username.ilike(f"%{search.strip()}%"), User.email.ilike(f"%{search.strip()}%"))
        )
    total_users = (await session.execute(count_stmt)).scalar() or 0

    # Paginate and order by points desc
    query = base_query.order_by(desc("points"), desc(User.id)).offset(offset).limit(limit)
    res = await session.execute(query)
    rows = res.all()

    users_list = [
        AdminUserItem(
            id=r.id,
            username=r.username or "Anonymous",
            email=r.email or "",
            created_at=r.created_at,
            is_admin=bool(r.is_admin),
            total_points=int(r.points),
            total_wins=int(r.wins),
            games_played=int(r.games_played),
            current_streak=int(r.streak),
        )
        for r in rows
    ]

    return AdminUsersResponse(total=total_users, users=users_list)


@router.get("/live-feed", response_model=AdminLiveFeedResponse)
async def get_admin_live_feed(
    mode: Optional[str] = Query(None),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    recent_questions: list[AdminLiveQuestion] = []
    recent_guesses: list[AdminLiveGuess] = []

    modes_to_query = []
    if mode is None:
        modes_to_query = list(ADMIN_MODE_CONFIGS.values())
    else:
        norm_mode = mode.lower().strip().split(":", 1)[0]
        if norm_mode in ADMIN_MODE_CONFIGS:
            modes_to_query = [ADMIN_MODE_CONFIGS[norm_mode]]

    for cfg in modes_to_query:
        col_target_subtitle = (
            func.cast(cfg.target_subtitle_col, String)
            if cfg.target_subtitle_col is not None
            else literal(cfg.default_subtitle)
        )

        q_stmt = (
            select(
                cfg.question_model,
                cfg.target_name_col.label("target_name"),
                col_target_subtitle.label("target_subtitle"),
            )
            .join(cfg.day_model, cfg.question_model.day_id == cfg.day_model.id)
            .join(cfg.target_model, cfg.target_fk_col == cfg.target_model.id)
            .options(joinedload(cfg.question_model.user))
            .order_by(desc(cfg.question_model.id))
            .limit(30)
        )
        q_res = await session.execute(q_stmt)
        for q_obj, t_name, t_sub in q_res.all():
            src, _ = classify_question_source(q_obj.valid, q_obj.context)
            recent_questions.append(
                AdminLiveQuestion(
                    id=q_obj.id,
                    mode=cfg.mode_key,
                    username=q_obj.user.username
                    if q_obj.user
                    else (f"Guest {q_obj.guest_id[:8]}" if getattr(q_obj, "guest_id", None) else "Guest"),
                    question=getattr(q_obj, "original_question", None) or getattr(q_obj, "question", "") or "",
                    valid=q_obj.valid,
                    answer=q_obj.answer,
                    explanation=q_obj.explanation,
                    clarification=getattr(q_obj, "clarification", None),
                    asked_at=q_obj.asked_at,
                    target_name=t_name,
                    target_subtitle=str(t_sub) if t_sub else None,
                    source=src,
                )
            )

        g_stmt = (
            select(
                cfg.guess_model,
                cfg.target_name_col.label("target_name"),
                col_target_subtitle.label("target_subtitle"),
            )
            .join(cfg.day_model, cfg.guess_model.day_id == cfg.day_model.id)
            .join(cfg.target_model, cfg.target_fk_col == cfg.target_model.id)
            .options(joinedload(cfg.guess_model.user))
            .order_by(desc(cfg.guess_model.id))
            .limit(30)
        )
        g_res = await session.execute(g_stmt)
        for g_obj, t_name, t_sub in g_res.all():
            recent_guesses.append(
                AdminLiveGuess(
                    id=g_obj.id,
                    mode=cfg.mode_key,
                    username=g_obj.user.username
                    if g_obj.user
                    else (f"Guest {g_obj.guest_id[:8]}" if getattr(g_obj, "guest_id", None) else "Guest"),
                    guess=getattr(g_obj, "guess", ""),
                    answer=bool(g_obj.answer),
                    guessed_at=g_obj.guessed_at,
                    target_name=t_name,
                    target_subtitle=str(t_sub) if t_sub else None,
                )
            )

    recent_questions.sort(key=lambda x: x.asked_at or datetime.min, reverse=True)
    recent_guesses.sort(key=lambda x: x.guessed_at or datetime.min, reverse=True)

    return AdminLiveFeedResponse(
        recent_questions=recent_questions[:45],
        recent_guesses=recent_guesses[:45],
    )


@router.get("/questions", response_model=AdminQuestionsListResponse)
async def list_admin_questions(
    mode: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date: Optional[date] = Query(None),
    source: Optional[str] = Query(None),
    answer: Optional[str] = Query(None),
    target_name: Optional[str] = Query(None),
    has_report: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    items, total = await query_admin_questions(
        session=session,
        mode=mode,
        search=search,
        date_filter=date,
        source_filter=source,
        answer_filter=answer,
        target_name_filter=target_name,
        has_report_filter=has_report,
        page=page,
        limit=limit,
    )
    return AdminQuestionsListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/game-sessions", response_model=AdminGameSessionsResponse)
async def list_admin_game_sessions(
    mode: str = Query("countrydle"),
    date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    player_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    if heraldry_mode(mode):
        items, total = await query_heraldry_sessions(
            session, mode, date or get_today_date(), status, player_type, page, limit
        )
        return AdminGameSessionsResponse(items=items, total=total, page=page, limit=limit)
    items, total = await query_admin_game_sessions(
        session=session,
        mode=mode,
        target_date=date,
        status_filter=status,
        player_type_filter=player_type,
        page=page,
        limit=limit,
    )
    return AdminGameSessionsResponse(items=items, total=total, page=page, limit=limit)


@router.get("/game-sessions/stats", response_model=AdminTargetStrategyStats)
async def get_admin_game_session_stats(
    mode: str = Query("countrydle"),
    date: Optional[date] = Query(None),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    if heraldry_mode(mode):
        return await query_heraldry_stats(session, mode, date or get_today_date())
    stats = await query_admin_target_stats(
        session=session,
        mode=mode,
        target_date=date,
    )
    return stats


@router.post("/questions/invalidate-fallback", response_model=AdminInvalidateFallbackResponse)
async def invalidate_fallback_answer_endpoint(
    payload: AdminInvalidateFallbackRequest,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    success, message = await invalidate_question_fallback(
        session=session,
        mode=payload.mode,
        question_id=payload.question_id,
    )
    return AdminInvalidateFallbackResponse(
        success=success,
        mode=payload.mode,
        question_id=payload.question_id,
        message=message,
    )
