import logging
import random
from datetime import date, timedelta
from typing import Set

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from continental.utils import get_continent_country_ids
from db.models.continental import ContinentCode, ContinentalDay
from db.repositories.continental import COOLDOWN_DAYS

logger = logging.getLogger("countrydle.continental.scheduler")


async def generate_continental_days(session: AsyncSession, days_ahead: int = 5):
    """Generate daily puzzles for Europe, Asia, Africa, and Americas for the next N days."""
    today = date.today()
    for offset in range(days_ahead):
        day_date = today + timedelta(days=offset)

        # Track countries chosen on this specific day across continents to prevent same-day collisions
        chosen_today_country_ids: Set[int] = set()

        # Check existing entries for day_date
        existing_res = await session.execute(
            select(ContinentalDay).where(ContinentalDay.date == day_date)
        )
        existing_days = {d.continent: d for d in existing_res.scalars().all()}
        for d in existing_days.values():
            chosen_today_country_ids.add(d.country_id)

        for continent in ContinentCode:
            if continent in existing_days:
                continue

            cooldown = COOLDOWN_DAYS.get(continent, 30)
            recent_res = await session.execute(
                select(ContinentalDay.country_id).where(
                    and_(
                        ContinentalDay.continent == continent,
                        ContinentalDay.date >= day_date - timedelta(days=cooldown),
                        ContinentalDay.date < day_date,
                    )
                )
            )
            recent_ids = set(recent_res.scalars().all())

            # Fetch candidate countries for this continent
            candidate_ids = await get_continent_country_ids(continent, session)
            if not candidate_ids:
                logger.error("No candidate countries found for %s", continent)
                continue

            # Eligible = candidate - recent cooldown - countries already picked today in other continental modes
            eligible_ids = [
                cid
                for cid in candidate_ids
                if cid not in recent_ids and cid not in chosen_today_country_ids
            ]

            # Fallback if over-constrained
            if not eligible_ids:
                eligible_ids = [
                    cid for cid in candidate_ids if cid not in chosen_today_country_ids
                ]
            if not eligible_ids:
                eligible_ids = candidate_ids

            selected_id = random.choice(eligible_ids)
            chosen_today_country_ids.add(selected_id)

            new_day = ContinentalDay(
                continent=continent,
                country_id=selected_id,
                date=day_date,
            )
            session.add(new_day)

    await session.commit()
    logger.info("Successfully checked/generated continental puzzles through %s", today + timedelta(days=days_ahead))
