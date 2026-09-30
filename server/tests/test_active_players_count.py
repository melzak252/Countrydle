from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models.blog import DailyBlogPost
from db.models.continental import ContinentalDay, ContinentalState, ContinentCode

from db.base import Base
from db.models.continental import ContinentalDay, ContinentalState, ContinentCode
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.guest_participation import GuestParticipation
from db.models.powiat import Powiat
from db.models.powiatdle import PowiatdleDay, PowiatdleState
from db.models.us_state import USState
from db.models.us_statedle import USStatedleDay, USStatedleState
from db.models.user import User
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState
from db.repositories.participation import ParticipationRepository


TODAY = date(2026, 9, 29)


class ReportingSession:
    """Execute production SQL on an isolated SQLite database."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


@pytest.fixture
def participation_test_db():
    engine = create_engine("sqlite://")
    models = (
        User, Country, USState, Powiat, Wojewodztwo, DailyBlogPost,
        CountrydleDay, CountrydleState,
        USStatedleDay, USStatedleState,
        PowiatdleDay, PowiatdleState,
        WojewodztwodleDay, WojewodztwodleState,
        FlagdleDay, FlagdleState,
        ContinentalDay, ContinentalState,
        GuestParticipation,
    )
    Base.metadata.create_all(engine, tables=[model.__table__ for model in models])
    with Session(engine) as session:
        session.add_all([
            Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"),
            USState(id=1, name="California"),
            Powiat(id=1, nazwa="warszawski"),
            Wojewodztwo(id=1, nazwa="mazowieckie"),
            CountrydleDay(id=1, country_id=1, date=TODAY),
            USStatedleDay(id=1, us_state_id=1, date=TODAY),
            PowiatdleDay(id=1, powiat_id=1, date=TODAY),
            WojewodztwodleDay(id=1, wojewodztwo_id=1, date=TODAY),
            FlagdleDay(id=1, country_id=1, date=TODAY),
            ContinentalDay(id=1, country_id=1, continent=ContinentCode.EUROPE, date=TODAY),
        ])
        session.flush()
        yield session, ReportingSession(session)
    engine.dispose()


@pytest.mark.anyio
async def test_active_players_count_includes_players_who_only_asked_question(participation_test_db):
    db, session = participation_test_db
    # User 1 asked 2 questions, made 0 guesses in Countrydle
    db.add(CountrydleState(user_id=1, day_id=1, questions_asked=2, guesses_made=0))
    # Guest A asked 1 question, made 0 guesses in US Statedle
    db.add(GuestParticipation(guest_id="guest-a", mode="us_statedle", day_id=1, questions_asked=1, guesses_made=0))
    # User 2 opened the game but asked 0 questions and made 0 guesses (inactive)
    db.add(CountrydleState(user_id=2, day_id=1, questions_asked=0, guesses_made=0))
    db.flush()

    repo = ParticipationRepository(session)
    stats = await repo.get_stats(TODAY)
    modes = await repo.get_mode_stats(TODAY)

    assert stats["total_players"] == 2
    assert modes["countrydle"]["total_players"] == 1
    assert modes["countrydle"]["total_questions"] == 2
    assert modes["us_statedle"]["total_players"] == 1
    assert modes["us_statedle"]["total_questions"] == 1


@pytest.mark.anyio
async def test_active_players_count_includes_players_who_only_guessed(participation_test_db):
    db, session = participation_test_db
    # User 1 made 1 guess, asked 0 questions in Countrydle
    db.add(CountrydleState(user_id=1, day_id=1, questions_asked=0, guesses_made=1, won=True))
    # Guest B made 1 guess, asked 0 questions in Powiatdle
    db.add(GuestParticipation(guest_id="guest-b", mode="powiatdle", day_id=1, questions_asked=0, guesses_made=1))
    db.flush()

    repo = ParticipationRepository(session)
    stats = await repo.get_stats(TODAY)
    modes = await repo.get_mode_stats(TODAY)

    assert stats["total_players"] == 2
    assert modes["countrydle"]["total_players"] == 1
    assert modes["countrydle"]["total_guesses"] == 1
    assert modes["powiatdle"]["total_players"] == 1
    assert modes["powiatdle"]["total_guesses"] == 1


@pytest.mark.anyio
async def test_active_players_count_deduplicates_across_questions_and_guesses(participation_test_db):
    db, session = participation_test_db
    # User 1 asked questions AND made guesses in Countrydle
    db.add(CountrydleState(user_id=1, day_id=1, questions_asked=5, guesses_made=2, won=True))
    # Guest C asked questions AND made guesses in Flagdle
    db.add(GuestParticipation(guest_id="guest-c", mode="flagdle", day_id=1, questions_asked=3, guesses_made=1, won=False))
    db.flush()

    repo = ParticipationRepository(session)
    stats = await repo.get_stats(TODAY)

    # 2 distinct active players, not 4
    assert stats["total_players"] == 2
    assert stats["total_questions"] == 8
    assert stats["total_guesses"] == 3


@pytest.mark.anyio
async def test_admin_overview_uses_utc_date_and_fetches_stats(participation_test_db, monkeypatch):
    db, session = participation_test_db
    db.add(CountrydleState(user_id=1, day_id=1, questions_asked=1, guesses_made=1, won=True))
    db.add(GuestParticipation(guest_id="guest-d", mode="continental:europe", day_id=1, questions_asked=2, guesses_made=0))
    db.flush()

    import admin

    # Ensure admin.get_admin_overview resolves UTC date
    monkeypatch.setattr(admin.CountrydleRepository, "get_today_country", AsyncMock(return_value=SimpleNamespace(country_id=1)))
    monkeypatch.setattr(admin.CountryRepository, "get", AsyncMock(return_value=SimpleNamespace(name="Poland")))
    monkeypatch.setattr(admin.USStatedleDayRepository, "get_today_us_state", AsyncMock(return_value=None))
    monkeypatch.setattr(admin.PowiatdleDayRepository, "get_today_powiat", AsyncMock(return_value=None))
    monkeypatch.setattr(admin.WojewodztwodleDayRepository, "get_today_wojewodztwo", AsyncMock(return_value=None))

    # Mock datetime in admin to return TODAY as UTC
    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(TODAY.year, TODAY.month, TODAY.day, 12, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(admin, "datetime", MockDatetime)

    overview = await admin.get_admin_overview(admin=None, session=session)

    assert overview.today.total_players == 2
    assert overview.today.total_winners == 1
    assert overview.today.total_questions == 3
    assert overview.today.total_guesses == 1


@pytest.mark.anyio
async def test_regional_modes_generate_day_on_question(monkeypatch):
    import us_statedle
    import powiatdle
    import wojewodztwodle

    fake_day = SimpleNamespace(id=42, us_state_id=1, powiat_id=1, wojewodztwo_id=1)
    mock_generate_us = AsyncMock(return_value=fake_day)
    mock_generate_powiat = AsyncMock(return_value=fake_day)
    mock_generate_woj = AsyncMock(return_value=fake_day)

    monkeypatch.setattr(us_statedle.USStatedleDayRepository, "get_today_us_state", AsyncMock(return_value=None))
    monkeypatch.setattr(us_statedle.USStatedleDayRepository, "generate_new_day_us_state", mock_generate_us)
    monkeypatch.setattr(powiatdle.PowiatdleDayRepository, "get_today_powiat", AsyncMock(return_value=None))
    monkeypatch.setattr(powiatdle.PowiatdleDayRepository, "generate_new_day_powiat", mock_generate_powiat)
    monkeypatch.setattr(wojewodztwodle.WojewodztwodleDayRepository, "get_today_wojewodztwo", AsyncMock(return_value=None))
    monkeypatch.setattr(wojewodztwodle.WojewodztwodleDayRepository, "generate_new_day_wojewodztwo", mock_generate_woj)

    class MockQuestion:
        valid = False
        answer = None
        explanation = "Error"
        def model_dump(self):
            return {"valid": False, "answer": None, "explanation": "Error", "original_question": "Test", "question": "Test", "day_id": 42}

    mock_q = MockQuestion()
    monkeypatch.setattr(us_statedle.uutils, "analyze_and_answer_locally", AsyncMock(return_value=(mock_q, None)))
    monkeypatch.setattr(powiatdle.putils, "analyze_and_answer_locally", AsyncMock(return_value=(mock_q, None)))
    monkeypatch.setattr(wojewodztwodle.wutils, "analyze_and_answer_locally", AsyncMock(return_value=(mock_q, None)))

    fake_session = AsyncMock()
    fake_request = SimpleNamespace()
    fake_response = SimpleNamespace()

    # Calling _do_ask_question when get_today_... is None must trigger generate_new_day_...
    await us_statedle._do_ask_question(SimpleNamespace(question="Test"), None, fake_session, fake_request, fake_response)
    assert mock_generate_us.called

    await powiatdle._do_ask_question(SimpleNamespace(question="Test"), None, fake_session, fake_request, fake_response)
    assert mock_generate_powiat.called

    await wojewodztwodle._do_ask_question(SimpleNamespace(question="Test"), None, fake_session, fake_request, fake_response)
    assert mock_generate_woj.called


def test_sanitize_explanation_removes_target_name_and_plumbing():
    from utils.explanation_sanitizer import sanitize_explanation_for_player

    raw = "The provided text mentions that Vietnam has numerous islands, but it does not specify the total area of these islands or compare it to the mainland territory to determine if islands constitute the majority of Vietnam's land area."
    sanitized = sanitize_explanation_for_player(raw, {"Vietnam", "Socialist Republic of Vietnam"}, "the country")

    assert "Vietnam" not in sanitized
    assert "provided text" not in sanitized.lower()
    assert sanitized.startswith("The country has numerous islands")
    assert "majority of the country's land area" in sanitized
