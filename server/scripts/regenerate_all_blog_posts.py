import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import desc, select

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from db import AsyncSessionLocal
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.repositories.blog import BlogRepository
from schemas.blog import BlogPostUpdate
from utils.blog_generator import create_daily_blog_post

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def regenerate_all():
    logger.info("Starting regeneration of all daily blog posts with anti-slop engine...")
    async with AsyncSessionLocal() as session:
        posts_res = await session.execute(
            select(DailyBlogPost.id, DailyBlogPost.date, DailyBlogPost.country_id,
                   DailyBlogPost.updated_at, DailyBlogPost.content_markdown,
                   Country.name.label("country_name"))
            .outerjoin(Country, Country.id == DailyBlogPost.country_id)
            .order_by(desc(DailyBlogPost.date))
        )
        posts = list(posts_res.all())
        engine = session.bind
    # Preserve the exact original version; do not hold a DB transaction during I/O.
    logger.info(f"Found {len(posts)} posts to regenerate.")

    for idx, post in enumerate(posts, 1):
        if not post.country_name:
            logger.warning(f"[{idx}/{len(posts)}] Country ID {post.country_id} not found, skipping.")
            continue
        if "### The Deduction Path" in (post.content_markdown or ""):
            logger.info(f"[{idx}/{len(posts)}] Skipping {post.date} ({post.country_name}) - already clean.")
            continue
        logger.info(f"[{idx}/{len(posts)}] Regenerating post for {post.date} ({post.country_name})...")
        try:
            new_post = await create_daily_blog_post(engine, post.country_id, post.country_name, post.date)
            payload = {field: getattr(new_post, field) for field in BlogPostUpdate.model_fields}
            payload["ai_assisted"] = new_post.ai_assisted
            async with AsyncSessionLocal() as session:
                replaced = await BlogRepository(session).replace_generated(post.id, payload, post.updated_at)
            if not replaced:
                logger.warning(f"  Skipped {post.country_name}: article changed or was deleted during generation.")
                continue
            logger.info(f"  ✓ Updated {post.country_name}")
        except Exception as e:
            logger.error(f"  ✗ Error regenerating {post.country_name}: {e}")


if __name__ == "__main__":
    asyncio.run(regenerate_all())
