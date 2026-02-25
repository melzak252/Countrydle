from datetime import date
import random
from typing import List
from pydantic import BaseModel
from sqlalchemy import Integer, and_, case, cast, func, select
from sqlalchemy.orm import joinedload, aliased, contains_eager
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country, CountrydleState, CountrydleDay, User
from db.repositories.country import CountryRepository
from db.models import CountrydleGuess
from db.repositories.user import UserRepository
from db.models.user import UserPoints
from schemas.countrydle import LeaderboardEntry, UserStatistics
from schemas.statistics import GameStatistics, GameHistoryEntry
from db.models.question import CountrydleQuestion
from db.repositories.question import CountrydleQuestionsRepository
from db.repositories.guess import CountrydleGuessRepository

MAX_GUESSES = 3
MAX_QUESTIONS = 10


class CountrydleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    ### CountrydleDay
    async def get_day_county(self, dcid: int) -> CountrydleDay | None:
        result = await self.session.execute(
            select(CountrydleDay).where(CountrydleDay.id == dcid)
        )

        return result.scalars().first()

    async def get_day_country_by_date(self, day_date: date) -> CountrydleDay | None:
        result = await self.session.execute(
            select(CountrydleDay).where(CountrydleDay.date == day_date)
        )

        return result.scalars().first()

    async def get_today_country(self) -> CountrydleDay | None:
        result = await self.session.execute(
            select(CountrydleDay)
            .where(CountrydleDay.date == date.today())
            .order_by(CountrydleDay.id.desc())
        )

        return result.scalars().first()

    async def get_today_country_sync(self) -> CountrydleDay | None:
        # This is for debugging purposes if needed, but we should use async
        result = await self.session.execute(
            select(CountrydleDay)
            .where(CountrydleDay.date == date.today())
            .order_by(CountrydleDay.id.desc())
        )
        return result.scalars().first()

    async def get_last_added_day_country(self) -> CountrydleDay | None:
        result = await self.session.execute(
            select(CountrydleDay).order_by(CountrydleDay.date.desc())
        )

        return result.scalars().first()

    async def create_day_country(self, country: Country) -> CountrydleDay:
        new_entry = CountrydleDay(country_id=country.id)

        self.session.add(new_entry)

        try:
            await self.session.commit()  # Commit the transaction
            await self.session.refresh(new_entry)  # Refresh the instance to get the ID
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return new_entry

    async def create_day_country_with_date(
        self, country: Country, day_date: date
    ) -> CountrydleDay:
        new_entry = CountrydleDay(country_id=country.id, date=day_date)

        self.session.add(new_entry)

        try:
            await self.session.commit()  # Commit the transaction
            await self.session.refresh(new_entry)  # Refresh the instance to get the ID
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return new_entry

    async def generate_new_day_country(
        self, day_date: date | None = None
    ) -> CountrydleDay:
        countries = await CountryRepository(self.session).get_all_countries()
        if not countries:
            raise ValueError("No countries in database!")

        country = random.choice(countries)

        if not day_date:
            new_country = await self.create_day_country(country)
        else:
            new_country = await self.create_day_country_with_date(country, day_date)

        return new_country

    async def get_countrydle_history(self):
        result = await self.session.execute(
            select(CountrydleDay)
            .options(joinedload(CountrydleDay.country))
            .where(CountrydleDay.date < date.today())
            .order_by(CountrydleDay.date.desc())
        )

        return result.scalars().all()

    async def get_countries_count(self):
        dc = aliased(CountrydleDay)
        stmt = (
            select(
                Country.id,
                Country.name,
                func.count(dc.id).label("count"),
                func.max(dc.date).label("last"),
            )
            .outerjoin(dc, Country.id == dc.country_id)
            .where(dc.date < date.today())
            .group_by(Country.id, Country.name)
            .order_by(
                func.count(dc.id).desc(), func.max(dc.date).desc(), Country.name.asc()
            )
        )

        result = await self.session.execute(stmt)

        countries_with_count = result.all()

        return countries_with_count

    async def get_leaderboard(self):
        cs = aliased(CountrydleState)
        up = aliased(UserPoints)
        stmt = (
            select(
                User.id,
                User.username,
                func.coalesce(up.points, 0).label("points"),
                func.coalesce(func.sum(cs.won.cast(Integer)), 0).label("wins"),
                func.coalesce(up.streak, 0).label("streak"),
            )
            .outerjoin(up, User.id == up.user_id)
            .outerjoin(cs, User.id == cs.user_id)
            .where(
                and_(
                    User.username.not_like("test_%"),
                    User.username.not_like("pytest_%"),
                    User.username.not_like("guess_c_%"),
                    User.username.not_like("ask_q_%"),
                )
            )
            .group_by(
                User.id,
                User.username,
                up.points,
                up.streak,
            )
            .order_by(
                func.coalesce(up.points, 0).desc(),
                func.coalesce(func.sum(cs.won.cast(Integer)), 0).desc(),
                func.coalesce(up.streak, 0).desc(),
            )
        )

        result = await self.session.execute(stmt)

        leaderboard = [
            LeaderboardEntry(
                id=row.id,
                username=row.username,
                points=row.points,
                streak=row.streak,
                wins=row.wins,
            )
            for row in result.all()
        ]

        return leaderboard

    async def get_user_statistics(self, user: User) -> UserStatistics:
        up = await UserRepository(self.session).get_user_points(user.id)
        result = await self.session.execute(
            select(
                func.sum(CountrydleState.won.cast(Integer)).label("wins"),
            ).where(CountrydleState.user_id == user.id)
        )
        wins = result.scalar() or 0

        q_stats = await CountrydleQuestionsRepository(
            self.session
        ).get_user_question_statistics(user)

        questions_asked = q_stats[0] if q_stats else 0
        corr_quest = q_stats[1] if q_stats else 0
        incorr_questions = q_stats[2] if q_stats else 0

        g_stats = await CountrydleGuessRepository(
            self.session
        ).get_user_guess_statistics(user)

        guesses_made = g_stats[0] if g_stats else 0
        guesses_correct = g_stats[1] if g_stats else 0
        guesses_incorrect = g_stats[2] if g_stats else 0

        history = await CountrydleStateRepository(
            self.session
        ).get_player_countrydle_states(user, show_today=False)

        profile = UserStatistics(
            user=user,
            points=up.points if up else 0,
            streak=up.streak if up else 0,
            wins=wins,
            questions_asked=questions_asked or 0,
            questions_correct=corr_quest or 0,
            questions_incorrect=incorr_questions or 0,
            guesses_made=guesses_made or 0,
            guesses_correct=guesses_correct or 0,
            guesses_incorrect=guesses_incorrect or 0,
            history=history,
        )

        return profile

    async def get_game_statistics(self, user: User) -> GameStatistics:
        up = await UserRepository(self.session).get_user_points(user.id)

        # Calculate wins and games played
        stmt = select(
            func.coalesce(func.sum(cast(CountrydleState.won, Integer)), 0).label(
                "wins"
            ),
            func.count(CountrydleState.id).label("games_played"),
        ).where(CountrydleState.user_id == user.id)
        result = await self.session.execute(stmt)
        row = result.first()

        wins = row.wins if row else 0
        games_played = row.games_played if row else 0
        points = up.points if up else 0
        streak = up.streak if up else 0

        # Get history
        history_stmt = (
            select(CountrydleState)
            .options(joinedload(CountrydleState.day).joinedload(CountrydleDay.country))
            .where(
                and_(
                    CountrydleState.user_id == user.id,
                    CountrydleState.is_game_over == True,
                )
            )
            .order_by(CountrydleState.id.desc())
        )
        history_result = await self.session.execute(history_stmt)
        history_states = history_result.scalars().all()

        history_entries = [
            GameHistoryEntry(
                date=str(state.day.date),
                won=state.won,
                points=state.points,
                attempts=state.guesses_made,
                target_name=state.day.country.name if state.won else "???",
            )
            for state in history_states
        ]

        return GameStatistics(
            points=points,
            wins=wins,
            games_played=games_played,
            streak=streak,
            history=history_entries,
        )


class CountrydleStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, csid: int) -> CountrydleState:
        result = await self.session.execute(
            select(CountrydleState).where(CountrydleState.id == csid)
        )

        return result.scalars().first()

    async def calc_points(self, state: CountrydleState) -> int:
        question_points = state.remaining_questions * 100
        guess_points = 100 * (((state.remaining_guesses + 1) ** 2) + 1)

        return question_points + guess_points

    async def guess_made(
        self, state: CountrydleState, guess: CountrydleGuess
    ) -> CountrydleState:
        state.guesses_made += 1
        state.remaining_guesses -= 1

        if not state.remaining_guesses:
            state.is_game_over = True
            state.won = False

        if guess.answer:
            state.is_game_over = True
            state.won = True

        points = 0
        if state.won:
            points = await self.calc_points(state)
            state.points = points

        if state.is_game_over:
            await UserRepository(self.session).update_points(state.user_id, state)

        await self.session.commit()

        return state

    async def get_player_countrydle_state(
        self,
        user: User,
        day: CountrydleDay,
        max_questions: int = 10,
        max_guesses: int = 3,
    ) -> CountrydleState:
        result = await self.session.execute(
            select(CountrydleState)
            .where(CountrydleState.user_id == user.id, CountrydleState.day_id == day.id)
            .order_by(CountrydleState.id.asc())
        )

        state = result.scalars().first()

        if state is None:
            return await self.add_countrydle_state(
                user, day, max_questions, max_guesses
            )

        return state

    async def get_player_countrydle_states(
        self, user: User, show_today: bool = True
    ) -> List[CountrydleState]:
        result = await self.session.execute(
            select(CountrydleState)
            .options(
                joinedload(CountrydleState.user),
                joinedload(CountrydleState.day),
                joinedload(CountrydleState.day, CountrydleDay.country),
            )
            .where(
                and_(
                    CountrydleState.user_id == user.id,
                    CountrydleState.is_game_over,
                )
            )
            .order_by(CountrydleState.id.desc())
        )

        states = result.scalars().all()

        if not show_today:
            for state in states:
                if state.day.date == date.today():
                    state.day.country = None

        return states

    async def add_countrydle_state(
        self,
        user: User,
        day: CountrydleDay,
        max_questions: int = MAX_QUESTIONS,
        max_guesses: int = MAX_GUESSES,
    ) -> CountrydleState:

        new_entry = CountrydleState(
            user_id=user.id,
            day_id=day.id,
            remaining_questions=max_questions,
            remaining_guesses=max_guesses,
            questions_asked=0,
            guesses_made=0,
        )

        self.session.add(new_entry)

        try:
            await self.session.commit()  # Commit the transaction
            await self.session.refresh(new_entry)  # Refresh the instance to get the ID
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return new_entry

    async def get_state(
        self,
        user: User,
        day: CountrydleDay,
        max_questions: int = 10,
        max_guesses: int = 3,
    ) -> CountrydleState:
        result = await self.session.execute(
            select(CountrydleState)
            .where(CountrydleState.user_id == user.id, CountrydleState.day_id == day.id)
            .order_by(CountrydleState.id.asc())
        )

        state = result.scalars().first()

        if state is None:
            return await self.add_countrydle_state(
                user, day, max_questions, max_guesses
            )

        return state

    async def update_countrydle_state(self, state: CountrydleState):
        await self.session.merge(state)

        try:
            await self.session.commit()
            await self.session.refresh(state)
        except Exception as ex:
            await self.session.rollback()
            raise ex

        return state
