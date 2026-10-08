import pytest
from sqlalchemy import select

from daily_clock import utc_today
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.guess import CountrydleGuess


@pytest.fixture
async def country_day(daily_api_db):
    async with daily_api_db() as session:
        session.add(CountrydleDay(id=1, country_id=1, date=utc_today()))
        await session.commit()


@pytest.mark.anyio
async def test_get_countries(auth_client):
    response = await auth_client.get("/countrydle/countries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]


@pytest.mark.real_database
@pytest.mark.anyio
async def test_get_game_state(auth_client, country_day, daily_api_db):
    response = await auth_client.get("/countrydle/state")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"]["remaining_guesses"] == 3
    assert data["state"]["remaining_questions"] == 10
    assert data["state"]["guesses_made"] == 0
    assert data["state"]["questions_asked"] == 0
    assert data["state"]["is_game_over"] is False
    assert data["country"] is None
    assert data["guesses"] == []
    assert data["questions"] == []
    async with daily_api_db() as session:
        state = (await session.scalars(select(CountrydleState))).one()
        assert state.user_id == 1
        assert state.day_id == 1
        assert state.remaining_guesses == 3
        assert state.remaining_questions == 10


@pytest.mark.real_database
@pytest.mark.anyio
async def test_make_guess_correct(auth_client, country_day, daily_api_db):
    response = await auth_client.post(
        "/countrydle/guess", json={"guess": "Poland", "country_id": 1},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["answer"] is True
    assert data["distance_km"] == 0
    async with daily_api_db() as session:
        state = (await session.scalars(select(CountrydleState))).one()
        guess = (await session.scalars(select(CountrydleGuess))).one()
        assert guess.id == data["id"]
        assert guess.guess == "Poland"
        assert guess.answer is True
        assert guess.user_id == state.user_id == 1
        assert guess.day_id == state.day_id == 1
        assert state.won is True
        assert state.is_game_over is True
        assert state.guesses_made == 1
        assert state.remaining_guesses == 2
        assert state.questions_asked == 0
        assert state.remaining_questions == 10
        assert state.points > 0
    reloaded = await auth_client.get("/countrydle/state")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["state"]["won"] is True
    assert reloaded.json()["country"]["name"] == "Poland"
    assert len(reloaded.json()["guesses"]) == 1


@pytest.mark.anyio
async def test_ask_question_too_long(auth_client):
    long_question = "a" * 101
    question_data = {"question": long_question}
    response = await auth_client.post("/countrydle/question", json=question_data)
    assert response.status_code == 422  # Unprocessable Entity for validation error
