import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date
from sqlalchemy import select

from app import app
from daily_clock import utc_today
from db.models import CountrydleDay, CountrydleGuess
from db.models.guest_participation import GuestParticipation
from utils.guest_session import GUEST_IDENTITY_COOKIE, create_guest_game_token

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

@pytest.mark.real_database
@pytest.mark.anyio
async def test_guest_reveal_rejected_before_game_over(daily_api_db):
    async with daily_api_db() as session:
        session.add(CountrydleDay(id=1, country_id=1, date=utc_today()))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        # Even a validly signed projection of a win is not durable participation.
        client.cookies.set("guest_countrydle", create_guest_game_token("countrydle", 1, 3, True, True))
        response = await client.get("/countrydle/reveal")
        assert response.status_code == 400
        assert "Cannot reveal country before game is over" in response.json()["detail"]
    async with daily_api_db() as session:
        assert list((await session.scalars(select(GuestParticipation))).all()) == []
        assert list((await session.scalars(select(CountrydleGuess))).all()) == []


@pytest.mark.real_database
@pytest.mark.anyio
async def test_guest_reveal_allowed_after_game_over(daily_api_db):
    async with daily_api_db() as session:
        session.add(CountrydleDay(id=1, country_id=1, date=utc_today()))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        accepted_ids = []
        for _ in range(3):
            guess_res = await client.post(
                "/countrydle/guess", json={"guess": "Germany", "country_id": 2},
            )
            assert guess_res.status_code == 200, guess_res.text
            assert guess_res.json()["answer"] is False
            accepted_ids.append(guess_res.json()["id"])

        identity_token = client.cookies.get(GUEST_IDENTITY_COOKIE)
        assert identity_token is not None
        client.cookies.clear()
        client.cookies.set(GUEST_IDENTITY_COOKIE, identity_token)
        # Reload and reveal must use durable terminal progress without a mode cookie.
        state_res = await client.get("/countrydle/state")
        assert state_res.status_code == 200, state_res.text
        assert state_res.json()["state"]["guesses_made"] == 3
        assert state_res.json()["state"]["remaining_guesses"] == 0
        assert state_res.json()["state"]["is_game_over"] is True
        assert state_res.json()["state"]["won"] is False
        assert [guess["id"] for guess in state_res.json()["guesses"]] == accepted_ids
        reveal_res = await client.get("/countrydle/reveal")
        assert reveal_res.status_code == 200, reveal_res.text
        assert reveal_res.json()["id"] == 1
        assert reveal_res.json()["name"] == "Poland"

    async with daily_api_db() as session:
        participation = (await session.scalars(select(GuestParticipation))).one()
        guesses = list((await session.scalars(select(CountrydleGuess).order_by(CountrydleGuess.id))).all())
        assert (participation.mode, participation.day_id, participation.guesses_made, participation.won) == (
            "countrydle", 1, 3, False,
        )
        assert [(guess.id, guess.guest_id, guess.user_id, guess.answer) for guess in guesses] == [
            (guess_id, participation.guest_id, None, False) for guess_id in accepted_ids
        ]
