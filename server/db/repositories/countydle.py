from datetime import date
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models.countydle import (
    CountydleDay,
    CountydleGuess,
    CountydleQuestion,
    CountydleState,
)
from db.models.english_county import EnglishCounty
from db.models.user import User
from db.repositories.leaderboard import get_leaderboard as aggregate_leaderboard
from game_logic import count_consecutive_daily_wins
from schemas.countrydle import LeaderboardEntry
from schemas.countydle import EnglishCountyGuessCreate, EnglishCountyQuestionCreate


class CountydleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_county(self) -> Optional[CountydleDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(CountydleDay).where(CountydleDay.date == today)
        )
        return result.scalar_one_or_none()

    async def get_day_county_by_date(self, game_date: date) -> Optional[CountydleDay]:
        result = await self.session.execute(
            select(CountydleDay).where(CountydleDay.date == game_date)
        )
        return result.scalar_one_or_none()

    async def generate_new_day_county(self, cooldown_days: int = 25) -> CountydleDay:
        import random

        recent_subq = (
            select(CountydleDay.county_id)
            .where(CountydleDay.county_id.isnot(None))
            .order_by(CountydleDay.id.desc())
            .limit(cooldown_days)
        )
        recent_ids = set((await self.session.execute(recent_subq)).scalars().all())

        all_counties = (await self.session.execute(select(EnglishCounty))).scalars().all()
        if not all_counties:
            raise Exception("No English counties found in database!")

        eligible = [c for c in all_counties if c.id not in recent_ids]
        if not eligible:
            eligible = all_counties

        county = random.choice(eligible)

        new_day = CountydleDay(county_id=county.id)
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)
        return new_day

    async def get_history(self) -> List[CountydleDay]:
        result = await self.session.execute(
            select(CountydleDay)
            .options(joinedload(CountydleDay.county))
            .where(CountydleDay.date < date.today())
            .order_by(CountydleDay.date.desc())
        )
        return list(result.scalars().all())


class CountydleStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self, user: User, day: CountydleDay
    ) -> Optional[CountydleState]:
        result = await self.session.execute(
            select(CountydleState).where(
                and_(
                    CountydleState.user_id == user.id,
                    CountydleState.day_id == day.id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_state(
        self,
        user: User,
        day: CountydleDay,
        max_questions: int = 8,
        max_guesses: int = 3,
    ) -> CountydleState:
        from db.repositories.question_accounting import lock_question_state

        existing = await lock_question_state(self.session, CountydleState, user.id, day.id)
        if existing is not None:
            await self.session.commit()
            return existing
        new_state = CountydleState(
            user_id=user.id,
            day_id=day.id,
            remaining_questions=max_questions,
            remaining_guesses=max_guesses,
        )
        self.session.add(new_state)
        await self.session.commit()
        await self.session.refresh(new_state)
        return new_state

    async def update_state(self, state: CountydleState) -> CountydleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_current_streak(self, user_id: int, puzzle_date: date) -> int:
        stmt = (
            select(CountydleDay.date, CountydleState.won)
            .join(CountydleDay, CountydleState.day_id == CountydleDay.id)
            .where(
                and_(
                    CountydleState.user_id == user_id,
                    CountydleState.is_game_over == True,
                    CountydleDay.date < puzzle_date,
                )
            )
            .order_by(CountydleDay.date.desc())
        )
        result = await self.session.execute(stmt)
        completed_games = [(row.date, row.won) for row in result.all()]
        return count_consecutive_daily_wins(completed_games, puzzle_date)

    async def calc_points(
        self,
        state: CountydleState,
        elapsed_seconds: int | None = None,
        streak: int = 0,
    ) -> int:
        from game_logic import COUNTYDLE_CONFIG, calculate_points

        base = calculate_points(
            config=COUNTYDLES_CONFIG if False else COUNTYDLE_CONFIG,
            won=state.won,
            questions_used=state.questions_asked,
            guesses_used=state.guesses_made,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )
        # 48 ceremonial counties medium bonus (+200, matching 50-state USStatedle)
        return (base + 200) if state.won else 0

    async def get_leaderboard(self, type: str = "monthly") -> List[LeaderboardEntry]:
        return await aggregate_leaderboard(
            self.session,
            CountydleState,
            CountydleDay,
            type,
            minimum_average_games=5,
        )


class CountydleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(
        self, guess_create: EnglishCountyGuessCreate, *, commit: bool = True
    ) -> CountydleGuess:
        new_guess = CountydleGuess(
            **guess_create.model_dump(exclude={"elapsed_seconds"})
        )
        self.session.add(new_guess)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_day_guesses(
        self, user: User, day: CountydleDay
    ) -> List[CountydleGuess]:
        result = await self.session.execute(
            select(CountydleGuess)
            .where(
                and_(
                    CountydleGuess.user_id == user.id,
                    CountydleGuess.day_id == day.id,
                )
            )
            .order_by(CountydleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())


class CountydleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(
        self, question_create: EnglishCountyQuestionCreate
    ) -> CountydleQuestion:
        data = question_create.model_dump()
        data.pop("intent", None)
        data.pop("required_info", None)
        new_question = CountydleQuestion(**data)
        self.session.add(new_question)
        await self.session.flush()
        return new_question

    async def get_user_day_questions(
        self, user: User, day: CountydleDay
    ) -> List[CountydleQuestion]:
        result = await self.session.execute(
            select(CountydleQuestion)
            .where(
                and_(
                    CountydleQuestion.user_id == user.id,
                    CountydleQuestion.day_id == day.id,
                    CountydleQuestion.valid.is_(True),
                    CountydleQuestion.answer.is_not(None),
                )
            )
            .order_by(CountydleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_questions(
        self, limit: int | None = None, offset: int = 0
    ) -> List[CountydleQuestion]:
        query = (
            select(CountydleQuestion)
            .options(
                joinedload(CountydleQuestion.user),
                joinedload(CountydleQuestion.day).joinedload(CountydleDay.county),
            )
            .order_by(CountydleQuestion.asked_at.desc())
        )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_questions(self) -> int:
        result = await self.session.execute(select(func.count(CountydleQuestion.id)))
        return int(result.scalar_one())
