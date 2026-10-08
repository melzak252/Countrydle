from typing import List
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CountrydleDay, CountrydleGuess, User
from schemas.countrydle import (
    GuessCreate,
)


class CountrydleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, gid: int) -> CountrydleGuess:
        result = await self.session.execute(select(CountrydleGuess).where(CountrydleGuess.id == gid))

        return result.scalars().first()

    async def add_guess(
        self, guess: GuessCreate, *, commit: bool = True, guest_id: str | None = None
    ) -> CountrydleGuess:
        data = guess.model_dump(exclude={"country_id"})
        if guest_id is not None:
            data["guest_id"] = guest_id
        new_entry = CountrydleGuess(**data)
        self.session.add(new_entry)

        try:
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
            await self.session.refresh(new_entry)
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return new_entry

    async def get_user_day_guesses(self, user: User, day: CountrydleDay) -> List[CountrydleGuess]:
        questions_result = await self.session.execute(
            select(CountrydleGuess).where(CountrydleGuess.user_id == user.id, CountrydleGuess.day_id == day.id)
        )

        return questions_result.scalars().all()

    async def get_user_guess_statistics(self, user: User) -> List[CountrydleGuess]:
        questions_result = await self.session.execute(
            select(
                func.count(CountrydleGuess.id).label("count"),
                func.sum(CountrydleGuess.answer.cast(Integer)).label("correct"),
                func.sum((CountrydleGuess.answer == False).cast(Integer)).label("incorrect"),
            ).where(CountrydleGuess.user_id == user.id)
        )
        row = questions_result.first()
        return row
