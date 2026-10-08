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
async def test_guest_reveal_rejected_before_game_over(async_client: AsyncClient):
    async_client.cookies.clear()
    with patch(
        "db.repositories.countrydle.CountrydleRepository.get_today_country",
        new_callable=AsyncMock,
    ) as mock_get_today:
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
        mock_get_today.return_value = mock_day

        response = await async_client.get("/countrydle/reveal")
        assert response.status_code == 400
        assert "Cannot reveal country before game is over" in response.json()["detail"]


@pytest.mark.anyio
async def test_guest_reveal_allowed_after_game_over(async_client: AsyncClient):
    async_client.cookies.clear()
    with (
        patch(
            "db.repositories.countrydle.CountrydleRepository.get_today_country",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.country.CountryRepository.get",
            new_callable=AsyncMock,
        ) as mock_get_country,
    ):
        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 100
        mock_get_today.return_value = mock_day

        mock_country = MagicMock()
        mock_country.id = 100
        mock_country.name = "Poland"
        mock_country.official_name = "Republic of Poland"
        mock_get_country.return_value = mock_country

        # Make 3 incorrect guesses to reach game over
        for _ in range(3):
            guess_res = await async_client.post(
                "/countrydle/guess",
                json={"guess": "Germany", "country_id": 99},
            )
            assert guess_res.status_code == 200

        # Now reveal must succeed
        reveal_res = await async_client.get("/countrydle/reveal")
        assert reveal_res.status_code == 200
        data = reveal_res.json()
        assert data["id"] == 100
        assert data["name"] == "Poland"
