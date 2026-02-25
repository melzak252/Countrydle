import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.anyio
async def test_get_countries(auth_client):
    response = await auth_client.get("/countrydle/countries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]


@pytest.mark.anyio
async def test_get_game_state(auth_client):
    from unittest.mock import MagicMock

    with (
        patch(
            "db.repositories.countrydle.CountrydleRepository.get_today_country",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.countrydle.CountrydleStateRepository.get_state",
            new_callable=AsyncMock,
        ) as mock_get_state,
        patch(
            "db.repositories.guess.CountrydleGuessRepository.get_user_day_guesses",
            new_callable=AsyncMock,
        ) as mock_get_guesses,
        patch(
            "db.repositories.question.CountrydleQuestionsRepository.get_user_day_questions",
            new_callable=AsyncMock,
        ) as mock_get_questions,
    ):
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
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

        response = await auth_client.get("/countrydle/state")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "remaining_guesses" in data["state"]


@pytest.mark.anyio
async def test_make_guess_correct(async_client):
    # Mock dependencies to test logic without DB
    with (
        patch(
            "db.repositories.countrydle.CountrydleRepository.get_today_country",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.countrydle.CountrydleStateRepository.get_player_countrydle_state",
            new_callable=AsyncMock,
        ) as mock_get_state,
        patch(
            "db.repositories.country.CountryRepository.get", new_callable=AsyncMock
        ) as mock_get_country,
        patch(
            "db.repositories.guess.CountrydleGuessRepository.add_guess",
            new_callable=AsyncMock,
        ) as mock_add_guess,
        patch(
            "db.repositories.countrydle.CountrydleStateRepository.guess_made",
            new_callable=AsyncMock,
        ) as mock_guess_made,
    ):
        # Setup mocks
        from unittest.mock import MagicMock

        # Mock DayCountry
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
        mock_get_today.return_value = mock_day

        # Mock State
        mock_state = MagicMock()
        mock_state.remaining_guesses = 3
        mock_state.remaining_questions = 10
        mock_state.is_game_over = False
        mock_state.won = False
        mock_get_state.return_value = mock_state

        # Mock Country
        mock_country = MagicMock()
        mock_country.id = 100
        mock_country.name = "Poland"
        mock_country.official_name = "Republic of Poland"
        mock_get_country.return_value = mock_country

        # Mock Guess Result
        mock_guess_result = MagicMock()
        mock_guess_result.id = 1
        mock_guess_result.guess = "Poland"
        mock_guess_result.answer = True
        mock_guess_result.guessed_at = "2023-01-01T12:00:00"
        mock_add_guess.return_value = mock_guess_result

    from app import app
    from users.utils import get_current_or_guest_user
    from db.models import User

    async def mock_get_current_user():
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "test_user"
        return user

    app.dependency_overrides[get_current_or_guest_user] = mock_get_current_user

    try:
        pass
    finally:
        app.dependency_overrides = {}


@pytest.mark.anyio
async def test_make_guess_correct_mocked(async_client):
    from app import app
    from users.utils import get_current_or_guest_user
    from db.models import User
    from unittest.mock import MagicMock

    # Override User Dependency
    async def mock_get_current_user():
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "test_user"
        user.email = "test@example.com"
        user.verified = True
        return user

    app.dependency_overrides[get_current_or_guest_user] = mock_get_current_user

    try:
        with (
            patch(
                "db.repositories.countrydle.CountrydleRepository.get_today_country",
                new_callable=AsyncMock,
            ) as mock_get_today,
            patch(
                "db.repositories.countrydle.CountrydleStateRepository.get_player_countrydle_state",
                new_callable=AsyncMock,
            ) as mock_get_state,
            patch(
                "db.repositories.country.CountryRepository.get", new_callable=AsyncMock
            ) as mock_get_country,
            patch(
                "db.repositories.guess.CountrydleGuessRepository.add_guess",
                new_callable=AsyncMock,
            ) as mock_add_guess,
            patch(
                "db.repositories.countrydle.CountrydleStateRepository.guess_made",
                new_callable=AsyncMock,
            ) as mock_guess_made,
        ):
            # Mock DayCountry
            mock_day = MagicMock()
            mock_day.id = 1
            mock_day.country_id = 100
            mock_get_today.return_value = mock_day

            # Mock State
            mock_state = MagicMock()
            mock_state.remaining_guesses = 3
            mock_state.remaining_questions = 10
            mock_state.is_game_over = False
            mock_state.won = False
            mock_get_state.return_value = mock_state

            # Mock Country
            mock_country = MagicMock()
            mock_country.id = 100
            mock_country.name = "Poland"
            mock_get_country.return_value = mock_country

            # Mock Guess Result
            mock_guess_result = MagicMock()
            mock_guess_result.id = 1
            mock_guess_result.guess = "Poland"
            mock_guess_result.answer = True
            mock_guess_result.guessed_at = "2023-01-01T12:00:00"
            mock_add_guess.return_value = mock_guess_result

            # Test Data
            guess_data = {
                "guess": "Poland",
                "country_id": 100,  # Correct ID
            }

            response = await async_client.post("/countrydle/guess", json=guess_data)

            assert response.status_code == 200
            data = response.json()
            assert data["answer"] is True

            # Verify add_guess was called with correct data
            args, _ = mock_add_guess.call_args
            guess_create_arg = args[0]
            assert guess_create_arg.country_id == 100
            assert guess_create_arg.answer is True

    finally:
        app.dependency_overrides = {}


@pytest.mark.anyio
async def test_ask_question_too_long(auth_client):
    long_question = "a" * 51
    question_data = {"question": long_question}
    response = await auth_client.post("/countrydle/question", json=question_data)
    assert response.status_code == 422  # Unprocessable Entity for validation error
    # Mocking the external dependencies for asking a question
    # We need to mock:
    # 1. gutils.enhance_question (LLM)
    # 2. gutils.ask_question (LLM + Qdrant)
    # 3. add_question_to_qdrant (Qdrant)

    with (
        patch(
            "countrydle.utils.enhance_question", new_callable=AsyncMock
        ) as mock_enhance,
        patch("countrydle.utils.ask_question", new_callable=AsyncMock) as mock_ask,
        patch(
            "countrydle.__init__.add_question_to_qdrant", new_callable=AsyncMock
        ) as mock_add_qdrant,
        patch(
            "db.repositories.question.CountrydleQuestionsRepository.create_question",
            new_callable=AsyncMock,
        ) as mock_create_question,
    ):
        # Setup mocks
        mock_enhance.return_value.valid = True
        mock_enhance.return_value.original_question = "Is it in Europe?"
        mock_enhance.return_value.question = "Is the country located in Europe?"
        mock_enhance.return_value.explanation = "Explanation"

        from schemas.countrydle import QuestionCreate, QuestionDisplay
        from datetime import datetime

        mock_q_create = QuestionCreate(
            original_question="Is it in Europe?",
            question="Is the country located in Europe?",
            valid=True,
            explanation="Yes",
            answer=True,
            user_id=1,
            day_id=1,  # This ID doesn't matter if we mock the create_question
            context="Context",
        )
        mock_ask.return_value = (mock_q_create, [0.1] * 1536)

        # Mock the create_question method return value
        from unittest.mock import MagicMock

        mock_question_db_obj = MagicMock()
        mock_question_db_obj.id = 123
        mock_question_db_obj.original_question = "Is it in Europe?"
        mock_question_db_obj.question = "Is the country located in Europe?"
        mock_question_db_obj.valid = True
        mock_question_db_obj.answer = True
        mock_question_db_obj.user_id = 1
        mock_question_db_obj.day_id = 1
        mock_question_db_obj.asked_at = datetime.now()
        mock_question_db_obj.explanation = "Explanation"

        mock_create_question.return_value = mock_question_db_obj

        question_data = {"question": "Is it in Europe?"}
        response = await auth_client.post("/countrydle/question", json=question_data)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["original_question"] == "Is it in Europe?"
