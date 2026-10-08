import asyncio
import logging
import os
import sys
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

# Add server to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from db import AsyncSessionLocal
from db.models.blog import DailyBlogPost
from db.models.countrydle import CountrydleDay
from db.repositories.blog import BlogRepository
from utils.blog_generator import create_daily_blog_post

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_blog_posts(days_count: int = 5):
    logger.info(f"Starting blog post backfill for up to {days_count} past days...")
    today = date.today()

    async with AsyncSessionLocal() as session:
        repo = BlogRepository(session)

        # Query past CountrydleDays before today
        stmt = (
            select(CountrydleDay)
            .options(joinedload(CountrydleDay.country))
            .where(CountrydleDay.date < today)
            .order_by(desc(CountrydleDay.date))
            .limit(days_count)
        )
        res = await session.execute(stmt)
        past_days = list(res.scalars().all())

        logger.info(f"Found {len(past_days)} past Countrydle days to check.")

        for day in past_days:
            if not day.country:
                continue

            existing = await repo.get_by_date(day.date)
            if existing:
                logger.info(f"Post for {day.date} ({day.country.name}) already exists. Skipping.")
                continue

            logger.info(f"Generating blog post for {day.date} ({day.country.name})...")
            try:
                post = await create_daily_blog_post(session, day.country, day.date)
                await repo.create(post)
                logger.info(f"Successfully created post for {day.date}: '{post.title}'")
            except Exception as e:
                logger.error(f"Failed to generate post for {day.date}: {e}", exc_info=True)


if __name__ == "__main__":
    count = 5
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    asyncio.run(backfill_blog_posts(count))
