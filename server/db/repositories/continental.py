from datetime import date, timedelta
import random
from typing import List, Optional, Set
from sqlalchemy import and_, or_, cast, desc, func, Integer, select, update
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
from game_logic import calculate_points, CONTINENTAL_CONFIG
from schemas.continental import ContinentalGuessCreate
from schemas.countrydle import LeaderboardEntry
from continental.utils import get_continent_country_ids


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
        return result.scalars().first()

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
        return result.scalars().first()

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

    async def get_current_streak(self, user_id: int | None, continent: ContinentCode | None = None) -> int:
        if not user_id:
            return 0
        query = (
            select(ContinentalState)
            .join(ContinentalDay, ContinentalState.day_id == ContinentalDay.id)
            .where(
                and_(
                    ContinentalState.user_id == user_id,
                    ContinentalState.is_game_over == True,
                )
            )
        )
        if continent:
            query = query.where(ContinentalDay.continent == continent)

        query = query.order_by(ContinentalState.id.desc())
        res = await self.session.execute(query)
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
    ) -> ContinentalState:
        state.guesses_made += 1
        state.remaining_guesses = max(0, CONTINENTAL_CONFIG.max_guesses - state.guesses_made)

        if guess.answer:
            state.won = True
            state.is_game_over = True
            streak = await self.get_current_streak(state.user_id, continent)
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
        if type == "monthly":
            current_month = date.today().replace(day=1)
            stmt = (
                select(
                    User.id,
                    User.username,
                    func.coalesce(func.sum(ContinentalState.points), 0).label("points"),
                    func.coalesce(func.sum(cast(ContinentalState.won, Integer)), 0).label("wins"),
                )
                .join(User, User.id == ContinentalState.user_id)
                .join(ContinentalDay, ContinentalState.day_id == ContinentalDay.id)
                .where(
                    and_(
                        ContinentalDay.continent == continent,
                        User.username.not_like("test_%"),
                        User.username.not_like("pytest_%"),
                        ContinentalDay.date >= current_month,
                        or_(ContinentalState.questions_asked > 0, ContinentalState.guesses_made > 0),
                    )
                )
                .group_by(User.id, User.username)
                .order_by(desc("points"), desc("wins"))
            )
            result = await self.session.execute(stmt)
            return [
                LeaderboardEntry(
                    id=row.id,
                    username=row.username,
                    points=row.points,
                    wins=row.wins,
                    streak=0,
                )
                for row in result.all()
            ]
        elif type == "average":
            stmt = (
                select(
                    User.id,
                    User.username,
                    func.coalesce(func.sum(ContinentalState.points), 0).label("points"),
                    func.coalesce(func.sum(cast(ContinentalState.won, Integer)), 0).label("wins"),
                    func.count(ContinentalState.id).label("games_played"),
                )
                .join(User, User.id == ContinentalState.user_id)
                .join(ContinentalDay, ContinentalState.day_id == ContinentalDay.id)
                .where(
                    and_(
                        ContinentalDay.continent == continent,
                        User.username.not_like("test_%"),
                        User.username.not_like("pytest_%"),
                        or_(ContinentalState.questions_asked > 0, ContinentalState.guesses_made > 0),
                    )
                )
                .group_by(User.id, User.username)
                .having(func.count(ContinentalState.id) >= 3)
            )
            result = await self.session.execute(stmt)
            leaderboard = []
            for row in result.all():
                avg_points = round(row.points / row.games_played, 2)
                leaderboard.append(
                    {
                        "id": row.id,
                        "username": row.username,
                        "points": avg_points,
                        "wins": row.wins,
                        "streak": 0,
                    }
                )
            leaderboard.sort(key=lambda x: (x["points"], x["wins"]), reverse=True)
            return [LeaderboardEntry(**entry) for entry in leaderboard]
        return []


class ContinentalGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: ContinentalGuessCreate) -> ContinentalGuess:
        new_guess = ContinentalGuess(
            user_id=guess_create.user_id,
            day_id=guess_create.day_id,
            guess=guess_create.guess,
            country_id=guess_create.country_id,
            answer=guess_create.answer,
            elapsed_seconds=guess_create.elapsed_seconds,
        )
        self.session.add(new_guess)
        await self.session.commit()
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
        await self.session.commit()
        await self.session.refresh(new_quest)
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
                )
            )
            .order_by(ContinentalQuestion.id.asc())
        )
        return list(result.scalars().all())

    async def claim_guest_questions(
        self, user_id: int, day_id: int, question_ids: List[int]
    ) -> None:
        if not question_ids:
            return
        await self.session.execute(
            update(ContinentalQuestion)
            .where(
                and_(
                    ContinentalQuestion.id.in_(question_ids),
                    ContinentalQuestion.user_id == None,
                    ContinentalQuestion.day_id == day_id,
                )
            )
            .values(user_id=user_id)
        )
