from __future__ import annotations

from datetime import timedelta
import logging

from db import AsyncSessionLocal
from db.repositories.flagdle import FlagdleDayRepository
from daily_clock import utc_today

logger = logging.getLogger("countrydle.flagdle")


async def generate_day_flags() -> None:
    """Pre-generates Flagdle targets for the next 5 days."""
    async with AsyncSessionLocal() as session:
        repo = FlagdleDayRepository(session)
        today = utc_today()
        for day_date in (today + timedelta(days=n) for n in range(5)):
            try:
                existing = await repo.get_day_flag_by_date(day_date)
                if existing is not None:
                    continue
                logger.info("Generating Flagdle target for %s", day_date)
                await repo.generate_new_day_flag(day_date)
            except Exception as e:
                logger.error("Error generating Flagdle target for %s: %s", day_date, e, exc_info=True)
                raise
