from datetime import date

from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import (
    WojewodztwodleDay,
    WojewodztwodleState,
    WojewodztwodleGuess,
    WojewodztwodleQuestion,
)
from db.models.user import User
from schemas.wojewodztwodle import WojewodztwoGuessCreate, WojewodztwoQuestionCreate
from schemas.countrydle import LeaderboardEntry
from db.repositories.leaderboard import get_leaderboard as aggregate_leaderboard
from game_logic import count_consecutive_daily_wins


class WojewodztwodleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_wojewodztwo(self) -> Optional[WojewodztwodleDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(WojewodztwodleDay).where(WojewodztwodleDay.date == today)
        )
        return result.scalar_one_or_none()

    async def get_day_wojewodztwo_by_date(self, game_date: date) -> Optional[WojewodztwodleDay]:
        result = await self.session.execute(
            select(WojewodztwodleDay).where(WojewodztwodleDay.date == game_date)
        )
        return result.scalar_one_or_none()

    async def generate_new_day_wojewodztwo(self, cooldown_days: int = 10) -> WojewodztwodleDay:
        import random
        recent_subq = (
            select(WojewodztwodleDay.wojewodztwo_id)
            .where(WojewodztwodleDay.wojewodztwo_id.isnot(None))
            .order_by(WojewodztwodleDay.id.desc())
            .limit(cooldown_days)
        )
        recent_ids = set((await self.session.execute(recent_subq)).scalars().all())

        all_voivodeships = (await self.session.execute(select(Wojewodztwo))).scalars().all()
        if not all_voivodeships:
            raise Exception("No wojewodztwa found in database!")

        eligible = [w for w in all_voivodeships if w.id not in recent_ids]
        if not eligible:
            eligible = all_voivodeships

        wojewodztwo = random.choice(eligible)

        new_day = WojewodztwodleDay(wojewodztwo_id=wojewodztwo.id)
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)
        return new_day

    async def get_history(self) -> List[WojewodztwodleDay]:
        from datetime import date

        result = await self.session.execute(
            select(WojewodztwodleDay)
            .options(joinedload(WojewodztwodleDay.wojewodztwo))
            .where(WojewodztwodleDay.date < date.today())
            .order_by(WojewodztwodleDay.date.desc())
        )
        return result.scalars().all()


class WojewodztwodleStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self, user: User, day: WojewodztwodleDay
    ) -> Optional[WojewodztwodleState]:
        result = await self.session.execute(
            select(WojewodztwodleState).where(
                and_(
                    WojewodztwodleState.user_id == user.id,
                    WojewodztwodleState.day_id == day.id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_state(
        self,
        user: User,
        day: WojewodztwodleDay,
        max_questions: int = 5,
        max_guesses: int = 2,
    ) -> WojewodztwodleState:
        new_state = WojewodztwodleState(
            user_id=user.id,
            day_id=day.id,
            remaining_questions=max_questions,
            remaining_guesses=max_guesses,
        )
        self.session.add(new_state)
        await self.session.commit()
        await self.session.refresh(new_state)
        return new_state

    async def update_state(self, state: WojewodztwodleState) -> WojewodztwodleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_current_streak(self, user_id: int, puzzle_date: date) -> int:
        stmt = (
            select(WojewodztwodleDay.date, WojewodztwodleState.won)
            .join(WojewodztwodleDay, WojewodztwodleState.day_id == WojewodztwodleDay.id)
            .where(
                and_(
                    WojewodztwodleState.user_id == user_id,
                    WojewodztwodleState.is_game_over == True,
                    WojewodztwodleDay.date < puzzle_date,
                )
            )
            .order_by(WojewodztwodleDay.date.desc())
        )
        result = await self.session.execute(stmt)
        completed_games = [(row.date, row.won) for row in result.all()]
        return count_consecutive_daily_wins(completed_games, puzzle_date)

    async def calc_points(
        self,
        state: WojewodztwodleState,
        elapsed_seconds: int | None = None,
        streak: int = 0,
    ) -> int:
        from game_logic import calculate_points, WOJEWODZTWDLE_CONFIG
        return calculate_points(
            config=WOJEWODZTWDLE_CONFIG,
            won=state.won,
            questions_used=state.questions_asked,
            guesses_used=state.guesses_made,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )
    async def get_leaderboard(self, type: str = "monthly") -> List[LeaderboardEntry]:
        return await aggregate_leaderboard(
            self.session,
            WojewodztwodleState,
            WojewodztwodleDay,
            type,
            minimum_average_games=5,
        )


class WojewodztwodleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(
        self, guess_create: WojewodztwoGuessCreate
    ) -> WojewodztwodleGuess:
        new_guess = WojewodztwodleGuess(**guess_create.model_dump(exclude={"elapsed_seconds"}))
        self.session.add(new_guess)
        await self.session.commit()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_day_guesses(
        self, user: User, day: WojewodztwodleDay
    ) -> List[WojewodztwodleGuess]:
        result = await self.session.execute(
            select(WojewodztwodleGuess)
            .where(
                and_(
                    WojewodztwodleGuess.user_id == user.id,
                    WojewodztwodleGuess.day_id == day.id,
                )
            )
            .order_by(WojewodztwodleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())


class WojewodztwodleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(
        self, question_create: WojewodztwoQuestionCreate
    ) -> WojewodztwodleQuestion:
        data = question_create.model_dump()
        # Remove fields that are not in the DB model
        data.pop("intent", None)
        data.pop("required_info", None)
        new_question = WojewodztwodleQuestion(**data)
        self.session.add(new_question)
        await self.session.commit()
        await self.session.refresh(new_question)
        return new_question


    async def get_user_day_questions(
        self, user: User, day: WojewodztwodleDay
    ) -> List[WojewodztwodleQuestion]:
        result = await self.session.execute(
            select(WojewodztwodleQuestion)
            .where(
                and_(
                    WojewodztwodleQuestion.user_id == user.id,
                    WojewodztwodleQuestion.day_id == day.id,
                )
            )
            .order_by(WojewodztwodleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_questions(
        self, limit: int | None = None, offset: int = 0
    ) -> List[WojewodztwodleQuestion]:
        query = (
            select(WojewodztwodleQuestion)
            .options(
                joinedload(WojewodztwodleQuestion.user),
                joinedload(WojewodztwodleQuestion.day).joinedload(WojewodztwodleDay.wojewodztwo)
            )
            .order_by(WojewodztwodleQuestion.asked_at.desc())
        )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        result = await self.session.execute(
            query
        )
        return list(result.scalars().all())

    async def count_questions(self) -> int:
        result = await self.session.execute(select(func.count(WojewodztwodleQuestion.id)))
        return int(result.scalar_one())
