import pytest
from httpx import AsyncClient, ASGITransport
from app import app
import csv
import os
from pathlib import Path
from types import SimpleNamespace

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
def mock_common_database_repositories(monkeypatch, request):
    """Keep endpoint tests hermetic when PostgreSQL is not running locally.

    Most API tests patch their domain repositories directly. Auth endpoints and
    a small countries-list smoke test used to hit the real database, which makes
    the suite fail on machines without the Docker `db` host. These defaults are
    intentionally small and can still be overridden by per-test patches.
    """
    if request.node.get_closest_marker("real_database"):
        return

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

    async def generate_new_day_country(self):
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

    async def update_countrydle_state(self, state):
        return state

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
