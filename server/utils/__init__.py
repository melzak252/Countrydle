from datetime import date, timedelta
import logging


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db import AsyncSessionLocal
from db.base import Base
from db.models import *  # noqa: F403
from db.repositories.countrydle import CountrydleRepository, CountrydleStateRepository
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import select

from db.repositories.user import UserRepository


async def check_streaks():
    async with AsyncSessionLocal() as session:
        u_repo = UserRepository(session)
        cs_repo = CountrydleStateRepository(session)

        users = await u_repo.get_all_verified_users()
        yesterday = date.today() - timedelta(days=1)
        dc_yesterday = await CountrydleRepository(session).get_day_country_by_date(
            yesterday
        )

        if dc_yesterday is None:
            logging.error(f"DayCountry for {yesterday} not found.")
            return

        for user in users:
            points = await u_repo.get_user_points(user.id)
            if not points:
                points = await u_repo.add_user_points(user.id)

            yesterday_state = await cs_repo.get_player_countrydle_state(
                user, dc_yesterday
            )

            if yesterday_state is None or not yesterday_state.is_game_over:
                points.streak = 0

            await session.commit()


async def generate_day_countries():
    async with AsyncSessionLocal() as session:
        c_repo = CountrydleRepository(session)

        for day_date in (date.today() + timedelta(days=n) for n in range(5)):
            # Existing rows, including preserved played targets, must not stop
            # generation for later dates. Gameplay lookups enforce eligibility.
            day_country = await session.scalar(
                select(CountrydleDay.id).where(CountrydleDay.date == day_date)
            )
            if day_country is not None:
                logging.info(f"DayCountry for {day_date} already exists.")
                continue

            print(f"Generating country for {day_date}")
            await c_repo.generate_new_day_country(day_date)

async def generate_day_flags():
    from flagdle.scheduler import generate_day_flags as _gen_flags
    await _gen_flags()


async def generate_yesterday_blog_post():
    from db.repositories.blog import BlogRepository
    from utils.blog_generator import create_daily_blog_post

    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as session:
        repo = BlogRepository(session)
        existing = await repo.get_by_date(yesterday)
        if existing:
            logging.info(f"Blog post for {yesterday} already exists.")
            return

        day_country = await CountrydleRepository(session).get_day_country_by_date(yesterday)
        if not day_country:
            logging.warning(f"No CountrydleDay found for {yesterday} to generate blog post.")
            return

        from db.repositories.country import CountryRepository
        country = await CountryRepository(session).get(day_country.country_id)
        if not country:
            logging.warning(f"No Country found for ID {day_country.country_id} to generate blog post.")
            return

        try:
            post = await create_daily_blog_post(session, country, yesterday)
            await repo.create(post)
            logging.info(f"Successfully generated daily blog post for {yesterday} ({country.name}).")
        except Exception as e:
            logging.error(f"Error generating daily blog post for {yesterday}: {e}", exc_info=True)

async def run_generate_continental_days():
    try:
        async with AsyncSessionLocal() as session:
            from continental.scheduler import generate_continental_days
            await generate_continental_days(session, days_ahead=5)
    except Exception as e:
        logging.error(f"Error generating continental days: {e}", exc_info=True)

scheduler = AsyncIOScheduler()
scheduler.add_job(generate_day_countries, CronTrigger(hour=0, minute=0))
scheduler.add_job(check_streaks, CronTrigger(hour=0, minute=0))
scheduler.add_job(generate_yesterday_blog_post, CronTrigger(hour=0, minute=5))
scheduler.add_job(run_generate_continental_days, CronTrigger(hour=0, minute=0))
scheduler.add_job(generate_day_flags, CronTrigger(hour=0, minute=0))
