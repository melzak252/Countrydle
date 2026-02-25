import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from db.models import User
from users.utils import get_current_or_guest_user
from app import app


@pytest.fixture
async def mock_user_override():
    async def mock_get_current_user():
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "test_user"
        user.email = "test@example.com"
        user.verified = True
        return user

    app.dependency_overrides[get_current_or_guest_user] = mock_get_current_user
    yield
    app.dependency_overrides = {}


@pytest.mark.anyio
async def test_us_statedle_state(async_client, mock_user_override):
    with (
        patch(
            "db.repositories.us_statedle.USStatedleDayRepository.get_today_us_state",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.us_statedle.USStatedleStateRepository.get_state",
            new_callable=AsyncMock,
        ) as mock_get_state,
        patch(
            "db.repositories.us_statedle.USStatedleGuessRepository.get_user_day_guesses",
            new_callable=AsyncMock,
        ) as mock_get_guesses,
        patch(
            "db.repositories.us_statedle.USStatedleQuestionRepository.get_user_day_questions",
            new_callable=AsyncMock,
        ) as mock_get_questions,
    ):
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.us_state_id = 10
        mock_day.date = "2023-01-01"
        mock_get_today.return_value = mock_day

        # Mock State
        mock_state = MagicMock()
        mock_state.id = 1
        mock_state.user_id = 1
        mock_state.day_id = 1
        mock_state.remaining_questions = 10
        mock_state.remaining_guesses = 3
        mock_state.questions_asked = 0
        mock_state.guesses_made = 0
        mock_state.is_game_over = False
        mock_state.won = False
        mock_state.points = 0
        mock_get_state.return_value = mock_state

        mock_get_guesses.return_value = []
        mock_get_questions.return_value = []

        response = await async_client.get("/us_statedle/state")
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["remaining_questions"] == 10
        assert data["state"]["remaining_guesses"] == 3


@pytest.mark.anyio
async def test_wojewodztwodle_state(async_client, mock_user_override):
    with (
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleDayRepository.get_today_wojewodztwo",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleStateRepository.get_state",
            new_callable=AsyncMock,
        ) as mock_get_state,
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleGuessRepository.get_user_day_guesses",
            new_callable=AsyncMock,
        ) as mock_get_guesses,
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleQuestionRepository.get_user_day_questions",
            new_callable=AsyncMock,
        ) as mock_get_questions,
    ):
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.wojewodztwo_id = 5
        mock_day.date = "2023-01-01"
        mock_get_today.return_value = mock_day

        # Mock State
        mock_state = MagicMock()
        mock_state.id = 1
        mock_state.user_id = 1
        mock_state.day_id = 1
        mock_state.remaining_questions = 10
        mock_state.remaining_guesses = 3
        mock_state.questions_asked = 0
        mock_state.guesses_made = 0
        mock_state.is_game_over = False
        mock_state.won = False
        mock_state.points = 0
        mock_get_state.return_value = mock_state

        mock_get_guesses.return_value = []
        mock_get_questions.return_value = []

        response = await async_client.get("/wojewodztwodle/state")
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["remaining_questions"] == 10
        assert data["state"]["remaining_guesses"] == 3


@pytest.mark.anyio
async def test_us_statedle_guess_correct(async_client, mock_user_override):
    with (
        patch(
            "db.repositories.us_statedle.USStatedleDayRepository.get_today_us_state",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.us_statedle.USStatedleStateRepository.get_state",
            new_callable=AsyncMock,
        ) as mock_get_state,
        patch(
            "db.repositories.us_statedle.USStatedleGuessRepository.add_guess",
            new_callable=AsyncMock,
        ) as mock_add_guess,
        patch(
            "db.repositories.us_statedle.USStatedleStateRepository.update_state",
            new_callable=AsyncMock,
        ) as mock_update_state,
    ):
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.us_state_id = 10
        mock_get_today.return_value = mock_day

        # Mock State
        mock_state = MagicMock()
        mock_state.remaining_guesses = 3
        mock_state.remaining_questions = 10
        mock_state.guesses_made = 0
        mock_state.won = False
        mock_state.is_game_over = False
        mock_get_state.return_value = mock_state

        # Mock Guess Result
        mock_guess_result = MagicMock()
        mock_guess_result.id = 1
        mock_guess_result.guess = "California"
        mock_guess_result.us_state_id = 10
        mock_guess_result.answer = True
        from datetime import datetime

        mock_guess_result.guessed_at = datetime.now()
        mock_add_guess.return_value = mock_guess_result

        guess_data = {"guess": "California", "us_state_id": 10}

        response = await async_client.post("/us_statedle/guess", json=guess_data)
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] is True
        assert mock_update_state.called


@pytest.mark.anyio
async def test_wojewodztwodle_guess_correct(async_client, mock_user_override):
    with (
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleDayRepository.get_today_wojewodztwo",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleStateRepository.get_state",
            new_callable=AsyncMock,
        ) as mock_get_state,
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleGuessRepository.add_guess",
            new_callable=AsyncMock,
        ) as mock_add_guess,
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleStateRepository.update_state",
            new_callable=AsyncMock,
        ) as mock_update_state,
    ):
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.wojewodztwo_id = 5
        mock_get_today.return_value = mock_day

        # Mock State
        mock_state = MagicMock()
        mock_state.remaining_guesses = 3
        mock_state.remaining_questions = 10
        mock_state.guesses_made = 0
        mock_state.won = False
        mock_state.is_game_over = False
        mock_get_state.return_value = mock_state

        # Mock Guess Result
        mock_guess_result = MagicMock()
        mock_guess_result.id = 1
        mock_guess_result.guess = "Małopolskie"
        mock_guess_result.wojewodztwo_id = 5
        mock_guess_result.answer = True
        from datetime import datetime

        mock_guess_result.guessed_at = datetime.now()
        mock_add_guess.return_value = mock_guess_result

        guess_data = {"guess": "Małopolskie", "wojewodztwo_id": 5}

        response = await async_client.post("/wojewodztwodle/guess", json=guess_data)
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] is True
        assert mock_update_state.called
