from datetime import date

from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.powiat import Powiat
from db.models.powiatdle import (
    PowiatdleDay,
    PowiatdleState,
    PowiatdleGuess,
    PowiatdleQuestion,
)
from db.models.user import User
from schemas.powiatdle import PowiatGuessCreate, PowiatQuestionCreate
from schemas.countrydle import LeaderboardEntry
from db.repositories.leaderboard import get_leaderboard as aggregate_leaderboard
from game_logic import count_consecutive_daily_wins


class PowiatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Powiat]:
        result = await self.session.execute(select(Powiat))
        return list(result.scalars().all())

    async def get(self, powiat_id: int) -> Optional[Powiat]:
        result = await self.session.execute(
            select(Powiat).where(Powiat.id == powiat_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, nazwa: str) -> Optional[Powiat]:
        result = await self.session.execute(select(Powiat).where(Powiat.nazwa == nazwa))
        return result.scalar_one_or_none()


class PowiatdleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_powiat(self) -> Optional[PowiatdleDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(PowiatdleDay).where(PowiatdleDay.date == today)
        )
        return result.scalar_one_or_none()

    async def get_day_powiat_by_date(self, game_date: date) -> Optional[PowiatdleDay]:
        result = await self.session.execute(
            select(PowiatdleDay).where(PowiatdleDay.date == game_date)
        )
        return result.scalar_one_or_none()

    async def generate_new_day_powiat(self, cooldown_days: int = 90) -> PowiatdleDay:
        import random
        recent_subq = (
            select(PowiatdleDay.powiat_id)
            .where(PowiatdleDay.powiat_id.isnot(None))
            .order_by(PowiatdleDay.id.desc())
            .limit(cooldown_days)
        )
        recent_ids = set((await self.session.execute(recent_subq)).scalars().all())

        all_powiaty = (await self.session.execute(select(Powiat))).scalars().all()
        if not all_powiaty:
            raise Exception("No powiaty found in database!")

        eligible = [p for p in all_powiaty if p.id not in recent_ids]
        if not eligible:
            eligible = all_powiaty

        powiat = random.choice(eligible)

        new_day = PowiatdleDay(powiat_id=powiat.id)
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)
        return new_day

    async def get_history(self) -> List[PowiatdleDay]:
        from datetime import date

        result = await self.session.execute(
            select(PowiatdleDay)
            .options(joinedload(PowiatdleDay.powiat))
            .where(PowiatdleDay.date < date.today())
            .order_by(PowiatdleDay.date.desc())
        )
        return result.scalars().all()


class PowiatdleStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self, user: User, day: PowiatdleDay
    ) -> Optional[PowiatdleState]:
        result = await self.session.execute(
            select(PowiatdleState).where(
                and_(PowiatdleState.user_id == user.id, PowiatdleState.day_id == day.id)
            )
        )
        return result.scalar_one_or_none()

    async def create_state(
        self,
        user: User,
        day: PowiatdleDay,
        max_questions: int = 15,
        max_guesses: int = 3,
    ) -> PowiatdleState:
        from db.repositories.question_accounting import lock_question_state
        existing = await lock_question_state(self.session, PowiatdleState, user.id, day.id)
        if existing is not None:
            await self.session.commit()
            return existing
        new_state = PowiatdleState(
            user_id=user.id,
            day_id=day.id,
            remaining_questions=max_questions,
            remaining_guesses=max_guesses,
        )
        self.session.add(new_state)
        await self.session.commit()
        await self.session.refresh(new_state)
        return new_state

    async def update_state(self, state: PowiatdleState) -> PowiatdleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_current_streak(self, user_id: int, puzzle_date: date) -> int:
        stmt = (
            select(PowiatdleDay.date, PowiatdleState.won)
            .join(PowiatdleDay, PowiatdleState.day_id == PowiatdleDay.id)
            .where(
                and_(
                    PowiatdleState.user_id == user_id,
                    PowiatdleState.is_game_over == True,
                    PowiatdleDay.date < puzzle_date,
                )
            )
            .order_by(PowiatdleDay.date.desc())
        )
        result = await self.session.execute(stmt)
        completed_games = [(row.date, row.won) for row in result.all()]
        return count_consecutive_daily_wins(completed_games, puzzle_date)

    async def calc_points(
        self,
        state: PowiatdleState,
        elapsed_seconds: int | None = None,
        streak: int = 0,
    ) -> int:
        from game_logic import calculate_points, POWIATDLE_CONFIG
        base = calculate_points(
            config=POWIATDLE_CONFIG,
            won=state.won,
            questions_used=state.questions_asked,
            guesses_used=state.guesses_made,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )
        # Powiaty difficulty bonus (+500 for solving one of 380 counties)
        return (base + 500) if state.won else 0
    async def get_leaderboard(self, type: str = "monthly") -> List[LeaderboardEntry]:
        return await aggregate_leaderboard(
            self.session,
            PowiatdleState,
            PowiatdleDay,
            type,
            minimum_average_games=5,
        )



class PowiatdleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: PowiatGuessCreate, *, commit: bool = True) -> PowiatdleGuess:
        new_guess = PowiatdleGuess(**guess_create.model_dump(exclude={"elapsed_seconds"}))
        self.session.add(new_guess)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_day_guesses(
        self, user: User, day: PowiatdleDay
    ) -> List[PowiatdleGuess]:
        result = await self.session.execute(
            select(PowiatdleGuess)
            .where(
                and_(PowiatdleGuess.user_id == user.id, PowiatdleGuess.day_id == day.id)
            )
            .order_by(PowiatdleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())


class PowiatdleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(
        self, question_create: PowiatQuestionCreate
    ) -> PowiatdleQuestion:
        data = question_create.model_dump()
        # Remove fields that are not in the DB model
        data.pop("intent", None)
        data.pop("required_info", None)
        new_question = PowiatdleQuestion(**data)
        self.session.add(new_question)
        await self.session.flush()
        return new_question


    async def get_user_day_questions(
        self, user: User, day: PowiatdleDay
    ) -> List[PowiatdleQuestion]:
        result = await self.session.execute(
            select(PowiatdleQuestion)
            .where(
                and_(
                    PowiatdleQuestion.user_id == user.id,
                    PowiatdleQuestion.day_id == day.id,
                    PowiatdleQuestion.valid.is_(True),
                    PowiatdleQuestion.answer.is_not(None),
                )
            )
            .order_by(PowiatdleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_questions(
        self, limit: int | None = None, offset: int = 0
    ) -> List[PowiatdleQuestion]:
        query = (
            select(PowiatdleQuestion)
            .options(
                joinedload(PowiatdleQuestion.user),
                joinedload(PowiatdleQuestion.day).joinedload(PowiatdleDay.powiat)
            )
            .order_by(PowiatdleQuestion.asked_at.desc())
        )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        result = await self.session.execute(
            query
        )
        return list(result.scalars().all())

    async def count_questions(self) -> int:
        result = await self.session.execute(select(func.count(PowiatdleQuestion.id)))
        return int(result.scalar_one())
