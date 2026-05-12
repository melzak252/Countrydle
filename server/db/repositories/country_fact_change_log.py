from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.country_fact_change_log import CountryFactChangeLog


class CountryFactChangeLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> CountryFactChangeLog:
        entry = CountryFactChangeLog(**kwargs)
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def get_recent(self, limit: int = 50, offset: int = 0) -> list[CountryFactChangeLog]:
        result = await self.session.execute(
            select(CountryFactChangeLog)
            .order_by(CountryFactChangeLog.created_at.desc(), CountryFactChangeLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
