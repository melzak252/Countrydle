import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.anyio
async def test_countrydle_question_survives_unexpected_crash(async_client: AsyncClient):
    with patch(
        "countrydle.gutils.analyze_and_answer_locally",
        side_effect=RuntimeError("Simulated LLM network timeout"),
    ):
        response = await async_client.post(
            "/countrydle/question",
            json={"question": "Does it border Poland?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["answer"] is None
        assert "Could not verify" in data["explanation"]


@pytest.mark.anyio
async def test_us_statedle_question_survives_unexpected_crash(async_client: AsyncClient):
    with (
        patch(
            "db.repositories.us_statedle.USStatedleDayRepository.get_today_us_state",
            new_callable=AsyncMock,
            return_value=MagicMock(id=1, us_state_id=1),
        ),
        patch(
            "us_statedle.uutils.analyze_and_answer_locally",
            side_effect=Exception("Simulated SQLite corruption"),
        ),
    ):
        response = await async_client.post(
            "/us_statedle/question",
            json={"question": "Does it border Utah?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["answer"] is None
        assert "Could not verify" in data["explanation"]


@pytest.mark.anyio
async def test_wojewodztwodle_question_survives_unexpected_crash(async_client: AsyncClient):
    with (
        patch(
            "db.repositories.wojewodztwodle.WojewodztwodleDayRepository.get_today_wojewodztwo",
            new_callable=AsyncMock,
            return_value=MagicMock(id=1, wojewodztwo_id=1),
        ),
        patch(
            "wojewodztwodle.wutils.analyze_and_answer_locally",
            side_effect=Exception("Simulated Qdrant failure"),
        ),
    ):
        response = await async_client.post(
            "/wojewodztwodle/question",
            json={"question": "Czy to województwo ma dostęp do morza?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["answer"] is None


@pytest.mark.anyio
async def test_powiatdle_question_survives_unexpected_crash(async_client: AsyncClient):
    with (
        patch(
            "db.repositories.powiatdle.PowiatdleDayRepository.get_today_powiat",
            new_callable=AsyncMock,
            return_value=MagicMock(id=1, powiat_id=1),
        ),
        patch(
            "powiatdle.putils.analyze_and_answer_locally",
            side_effect=Exception("Simulated failure"),
        ),
    ):
        response = await async_client.post(
            "/powiatdle/question",
            json={"question": "Czy ma tablice KR?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["answer"] is None
