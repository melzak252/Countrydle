import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date

@pytest.mark.anyio
async def test_guest_get_state(async_client: AsyncClient):
    async_client.cookies.clear()
    with patch(
        "db.repositories.countrydle.CountrydleRepository.get_today_country",
        new_callable=AsyncMock,
    ) as mock_get_today:
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
        mock_day.date = date(2023, 1, 1)
        mock_get_today.return_value = mock_day

        response = await async_client.get("/countrydle/state")
        assert response.status_code == 200
        data = response.json()
        
        assert data["user"] is None
        assert data["date"] == "2023-01-01"
        assert data["state"]["remaining_questions"] == 10
        assert data["state"]["remaining_guesses"] == 3
        assert data["questions"] == []
        assert data["guesses"] == []
        assert data["country"] is None

@pytest.mark.anyio
async def test_guest_make_guess(async_client: AsyncClient):
    async_client.cookies.clear()
    with patch(
        "db.repositories.countrydle.CountrydleRepository.get_today_country",
        new_callable=AsyncMock,
    ) as mock_get_today:
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
        mock_day.date = date(2023, 1, 1)
        mock_get_today.return_value = mock_day

        guess_data = {
            "guess": "Poland",
            "country_id": 100,
        }
        
        response = await async_client.post("/countrydle/guess", json=guess_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["guess"] == "Poland"
        assert data["country_id"] == 100
        assert data["answer"] is True
        assert "guessed_at" in data

@pytest.mark.anyio
async def test_guest_ask_question(async_client: AsyncClient):
    async_client.cookies.clear()
    with (
        patch(
            "db.repositories.countrydle.CountrydleRepository.get_today_country",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "countrydle.utils.enhance_question", new_callable=AsyncMock
        ) as mock_enhance,
        patch("countrydle.utils.ask_question", new_callable=AsyncMock) as mock_ask,
        patch(
            "countrydle.add_question_to_qdrant", new_callable=AsyncMock
        ) as mock_add_qdrant,
        patch(
            "db.repositories.question.CountrydleQuestionsRepository.create_question",
            new_callable=AsyncMock,
        ) as mock_create_question,
    ):
        # Mock Day
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
        mock_day.date = date(2023, 1, 1)
        mock_get_today.return_value = mock_day

        # Mock Enhance
        mock_enhance.return_value.valid = True
        mock_enhance.return_value.original_question = "Is it in Europe?"
        mock_enhance.return_value.question = "Is the country located in Europe?"
        mock_enhance.return_value.explanation = "Explanation"

        # Mock Ask
        from schemas.countrydle import QuestionCreate
        mock_q_create = QuestionCreate(
            original_question="Is it in Europe?",
            question="Is the country located in Europe?",
            valid=True,
            explanation="Yes",
            answer=True,
            user_id=None,
            day_id=1,
            context="Context",
        )
        mock_ask.return_value = (mock_q_create, [0.1] * 1536)

        # Mock DB Question
        from datetime import datetime
        mock_question_db_obj = MagicMock()
        mock_question_db_obj.id = 123
        mock_question_db_obj.original_question = "Is it in Europe?"
        mock_question_db_obj.question = "Is the country located in Europe?"
        mock_question_db_obj.valid = True
        mock_question_db_obj.answer = True
        mock_question_db_obj.user_id = None
        mock_question_db_obj.day_id = 1
        mock_question_db_obj.asked_at = datetime.now()
        mock_question_db_obj.explanation = "Explanation"
        mock_create_question.return_value = mock_question_db_obj

        question_data = {"question": "Is it in Europe?"}
        response = await async_client.post("/countrydle/question", json=question_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] is None
        assert data["answer"] is True
