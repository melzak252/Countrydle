from typing import List, Optional
from sqlalchemy import select, func, and_, cast, Integer, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState, WojewodztwodleGuess, WojewodztwodleQuestion
from db.models.user import User
from schemas.wojewodztwodle import WojewodztwoGuessCreate, WojewodztwoQuestionCreate
from schemas.countrydle import LeaderboardEntry
from schemas.statistics import GameStatistics, GameHistoryEntry


class WojewodztwodleDayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today_wojewodztwo(self) -> Optional[WojewodztwodleDay]:
        today = func.current_date()
        result = await self.session.execute(
            select(WojewodztwodleDay).where(WojewodztwodleDay.date == today)
        )
        return result.scalar_one_or_none()

    async def generate_new_day_wojewodztwo(self) -> WojewodztwodleDay:
        # Get a random wojewodztwo
        result = await self.session.execute(select(Wojewodztwo).order_by(func.random()).limit(1))
        wojewodztwo = result.scalar_one_or_none()
        
        if not wojewodztwo:
            raise Exception("No wojewodztwa found in database!")

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

    async def get_state(self, user: User, day: WojewodztwodleDay) -> Optional[WojewodztwodleState]:
        result = await self.session.execute(
            select(WojewodztwodleState).where(
                and_(
                    WojewodztwodleState.user_id == user.id,
                    WojewodztwodleState.day_id == day.id
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_state(self, user: User, day: WojewodztwodleDay) -> WojewodztwodleState:
        new_state = WojewodztwodleState(user_id=user.id, day_id=day.id)
        self.session.add(new_state)
        await self.session.commit()
        await self.session.refresh(new_state)
        return new_state

    async def update_state(self, state: WojewodztwodleState) -> WojewodztwodleState:
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_leaderboard(self) -> List[LeaderboardEntry]:
        stmt = (
            select(
                User.id,
                User.username,
                func.coalesce(func.sum(WojewodztwodleState.points), 0).label("points"),
                func.coalesce(func.sum(cast(WojewodztwodleState.won, Integer)), 0).label("wins"),
            )
            .join(User, User.id == WojewodztwodleState.user_id)
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
                func.coalesce(func.sum(WojewodztwodleState.points), 0).label("points"),
                func.coalesce(func.sum(cast(WojewodztwodleState.won, Integer)), 0).label("wins"),
                func.count(WojewodztwodleState.id).label("games_played")
            )
            .where(WojewodztwodleState.user_id == user.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        
        points = row.points if row else 0
        wins = row.wins if row else 0
        games_played = row.games_played if row else 0

        # Get history
        history_stmt = (
            select(WojewodztwodleState)
            .options(joinedload(WojewodztwodleState.day).joinedload(WojewodztwodleDay.wojewodztwo))
            .where(and_(WojewodztwodleState.user_id == user.id, WojewodztwodleState.is_game_over == True))
            .order_by(WojewodztwodleState.id.desc())
        )
        history_result = await self.session.execute(history_stmt)
        history_states = history_result.scalars().all()

        history_entries = [
            GameHistoryEntry(
                date=str(state.day.date),
                won=state.won,
                points=state.points,
                attempts=state.guesses_made,
                target_name=state.day.wojewodztwo.nazwa
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


class WojewodztwodleGuessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_guess(self, guess_create: WojewodztwoGuessCreate) -> WojewodztwodleGuess:
        new_guess = WojewodztwodleGuess(**guess_create.model_dump())
        self.session.add(new_guess)
        await self.session.commit()
        await self.session.refresh(new_guess)
        return new_guess

    async def get_user_day_guesses(self, user: User, day: WojewodztwodleDay) -> List[WojewodztwodleGuess]:
        result = await self.session.execute(
            select(WojewodztwodleGuess).where(
                and_(
                    WojewodztwodleGuess.user_id == user.id,
                    WojewodztwodleGuess.day_id == day.id
                )
            ).order_by(WojewodztwodleGuess.guessed_at.asc())
        )
        return list(result.scalars().all())


class WojewodztwodleQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(self, question_create: WojewodztwoQuestionCreate) -> WojewodztwodleQuestion:
        new_question = WojewodztwodleQuestion(**question_create.model_dump())
        self.session.add(new_question)
        await self.session.commit()
        await self.session.refresh(new_question)
        return new_question

    async def get_user_day_questions(self, user: User, day: WojewodztwodleDay) -> List[WojewodztwodleQuestion]:
        result = await self.session.execute(
            select(WojewodztwodleQuestion).where(
                and_(
                    WojewodztwodleQuestion.user_id == user.id,
                    WojewodztwodleQuestion.day_id == day.id
                )
            ).order_by(WojewodztwodleQuestion.asked_at.asc())
        )
        return list(result.scalars().all())
