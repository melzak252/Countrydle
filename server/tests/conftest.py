import pytest
from httpx import AsyncClient, ASGITransport
from app import app
import csv
import os
from pathlib import Path
from types import SimpleNamespace
from tests.test_guess_accounting import guess_db

# Use the existing database for tests (or a separate test DB if configured)
DATABASE_URL = os.getenv("DATABASE_URL")
DEFAULT_COUNTRYDLE_EVAL_CSV = Path(__file__).resolve().parents[1] / "test_reports" / "countrydle_pipeline_eval.csv"


def pytest_configure(config):
    config._countrydle_eval_rows = []


def pytest_sessionfinish(session, exitstatus):
    rows = getattr(session.config, "_countrydle_eval_rows", [])
    if not rows:
        return

    output_path = Path(os.getenv("COUNTRYDLE_EVAL_CSV", DEFAULT_COUNTRYDLE_EVAL_CSV))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "question",
        "country",
        "expected_answer",
        "pipeline_answer",
        "is_correct",
        "evaluation_mode",
        "answering_executed",
        "source",
        "went_further",
        "enhanced_question",
        "relation",
        "explanation",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def record_countrydle_eval(request):
    def _record(**row):
        request.config._countrydle_eval_rows.append(row)

    return _record

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def make_test_user(
    username: str = "pytest_user",
    email: str = "pytest@example.com",
    user_id: int = 1,
):
    return SimpleNamespace(
        id=user_id,
        username=username,
        email=email,
        hashed_password="test-hash",
        is_admin=False,
        verified=True,
    )


@pytest.fixture(autouse=True)
def isolate_question_attempt_rate_limit(monkeypatch):
    from utils.question_rate_limit import question_attempt_limiter

    question_attempt_limiter.clear()
    monkeypatch.setattr(question_attempt_limiter, "max_requests", 1000)
    yield
    question_attempt_limiter.clear()


@pytest.fixture(autouse=True)
def mock_common_database_repositories(monkeypatch, request):
    """Keep endpoint tests hermetic when PostgreSQL is not running locally.

    Most API tests patch their domain repositories directly. Auth endpoints and
    a small countries-list smoke test used to hit the real database, which makes
    the suite fail on machines without the Docker `db` host. These defaults are
    intentionally small and can still be overridden by per-test patches.
    """
    if request.node.get_closest_marker("real_database") or "daily_api_db" in request.fixturenames:
        return

    # Endpoint unit tests replace action repositories; participation shares their
    # transaction and must not open a separate connection to the application DB.
    from importlib import import_module
    from unittest.mock import AsyncMock
    from utils.guest_session import get_guest_identity

    async def record_guest_action(
        session, request, response, mode, day_id, *, max_guesses,
        question=False, won=None, max_questions=None,
    ):
        return SimpleNamespace(
            guest_id=get_guest_identity(request, response),
            mode=mode, day_id=day_id, user_id=None,
            questions_asked=int(question), guesses_made=int(not question), won=bool(won),
        )

    for mode in ("countrydle", "continental", "flagdle", "us_statedle", "powiatdle", "wojewodztwodle"):
        module = import_module(mode)
        monkeypatch.setattr(module, "record_guest_action", record_guest_action)
        monkeypatch.setattr(module, "get_guest_progress", AsyncMock(return_value=(None, [], [])))
        monkeypatch.setattr(module, "claim_guest_history", AsyncMock(return_value=False))
        if hasattr(module, "check_guest_question_available"):
            monkeypatch.setattr(module, "check_guest_question_available", AsyncMock(return_value=None))

    async def register_user(self, user):
        return make_test_user(username=user.username, email=user.email)

    async def get_user(self, username):
        return make_test_user(username=username, email=f"{username}@example.com")

    async def get_by_email(self, email):
        username = "pytest_user" if email == "pytest@example.com" else email.split("@", 1)[0]
        return make_test_user(username=username, email=email)

    async def get_all_countries(self):
        return [
            SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland"),
            SimpleNamespace(id=2, name="Germany", official_name="Federal Republic of Germany"),
        ]

    async def get_country(self, country_id):
        return SimpleNamespace(id=country_id, name="Poland", official_name="Republic of Poland")

    async def get_today_country(self):
        return SimpleNamespace(id=1, country_id=100, date=None)

    async def generate_new_day_country(self, *args, **kwargs):
        return SimpleNamespace(id=1, country_id=100, date=None)

    async def get_player_countrydle_state(self, user, daily_country, max_questions, max_guesses):
        return SimpleNamespace(
            id=1,
            user_id=user.id,
            day_id=daily_country.id,
            remaining_questions=max_questions,
            remaining_guesses=max_guesses,
            questions_asked=0,
            guesses_made=0,
            won=False,
            is_game_over=False,
        )

    async def update_countrydle_state(self, state, *, commit=True):
        return state
    async def flagdle_add_guess(self, guess_create, *, commit=True):
        from types import SimpleNamespace
        from datetime import datetime
        return SimpleNamespace(
            id=1,
            guess=guess_create.guess,
            country_id=guess_create.country_id,
            day_id=guess_create.day_id,
            user_id=guess_create.user_id,
            answer=guess_create.answer,
            distance_km=guess_create.distance_km,
            bearing_degrees=guess_create.bearing_degrees,
            bearing_direction=guess_create.bearing_direction,
            bearing_arrow=guess_create.bearing_arrow,
            matched_colors=guess_create.matched_colors or [],
            missed_colors=guess_create.missed_colors or [],
            remaining_colors_count=guess_create.remaining_colors_count or 0,
            matched_symbols=guess_create.matched_symbols or [],
            revealed_tile=guess_create.revealed_tile,
            elapsed_seconds=guess_create.elapsed_seconds,
            guessed_at=datetime.now(),
        )

    async def countrydle_add_guess(self, guess_create, *, commit=True):
        from datetime import datetime
        return SimpleNamespace(
            id=1,
            guess=guess_create.guess,
            country_id=guess_create.country_id,
            day_id=guess_create.day_id,
            user_id=guess_create.user_id,
            answer=guess_create.answer,
            guessed_at=datetime.now(),
        )

    async def get_us_state(self, state_id):
        return SimpleNamespace(id=state_id, name="California", code="CA")

    async def get_wojewodztwo(self, wojewodztwo_id):
        return SimpleNamespace(id=wojewodztwo_id, nazwa="Małopolskie")

    monkeypatch.setattr("db.repositories.guess.CountrydleGuessRepository.add_guess", countrydle_add_guess)
    monkeypatch.setattr("db.repositories.us_state.USStateRepository.get", get_us_state)
    monkeypatch.setattr("db.repositories.wojewodztwo.WojewodztwoRepository.get", get_wojewodztwo)

    monkeypatch.setattr("db.repositories.user.UserRepository.register_user", register_user)
    monkeypatch.setattr("db.repositories.user.UserRepository.get_user", get_user)
    monkeypatch.setattr("db.repositories.user.UserRepository.get_by_email", get_by_email)
    monkeypatch.setattr("db.repositories.user.UserRepository.verify_password", staticmethod(lambda *_: True))
    monkeypatch.setattr("db.repositories.country.CountryRepository.get_all_countries", get_all_countries)
    monkeypatch.setattr("db.repositories.country.CountryRepository.get", get_country)
    monkeypatch.setattr("db.repositories.countrydle.CountrydleRepository.get_today_country", get_today_country)
    monkeypatch.setattr("db.repositories.countrydle.CountrydleRepository.generate_new_day_country", generate_new_day_country)
    monkeypatch.setattr("db.repositories.countrydle.CountrydleStateRepository.get_player_countrydle_state", get_player_countrydle_state)
    monkeypatch.setattr("db.repositories.countrydle.CountrydleStateRepository.update_countrydle_state", update_countrydle_state)
    monkeypatch.setattr("db.repositories.flagdle.FlagdleGuessRepository.add_guess", flagdle_add_guess)

@pytest.fixture
async def token(async_client):
    return "pytest-access-token"

@pytest.fixture
async def auth_client(async_client, token):
    from users.utils import get_current_or_guest_user, get_current_user

    async def mock_get_current_user():
        return make_test_user()

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_current_or_guest_user] = mock_get_current_user
    async_client.cookies.set("access_token", token)
    yield async_client
    async_client.cookies.delete("access_token")
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_or_guest_user, None)


@pytest.fixture
async def daily_api_db(guess_db, monkeypatch):
    """Real daily/account/guest repositories in an owned disposable PostgreSQL schema."""
    from db import get_db
    from utils import guest_session

    monkeypatch.setattr(guest_session, "SECRET_KEY", "isolated-daily-api-signing-key-20261007")

    async def isolated_session():
        async with guess_db.factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = isolated_session
    try:
        yield guess_db.factory
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
async def daily_api_client(daily_api_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        yield client
