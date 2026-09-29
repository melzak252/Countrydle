import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.countrydle import CountrydleDay
from db.repositories.blog import BlogRepository
from db.repositories.countrydle import CountrydleRepository
from schemas.blog import BlogPostDisplay, BlogPostListResponse, BlogPostSummary
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
        eval_date = date.today() - timedelta(days=1)

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
