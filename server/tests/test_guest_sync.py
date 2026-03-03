import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date, datetime
from db.models import User, CountrydleDay, CountrydleState

from app import app
from users.utils import get_current_user

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    return user

@pytest.fixture
def override_get_current_user(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def mock_day():
    day = MagicMock(spec=CountrydleDay)
    day.id = 10
    day.country_id = 100
    day.date = date(2023, 1, 1)
    return day

@pytest.mark.anyio
async def test_sync_guest_data_success(async_client: AsyncClient, mock_user, mock_day, override_get_current_user):
    # Mock Repository methods
    with (
        patch("db.repositories.countrydle.CountrydleRepository.get_day_country_by_date", new_callable=AsyncMock) as mock_get_day,
        patch("db.repositories.countrydle.CountrydleStateRepository.get_state", new_callable=AsyncMock) as mock_get_state,
        patch("db.repositories.countrydle.CountrydleStateRepository.update_countrydle_state", new_callable=AsyncMock) as mock_update_state,
        patch("db.repositories.guess.CountrydleGuessRepository.add_guess", new_callable=AsyncMock) as mock_add_guess,
        patch("db.repositories.countrydle.CountrydleStateRepository.calc_points", new_callable=AsyncMock) as mock_calc_points,
        patch("db.repositories.user.UserRepository.update_points", new_callable=AsyncMock) as mock_update_points,
        patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute,
        patch("countrydle.get_state", new_callable=AsyncMock) as mock_get_final_state
    ):
        mock_get_day.return_value = mock_day
        
        # Initial state (no progress)
        initial_state = MagicMock(spec=CountrydleState)
        initial_state.questions_asked = 0
        initial_state.guesses_made = 0
        initial_state.won = False
        initial_state.is_game_over = False
        mock_get_state.return_value = initial_state
        
        mock_calc_points.return_value = 500
        
        # Final state response mock
        from schemas.countrydle import CountrydleStateResponse, CountrydleStateSchema
        mock_get_final_state.return_value = CountrydleStateResponse(
            user=None, # In reality it would be the user, but for the mock it just needs to match schema
            date="2023-01-01",
            state=CountrydleStateSchema(
                remaining_questions=8,
                remaining_guesses=2,
                questions_asked=2,
                guesses_made=1,
                is_game_over=True,
                won=True
            ),
            questions=[],
            guesses=[]
        )

        sync_payload = {
            "date": "2023-01-01",
            "state": {
                "remaining_questions": 8,
                "remaining_guesses": 2,
                "questions_asked": 2,
                "guesses_made": 1,
                "is_game_over": True,
                "won": True
            },
            "questions": [1, 2],
            "guesses": [
                {"guess": "Poland", "country_id": 100}
            ]
        }

        response = await async_client.post("/countrydle/sync", json=sync_payload)
        
        assert response.status_code == 200
        
        # Verify state was updated
        assert initial_state.questions_asked == 2
        assert initial_state.guesses_made == 1
        assert initial_state.won is True
        assert initial_state.is_game_over is True
        assert initial_state.points == 500
        
        # Verify repository calls
        mock_get_day.assert_called_once_with(date(2023, 1, 1))
        mock_update_state.assert_called_once_with(initial_state)
        mock_add_guess.assert_called_once()
        mock_update_points.assert_called_once()

@pytest.mark.anyio
async def test_sync_guest_data_already_has_progress(async_client: AsyncClient, mock_user, mock_day, override_get_current_user):
    with (
        patch("db.repositories.countrydle.CountrydleRepository.get_day_country_by_date", new_callable=AsyncMock) as mock_get_day,
        patch("db.repositories.countrydle.CountrydleStateRepository.get_state", new_callable=AsyncMock) as mock_get_state,
        patch("countrydle.get_state", new_callable=AsyncMock) as mock_get_final_state
    ):
        mock_get_day.return_value = mock_day
        
        # State with existing progress
        existing_state = MagicMock(spec=CountrydleState)
        existing_state.questions_asked = 1
        existing_state.guesses_made = 0
        mock_get_state.return_value = existing_state
        
        from schemas.countrydle import CountrydleStateResponse, CountrydleStateSchema
        mock_get_final_state.return_value = CountrydleStateResponse(
            user=None,
            date="2023-01-01",
            state=CountrydleStateSchema(
                remaining_questions=9,
                remaining_guesses=3,
                questions_asked=1,
                guesses_made=0,
                is_game_over=False,
                won=False
            ),
            questions=[],
            guesses=[]
        )

        sync_payload = {
            "date": "2023-01-01",
            "state": {
                "remaining_questions": 5,
                "remaining_guesses": 3,
                "questions_asked": 5,
                "guesses_made": 0,
                "is_game_over": False,
                "won": False
            },
            "questions": [1, 2, 3, 4, 5],
            "guesses": []
        }

        response = await async_client.post("/countrydle/sync", json=sync_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["questions_asked"] == 1 # Should return existing progress, not synced one


@pytest.mark.anyio
async def test_sync_guest_data_invalid_date(async_client: AsyncClient, mock_user, override_get_current_user):
    sync_payload = {
        "date": "invalid-date",
        "state": {
            "remaining_questions": 10,
            "remaining_guesses": 3,
            "questions_asked": 0,
            "guesses_made": 0,
            "is_game_over": False,
            "won": False
        },
        "questions": [],
        "guesses": []
    }
    response = await async_client.post("/countrydle/sync", json=sync_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid date format. Use YYYY-MM-DD."

