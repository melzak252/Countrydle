from datetime import date

from typing import List, Optional
from sqlalchemy import select, func, and_, or_, cast, Integer, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.us_state import USState
from db.models.us_statedle import (
    USStatedleDay,
    USStatedleState,
    USStatedleGuess,
    USStatedleQuestion,
)
from db.models.user import User
from schemas.us_statedle import USStateGuessCreate, USStateQuestionCreate
from schemas.countrydle import LeaderboardEntry
from schemas.statistics import GameStatistics, GameHistoryEntry
from db.repositories.leaderboard import get_leaderboard as aggregate_leaderboard
from game_logic import count_consecutive_daily_wins


class USStatedleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_us_state(self) -> Optional[USStatedleDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(USStatedleDay).where(USStatedleDay.date == today)
        )
        return result.scalar_one_or_none()

    async def get_day_us_state_by_date(self, game_date: date) -> Optional[USStatedleDay]:
        result = await self.session.execute(
            select(USStatedleDay).where(USStatedleDay.date == game_date)
        )
        return result.scalar_one_or_none()

    async def generate_new_day_us_state(self, cooldown_days: int = 25) -> USStatedleDay:
        import random
        recent_subq = (
            select(USStatedleDay.us_state_id)
            .where(USStatedleDay.us_state_id.isnot(None))
            .order_by(USStatedleDay.id.desc())
            .limit(cooldown_days)
        )
        recent_ids = set((await self.session.execute(recent_subq)).scalars().all())

        all_states = (await self.session.execute(select(USState))).scalars().all()
        if not all_states:
            raise Exception("No US states found in database!")

        eligible = [s for s in all_states if s.id not in recent_ids]
        if not eligible:
            eligible = all_states

        us_state = random.choice(eligible)

        new_day = USStatedleDay(us_state_id=us_state.id)
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)
        return new_day

    async def get_history(self) -> List[USStatedleDay]:
        from datetime import date

        result = await self.session.execute(
            select(USStatedleDay)
            .options(joinedload(USStatedleDay.us_state))
            .where(USStatedleDay.date < date.today())
            .order_by(USStatedleDay.date.desc())
        )
        return result.scalars().all()


class USStatedleStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self, user: User, day: USStatedleDay
    ) -> Optional[USStatedleState]:
        result = await self.session.execute(
            select(USStatedleState).where(
                and_(
                    USStatedleState.user_id == user.id, USStatedleState.day_id == day.id
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_state(
        self,
        user: User,
        day: USStatedleDay,
        max_questions: int = 8,
        max_guesses: int = 3,
    ) -> USStatedleState:
        new_state = USStatedleState(
            user_id=user.id,
            day_id=day.id,
            remaining_questions=max_questions,
            remaining_guesses=max_guesses,
        )
        self.session.add(new_state)
        await self.session.commit()
        await self.session.refresh(new_state)
        return new_state

    async def update_state(self, state: USStatedleState) -> USStatedleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_current_streak(self, user_id: int, puzzle_date: date) -> int:
        stmt = (
            select(USStatedleDay.date, USStatedleState.won)
            .join(USStatedleDay, USStatedleState.day_id == USStatedleDay.id)
            .where(
                and_(
                    USStatedleState.user_id == user_id,
                    USStatedleState.is_game_over == True,
                    USStatedleDay.date < puzzle_date,
                )
            )
            .order_by(USStatedleDay.date.desc())
        )
        result = await self.session.execute(stmt)
        completed_games = [(row.date, row.won) for row in result.all()]
        return count_consecutive_daily_wins(completed_games, puzzle_date)

    async def calc_points(
        self,
        state: USStatedleState,
        elapsed_seconds: int | None = None,
        streak: int = 0,
    ) -> int:
        from game_logic import calculate_points, USSTATEDLE_CONFIG
        base = calculate_points(
            config=USSTATEDLE_CONFIG,
            won=state.won,
            questions_used=state.questions_asked,
            guesses_used=state.guesses_made,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )
        # US States medium bonus (+200 for 50 states)
        return (base + 200) if state.won else 0
    async def get_leaderboard(self, type: str = "monthly") -> List[LeaderboardEntry]:
        return await aggregate_leaderboard(
            self.session,
            USStatedleState,
            USStatedleDay,
            type,
            minimum_average_games=5,
        )
    async def get_user_statistics(self, user: User) -> GameStatistics:
        # Calculate total points and wins
        stmt = select(
            func.coalesce(func.sum(USStatedleState.points), 0).label("points"),
            func.coalesce(func.sum(cast(USStatedleState.won, Integer)), 0).label(
                "wins"
            ),
            func.count(USStatedleState.id).label("games_played"),
        ).where(USStatedleState.user_id == user.id)
        result = await self.session.execute(stmt)
        row = result.first()

        points = row.points if row else 0
        wins = row.wins if row else 0
        games_played = row.games_played if row else 0

        # Get history
        history_stmt = (
            select(USStatedleState)
            .options(joinedload(USStatedleState.day).joinedload(USStatedleDay.us_state))
            .where(
                and_(
                    USStatedleState.user_id == user.id,
                    USStatedleState.is_game_over == True,
                )
            )
            .order_by(USStatedleState.id.desc())
        )
        history_result = await self.session.execute(history_stmt)
        history_states = history_result.scalars().all()

        from datetime import date

        history_entries = [
            GameHistoryEntry(
                date=str(state.day.date),
                won=state.won,
                points=state.points,
                attempts=state.guesses_made,
                target_name=state.day.us_state.name if state.day.date != date.today() else "???",
            )
            for state in history_states
        ]

        current_streak = 0
        for s in history_states:
            if s.won:
                current_streak += 1
            else:
                break

        return GameStatistics(
            points=points,
            wins=wins,
            games_played=games_played,
            streak=current_streak,
            history=history_entries,
        )


class USStatedleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: USStateGuessCreate) -> USStatedleGuess:
        new_guess = USStatedleGuess(**guess_create.model_dump(exclude={"elapsed_seconds"}))
        self.session.add(new_guess)
        await self.session.commit()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_day_guesses(
        self, user: User, day: USStatedleDay
    ) -> List[USStatedleGuess]:
        result = await self.session.execute(
            select(USStatedleGuess)
            .where(
                and_(
                    USStatedleGuess.user_id == user.id, USStatedleGuess.day_id == day.id
                )
            )
            .order_by(USStatedleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())


class USStatedleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(
        self, question_create: USStateQuestionCreate
    ) -> USStatedleQuestion:
        data = question_create.model_dump()
        # Remove fields that are not in the DB model
        data.pop("intent", None)
        data.pop("required_info", None)
        new_question = USStatedleQuestion(**data)
        self.session.add(new_question)
        await self.session.commit()
        await self.session.refresh(new_question)
        return new_question


    async def get_user_day_questions(
        self, user: User, day: USStatedleDay
    ) -> List[USStatedleQuestion]:
        result = await self.session.execute(
            select(USStatedleQuestion)
            .where(
                and_(
                    USStatedleQuestion.user_id == user.id,
                    USStatedleQuestion.day_id == day.id,
                )
            )
            .order_by(USStatedleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_questions(
        self, limit: int | None = None, offset: int = 0
    ) -> List[USStatedleQuestion]:
        query = (
            select(USStatedleQuestion)
            .options(
                joinedload(USStatedleQuestion.user),
                joinedload(USStatedleQuestion.day).joinedload(USStatedleDay.us_state)
            )
            .order_by(USStatedleQuestion.asked_at.desc())
        )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        result = await self.session.execute(
            query
        )
        return list(result.scalars().all())

    async def count_questions(self) -> int:
        result = await self.session.execute(select(func.count(USStatedleQuestion.id)))
        return int(result.scalar_one())
