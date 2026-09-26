from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from db.models import Country, User
from db.models.continental import (
    ContinentCode,
    ContinentalDay,
    ContinentalGuess,
    ContinentalQuestion,
    ContinentalState,
)
from game_logic import calculate_points, CONTINENTAL_CONFIG
from continental.utils import (
    get_continent_country_names,
    is_eligible_candidate,
)
from users.utils import get_current_or_guest_user, get_current_user


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 42
    user.username = "explorer"
    user.email = "explorer@example.com"
    user.verified = True
    user.is_admin = False
    return user


@pytest.fixture
async def mock_auth(mock_user):
    async def _get_user():
        return mock_user

    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_current_or_guest_user] = _get_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_or_guest_user, None)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_continental_config():
    """Verify calibrated configuration: 8 questions, 3 guesses."""
    assert CONTINENTAL_CONFIG.max_questions == 8
    assert CONTINENTAL_CONFIG.max_guesses == 3


def test_continental_scoring_formula():
    """Verify scoring calculations match the calibrated formula."""
    # Theoretical max: 500 (base) + 1500 (0Q) + 500 (1G) + 300 (speed) + 500 (10 streak) = 3300
    score_max = calculate_points(
        config=CONTINENTAL_CONFIG,
        won=True,
        questions_used=0,
        guesses_used=1,
        elapsed_seconds=0,
        streak=10,
    )
    assert score_max == 3300

    # 8 questions used, 3 guesses used, no speed, 0 streak: 500 + 0 + 167 = 667
    score_low = calculate_points(
        config=CONTINENTAL_CONFIG,
        won=True,
        questions_used=8,
        guesses_used=3,
        elapsed_seconds=400,
        streak=0,
    )
    assert score_low == 667

    # Loss gives 0 points
    assert calculate_points(config=CONTINENTAL_CONFIG, won=False, questions_used=4, guesses_used=3) == 0


def test_candidate_counts_per_continent():
    """Verify exact candidate counts per specification."""
    europe = get_continent_country_names(ContinentCode.EUROPE)
    asia = get_continent_country_names(ContinentCode.ASIA)
    africa = get_continent_country_names(ContinentCode.AFRICA)
    americas = get_continent_country_names(ContinentCode.AMERICAS)

    assert len(europe) == 47
    assert len(asia) == 46
    assert len(africa) == 54
    assert len(americas) == 35


def test_transcontinental_candidate_rules():
    """Playable pools apply game exclusions without removing shared countries."""
    europe = set(get_continent_country_names(ContinentCode.EUROPE))
    asia = set(get_continent_country_names(ContinentCode.ASIA))

    for country in ["Russia", "Turkey"]:
        assert country in europe
        assert country in asia

    assert "Azerbaijan" not in europe
    assert "Azerbaijan" in asia
    assert "Kosovo" in europe
    assert "Israel" not in asia

    # Germany is in Europe, not in Asia
    assert "Germany" in europe
    assert "Germany" not in asia

    # Japan is in Asia, not in Europe
    assert "Japan" in asia
    assert "Japan" not in europe

    # Whitelist eligibility checker
    assert is_eligible_candidate("Russia", ContinentCode.EUROPE) is True
    assert is_eligible_candidate("Russia", ContinentCode.ASIA) is True
    assert is_eligible_candidate("Brazil", ContinentCode.EUROPE) is False
    assert is_eligible_candidate("Egypt", ContinentCode.AFRICA) is True


@pytest.mark.anyio
async def test_get_state_guest(client):
    """Test GET /continental/{continent}/state for unauthenticated guest."""
    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.continent = ContinentCode.EUROPE
    mock_day.country_id = 100
    mock_day.date = date(2026, 9, 22)

    with patch(
        "db.repositories.continental.ContinentalDayRepository.get_today_day",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.country.CountryRepository.get",
        new_callable=AsyncMock,
        return_value=Country(id=100, name="Poland", official_name="Republic of Poland", md_file=""),
    ):
        res = await client.get("/continental/europe/state")
        assert res.status_code == 200
        data = res.json()
        assert data["user"] is None
        assert data["state"]["remaining_questions"] == 8
        assert data["state"]["remaining_guesses"] == 3
        assert data["state"]["is_game_over"] is False
        assert data["country"] is None


@pytest.mark.anyio
async def test_get_countries_endpoint(client):
    """Test GET /continental/{continent}/countries returns filtered list."""
    mock_countries = [
        Country(id=1, name="Albania", official_name="Republic of Albania", md_file=""),
        Country(id=2, name="Andorra", official_name="Principality of Andorra", md_file=""),
    ]
    with patch(
        "continental.get_continent_countries",
        new_callable=AsyncMock,
        return_value=mock_countries,
    ):
        res = await client.get("/continental/europe/countries")
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 2
        assert items[0]["name"] == "Albania"
        assert items[1]["name"] == "Andorra"


@pytest.mark.anyio
async def test_reveal_endpoint(client):
    """Test GET /continental/{continent}/reveal returns secret country."""
    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.continent = ContinentCode.EUROPE
    mock_day.country_id = 100
    mock_day.date = date(2026, 9, 22)

    with patch(
        "db.repositories.continental.ContinentalDayRepository.get_today_day",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.country.CountryRepository.get",
        new_callable=AsyncMock,
        return_value=Country(id=100, name="Poland", official_name="Republic of Poland", md_file=""),
    ):
        res = await client.get("/continental/europe/reveal")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Poland"


@pytest.mark.anyio
async def test_candidate_validation_rejects_out_of_scope_guess(client, mock_auth):
    """Submitting a guess outside the continent whitelist returns HTTP 400."""
    res = await client.post(
        "/continental/europe/guess",
        json={"guess": "Brazil", "country_id": 50},
    )
    assert res.status_code == 400
    assert "not an eligible country in Europedle" in res.json()["detail"]


@pytest.mark.anyio
async def test_guess_with_geo_hints(client, mock_auth):
    """Submitting an eligible incorrect guess produces distance and bearing hints."""
    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.continent = ContinentCode.EUROPE
    mock_day.country_id = 100
    mock_day.date = date(2026, 9, 22)

    target_c = Country(id=100, name="Poland", official_name="Republic of Poland", md_file="")
    guessed_c = Country(id=101, name="Germany", official_name="Federal Republic of Germany", md_file="")

    mock_state = MagicMock()
    mock_state.id = 1
    mock_state.user_id = 42
    mock_state.day_id = 1
    mock_state.remaining_questions = 8
    mock_state.remaining_guesses = 2
    mock_state.questions_asked = 0
    mock_state.guesses_made = 1
    mock_state.is_game_over = False
    mock_state.won = False
    mock_state.points = 0

    mock_guess_db = MagicMock()
    mock_guess_db.id = 10
    mock_guess_db.guess = "Germany"
    mock_guess_db.country_id = 101
    mock_guess_db.answer = False
    mock_guess_db.guessed_at = datetime.now()
    mock_guess_db.elapsed_seconds = 15

    with patch(
        "db.repositories.continental.ContinentalDayRepository.get_today_day",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.country.CountryRepository.get",
        side_effect=lambda cid: target_c if cid == 100 else guessed_c,
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.get_state",
        new_callable=AsyncMock,
        return_value=mock_state,
    ), patch(
        "db.repositories.continental.ContinentalGuessRepository.add_guess",
        new_callable=AsyncMock,
        return_value=mock_guess_db,
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.guess_made",
        new_callable=AsyncMock,
        return_value=mock_state,
    ):
        res = await client.post(
            "/continental/europe/guess",
            json={"guess": "Germany", "country_id": 101, "elapsed_seconds": 15},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["guess"] == "Germany"
        assert data["answer"] is False
        assert data["distance_km"] is not None
        assert data["distance_km"] > 0


@pytest.mark.anyio
async def test_question_deducts_turn(client, mock_auth):
    """Asking a valid question increments questions_asked and decrements remaining_questions."""
    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.continent = ContinentCode.EUROPE
    mock_day.country_id = 100
    mock_day.date = date(2026, 9, 22)

    target_c = Country(id=100, name="Poland", official_name="Republic of Poland", md_file="")

    mock_state = MagicMock()
    mock_state.id = 1
    mock_state.user_id = 42
    mock_state.day_id = 1
    mock_state.remaining_questions = 8
    mock_state.remaining_guesses = 3
    mock_state.questions_asked = 0
    mock_state.guesses_made = 0
    mock_state.is_game_over = False
    mock_state.won = False
    mock_state.points = 0

    mock_q = ContinentalQuestion(
        id=55,
        user_id=42,
        day_id=1,
        original_question="Is the country in Europe?",
        question="Is the country located in Europe?",
        valid=True,
        answer=True,
        explanation="Poland is located in Central Europe.",
        context="local_kb:continent",
        asked_at=datetime.now(),
    )

    with patch(
        "db.repositories.continental.ContinentalDayRepository.get_today_day",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.country.CountryRepository.get",
        new_callable=AsyncMock,
        return_value=target_c,
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.get_state",
        new_callable=AsyncMock,
        return_value=mock_state,
    ), patch(
        "db.repositories.continental.ContinentalQuestionRepository.create_question",
        new_callable=AsyncMock,
        return_value=mock_q,
    ), patch(
        "continental.gutils.analyze_and_answer_locally",
        new_callable=AsyncMock,
        return_value=(mock_q, None),
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.update_state",
        new_callable=AsyncMock,
        return_value=mock_state,
    ):
        res = await client.post(
            "/continental/europe/question",
            json={"question": "Is the country in Europe?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["answer"] is True
        assert mock_state.questions_asked == 1
        assert mock_state.remaining_questions == 7


@pytest.mark.anyio
async def test_guest_sync_endpoint(client, mock_auth):
    """Guest sync claims questions, persists guesses, and updates state."""
    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.continent = ContinentCode.EUROPE
    mock_day.country_id = 100
    mock_day.date = date(2026, 9, 22)

    target_c = Country(id=100, name="Poland", official_name="Republic of Poland", md_file="")

    mock_state = MagicMock()
    mock_state.id = 1
    mock_state.user_id = 42
    mock_state.day_id = 1
    mock_state.remaining_questions = 8
    mock_state.remaining_guesses = 3
    mock_state.questions_asked = 0
    mock_state.guesses_made = 0
    mock_state.is_game_over = False
    mock_state.won = False
    mock_state.points = 0

    with patch(
        "db.repositories.continental.ContinentalDayRepository.get_day_by_date",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.continental.ContinentalDayRepository.get_today_day",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.country.CountryRepository.get",
        new_callable=AsyncMock,
        return_value=target_c,
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.get_state",
        new_callable=AsyncMock,
        return_value=mock_state,
    ), patch(
        "db.repositories.continental.ContinentalGuessRepository.add_guess",
        new_callable=AsyncMock,
    ), patch(
        "db.repositories.continental.ContinentalQuestionRepository.claim_guest_questions",
        new_callable=AsyncMock,
    ), patch(
        "db.repositories.continental.ContinentalQuestionRepository.get_user_questions",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "db.repositories.continental.ContinentalGuessRepository.get_user_guesses",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.update_state",
        new_callable=AsyncMock,
        return_value=mock_state,
    ):
        res = await client.post(
            "/continental/europe/sync",
            json={
                "date": "2026-09-22",
                "state": {
                    "remaining_questions": 6,
                    "remaining_guesses": 2,
                    "questions_asked": 2,
                    "guesses_made": 1,
                    "is_game_over": False,
                    "won": False,
                },
                "questions": [10, 11],
                "guesses": [{"guess": "Germany", "country_id": 101, "elapsed_seconds": 20}],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["date"] == "2026-09-22"


@pytest.mark.anyio
async def test_guest_sync_rejects_unearned_terminal_win(client, mock_auth):
    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.continent = ContinentCode.EUROPE
    mock_day.country_id = 100

    mock_state = MagicMock()
    mock_state.questions_asked = 0
    mock_state.guesses_made = 0

    with patch(
        "db.repositories.continental.ContinentalDayRepository.get_day_by_date",
        new_callable=AsyncMock,
        return_value=mock_day,
    ), patch(
        "db.repositories.continental.ContinentalStateRepository.get_state",
        new_callable=AsyncMock,
        return_value=mock_state,
    ), patch(
        "db.repositories.user.UserRepository.update_points",
        new_callable=AsyncMock,
    ) as update_points, patch(
        "db.repositories.continental.ContinentalStateRepository.update_state",
        new_callable=AsyncMock,
    ) as update_state:
        response = await client.post(
            "/continental/europe/sync",
            json={
                "date": "2026-09-22",
                "state": {
                    "remaining_questions": 8,
                    "remaining_guesses": 3,
                    "questions_asked": 0,
                    "guesses_made": 0,
                    "is_game_over": True,
                    "won": True,
                },
                "questions": [],
                "guesses": [],
            },
        )

    assert response.status_code == 400
    update_points.assert_not_awaited()
    update_state.assert_not_awaited()

@pytest.mark.anyio
async def test_scheduler_anti_collision():
    """Verify daily rotation scheduler never picks the same country twice on the same day."""
    from continental.scheduler import generate_continental_days

    added_days = []

    class FakeSession:
        def __init__(self):
            self.added = []

        async def execute(self, stmt):
            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = []
            return mock_res

        def add(self, obj):
            self.added.append(obj)
            added_days.append(obj)

        async def commit(self):
            pass

    fake_session = FakeSession()

    with patch("continental.scheduler.get_continent_country_ids", new_callable=AsyncMock) as mock_ids:
        # Russia (144) is candidate in Europe and Asia
        mock_ids.side_effect = lambda continent, session: (
            [144, 2, 3] if continent == ContinentCode.EUROPE else
            [144, 4, 5] if continent == ContinentCode.ASIA else
            [6, 7] if continent == ContinentCode.AFRICA else
            [8, 9]
        )

        await generate_continental_days(fake_session, days_ahead=1)

        # Group by date and check that all country_ids on the same date are distinct
        by_date = {}
        for d in added_days:
            by_date.setdefault(d.date, []).append(d.country_id)

        for d_date, c_ids in by_date.items():
            assert len(c_ids) == len(set(c_ids)), f"Duplicate country on date {d_date}: {c_ids}"
