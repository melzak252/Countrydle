from __future__ import annotations

from datetime import date, timedelta
import random
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.country import Country
from db.models.flagdle import FlagdleDay, FlagdleState, FlagdleGuess
from db.models.user import User
from game_logic import calculate_flagdle_points
from schemas.flagdle import FlagdleGuessCreate
from country_eligibility import require_eligible_target
from db.repositories.country import CountryRepository


class FlagdleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_flag(self) -> Optional[FlagdleDay]:
        today = date.today()
        result = await self.session.execute(
            select(FlagdleDay)
            .options(joinedload(FlagdleDay.country))
            .where(FlagdleDay.date == today)
        )
        return require_eligible_target(result.scalars().first())

    async def get_day_flag_by_date(self, target_date: date) -> Optional[FlagdleDay]:
        result = await self.session.execute(
            select(FlagdleDay)
            .options(joinedload(FlagdleDay.country))
            .where(FlagdleDay.date == target_date)
        )
        return require_eligible_target(result.scalars().first())

    async def generate_new_day_flag(
        self, target_date: Optional[date] = None, cooldown_days: int = 90
    ) -> FlagdleDay:
        if target_date is None:
            target_date = date.today()

        existing = await self.get_day_flag_by_date(target_date)
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
        today = date.today()
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
        result = await self.session.execute(
            select(FlagdleState).where(
                and_(
                    FlagdleState.user_id == user.id,
                    FlagdleState.day_id == day_flag.id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_state(
        self, user: Optional[User], day_flag: FlagdleDay, max_guesses: int = 12
    ) -> FlagdleState:
        state = FlagdleState(
            user_id=user.id if user else None,
            day_id=day_flag.id,
            remaining_guesses=max_guesses,
            guesses_made=0,
            revealed_stage=1,
            is_game_over=False,
            won=False,
            points=0,
        )
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def update_state(self, state: FlagdleState) -> FlagdleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_current_streak(self, user_id: int) -> int:
        stmt = (
            select(FlagdleState)
            .where(
                and_(
                    FlagdleState.user_id == user_id,
                    FlagdleState.is_game_over == True,
                )
            )
            .order_by(FlagdleState.id.desc())
        )
        res = await self.session.execute(stmt)
        states = res.scalars().all()
        streak = 0
        for s in states:
            if s.won:
                streak += 1
            else:
                break
        return streak

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

    async def add_guess(self, guess_create: FlagdleGuessCreate) -> FlagdleGuess:
        guess = FlagdleGuess(
            guess=guess_create.guess,
            country_id=guess_create.country_id,
            day_id=guess_create.day_id,
            user_id=guess_create.user_id,
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
        await self.session.commit()
        await self.session.refresh(guess)
        return guess
