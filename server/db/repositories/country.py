from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from country_eligibility import excluded_country_names, is_country_eligible

from db.models import Country
from schemas.country import CountryBase


class CountryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, cid: int) -> Country:
        result = await self.session.execute(select(Country).where(Country.id == cid))

        return result.scalars().first()

    async def get_all_countries(self) -> List[Country]:
        result = await self.session.execute(
            select(Country).where(Country.name.notin_(excluded_country_names()))
        )

        return list(result.scalars().all())

    async def get_country_by_name(self, name: str) -> Country | None:
        result = await self.session.execute(
            select(Country).where(Country.name.ilike(name))
        )

        return result.scalars().first()

    async def validate_guess(self, country_id: int | None, name: str, mode: str | None = None) -> None:
        if not is_country_eligible(name, mode):
            raise HTTPException(status_code=400, detail="Country is not eligible for this game.")
        if country_id is not None and country_id > 0:
            country = await self.get(country_id)
            if country and not is_country_eligible(country.name, mode):
                raise HTTPException(status_code=400, detail="Country is not eligible for this game.")

    async def create_country(self, country: CountryBase) -> Country:
        new_entry = Country(**country.model_dump())

        self.session.add(new_entry)

        try:
            await self.session.commit()  # Commit the transaction
            await self.session.refresh(new_entry)  # Refresh the instance to get the ID
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return new_entry
