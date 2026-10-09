import asyncio
import logging
import os
import sys
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import desc, select

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from db import AsyncSessionLocal
from db.models.blog import DailyBlogPost
from db.models.country import Country
from utils.blog_generator import create_daily_blog_post

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def regenerate_all():
    logger.info("Starting regeneration of all daily blog posts with anti-slop engine...")
    async with AsyncSessionLocal() as session:
        posts_res = await session.execute(
            select(DailyBlogPost).order_by(desc(DailyBlogPost.date))
        )
        posts = list(posts_res.scalars().all())
        logger.info(f"Found {len(posts)} posts to regenerate.")

        for idx, post in enumerate(posts, 1):
            country = await session.get(Country, post.country_id)
            if not country:
                continue

            if "### The Deduction Path" in (post.content_markdown or ""):
                logger.info(f"[{idx}/{len(posts)}] Skipping {post.date} ({country.name}) - already clean.")
                continue

            logger.info(f"[{idx}/{len(posts)}] Regenerating post for {post.date} ({country.name})...")
            try:
                new_post = await create_daily_blog_post(session, country, post.date)
                post.title = new_post.title
                post.subtitle = new_post.subtitle
                post.summary = new_post.summary
                post.fast_facts = new_post.fast_facts
                post.fun_facts = new_post.fun_facts
                post.deduction_masterclass = new_post.deduction_masterclass
                post.content_markdown = new_post.content_markdown
                post.source_links = new_post.source_links
                post.editorial_note = new_post.editorial_note
                post.ai_assisted = new_post.ai_assisted
                post.reviewed_by_id = None
                post.reviewed_at = None
                post.updated_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(f"  ✓ Updated {country.name}")
            except Exception as e:
                logger.error(f"  ✗ Error regenerating {country.name}: {e}")


if __name__ == "__main__":
    asyncio.run(regenerate_all())
