from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.english_county import EnglishCounty


class EnglishCountyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[EnglishCounty]:
        result = await self.session.execute(
            select(EnglishCounty).order_by(EnglishCounty.name.asc())
        )
        return list(result.scalars().all())

    async def get(self, county_id: int) -> Optional[EnglishCounty]:
        result = await self.session.execute(
            select(EnglishCounty).where(EnglishCounty.id == county_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[EnglishCounty]:
        result = await self.session.execute(
            select(EnglishCounty).where(EnglishCounty.name == name)
        )
        return result.scalar_one_or_none()
