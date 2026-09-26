from datetime import date, timedelta
import random
from typing import List, Optional, Set
from sqlalchemy import and_, or_, cast, desc, func, Integer, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country, User
from db.models.continental import (
    ContinentCode,
    ContinentalDay,
    ContinentalState,
    ContinentalGuess,
    ContinentalQuestion,
)
from game_logic import calculate_points, count_consecutive_daily_wins, CONTINENTAL_CONFIG
from schemas.continental import ContinentalGuessCreate
from schemas.countrydle import LeaderboardEntry
from continental.utils import get_continent_country_ids
from db.repositories.leaderboard import get_leaderboard as aggregate_leaderboard
from country_eligibility import require_eligible_target


COOLDOWN_DAYS: dict[ContinentCode, int] = {
    ContinentCode.EUROPE: 35,
    ContinentCode.ASIA: 35,
    ContinentCode.AFRICA: 40,
    ContinentCode.AMERICAS: 25,
}


class ContinentalDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_day(self, continent: ContinentCode) -> Optional[ContinentalDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(ContinentalDay)
            .options(joinedload(ContinentalDay.country))
            .where(
                and_(
                    ContinentalDay.continent == continent,
                    ContinentalDay.date == today,
                )
            )
            .order_by(ContinentalDay.id.desc())
        )
        return require_eligible_target(result.scalars().first(), continent.value)

    async def get_day_by_date(
        self, continent: ContinentCode, day_date: date
    ) -> Optional[ContinentalDay]:
        result = await self.session.execute(
            select(ContinentalDay)
            .options(joinedload(ContinentalDay.country))
            .where(
                and_(
                    ContinentalDay.continent == continent,
                    ContinentalDay.date == day_date,
                )
            )
        )
        return require_eligible_target(result.scalars().first(), continent.value)

    async def get_history(self, continent: ContinentCode) -> List[ContinentalDay]:
        result = await self.session.execute(
            select(ContinentalDay)
            .options(joinedload(ContinentalDay.country))
            .where(
                and_(
                    ContinentalDay.continent == continent,
                    ContinentalDay.date < date.today(),
                )
            )
            .order_by(ContinentalDay.date.desc())
        )
        return list(result.scalars().all())

    async def generate_new_day(
        self,
        continent: ContinentCode,
        day_date: Optional[date] = None,
        excluded_ids: Optional[Set[int]] = None,
    ) -> ContinentalDay:
        target_date = day_date or date.today()
        cooldown = COOLDOWN_DAYS.get(continent, 30)

        recent_subq = (
            select(ContinentalDay.country_id)
            .where(
                and_(
                    ContinentalDay.continent == continent,
                    ContinentalDay.date >= target_date - timedelta(days=cooldown),
                    ContinentalDay.date < target_date,
                )
            )
        )
        recent_ids = set((await self.session.execute(recent_subq)).scalars().all())

        candidate_ids = await get_continent_country_ids(continent, self.session)
        if not candidate_ids:
            raise ValueError(f"No candidate countries found for continent {continent}!")

        excluded = set(excluded_ids or [])

        # Priority 1: Candidate not in recent cooldown and not picked in other continental modes today
        eligible = [cid for cid in candidate_ids if cid not in recent_ids and cid not in excluded]

        # Priority 2: If over-constrained by cooldown, at least enforce same-day collision exclusion
        if not eligible:
            eligible = [cid for cid in candidate_ids if cid not in excluded]

        # Priority 3: Ultimate fallback
        if not eligible:
            eligible = candidate_ids

        selected_id = random.choice(eligible)

        new_day = ContinentalDay(
            continent=continent,
            country_id=selected_id,
            date=target_date,
        )
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)

        # Eagerly load country relationship
        day_with_country = await self.get_day_by_date(continent, target_date)
        return day_with_country or new_day


class ContinentalStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self,
        user: User,
        day: ContinentalDay,
        max_questions: int = CONTINENTAL_CONFIG.max_questions,
        max_guesses: int = CONTINENTAL_CONFIG.max_guesses,
    ) -> ContinentalState:
        result = await self.session.execute(
            select(ContinentalState).where(
                and_(
                    ContinentalState.user_id == user.id,
                    ContinentalState.day_id == day.id,
                )
            )
        )
        state = result.scalar_one_or_none()
        if not state:
            from db.repositories.question_accounting import lock_question_state
            state = await lock_question_state(self.session, ContinentalState, user.id, day.id)
            if state is not None:
                await self.session.commit()
                return state
            state = ContinentalState(
                user_id=user.id,
                day_id=day.id,
                remaining_questions=max_questions,
                remaining_guesses=max_guesses,
                questions_asked=0,
                guesses_made=0,
                is_game_over=False,
                won=False,
                points=0,
            )
            self.session.add(state)
            await self.session.commit()
            await self.session.refresh(state)
        return state

    async def update_state(self, state: ContinentalState) -> ContinentalState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_current_streak(
        self,
        user_id: int | None,
        puzzle_date: date,
        continent: ContinentCode | None = None,
    ) -> int:
        if not user_id:
            return 0
        query = (
            select(ContinentalDay.date, ContinentalState.won)
            .join(ContinentalDay, ContinentalState.day_id == ContinentalDay.id)
            .where(
                and_(
                    ContinentalState.user_id == user_id,
                    ContinentalState.is_game_over == True,
                    ContinentalDay.date < puzzle_date,
                )
            )
        )
        if continent:
            query = query.where(ContinentalDay.continent == continent)

        query = query.order_by(ContinentalDay.date.desc())
        result = await self.session.execute(query)
        completed_games = [(row.date, row.won) for row in result.all()]
        return count_consecutive_daily_wins(completed_games, puzzle_date)

    async def calc_points(
        self,
        state: ContinentalState,
        elapsed_seconds: Optional[int] = None,
        streak: int = 0,
    ) -> int:
        return calculate_points(
            config=CONTINENTAL_CONFIG,
            won=state.won,
            questions_used=state.questions_asked,
            guesses_used=state.guesses_made,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )

    async def guess_made(
        self,
        state: ContinentalState,
        guess: ContinentalGuess,
        elapsed_seconds: Optional[int] = None,
        continent: ContinentCode | None = None,
        *,
        puzzle_date: date,
    ) -> ContinentalState:
        state.guesses_made += 1
        state.remaining_guesses = max(0, CONTINENTAL_CONFIG.max_guesses - state.guesses_made)

        if guess.answer:
            state.won = True
            state.is_game_over = True
            streak = await self.get_current_streak(state.user_id, puzzle_date, continent)
            state.points = await self.calc_points(
                state, elapsed_seconds=elapsed_seconds, streak=streak + 1
            )
        elif state.guesses_made >= CONTINENTAL_CONFIG.max_guesses:
            state.is_game_over = True
            state.points = 0

        return await self.update_state(state)

    async def get_leaderboard(
        self, continent: ContinentCode, type: str = "monthly"
    ) -> List[LeaderboardEntry]:
        return await aggregate_leaderboard(
            self.session,
            ContinentalState,
            ContinentalDay,
            type,
            minimum_average_games=3,
            day_filters=(ContinentalDay.continent == continent,),
        )


class ContinentalGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: ContinentalGuessCreate, *, commit: bool = True) -> ContinentalGuess:
        new_guess = ContinentalGuess(
            user_id=guess_create.user_id,
            day_id=guess_create.day_id,
            guess=guess_create.guess,
            country_id=guess_create.country_id,
            answer=guess_create.answer,
            elapsed_seconds=guess_create.elapsed_seconds,
        )
        self.session.add(new_guess)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_guesses(
        self, user_id: Optional[int], day_id: int
    ) -> List[ContinentalGuess]:
        if user_id is None:
            return []
        result = await self.session.execute(
            select(ContinentalGuess)
            .where(
                and_(
                    ContinentalGuess.user_id == user_id,
                    ContinentalGuess.day_id == day_id,
                )
            )
            .order_by(ContinentalGuess.id.asc())
        )
        return list(result.scalars().all())


class ContinentalQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(self, question_create) -> ContinentalQuestion:
        new_quest = ContinentalQuestion(
            user_id=getattr(question_create, "user_id", None),
            day_id=question_create.day_id,
            original_question=question_create.original_question,
            question=getattr(question_create, "question", None),
            valid=question_create.valid,
            answer=getattr(question_create, "answer", None),
            explanation=getattr(question_create, "explanation", None),
            context=getattr(question_create, "context", None),
        )
        self.session.add(new_quest)
        await self.session.flush()
        return new_quest

    async def get_user_questions(
        self, user_id: Optional[int], day_id: int
    ) -> List[ContinentalQuestion]:
        if user_id is None:
            return []
        result = await self.session.execute(
            select(ContinentalQuestion)
            .where(
                and_(
                    ContinentalQuestion.user_id == user_id,
                    ContinentalQuestion.day_id == day_id,
                    ContinentalQuestion.valid.is_(True),
                    ContinentalQuestion.answer.is_not(None),
                )
            )
            .order_by(ContinentalQuestion.id.asc())
        )
        return list(result.scalars().all())

