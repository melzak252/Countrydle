import argparse
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def regenerate_recent(days_count: int = 14):
    logger.info(f"Starting regeneration of the last {days_count} daily blog posts with Gemini...")
    async with AsyncSessionLocal() as session:
        posts_res = await session.execute(
            select(DailyBlogPost.id, DailyBlogPost.date, DailyBlogPost.country_id,
                   DailyBlogPost.updated_at, Country.name.label("country_name"))
            .outerjoin(Country, Country.id == DailyBlogPost.country_id)
            .order_by(desc(DailyBlogPost.date)).limit(days_count)
        )
        posts = list(posts_res.all())
        engine = session.bind
    # Snapshot scalar values and release the read transaction before slow generation.
    logger.info(f"Found {len(posts)} posts to regenerate.")

    for idx, post in enumerate(posts, 1):
        if not post.country_name:
            logger.warning(f"[{idx}/{len(posts)}] Country ID {post.country_id} not found, skipping.")
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
            quiz = (new_post.deduction_masterclass or {}).get("quiz")
            quiz_q = quiz.get("question") if quiz else "No quiz"
            logger.info(f"  ✓ Updated {post.country_name}: '{new_post.title}'")
            logger.info(f"    Quiz: {quiz_q}")
        except Exception as e:
            logger.error(f"  ✗ Error regenerating {post.country_name}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate recent daily blog posts using Gemini.")
    parser.add_argument("--days", type=int, default=14, help="Number of recent posts to regenerate (default: 14)")
    args = parser.parse_args()
    asyncio.run(regenerate_recent(args.days))
