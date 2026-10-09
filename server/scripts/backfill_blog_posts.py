import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import desc, select

# Add server to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from db import AsyncSessionLocal
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.models.countrydle import CountrydleDay
from db.repositories.blog import BlogRepository
from utils.blog_generator import create_daily_blog_post

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_blog_posts(days_count: int = 5):
    logger.info(f"Starting blog post backfill for up to {days_count} past days...")
    today = datetime.now(timezone.utc).date()

    async with AsyncSessionLocal() as session:
        # Snapshot scalar inputs, including existence, before provider I/O.
        # Never include the current or future UTC puzzle in a historical recap.
        stmt = (
            select(CountrydleDay.date, Country.id.label("country_id"),
                   Country.name.label("country_name"), DailyBlogPost.id.label("post_id"))
            .outerjoin(Country, Country.id == CountrydleDay.country_id)
            .outerjoin(DailyBlogPost, DailyBlogPost.date == CountrydleDay.date)
            .where(CountrydleDay.date < today)
            .order_by(desc(CountrydleDay.date))
            .limit(days_count)
        )
        res = await session.execute(stmt)
        past_days = list(res.all())
        engine = session.bind

    logger.info(f"Found {len(past_days)} past Countrydle days to check.")
    for day in past_days:
        if day.country_id is None:
            continue
        if day.post_id is not None:
            logger.info(f"Post for {day.date} ({day.country_name}) already exists. Skipping.")
            continue

        logger.info(f"Generating blog post for {day.date} ({day.country_name})...")
        try:
            post = await create_daily_blog_post(engine, day.country_id, day.country_name, day.date)
            async with AsyncSessionLocal() as session:
                await BlogRepository(session).create(post)
            logger.info(f"Successfully created post for {day.date}: '{post.title}'")
        except Exception as e:
            logger.error(f"Failed to generate post for {day.date}: {e}", exc_info=True)


if __name__ == "__main__":
    count = 5
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    asyncio.run(backfill_blog_posts(count))
