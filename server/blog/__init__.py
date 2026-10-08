import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from daily_clock import utc_today
from db import get_db
from db.models.countrydle import CountrydleDay, CountrydleQuestion, CountrydleGuess, CountrydleState
from db.repositories.blog import BlogRepository
from db.repositories.countrydle import CountrydleRepository
from db.repositories.participation import ParticipationRepository
from schemas.blog import BlogPostDisplay, BlogPostListResponse, BlogPostSummary, CommunityGameDebrief, TopQuestionStat, WrongGuessStat
from sqlalchemy import func, desc, select, or_
from utils.blog_generator import create_daily_blog_post
from utils.country_codes import get_country_code
from functools import lru_cache
from pathlib import Path
import sqlite3
from typing import List, Optional

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _get_country_continent_map() -> dict[str, str]:
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "data" if (base / "data").exists() else base.parent / "data"
    facts_db = data_dir / "country_facts.sqlite"
    if not facts_db.exists():
        return {}
    try:
        conn = sqlite3.connect(f"{facts_db.resolve().as_uri()}?mode=ro", uri=True)
        rows = conn.execute("""
            SELECT c.app_country_name, cc.continent
            FROM countries c
            JOIN country_continents cc ON c.id = cc.country_id
        """).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

def resolve_country_continent(name: str) -> str:
    m = _get_country_continent_map()
    return m.get(name, "World")

def compute_difficulty(win_rate_pct: Optional[float]) -> str:
    if win_rate_pct is None:
        return "Medium"
    if win_rate_pct >= 65.0:
        return "Easy"
    if win_rate_pct >= 35.0:
        return "Medium"
    return "Challenging"

router = APIRouter(prefix="/blog", tags=["blog"])

async def get_day_community_telemetry(session: AsyncSession, post_date: date) -> CommunityGameDebrief:
    try:
        day_res = await session.execute(
            select(CountrydleDay).where(CountrydleDay.date == post_date)
        )
        day = day_res.scalars().first()
        if not day:
            return CommunityGameDebrief(has_telemetry=False)

        # 1. Unified Player & Solver statistics (Counting unique authenticated AND guest players)
        part_repo = ParticipationRepository(session)
        stats = await part_repo.get_stats(post_date, "countrydle")
        tot_players = stats.get("total_players", 0)
        tot_wins = stats.get("winners_count", 0)
        win_rate = stats.get("win_rate_pct", 0.0)
        avg_q = stats.get("avg_questions_won", 0.0)
        avg_g = stats.get("avg_guesses_won", 0.0)

        # Fallback for legacy days before GuestParticipation tracking was deployed
        if tot_players == 0:
            active_states = await session.execute(
                select(
                    func.count(CountrydleState.id),
                    func.count().filter(CountrydleState.won.is_(True)),
                    func.avg(CountrydleState.questions_asked).filter(CountrydleState.won.is_(True)),
                    func.avg(CountrydleState.guesses_made).filter(CountrydleState.won.is_(True)),
                ).where(
                    CountrydleState.day_id == day.id,
                    or_(CountrydleState.questions_asked > 0, CountrydleState.guesses_made > 0)
                )
            )
            l_row = active_states.one()
            l_players = l_row[0] or 0
            l_wins = l_row[1] or 0

            anon_guesses = await session.execute(
                select(
                    func.count(CountrydleGuess.id),
                    func.count().filter(CountrydleGuess.answer.is_(True))
                ).where(CountrydleGuess.day_id == day.id, CountrydleGuess.user_id.is_(None))
            )
            anon_row = anon_guesses.one()
            anon_g = anon_row[0] or 0
            anon_w = anon_row[1] or 0

            if l_players > 0 or anon_g > 0:
                tot_players = l_players + (1 if anon_g > 0 else 0)
                tot_wins = l_wins + (1 if anon_w > 0 else 0)
                win_rate = round((tot_wins / tot_players * 100), 1) if tot_players > 0 else 0.0
                avg_q = round(float(l_row[2]), 1) if l_row[2] is not None else 0.0
                avg_g = round(float(l_row[3]), 1) if l_row[3] is not None else (1.0 if anon_w > 0 else 0.0)

        high_score_res = await session.execute(
            select(func.max(CountrydleState.points)).where(
                CountrydleState.day_id == day.id,
                CountrydleState.won.is_(True)
            )
        )
        high_score = high_score_res.scalar_one_or_none()
        # 2. Top community questions
        top_questions = []
        try:
            q_res = await session.execute(
                select(
                    CountrydleQuestion.question,
                    CountrydleQuestion.answer,
                    CountrydleQuestion.explanation,
                    func.count(CountrydleQuestion.id).label('cnt')
                )
                .where(CountrydleQuestion.day_id == day.id, CountrydleQuestion.valid.is_(True))
                .group_by(CountrydleQuestion.question, CountrydleQuestion.answer, CountrydleQuestion.explanation)
                .order_by(desc('cnt'))
                .limit(6)
            )
            for q in q_res.all():
                pct = min(100, round(q.cnt / tot_players * 100)) if tot_players > 0 else None
                top_questions.append(
                    TopQuestionStat(
                        question=q.question or "",
                        answer="YES" if q.answer else "NO",
                        count=q.cnt,
                        pct=pct,
                        explanation=q.explanation
                    )
                )
        except Exception as q_exc:
            logger.debug("Could not query top questions for %s: %s", post_date, q_exc)

        # 3. Common wrong guesses
        pitfalls = []
        try:
            g_res = await session.execute(
                select(CountrydleGuess.guess, func.count(CountrydleGuess.id).label('cnt'))
                .where(CountrydleGuess.day_id == day.id, CountrydleGuess.answer.is_(False))
                .group_by(CountrydleGuess.guess)
                .order_by(desc('cnt'))
                .limit(4)
            )
            pitfalls = [
                WrongGuessStat(guess=g.guess or "", count=g.cnt)
                for g in g_res.all() if g.guess
            ]
        except Exception as g_exc:
            logger.debug("Could not query common wrong guesses for %s: %s", post_date, g_exc)

        has_data = tot_players > 0
        return CommunityGameDebrief(
            has_telemetry=has_data,
            total_challengers=tot_players,
            total_solvers=tot_wins,
            win_rate_pct=win_rate,
            avg_questions_to_win=avg_q,
            avg_guesses=avg_g,
            high_score=high_score,
            top_questions=top_questions,
            common_pitfalls=pitfalls,
            decisive_clue=top_questions[-1].question if top_questions else None
        )
    except Exception as exc:
        logger.warning("Could not calculate community telemetry for %s: %s", post_date, exc)
        return CommunityGameDebrief(has_telemetry=False)


@router.get("", response_model=BlogPostListResponse)
async def list_blog_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    repo = BlogRepository(session)
    offset = (page - 1) * limit
    posts, total = await repo.list_posts(limit=limit, offset=offset, search=search)

    summaries = []
    for p in posts:
        c_name = p.country.name if p.country else "Unknown"
        p_stats = await repo.get_day_player_stats(p.date)
        win_rate = p_stats.get("win_rate_pct")
        tot_players = p_stats.get("total_players")
        summaries.append(
            BlogPostSummary(
                id=p.id,
                date=p.date,
                slug=p.slug,
                title=p.title,
                subtitle=p.subtitle,
                reading_time_minutes=p.reading_time_minutes,
                summary=p.summary,
                country_name=c_name,
                country_code=get_country_code(c_name),
                continent=resolve_country_continent(c_name),
                difficulty=compute_difficulty(win_rate),
                win_rate_pct=win_rate,
                total_players=tot_players,
                created_at=p.created_at or datetime.now(),
            )
        )

    return BlogPostListResponse(total=total, posts=summaries)


@router.get("/latest", response_model=BlogPostDisplay)
async def get_latest_blog_post(session: AsyncSession = Depends(get_db)):
    repo = BlogRepository(session)
    post = await repo.get_latest()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No blog posts available yet.",
        )

    stats = await repo.get_day_player_stats(post.date)
    c_name = post.country.name if post.country else "Unknown"
    win_rate = stats.get("win_rate_pct")

    return BlogPostDisplay(
        id=post.id,
        date=post.date,
        country_id=post.country_id,
        slug=post.slug,
        title=post.title,
        subtitle=post.subtitle,
        reading_time_minutes=post.reading_time_minutes,
        summary=post.summary,
        fast_facts=post.fast_facts,
        fun_facts=post.fun_facts,
        deduction_masterclass=post.deduction_masterclass,
        content_markdown=post.content_markdown,
        country_name=c_name,
        country_code=get_country_code(c_name),
        continent=resolve_country_continent(c_name),
        difficulty=compute_difficulty(win_rate),
        win_rate_pct=win_rate,
        total_players=stats.get("total_players"),
        country=post.country,
        player_stats=stats,
        game_debrief=await get_day_community_telemetry(session, post.date),
        created_at=post.created_at or datetime.now(),
    )


@router.get("/{slug_or_date}", response_model=BlogPostDisplay)
async def get_blog_post(slug_or_date: str, session: AsyncSession = Depends(get_db)):
    repo = BlogRepository(session)

    # 1. Try slug
    post = await repo.get_by_slug(slug_or_date)

    # 2. If not found, try parsing as ISO date
    if not post:
        try:
            parsed_date = date.fromisoformat(slug_or_date)
            post = await repo.get_by_date(parsed_date)
        except ValueError:
            pass

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog post '{slug_or_date}' not found.",
        )

    stats = await repo.get_day_player_stats(post.date)
    c_name = post.country.name if post.country else "Unknown"
    win_rate = stats.get("win_rate_pct")

    # 3. Dynamic related posts (up to 3 recent other posts)
    all_recent, _ = await repo.list_posts(limit=6, offset=0)
    related: List[BlogPostSummary] = []
    for rp in all_recent:
        if rp.id != post.id and len(related) < 3:
            rp_c_name = rp.country.name if rp.country else "Unknown"
            rp_stats = await repo.get_day_player_stats(rp.date)
            related.append(
                BlogPostSummary(
                    id=rp.id,
                    date=rp.date,
                    slug=rp.slug,
                    title=rp.title,
                    subtitle=rp.subtitle,
                    reading_time_minutes=rp.reading_time_minutes,
                    summary=rp.summary,
                    country_name=rp_c_name,
                    country_code=get_country_code(rp_c_name),
                    continent=resolve_country_continent(rp_c_name),
                    difficulty=compute_difficulty(rp_stats.get("win_rate_pct")),
                    win_rate_pct=rp_stats.get("win_rate_pct"),
                    total_players=rp_stats.get("total_players"),
                    created_at=rp.created_at or datetime.now(),
                )
            )

    return BlogPostDisplay(
        id=post.id,
        date=post.date,
        country_id=post.country_id,
        slug=post.slug,
        title=post.title,
        subtitle=post.subtitle,
        reading_time_minutes=post.reading_time_minutes,
        summary=post.summary,
        fast_facts=post.fast_facts,
        fun_facts=post.fun_facts,
        deduction_masterclass=post.deduction_masterclass,
        content_markdown=post.content_markdown,
        country_name=c_name,
        country_code=get_country_code(c_name),
        continent=resolve_country_continent(c_name),
        difficulty=compute_difficulty(win_rate),
        win_rate_pct=win_rate,
        total_players=stats.get("total_players"),
        country=post.country,
        player_stats=stats,
        game_debrief=await get_day_community_telemetry(session, post.date),
        related_posts=related,
        created_at=post.created_at or datetime.now(),
    )


@router.post("/generate-daily", response_model=BlogPostDisplay)
async def generate_yesterday_post_endpoint(
    target_date: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Generate yesterday's (or a specified date's) daily blog post if not yet generated.
    """
    if target_date:
        try:
            eval_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format, use YYYY-MM-DD",
            )
    else:
        eval_date = utc_today() - timedelta(days=1)

    repo = BlogRepository(session)
    existing = await repo.get_by_date(eval_date)
    if existing:
        return await get_blog_post(existing.slug, session)

    # Find the CountrydleDay for that date
    day_country = await CountrydleRepository(session).get_day_country_by_date(eval_date)
    if not day_country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No mystery country found for {eval_date.isoformat()}.",
        )

    from db.repositories.country import CountryRepository
    country = await CountryRepository(session).get(day_country.country_id)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Country not found for ID {day_country.country_id}.",
        )

    new_post = await create_daily_blog_post(session, country, eval_date)
    saved_post = await repo.create(new_post)
    logger.info(f"Generated daily blog post for {eval_date} ({country.name})")

    return await get_blog_post(saved_post.slug, session)
