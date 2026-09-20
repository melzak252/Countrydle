import logging
from datetime import date, datetime, timedelta
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

logger = logging.getLogger(__name__)

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

    summaries = [
        BlogPostSummary(
            id=p.id,
            date=p.date,
            slug=p.slug,
            title=p.title,
            subtitle=p.subtitle,
            reading_time_minutes=p.reading_time_minutes,
            summary=p.summary,
            country_name=p.country.name if p.country else "Unknown",
            country_code=get_country_code(p.country.name if p.country else ""),
            created_at=p.created_at or datetime.now(),
        )
        for p in posts
    ]

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
        country_name=post.country.name if post.country else "Unknown",
        country_code=get_country_code(post.country.name if post.country else ""),
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
        country_name=post.country.name if post.country else "Unknown",
        country_code=get_country_code(post.country.name if post.country else ""),
        country=post.country,
        player_stats=stats,
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
    if not day_country or not day_country.country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No mystery country found for {eval_date.isoformat()}.",
        )

    new_post = await create_daily_blog_post(session, day_country.country, eval_date)
    saved_post = await repo.create(new_post)
    logger.info(f"Generated daily blog post for {eval_date} ({day_country.country.name})")

    return await get_blog_post(saved_post.slug, session)
