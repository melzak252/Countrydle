import logging
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import get_db
from db.models.blog import DailyBlogPost
from db.models.continental import ContinentCode, ContinentalDay
from db.models.country import Country
from db.models.countrydle import CountrydleState
from db.models.flagdle import FlagdleDay
from db.models.guess import CountrydleGuess
from db.models.question import CountrydleQuestion
from db.models.user import User, UserPoints
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
    AdminLiveFeedResponse,
    AdminLiveGuess,
    AdminLiveQuestion,
    AdminModeToday,
    AdminOverviewResponse,
    AdminOverviewToday,
    AdminPlatformTotals,
    AdminUserItem,
    AdminUsersResponse,
)
from users.utils import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _mode_today(stats, mode_key: str, mode_label: str, target_name: str) -> AdminModeToday:
    return AdminModeToday(
        mode_key=mode_key,
        mode_label=mode_label,
        target_name=target_name,
        players=stats.get("total_players", 0),
        winners=stats.get("winners_count", 0),
        win_rate_pct=stats.get("win_rate_pct", 0.0),
        questions=stats.get("total_questions", 0),
        guesses=stats.get("total_guesses", 0),
    )


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    today = date.today()

    # Resolve targets without creating puzzles for additional modes.
    c_day = await CountrydleRepository(session).get_today_country()
    c_target = "Unknown"
    if c_day:
        country = await CountryRepository(session).get(c_day.country_id)
        c_target = country.name if country else f"Country #{c_day.country_id}"

    us_day = await USStatedleDayRepository(session).get_today_us_state()
    us_target = "Unknown"
    if us_day:
        state = await USStateRepository(session).get(us_day.us_state_id)
        us_target = state.name if state else f"State #{us_day.us_state_id}"

    p_day = await PowiatdleDayRepository(session).get_today_powiat()
    p_target = "Unknown"
    if p_day:
        powiat = await PowiatRepository(session).get(p_day.powiat_id)
        p_target = powiat.nazwa if powiat else f"Powiat #{p_day.powiat_id}"

    w_day = await WojewodztwodleDayRepository(session).get_today_wojewodztwo()
    w_target = "Unknown"
    if w_day:
        woj = await WojewodztwoRepository(session).get(w_day.wojewodztwo_id)
        w_target = woj.nazwa if woj else f"Voivodeship #{w_day.wojewodztwo_id}"

    flag_target = (await session.execute(
        select(Country.name).join(FlagdleDay, FlagdleDay.country_id == Country.id)
        .where(FlagdleDay.date == today)
    )).scalar()
    continental_targets = dict((await session.execute(
        select(ContinentalDay.continent, Country.name)
        .join(Country, Country.id == ContinentalDay.country_id)
        .where(ContinentalDay.date == today)
    )).all())

    targets = [
        ("countrydle", "World Countries", c_target),
        ("us_statedle", "US States", us_target),
        ("powiatdle", "Polish Counties", p_target),
        ("wojewodztwodle", "Polish Voivodeships", w_target),
        ("flagdle", "Flags", flag_target or "Unknown"),
        *[
            (f"continental:{continent.value}", f"Continental: {continent.value.title()}",
             continental_targets.get(continent, "Unknown"))
            for continent in ContinentCode
        ],
    ]
    participation = ParticipationRepository(session)
    mode_stats = await participation.get_mode_stats(today)
    modes_today = [
        _mode_today(mode_stats.get(key, {}), key, label, target)
        for key, label, target in targets
    ]

    # Unique players across challenges; wins and win rate remain per-game metrics.
    daily_stats = await participation.get_daily_stats(today - timedelta(days=13), today)
    current = daily_stats.get(today, {})
    today_overview = AdminOverviewToday(
        total_players=current.get("total_players", 0),
        total_winners=current.get("winners_count", 0),
        win_rate_pct=current.get("win_rate_pct", 0.0),
        total_questions=current.get("total_questions", 0),
        total_guesses=current.get("total_guesses", 0),
    )

    history_14d = []
    for i in range(14):
        hist_date = today - timedelta(days=i)
        stats = daily_stats.get(hist_date, {})
        history_14d.append(
            AdminDaySummary(
                date=hist_date,
                total_players=stats.get("total_players", 0),
                total_winners=stats.get("winners_count", 0),
                win_rate_pct=stats.get("win_rate_pct", 0.0),
                total_questions=stats.get("total_questions", 0),
                total_guesses=stats.get("total_guesses", 0),
            )
        )

    # All-time tracked participation; legacy anonymous guesses are not people.
    platform = await participation.get_stats()
    u_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    b_total = (await session.execute(select(func.count(DailyBlogPost.id)))).scalar() or 0

    totals = AdminPlatformTotals(
        total_users=u_count,
        total_games=platform["total_games"],
        total_questions=platform["total_questions"],
        total_guesses=platform["total_guesses"],
        total_blog_posts=b_total,
    )

    return AdminOverviewResponse(
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
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    # Latest 35 Countrydle Questions
    q_stmt = (
        select(CountrydleQuestion)
        .options(joinedload(CountrydleQuestion.user))
        .order_by(desc(CountrydleQuestion.id))
        .limit(35)
    )
    q_res = await session.execute(q_stmt)
    q_rows = q_res.scalars().all()

    recent_questions = [
        AdminLiveQuestion(
            id=q.id,
            mode="countrydle",
            username=q.user.username if q.user else "Guest",
            question=q.original_question or q.question or "",
            valid=q.valid,
            answer=q.answer,
            explanation=q.explanation,
            asked_at=q.asked_at,
        )
        for q in q_rows
    ]

    # Latest 35 Countrydle Guesses
    g_stmt = (
        select(CountrydleGuess)
        .options(joinedload(CountrydleGuess.user))
        .order_by(desc(CountrydleGuess.id))
        .limit(35)
    )
    g_res = await session.execute(g_stmt)
    g_rows = g_res.scalars().all()

    recent_guesses = [
        AdminLiveGuess(
            id=g.id,
            mode="countrydle",
            username=g.user.username if g.user else "Guest",
            guess=g.guess,
            answer=bool(g.answer),
            guessed_at=g.guessed_at,
        )
        for g in g_rows
    ]

    return AdminLiveFeedResponse(
        recent_questions=recent_questions,
        recent_guesses=recent_guesses,
    )
