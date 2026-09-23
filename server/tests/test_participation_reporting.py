from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.base import Base
from db.models.blog import DailyBlogPost
from db.models.continental import ContinentalDay, ContinentalState
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.guest_participation import GuestParticipation
from db.models.powiatdle import PowiatdleDay, PowiatdleState
from db.models.us_statedle import USStatedleDay, USStatedleState
from db.models.user import User
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState
from db.repositories.blog import BlogRepository
from db.repositories.participation import ParticipationRepository


TODAY = date(2026, 9, 23)


class ReportingSession:
    """Execute production SQL on an isolated SQLite database, not the configured DB."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


@pytest.fixture
def reporting_db():
    engine = create_engine("sqlite://")
    models = (
        User, Country, DailyBlogPost, CountrydleDay, CountrydleState,
        USStatedleDay, USStatedleState, PowiatdleDay, PowiatdleState,
        WojewodztwodleDay, WojewodztwodleState, FlagdleDay, FlagdleState,
        ContinentalDay, ContinentalState, GuestParticipation,
    )
    Base.metadata.create_all(engine, tables=[model.__table__ for model in models])
    with Session(engine) as session:
        session.add_all([
            Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"),
            CountrydleDay(id=1, country_id=1, date=TODAY),
            CountrydleDay(id=2, country_id=1, date=TODAY - timedelta(days=1)),
        ])
        session.flush()
        yield session, ReportingSession(session)
    engine.dispose()


@pytest.mark.anyio
async def test_blog_stats_only_count_actual_actions_on_requested_puzzle_date(reporting_db):
    db, session = reporting_db
    db.add_all([
        CountrydleState(user_id=1, day_id=1),
        CountrydleState(user_id=2, day_id=1, won=True),
        CountrydleState(user_id=3, day_id=1, questions_asked=2),
        CountrydleState(user_id=4, day_id=1, guesses_made=1, won=True),
        CountrydleState(user_id=5, day_id=2, questions_asked=90, guesses_made=3, won=True),
        CountrydleState(user_id=None, day_id=1, guesses_made=3, won=True),
        GuestParticipation(guest_id="visitor", mode="countrydle", day_id=1,
                           questions_asked=4, guesses_made=2, won=True),
        GuestParticipation(guest_id="inactive", mode="countrydle", day_id=1),
        GuestParticipation(guest_id="yesterday", mode="countrydle", day_id=2,
                           questions_asked=90, guesses_made=3, won=True),
        GuestParticipation(guest_id="other-mode", mode="flagdle", day_id=1,
                           guesses_made=8, won=True),
    ])
    db.flush()

    stats = await BlogRepository(session).get_day_player_stats(TODAY)

    assert stats == {
        "total_players": 3, "winners_count": 2, "win_rate_pct": 66.7,
        "total_questions": 6, "total_guesses": 3,
        "avg_questions_won": 2.0, "avg_guesses_won": 1.5,
    }
    assert await BlogRepository(session).get_day_player_stats(TODAY + timedelta(days=1)) == {
        "total_players": 0, "winners_count": 0, "win_rate_pct": 0,
        "total_questions": 0, "total_guesses": 0,
        "avg_questions_won": 0, "avg_guesses_won": 0,
    }


@pytest.mark.anyio
async def test_synced_guest_is_excluded_in_favor_of_registered_state(reporting_db):
    db, session = reporting_db
    db.add_all([
        CountrydleState(user_id=7, day_id=1, questions_asked=3, guesses_made=2, won=True),
        GuestParticipation(guest_id="synced", user_id=7, mode="countrydle", day_id=1,
                           questions_asked=2, guesses_made=1, won=True),
        GuestParticipation(guest_id="unlinked", mode="countrydle", day_id=1, guesses_made=1),
    ])
    db.flush()

    stats = await BlogRepository(session).get_day_player_stats(TODAY)

    assert stats["total_players"] == 2
    assert stats["winners_count"] == 1
    assert stats["total_questions"] == 3
    assert stats["total_guesses"] == 3
    assert stats["avg_questions_won"] == 3
    assert stats["avg_guesses_won"] == 2


@pytest.mark.anyio
async def test_dashboard_deduplicates_people_across_modes_but_win_rate_counts_games(reporting_db, monkeypatch):
    db, session = reporting_db
    db.add_all([
        FlagdleDay(id=1, country_id=1, date=TODAY),
        ContinentalDay(id=1, country_id=1, continent="europe", date=TODAY),
        ContinentalDay(id=2, country_id=1, continent="asia", date=TODAY),
        CountrydleState(user_id=1, day_id=1, guesses_made=1, won=True),
        FlagdleState(user_id=1, day_id=1, guesses_made=2, won=True),
        ContinentalState(user_id=1, day_id=1, questions_asked=1),
        GuestParticipation(guest_id="1", mode="countrydle", day_id=1, questions_asked=1),
        GuestParticipation(guest_id="1", mode="flagdle", day_id=1, guesses_made=1, won=True),
        FlagdleState(user_id=2, day_id=1, questions_asked=1),
        GuestParticipation(guest_id="1", mode="continental:europe", day_id=1, guesses_made=1),
        GuestParticipation(guest_id="1", mode="continental:asia", day_id=2, guesses_made=1, won=True),
        GuestParticipation(guest_id="wrong-continent", mode="continental:asia", day_id=1, guesses_made=9),
        GuestParticipation(guest_id="yesterday", mode="countrydle", day_id=2, guesses_made=1),
    ])
    db.flush()
    repo = ParticipationRepository(session)

    stats = await repo.get_stats(TODAY)
    modes = await repo.get_mode_stats(TODAY)
    history = await repo.get_daily_stats(TODAY - timedelta(days=1), TODAY)

    assert stats["winners_count"] == 4
    assert stats["total_players"] == 3
    assert stats["total_games"] == 8
    assert modes["countrydle"]["total_players"] == 2
    assert stats["win_rate_pct"] == 50.0
    assert stats["total_questions"] == 3
    assert stats["total_guesses"] == 6
    assert modes["continental:europe"]["total_players"] == 2
    assert modes["continental:asia"]["total_players"] == 1
    assert modes["flagdle"]["total_players"] == 3
    assert modes["flagdle"]["total_questions"] == 1
    assert history[TODAY]["total_players"] == 3
    assert history[TODAY - timedelta(days=1)]["total_players"] == 1

    import admin

    async def no_target(_):
        return None

    monkeypatch.setattr(admin, "date", SimpleNamespace(today=lambda: TODAY))
    monkeypatch.setattr(admin.CountrydleRepository, "get_today_country", no_target)
    monkeypatch.setattr(admin.USStatedleDayRepository, "get_today_us_state", no_target)
    monkeypatch.setattr(admin.PowiatdleDayRepository, "get_today_powiat", no_target)
    monkeypatch.setattr(admin.WojewodztwodleDayRepository, "get_today_wojewodztwo", no_target)
    overview = await admin.get_admin_overview(admin=None, session=session)
    assert overview.today.total_players == 3
    assert overview.today.total_winners == 4
    assert overview.today.win_rate_pct == 50.0
    assert overview.history_14d[0].total_players == 3
    assert overview.history_14d[1].total_players == 1
    assert overview.history_14d[2].total_players == 0
    assert overview.totals.total_games == 9
    assert overview.totals.total_guesses == 7
    assert {mode.mode_key for mode in overview.modes_today} == {
        "countrydle", "us_statedle", "powiatdle", "wojewodztwodle", "flagdle",
        "continental:europe", "continental:asia", "continental:africa", "continental:americas",
    }


@pytest.mark.anyio
async def test_existing_blog_responses_refresh_stats_without_changing_article(reporting_db):
    from blog import get_blog_post, get_latest_blog_post

    db, session = reporting_db
    post = DailyBlogPost(
        date=TODAY, country_id=1, slug="existing-poland", title="Original title",
        subtitle="Original subtitle", summary="Original summary", fun_facts=[],
        content_markdown="Original generated prose: 99 players.",
    )
    db.add(post)
    db.add(CountrydleState(user_id=1, day_id=1))
    db.flush()
    before = await get_blog_post(post.slug, session)
    db.add(GuestParticipation(guest_id="new-player", mode="countrydle", day_id=1, guesses_made=1))
    db.flush()

    after = await get_blog_post(TODAY.isoformat(), session)
    latest = await get_latest_blog_post(session)

    assert before.player_stats["total_players"] == 0
    assert after.player_stats["total_players"] == latest.player_stats["total_players"] == 1
    assert after.content_markdown == before.content_markdown == post.content_markdown
    assert after.title == before.title == "Original title"
    assert not db.is_modified(post)
