import pytest
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
    long_question = "a" * 101
    question_data = {"question": long_question}
    response = await auth_client.post("/countrydle/question", json=question_data)
    assert response.status_code == 422  # Unprocessable Entity for validation error


@pytest.mark.anyio
async def test_ask_direct_country_question_correct_converts_to_winning_guess(async_client):
    from app import app
    from db.models import Country, CountrydleDay, CountrydleState, User
    from users.utils import get_current_or_guest_user
    from unittest.mock import MagicMock, patch, AsyncMock

    user = MagicMock(spec=User)
    user.id = 42
    user.is_authenticated = True

    async def mock_user():
        return user

    app.dependency_overrides[get_current_or_guest_user] = mock_user

    try:
        mock_day = MagicMock()
        mock_day.id = 100
        mock_day.country_id = 1
        mock_day.date = "2026-10-12"

        target_country = MagicMock(spec=Country)
        target_country.id = 1
        target_country.name = "Poland"
        target_country.official_name = "Republic of Poland"
        mock_day.country = target_country

        mock_state = MagicMock(spec=CountrydleState)
        mock_state.id = 1
        mock_state.user_id = 42
        mock_state.day_id = 100
        mock_state.remaining_questions = 10
        mock_state.remaining_guesses = 3
        mock_state.questions_asked = 0
        mock_state.guesses_made = 0
        mock_state.is_game_over = False
        mock_state.won = False
        mock_state.points = 0

        with (
            patch("countrydle.CountrydleRepository.get_today_country", new_callable=AsyncMock) as m_today,
            patch("countrydle.check_question_available", new_callable=AsyncMock),
            patch("countrydle.CountryRepository.get", new_callable=AsyncMock) as m_country,
            patch("countrydle.CountryRepository.validate_guess", new_callable=AsyncMock),
            patch("countrydle.CountrydleStateRepository.get_player_countrydle_state", new_callable=AsyncMock) as m_state,
            patch("countrydle.CountrydleGuessRepository.add_guess", new_callable=AsyncMock) as m_add_guess,
            patch("countrydle.CountrydleStateRepository.guess_made", new_callable=AsyncMock) as m_guess_made,
            patch("countrydle.CountrydleQuestionsRepository.create_question", new_callable=AsyncMock) as m_add_q,
            patch("countrydle.consume_question", new_callable=AsyncMock) as m_consume,
        ):
            m_today.return_value = mock_day
            m_country.return_value = target_country
            m_state.return_value = mock_state

            saved_guess = MagicMock()
            saved_guess.id = 1
            saved_guess.guess = "Poland"
            saved_guess.country_id = 1
            saved_guess.answer = True
            saved_guess.guessed_at = None
            m_add_guess.return_value = saved_guess

            saved_q = MagicMock()
            saved_q.id = 99
            saved_q.original_question = "Is it Poland?"
            saved_q.question = "Is the country Poland?"
            saved_q.valid = True
            saved_q.answer = True
            saved_q.clarification = "The country is Poland."
            saved_q.user_id = 42
            saved_q.day_id = 100
            saved_q.asked_at = None
            saved_q.explanation = "Poland is the target country."
            saved_q.fact_provenance = []
            m_add_q.return_value = saved_q

            response = await async_client.post("/countrydle/question", json={"question": "Is it Poland?"})
            assert response.status_code == 200
            data = response.json()

            # Must NOT consume question turn
            m_consume.assert_not_called()

            # Must execute guess
            m_add_guess.assert_called_once()
            m_guess_made.assert_called_once()

            # auto_guess must be present and winning
            assert "auto_guess" in data
            assert data["auto_guess"] is not None
            assert data["auto_guess"]["answer"] is True
            assert data["auto_guess"]["country_id"] == 1
    finally:
        app.dependency_overrides = {}


@pytest.mark.anyio
async def test_ask_direct_country_question_incorrect_consumes_question_not_guess(async_client):
    from app import app
    from db.models import Country, CountrydleDay, CountrydleState, User
    from users.utils import get_current_or_guest_user
    from unittest.mock import MagicMock, patch, AsyncMock

    user = MagicMock(spec=User)
    user.id = 42
    user.is_authenticated = True

    async def mock_user():
        return user

    app.dependency_overrides[get_current_or_guest_user] = mock_user

    try:
        mock_day = MagicMock()
        mock_day.id = 100
        mock_day.country_id = 1
        mock_day.date = "2026-10-12"

        target_country = MagicMock(spec=Country)
        target_country.id = 1
        target_country.name = "Poland"
        mock_day.country = target_country

        mock_state = MagicMock(spec=CountrydleState)
        mock_state.id = 1
        mock_state.user_id = 42
        mock_state.day_id = 100
        mock_state.remaining_questions = 10
        mock_state.remaining_guesses = 3
        mock_state.questions_asked = 0
        mock_state.guesses_made = 0
        mock_state.is_game_over = False
        mock_state.won = False

        with (
            patch("countrydle.CountrydleRepository.get_today_country", new_callable=AsyncMock) as m_today,
            patch("countrydle.check_question_available", new_callable=AsyncMock),
            patch("countrydle.CountryRepository.get", new_callable=AsyncMock) as m_country,
            patch("countrydle.CountryRepository.validate_guess", new_callable=AsyncMock),
            patch("countrydle.CountrydleStateRepository.get_player_countrydle_state", new_callable=AsyncMock) as m_state,
            patch("countrydle.CountrydleGuessRepository.add_guess", new_callable=AsyncMock) as m_add_guess,
            patch("countrydle.CountrydleStateRepository.guess_made", new_callable=AsyncMock) as m_guess_made,
            patch("countrydle.CountrydleQuestionsRepository.create_question", new_callable=AsyncMock) as m_add_q,
            patch("countrydle.consume_question", new_callable=AsyncMock) as m_consume,
        ):
            m_today.return_value = mock_day
            m_country.return_value = target_country
            m_state.return_value = mock_state

            saved_q = MagicMock()
            saved_q.id = 101
            saved_q.original_question = "Is it France?"
            saved_q.question = "Is the country France?"
            saved_q.valid = True
            saved_q.answer = False
            saved_q.clarification = "The country is not France."
            saved_q.user_id = 42
            saved_q.day_id = 100
            saved_q.asked_at = None
            saved_q.explanation = "Poland is the target country."
            saved_q.fact_provenance = []
            m_add_q.return_value = saved_q

            response = await async_client.post("/countrydle/question", json={"question": "Is it France?"})
            assert response.status_code == 200
            data = response.json()

            # For incorrect question: MUST consume question turn!
            m_consume.assert_called_once()

            # Must NOT execute guess!
            m_add_guess.assert_not_called()
            m_guess_made.assert_not_called()

            # auto_guess must NOT be present
            assert data.get("auto_guess") is None
            assert data["answer"] is False
    finally:
        app.dependency_overrides = {}
