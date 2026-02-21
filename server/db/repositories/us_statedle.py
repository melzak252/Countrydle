from typing import List, Optional
from sqlalchemy import select, func, and_, cast, Integer, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.us_state import USState
from db.models.us_statedle import USStatedleDay, USStatedleState, USStatedleGuess, USStatedleQuestion
from db.models.user import User
from schemas.us_statedle import USStateGuessCreate, USStateQuestionCreate
from schemas.countrydle import LeaderboardEntry
from schemas.statistics import GameStatistics, GameHistoryEntry


class USStatedleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_us_state(self) -> Optional[USStatedleDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(USStatedleDay).where(USStatedleDay.date == today)
        )
        return result.scalar_one_or_none()

    async def generate_new_day_us_state(self) -> USStatedleDay:
        # Get a random us_state
        result = await self.session.execute(select(USState).order_by(func.random()).limit(1))
        us_state = result.scalar_one_or_none()
        
        if not us_state:
            raise Exception("No US states found in database!")

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

    async def get_state(self, user: User, day: USStatedleDay) -> Optional[USStatedleState]:
        result = await self.session.execute(
            select(USStatedleState).where(
                and_(
                    USStatedleState.user_id == user.id,
                    USStatedleState.day_id == day.id
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_state(self, user: User, day: USStatedleDay) -> USStatedleState:
        new_state = USStatedleState(user_id=user.id, day_id=day.id)
        self.session.add(new_state)
        await self.session.commit()
        await self.session.refresh(new_state)
        return new_state

    async def update_state(self, state: USStatedleState) -> USStatedleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_leaderboard(self) -> List[LeaderboardEntry]:
        stmt = (
            select(
                User.id,
                User.username,
                func.coalesce(func.sum(USStatedleState.points), 0).label("points"),
                func.coalesce(func.sum(cast(USStatedleState.won, Integer)), 0).label("wins"),
            )
            .join(User, User.id == USStatedleState.user_id)
            .where(
                and_(
                    User.username.not_like('test_%'),
                    User.username.not_like('pytest_%'),
                    User.username.not_like('guess_c_%'),
                    User.username.not_like('ask_q_%')
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
                streak=0 # Streak not implemented yet for sub-games
            )
            for row in result.all()
        ]

    async def get_user_statistics(self, user: User) -> GameStatistics:
        # Calculate total points and wins
        stmt = (
            select(
                func.coalesce(func.sum(USStatedleState.points), 0).label("points"),
                func.coalesce(func.sum(cast(USStatedleState.won, Integer)), 0).label("wins"),
                func.count(USStatedleState.id).label("games_played")
            )
            .where(USStatedleState.user_id == user.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        
        points = row.points if row else 0
        wins = row.wins if row else 0
        games_played = row.games_played if row else 0

        # Get history
        history_stmt = (
            select(USStatedleState)
            .options(joinedload(USStatedleState.day).joinedload(USStatedleDay.us_state))
            .where(and_(USStatedleState.user_id == user.id, USStatedleState.is_game_over == True))
            .order_by(USStatedleState.id.desc())
        )
        history_result = await self.session.execute(history_stmt)
        history_states = history_result.scalars().all()

        history_entries = [
            GameHistoryEntry(
                date=str(state.day.date),
                won=state.won,
                points=state.points,
                attempts=state.guesses_made,
                target_name=state.day.us_state.name
            )
            for state in history_states
        ]

        return GameStatistics(
            points=points,
            wins=wins,
            games_played=games_played,
            streak=0, # TODO: Implement streak
            history=history_entries
        )


class USStatedleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: USStateGuessCreate) -> USStatedleGuess:
        new_guess = USStatedleGuess(**guess_create.model_dump())
        self.session.add(new_guess)
        await self.session.commit()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_day_guesses(self, user: User, day: USStatedleDay) -> List[USStatedleGuess]:
        result = await self.session.execute(
            select(USStatedleGuess).where(
                and_(
                    USStatedleGuess.user_id == user.id,
                    USStatedleGuess.day_id == day.id
                )
            ).order_by(USStatedleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())


class USStatedleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(self, question_create: USStateQuestionCreate) -> USStatedleQuestion:
        new_question = USStatedleQuestion(**question_create.model_dump())
        self.session.add(new_question)
        await self.session.commit()
        await self.session.refresh(new_question)
        return new_question

    async def get_user_day_questions(self, user: User, day: USStatedleDay) -> List[USStatedleQuestion]:
        result = await self.session.execute(
            select(USStatedleQuestion).where(
                and_(
                    USStatedleQuestion.user_id == user.id,
                    USStatedleQuestion.day_id == day.id
                )
            ).order_by(USStatedleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())
