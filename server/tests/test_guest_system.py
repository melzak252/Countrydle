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


@pytest.mark.anyio
@pytest.mark.parametrize("mode,path", [
    ("countrydle", "/countrydle/state"),
    ("continental", "/continental/europe/state"),
    ("flagdle", "/flagdle/state"),
])
@pytest.mark.parametrize("completion", ["question_quota", "win", "guesses_exhausted", "cookie_only"])
async def test_guest_factual_history_requires_recorded_completion(mode, path, completion, monkeypatch):
    from datetime import datetime
    from importlib import import_module
    from types import SimpleNamespace
    from fastapi import FastAPI
    from httpx import ASGITransport
    from db import get_db
    from users.utils import get_current_or_guest_user
    from utils.guest_session import create_guest_game_token

    module = import_module(mode)
    maximum = 12 if mode == "flagdle" else 3
    terminal = completion in {"win", "guesses_exhausted"}
    participation = None if completion == "cookie_only" else SimpleNamespace(
        guesses_made=maximum if completion == "guesses_exhausted" else 0,
        questions_asked=10, won=completion == "win",
    )
    question = SimpleNamespace(
        id=7, original_question="Is it in Europe?",
        question="Is Poland, whose capital is Warsaw, in Europe?",
        valid=True, answer=True, user_id=None, day_id=1, asked_at=datetime.now(),
        explanation="Poland is in Europe; its capital is Warsaw.",
        fact_provenance=[], context="Private retrieved facts about Poland",
    )
    day = SimpleNamespace(
        id=1, country_id=100, date=date.today(),
        country=SimpleNamespace(id=100, name="Poland", official_name="Republic of Poland"),
    )
    repository_name, method = {
        "countrydle": ("CountrydleRepository", "get_today_country"),
        "continental": ("ContinentalDayRepository", "get_today_day"),
        "flagdle": ("FlagdleDayRepository", "get_today_flag"),
    }[mode]
    monkeypatch.setattr(getattr(module, repository_name), method, AsyncMock(return_value=day))
    monkeypatch.setattr(module.CountryRepository, "get", AsyncMock(return_value=day.country))
    monkeypatch.setattr(module, "get_guest_question_history", AsyncMock(return_value=(participation, [question])))
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # A stale/signed game cookie cannot replace recorded completion proof.
        client.cookies.set(f"guest_{mode}", create_guest_game_token(mode, 1, maximum, True, True))
        response = await client.get(path)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"]["is_game_over"] is terminal
    assert payload["questions"][0]["id"] == 7
    assert "context" not in payload["questions"][0]
    if terminal:
        assert "Poland" in payload["questions"][0]["explanation"]
        assert "Warsaw" in payload["questions"][0]["explanation"]
    else:
        assert payload["questions"][0]["question"] == question.original_question
        assert not payload["questions"][0]["explanation"]
        assert payload["questions"][0]["fact_provenance"] == []
        assert "Poland" not in response.text and "Warsaw" not in response.text
