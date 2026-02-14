from datetime import date
import random
from typing import List
from pydantic import BaseModel
from sqlalchemy import Integer, and_, case, cast, func, select
from sqlalchemy.orm import joinedload, aliased, contains_eager
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country, CountrydleState, DayCountry, User
from db.repositories.country import CountryRepository
from db.models import Guess
from db.repositories.user import UserRepository
from db.models.user import UserPoints
from schemas.countrydle import LeaderboardEntry, UserStatistics
from db.models.question import Question
from db.repositories.question import QuestionsRepository
from db.repositories.guess import GuessRepository

MAX_GUESSES = 3
MAX_QUESTIONS = 10


class CountrydleRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    ### DayCountry
    async def get_day_county(self, dcid: int) -> DayCountry | None:
        result = await self.session.execute(
            select(DayCountry).where(DayCountry.id == dcid)
        )

        return result.scalars().first()

    async def get_day_country_by_date(self, day_date: date) -> DayCountry | None:
        result = await self.session.execute(
            select(DayCountry).where(DayCountry.date == day_date)
        )

        return result.scalars().first()

    async def get_today_country(self) -> DayCountry | None:
        result = await self.session.execute(
            select(DayCountry)
            .where(DayCountry.date == date.today())
            .order_by(DayCountry.id.desc())
        )

        return result.scalars().first()

    async def get_last_added_day_country(self) -> DayCountry | None:
        result = await self.session.execute(
            select(DayCountry).order_by(DayCountry.date.desc())
        )

        return result.scalars().first()

    async def create_day_country(self, country: Country) -> DayCountry:
        new_entry = DayCountry(country_id=country.id)

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
    ) -> DayCountry:
        new_entry = DayCountry(country_id=country.id, date=day_date)

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
    ) -> DayCountry:
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
            select(DayCountry)
            .options(joinedload(DayCountry.country))
            .where(DayCountry.date < date.today())
            .order_by(DayCountry.date.desc())
        )

        return result.scalars().all()

    async def get_countries_count(self):
        dc = aliased(DayCountry)
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
                    User.username.not_like('test_%'),
                    User.username.not_like('pytest_%'),
                    User.username.not_like('guess_c_%'),
                    User.username.not_like('ask_q_%')
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
        questions_asked, corr_quest, incorr_questions = await QuestionsRepository(
            self.session
        ).get_user_question_statistics(user)

        guesses_made, guesses_correct, guesses_incorrect = await GuessRepository(
            self.session
        ).get_user_guess_statistics(user)

        history = await CountrydleStateRepository(
            self.session
        ).get_player_countrydle_states(user, show_today=False)

        profile = UserStatistics(
            user=user,
            points=up.points,
            streak=up.streak,
            wins=wins,
            questions_asked=questions_asked,
            questions_correct=corr_quest,
            questions_incorrect=incorr_questions,
            guesses_made=guesses_made,
            guesses_correct=guesses_correct,
            guesses_incorrect=guesses_incorrect,
            history=history,
        )

        return profile


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

    async def guess_made(self, state: CountrydleState, guess: Guess) -> CountrydleState:
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
        self, user: User, day: DayCountry
    ) -> CountrydleState:
        result = await self.session.execute(
            select(CountrydleState)
            .where(CountrydleState.user_id == user.id, CountrydleState.day_id == day.id)
            .order_by(CountrydleState.id.asc())
        )

        state = result.scalars().first()

        if state is None:
            return await self.add_countrydle_state(user, day)

        return state

    async def get_player_countrydle_states(
        self, user: User, show_today: bool = True
    ) -> List[CountrydleState]:
        result = await self.session.execute(
            select(CountrydleState)
            .options(
                joinedload(CountrydleState.user),
                joinedload(CountrydleState.day),
                joinedload(CountrydleState.day, DayCountry.country),
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
        day: DayCountry,
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

    async def get_state(self, user: User, day: DayCountry) -> CountrydleState:
        result = await self.session.execute(
            select(CountrydleState)
            .where(CountrydleState.user_id == user.id, CountrydleState.day_id == day.id)
            .order_by(CountrydleState.id.asc())
        )

        state = result.scalars().first()

        if state is None:
            return await self.add_countrydle_state(user, day)

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
