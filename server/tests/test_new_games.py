import pytest
from sqlalchemy import select

from daily_clock import utc_today
from db.models.us_statedle import USStatedleDay, USStatedleGuess, USStatedleState
from db.models.wojewodztwodle import (
    WojewodztwodleDay,
    WojewodztwodleGuess,
    WojewodztwodleState,
)

pytestmark = pytest.mark.real_database


@pytest.fixture
async def regional_days(daily_api_db):
    async with daily_api_db() as session:
        session.add_all([
            USStatedleDay(id=1, us_state_id=1, date=utc_today()),
            WojewodztwodleDay(id=1, wojewodztwo_id=1, date=utc_today()),
        ])
        await session.commit()


@pytest.mark.anyio
async def test_us_statedle_state(auth_client, regional_days, daily_api_db):
    response = await auth_client.get("/us_statedle/state")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"]["remaining_questions"] == 8
    assert data["state"]["remaining_guesses"] == 3
    assert data["state"]["questions_asked"] == 0
    assert data["state"]["guesses_made"] == 0
    assert data["us_state"] is None
    assert data["guesses"] == []
    assert data["questions"] == []
    async with daily_api_db() as session:
        state = (await session.scalars(select(USStatedleState))).one()
        assert state.user_id == 1
        assert state.day_id == 1
        assert state.remaining_questions == 8
        assert state.remaining_guesses == 3


@pytest.mark.anyio
async def test_wojewodztwodle_state(auth_client, regional_days, daily_api_db):
    response = await auth_client.get("/wojewodztwodle/state")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"]["remaining_questions"] == 5
    assert data["state"]["remaining_guesses"] == 2
    assert data["state"]["questions_asked"] == 0
    assert data["state"]["guesses_made"] == 0
    assert data["wojewodztwo"] is None
    assert data["guesses"] == []
    assert data["questions"] == []
    async with daily_api_db() as session:
        state = (await session.scalars(select(WojewodztwodleState))).one()
        assert state.user_id == 1
        assert state.day_id == 1
        assert state.remaining_questions == 5
        assert state.remaining_guesses == 2


@pytest.mark.anyio
async def test_us_statedle_guess_correct(auth_client, regional_days, daily_api_db):
    response = await auth_client.post(
        "/us_statedle/guess", json={"guess": "California", "us_state_id": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is True
    async with daily_api_db() as session:
        state = (await session.scalars(select(USStatedleState))).one()
        guess = (await session.scalars(select(USStatedleGuess))).one()
        assert state.won is True
        assert state.is_game_over is True
        assert state.guesses_made == 1
        assert state.remaining_guesses == 2
        assert state.questions_asked == 0
        assert state.remaining_questions == 8
        assert state.points > 0
        assert guess.user_id == state.user_id == 1
        assert guess.day_id == state.day_id == 1
        assert guess.us_state_id == 1
        assert guess.answer is True
        assert guess.id == response.json()["id"]
    reloaded = await auth_client.get("/us_statedle/state")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["state"]["won"] is True
    assert reloaded.json()["us_state"]["name"] == "California"
    assert len(reloaded.json()["guesses"]) == 1


@pytest.mark.anyio
async def test_wojewodztwodle_guess_correct(auth_client, regional_days, daily_api_db):
    response = await auth_client.post(
        "/wojewodztwodle/guess", json={"guess": "Małopolskie", "wojewodztwo_id": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is True
    async with daily_api_db() as session:
        state = (await session.scalars(select(WojewodztwodleState))).one()
        guess = (await session.scalars(select(WojewodztwodleGuess))).one()
        assert state.won is True
        assert state.is_game_over is True
        assert state.guesses_made == 1
        assert state.remaining_guesses == 1
        assert state.questions_asked == 0
        assert state.remaining_questions == 5
        assert state.points > 0
        assert guess.user_id == state.user_id == 1
        assert guess.day_id == state.day_id == 1
        assert guess.wojewodztwo_id == 1
        assert guess.answer is True
        assert guess.id == response.json()["id"]
    reloaded = await auth_client.get("/wojewodztwodle/state")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["state"]["won"] is True
    assert reloaded.json()["wojewodztwo"]["nazwa"] == "Małopolskie"
    assert len(reloaded.json()["guesses"]) == 1
