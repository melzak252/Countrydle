from typing import List, Optional
from sqlalchemy import select, func, and_, or_, cast, Integer, desc
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

    async def get_day_powiat_by_date(self, day_date) -> Optional[PowiatdleDay]:
        result = await self.session.execute(
            select(PowiatdleDay).where(PowiatdleDay.date == day_date)
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

    async def get_current_streak(self, user_id: int) -> int:
        stmt = (
            select(PowiatdleState)
            .where(
                and_(
                    PowiatdleState.user_id == user_id,
                    PowiatdleState.is_game_over == True,
                )
            )
            .order_by(PowiatdleState.id.desc())
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
        if type == "monthly":
            from datetime import date
            current_month = date.today().replace(day=1)
            
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
                .join(PowiatdleDay, PowiatdleState.day_id == PowiatdleDay.id)
                .where(
                    and_(
                        User.username.not_like("test_%"),
                        User.username.not_like("pytest_%"),
                        User.username.not_like("guess_c_%"),
                        User.username.not_like("ask_q_%"),
                        PowiatdleDay.date >= current_month,
                        or_(PowiatdleState.questions_asked > 0, PowiatdleState.guesses_made > 0),
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
            
        elif type == "average":
            stmt = (
                select(
                    User.id,
                    User.username,
                    func.coalesce(func.sum(PowiatdleState.points), 0).label("points"),
                    func.coalesce(func.sum(cast(PowiatdleState.won, Integer)), 0).label(
                        "wins"
                    ),
                    func.count(PowiatdleState.id).label("games_played"),
                )
                .join(User, User.id == PowiatdleState.user_id)
                .where(
                    and_(
                        User.username.not_like("test_%"),
                        User.username.not_like("pytest_%"),
                        User.username.not_like("guess_c_%"),
                        User.username.not_like("ask_q_%"),
                        PowiatdleState.is_game_over == True,
                        or_(PowiatdleState.questions_asked > 0, PowiatdleState.guesses_made > 0),
                    )
                )
                .group_by(User.id, User.username)
                .having(func.count(PowiatdleState.id) >= 5)
            )

            result = await self.session.execute(stmt)

            leaderboard = []
            for row in result.all():
                avg_points = row.points / row.games_played if row.games_played > 0 else 0
                leaderboard.append({
                    "id": row.id,
                    "username": row.username,
                    "points": row.points,
                    "streak": 0,
                    "wins": row.wins,
                    "average_points": round(avg_points, 2),
                    "games_played": row.games_played,
                })

            leaderboard.sort(key=lambda x: x["average_points"], reverse=True)

            return [LeaderboardEntry(**entry) for entry in leaderboard]
            
        return []

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
                target_name=state.day.powiat.nazwa if state.day.date != date.today() else "???",
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
