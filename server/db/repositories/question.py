from typing import List, Any
from sqlalchemy import Integer, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import CountrydleDay, CountrydleQuestion, User
from schemas.countrydle import (
    QuestionCreate,
)


class CountrydleQuestionsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, qid: int) -> CountrydleQuestion | None:
        result = await self.session.execute(select(CountrydleQuestion).where(CountrydleQuestion.id == qid))

        return result.scalars().first()

    async def create_question(self, quesiton: QuestionCreate) -> CountrydleQuestion:
        data = quesiton.model_dump()
        # Remove fields that are not in the DB model
        data.pop("intent", None)
        data.pop("required_info", None)
        new_entry = CountrydleQuestion(**data)

        self.session.add(new_entry)


        try:
            await self.session.commit()  # Commit the transaction
            await self.session.refresh(new_entry)  # Refresh the instance to get the ID
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return new_entry

    async def get_user_day_questions(
        self, user: User, day: CountrydleDay
    ) -> List[CountrydleQuestion]:
        questions_result = await self.session.execute(
            select(CountrydleQuestion)
            .where(CountrydleQuestion.user_id == user.id, CountrydleQuestion.day_id == day.id)
            .order_by(CountrydleQuestion.id.asc())
        )
        return list(questions_result.scalars().all())

    async def get_user_question_statistics(self, user: User) -> Any:

        questions_result = await self.session.execute(
            select(
                func.count(CountrydleQuestion.id).label("count"),
                func.sum(CountrydleQuestion.answer.cast(Integer)).label("correct"),
                func.sum((CountrydleQuestion.answer == False).cast(Integer)).label("incorrect"),
            ).where(and_(CountrydleQuestion.user_id == user.id, CountrydleQuestion.valid == True))
        )
        row = questions_result.first()
        print(row)
        return row

    async def get_all_questions(
        self, limit: int | None = None, offset: int = 0
    ) -> List[CountrydleQuestion]:
        query = (
            select(CountrydleQuestion)
            .options(
                joinedload(CountrydleQuestion.user),
                joinedload(CountrydleQuestion.day).joinedload(CountrydleDay.country)
            )
            .order_by(CountrydleQuestion.asked_at.desc())
        )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        result = await self.session.execute(
            query
        )
        return list(result.scalars().all())

    async def count_questions(self) -> int:
        result = await self.session.execute(select(func.count(CountrydleQuestion.id)))
        return int(result.scalar_one())
