from __future__ import annotations

from datetime import date, timedelta
import random
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from daily_clock import utc_today
from db.models.country import Country
from db.models.flagdle import FlagdleDay, FlagdleState, FlagdleGuess, FlagdleQuestion
from db.models.user import User
from game_logic import calculate_flagdle_points, count_consecutive_daily_wins
from schemas.flagdle import FlagdleGuessCreate
from country_eligibility import require_eligible_target
from db.repositories.country import CountryRepository
from db.repositories.leaderboard import get_leaderboard as aggregate_leaderboard
from schemas.countrydle import LeaderboardEntry
from db.repositories.question_accounting import get_daily_state, lock_question_state


class FlagdleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_flag(self) -> Optional[FlagdleDay]:
        today = utc_today()
        result = await self.session.execute(
            select(FlagdleDay)
            .options(joinedload(FlagdleDay.country))
            .where(FlagdleDay.date == today)
        )
        return require_eligible_target(result.scalars().first(), today=today)

    async def get_day_flag_by_date(
        self, target_date: date, *, today: date | None = None
    ) -> Optional[FlagdleDay]:
        today = today if today is not None else utc_today()
        result = await self.session.execute(
            select(FlagdleDay)
            .options(joinedload(FlagdleDay.country))
            .where(FlagdleDay.date == target_date)
        )
        return require_eligible_target(result.scalars().first(), today=today)

    async def generate_new_day_flag(
        self, target_date: Optional[date] = None, cooldown_days: int = 90
    ) -> FlagdleDay:
        today = utc_today()
        if target_date is None:
            target_date = today

        existing = await self.get_day_flag_by_date(target_date, today=today)
        if existing:
            return existing

        recent_subq = (
            select(FlagdleDay.country_id)
            .where(FlagdleDay.date >= target_date - timedelta(days=cooldown_days))
        )
        recent_ids = set((await self.session.execute(recent_subq)).scalars().all())

        all_countries = await CountryRepository(self.session).get_all_countries()
        if not all_countries:
            raise Exception("No countries found in database!")

        eligible = [c for c in all_countries if c.id not in recent_ids]
        if not eligible:
            eligible = all_countries

        chosen_country = random.choice(eligible)
        new_day = FlagdleDay(country_id=chosen_country.id, date=target_date)
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)
        return new_day

    async def get_history(self) -> List[FlagdleDay]:
        today = utc_today()
        result = await self.session.execute(
            select(FlagdleDay)
            .options(joinedload(FlagdleDay.country))
            .where(FlagdleDay.date < today)
            .order_by(FlagdleDay.date.desc())
        )
        return list(result.scalars().all())


class FlagdleStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(self, user: Optional[User], day_flag: FlagdleDay) -> Optional[FlagdleState]:
        if not user:
            return None
        return await lock_question_state(self.session, FlagdleState, user.id, day_flag.id)

    async def create_state(
        self, user: Optional[User], day_flag: FlagdleDay, max_guesses: int = 12,
        *, commit: bool = True,
    ) -> FlagdleState:
        if user is not None:
            state = await get_daily_state(
                self.session, FlagdleState, user.id, day_flag.id, None, max_guesses,
            )
        else:
            state = FlagdleState(
                user_id=None, day_id=day_flag.id, remaining_guesses=max_guesses,
                questions_asked=0, guesses_made=0, revealed_stage=1,
                is_game_over=False, won=False, points=0,
            )
            self.session.add(state)
            await self.session.flush()
        if commit:
            await self.session.commit()
        return state

    async def update_state(self, state: FlagdleState, *, commit: bool = True) -> FlagdleState:
        self.session.add(state)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return state

    async def get_current_streak(self, user_id: int, puzzle_date: date) -> int:
        stmt = (
            select(FlagdleDay.date, FlagdleState.won)
            .join(FlagdleDay, FlagdleState.day_id == FlagdleDay.id)
            .where(
                and_(
                    FlagdleState.user_id == user_id,
                    FlagdleState.is_game_over == True,
                    FlagdleDay.date < puzzle_date,
                )
            )
            .order_by(FlagdleDay.date.desc())
        )
        result = await self.session.execute(stmt)
        completed_games = [(row.date, row.won) for row in result.all()]
        return count_consecutive_daily_wins(completed_games, puzzle_date)

    async def calc_points(
        self,
        state: FlagdleState,
        elapsed_seconds: Optional[int] = None,
        streak: int = 0,
    ) -> int:
        return calculate_flagdle_points(
            won=state.won,
            guesses_used=state.guesses_made,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )
    async def get_leaderboard(self, type: str = "monthly") -> List[LeaderboardEntry]:
        return await aggregate_leaderboard(
            self.session,
            FlagdleState,
            FlagdleDay,
            type,
            minimum_average_games=5,
        )



class FlagdleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_day_guesses(
        self, user: Optional[User], day_id: int
    ) -> List[FlagdleGuess]:
        if not user:
            return []
        result = await self.session.execute(
            select(FlagdleGuess)
            .where(
                and_(
                    FlagdleGuess.user_id == user.id,
                    FlagdleGuess.day_id == day_id,
                )
            )
            .order_by(FlagdleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())

    async def add_guess(
        self, guess_create: FlagdleGuessCreate, *, commit: bool = True, guest_id: str | None = None
    ) -> FlagdleGuess:
        guess = FlagdleGuess(
            guess=guess_create.guess,
            country_id=guess_create.country_id,
            day_id=guess_create.day_id,
            user_id=guess_create.user_id,
            guest_id=guest_id,
            answer=guess_create.answer,
            distance_km=guess_create.distance_km,
            bearing_degrees=guess_create.bearing_degrees,
            bearing_direction=guess_create.bearing_direction,
            bearing_arrow=guess_create.bearing_arrow,
            matched_colors=guess_create.matched_colors or [],
            missed_colors=guess_create.missed_colors or [],
            remaining_colors_count=guess_create.remaining_colors_count or 0,
            matched_symbols=guess_create.matched_symbols or [],
            revealed_tile=guess_create.revealed_tile,
            elapsed_seconds=guess_create.elapsed_seconds,
        )
        self.session.add(guess)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(guess)
        return guess


class FlagdleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(self, question_create):
        data = question_create.model_dump()
        for field in ("intent", "required_info", "server_version"):
            data.pop(field, None)
        question = FlagdleQuestion(**data)
        self.session.add(question)
        await self.session.flush()
        return question

    async def get_user_day_questions(self, user_id: int, day_id: int):
        result = await self.session.execute(
            select(FlagdleQuestion).where(
                FlagdleQuestion.user_id == user_id, FlagdleQuestion.day_id == day_id,
                FlagdleQuestion.valid.is_(True), FlagdleQuestion.answer.is_not(None),
            ).order_by(FlagdleQuestion.id)
        )
        return list(result.scalars().all())
