from typing import List, Optional
from sqlalchemy import select, func, and_, cast, Integer, desc
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
from schemas.statistics import GameStatistics, GameHistoryEntry


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

    async def generate_new_day_powiat(self) -> PowiatdleDay:
        # Get a random powiat
        result = await self.session.execute(
            select(Powiat).order_by(func.random()).limit(1)
        )
        powiat = result.scalar_one_or_none()

        if not powiat:
            raise Exception("No powiaty found in database!")

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

    async def calc_points(self, state: PowiatdleState) -> int:
        # Powiaty are hard (380 options), so higher rewards
        question_points = state.remaining_questions * 150
        guess_points = 200 * (((state.remaining_guesses + 1) ** 2) + 1)
        difficulty_bonus = 500
        return question_points + guess_points + difficulty_bonus

    async def get_leaderboard(self) -> List[LeaderboardEntry]:
        stmt = (
            select(
                User.id,
                User.username,
                func.coalesce(func.sum(PowiatdleState.points), 0).label("points"),
                func.coalesce(func.sum(cast(PowiatdleState.won, Integer)), 0).label(
                    "wins"
                ),
            )
            .join(User, User.id == PowiatdleState.user_id)
            .where(
                and_(
                    User.username.not_like("test_%"),
                    User.username.not_like("pytest_%"),
                    User.username.not_like("guess_c_%"),
                    User.username.not_like("ask_q_%"),
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
                streak=0,  # Streak not implemented yet for sub-games
            )
            for row in result.all()
        ]

    async def get_user_statistics(self, user: User) -> GameStatistics:
        # Calculate total points and wins
        stmt = select(
            func.coalesce(func.sum(PowiatdleState.points), 0).label("points"),
            func.coalesce(func.sum(cast(PowiatdleState.won, Integer)), 0).label("wins"),
            func.count(PowiatdleState.id).label("games_played"),
        ).where(PowiatdleState.user_id == user.id)
        result = await self.session.execute(stmt)
        row = result.first()

        points = row.points if row else 0
        wins = row.wins if row else 0
        games_played = row.games_played if row else 0

        # Get history
        history_stmt = (
            select(PowiatdleState)
            .options(joinedload(PowiatdleState.day).joinedload(PowiatdleDay.powiat))
            .where(
                and_(
                    PowiatdleState.user_id == user.id,
                    PowiatdleState.is_game_over == True,
                )
            )
            .order_by(PowiatdleState.id.desc())
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
                target_name=state.day.powiat.nazwa if state.won else "???",
            )
            for state in history_states
        ]

        return GameStatistics(
            points=points,
            wins=wins,
            games_played=games_played,
            streak=0,  # TODO: Implement streak
            history=history_entries,
        )


class PowiatdleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: PowiatGuessCreate) -> PowiatdleGuess:
        new_guess = PowiatdleGuess(**guess_create.model_dump())
        self.session.add(new_guess)
        await self.session.commit()
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
        new_question = PowiatdleQuestion(**question_create.model_dump())
        self.session.add(new_question)
        await self.session.commit()
        await self.session.refresh(new_question)
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
                )
            )
            .order_by(PowiatdleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())
