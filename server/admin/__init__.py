import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import get_db
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.guess import CountrydleGuess
from db.models.powiat import Powiat
from db.models.powiatdle import PowiatdleDay, PowiatdleGuess, PowiatdleQuestion, PowiatdleState
from db.models.question import CountrydleQuestion
from db.models.us_state import USState
from db.models.us_statedle import USStatedleDay, USStatedleGuess, USStatedleQuestion, USStatedleState
from db.models.user import User, UserPoints
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import (
    WojewodztwodleDay,
    WojewodztwodleGuess,
    WojewodztwodleQuestion,
    WojewodztwodleState,
)
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


async def _aggregate_mode_today(
    session: AsyncSession,
    state_cls,
    day_cls,
    mode_key: str,
    mode_label: str,
    target_name: str,
    today_date: date,
) -> AdminModeToday:
    stmt = (
        select(
            func.count(state_cls.id).label("players"),
            func.count(case((state_cls.won == True, 1))).label("winners"),
            func.coalesce(func.sum(state_cls.questions_asked), 0).label("questions"),
            func.coalesce(func.sum(state_cls.guesses_made), 0).label("guesses"),
        )
        .join(day_cls, day_cls.id == state_cls.day_id)
        .where(day_cls.date == today_date)
    )
    res = await session.execute(stmt)
    row = res.first()

    players = row.players if row else 0
    winners = row.winners if row else 0
    questions = int(row.questions) if row else 0
    guesses = int(row.guesses) if row else 0
    win_rate = round((winners / players) * 100, 1) if players > 0 else 0.0

    return AdminModeToday(
        mode_key=mode_key,
        mode_label=mode_label,
        target_name=target_name,
        players=players,
        winners=winners,
        win_rate_pct=win_rate,
        questions=questions,
        guesses=guesses,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db),
):
    today = date.today()

    # 1. Resolve Today's Targets for All 4 Modes
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

    # 2. Compute Mode-by-Mode Today's Breakdown
    m_country = await _aggregate_mode_today(session, CountrydleState, CountrydleDay, "countrydle", "World Countries", c_target, today)
    m_us = await _aggregate_mode_today(session, USStatedleState, USStatedleDay, "us_statedle", "US States", us_target, today)
    m_powiat = await _aggregate_mode_today(session, PowiatdleState, PowiatdleDay, "powiatdle", "Polish Counties", p_target, today)
    m_woj = await _aggregate_mode_today(session, WojewodztwodleState, WojewodztwodleDay, "wojewodztwodle", "Polish Voivodeships", w_target, today)

    modes_today = [m_country, m_us, m_powiat, m_woj]

    # Aggregate total for today
    today_players = sum(m.players for m in modes_today)
    today_winners = sum(m.winners for m in modes_today)
    today_questions = sum(m.questions for m in modes_today)
    today_guesses = sum(m.guesses for m in modes_today)
    today_win_rate = round((today_winners / today_players) * 100, 1) if today_players > 0 else 0.0

    today_overview = AdminOverviewToday(
        total_players=today_players,
        total_winners=today_winners,
        win_rate_pct=today_win_rate,
        total_questions=today_questions,
        total_guesses=today_guesses,
    )

    # 3. 14-Day Historical Series
    history_14d: List[AdminDaySummary] = []
    for i in range(14):
        hist_date = today - timedelta(days=i)
        stmt = (
            select(
                func.count(CountrydleState.id).label("players"),
                func.count(case((CountrydleState.won == True, 1))).label("winners"),
                func.coalesce(func.sum(CountrydleState.questions_asked), 0).label("questions"),
                func.coalesce(func.sum(CountrydleState.guesses_made), 0).label("guesses"),
            )
            .join(CountrydleDay, CountrydleDay.id == CountrydleState.day_id)
            .where(CountrydleDay.date == hist_date)
        )
        res = await session.execute(stmt)
        row = res.first()

        p_count = row.players if row else 0
        w_count = row.winners if row else 0
        q_count = int(row.questions) if row else 0
        g_count = int(row.guesses) if row else 0
        wr = round((w_count / p_count) * 100, 1) if p_count > 0 else 0.0

        history_14d.append(
            AdminDaySummary(
                date=hist_date,
                total_players=p_count,
                total_winners=w_count,
                win_rate_pct=wr,
                total_questions=q_count,
                total_guesses=g_count,
            )
        )

    # 4. Overall Platform Totals
    u_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    s_count = (await session.execute(select(func.count(CountrydleState.id)))).scalar() or 0
    q_total = (await session.execute(select(func.count(CountrydleQuestion.id)))).scalar() or 0
    g_total = (await session.execute(select(func.count(CountrydleGuess.id)))).scalar() or 0
    b_total = 0
    try:
        b_total = (await session.execute(select(func.count(DailyBlogPost.id)))).scalar() or 0
    except Exception:
        pass

    totals = AdminPlatformTotals(
        total_users=u_count,
        total_games=s_count,
        total_questions=q_total,
        total_guesses=g_total,
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
