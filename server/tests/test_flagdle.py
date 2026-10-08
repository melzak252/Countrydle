from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import select

from daily_clock import utc_today
from db.models.country import Country
from db.models.flagdle import FlagdleDay, FlagdleGuess
from db.models.guest_participation import GuestParticipation

from game_logic import calculate_flagdle_points
from flagdle.utils import (
    UNMASK_ORDER,
    evaluate_flag_clues,
    generate_asset_token,
    get_country_iso2,
    verify_asset_token,
)


@pytest.fixture
async def flag_day(daily_api_db):
    async with daily_api_db() as session:
        session.add_all([
            Country(id=143, name="Romania", official_name="Romania", md_file="Romania.md"),
            Country(id=34, name="Chad", official_name="Republic of Chad", md_file="Chad.md"),
        ])
        await session.flush()
        session.add(FlagdleDay(id=10, country_id=143, date=utc_today()))
        await session.commit()


def test_flagdle_points_calculation():
    """Verify Flagdle dynamic scoring curve."""
    # Loss gives 0
    assert calculate_flagdle_points(won=False, guesses_used=3) == 0

    # Win on 1st guess: base (500) + guess bonus (1500) = 2000 (no speed/streak)
    assert calculate_flagdle_points(won=True, guesses_used=1, elapsed_seconds=0, streak=0) == 2000

    # Win on 2nd guess: 500 + 1300 = 1800
    assert calculate_flagdle_points(won=True, guesses_used=2) == 1800

    # Win on 6th guess: 500 + 650 = 1150
    assert calculate_flagdle_points(won=True, guesses_used=6) == 1150

    # Win on 12th guess: 500 + 50 = 550
    assert calculate_flagdle_points(won=True, guesses_used=12) == 550

    # Streak bonus adds +50 per day up to 500
    score_streak_3 = calculate_flagdle_points(won=True, guesses_used=1, streak=3)
    assert score_streak_3 == 2000 + 150

    # Speed bonus gives bonus if elapsed < 180s
    score_fast = calculate_flagdle_points(won=True, guesses_used=1, elapsed_seconds=10)
    assert score_fast > 2000


def test_flagdle_asset_token_hmac():
    """Verify HMAC token generation and verification."""
    token = generate_asset_token(42)
    assert len(token) == 16
    assert verify_asset_token(42, token) is True
    assert verify_asset_token(43, token) is False
    assert verify_asset_token(42, "invalidtoken1234") is False


def test_flagdle_country_iso2():
    """Verify country name to ISO2 code resolution."""
    assert get_country_iso2("Poland") == "pl"
    assert get_country_iso2("France") == "fr"
    assert get_country_iso2("Germany") == "de"
    assert get_country_iso2("Palestine") == "ps"


def test_flagdle_clue_evaluation():
    """Verify color, symbol, and geo evaluation between countries."""
    # Romania (id 143) vs Chad (id 34)
    # Both share blue, red, yellow stripes, but are geographically distant (~3,492 km)
    clues = evaluate_flag_clues(target_country_id=143, guessed_country_id=34)

    assert "blue" in clues["matched_colors"]
    assert "red" in clues["matched_colors"]
    assert "yellow" in clues["matched_colors"]
    assert clues["missed_colors"] == []
    assert "stripes" in clues["matched_symbols"]
    assert clues["distance_km"] is not None
    assert 3400 <= clues["distance_km"] <= 3600
    assert clues["bearing_direction"] in ["N", "NNE"]
    assert clues["bearing_arrow"] == "↑"


def test_flagdle_clue_evaluation_missed_colors():
    """Verify evaluation when colors are missed."""
    # France (id 61: blue, white, red) vs Germany (id 65: black, red, yellow)
    clues = evaluate_flag_clues(target_country_id=61, guessed_country_id=65)
    assert "red" in clues["matched_colors"]
    assert "black" in clues["missed_colors"]
    assert "yellow" in clues["missed_colors"]


@pytest.mark.anyio
async def test_flagdle_countries_endpoint(async_client):
    """GET /flagdle/countries returns list of countries with iso2."""
    res = await async_client.get("/flagdle/countries")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "id" in first
    assert "name" in first
    assert "iso2" in first


@pytest.mark.real_database
@pytest.mark.anyio
async def test_flagdle_state_anti_cheat(daily_api_client, flag_day):
    """Active games expose neither the target nor its asset filename."""
    res = await daily_api_client.get("/flagdle/state")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["country"] is None
    assert data["state"]["is_game_over"] is False
    assert data["state"]["remaining_guesses"] == 12
    assert data["state"]["revealed_stage"] == 1
    assert "ro.svg" not in data["flag_asset_url"]
    assert "romania" not in data["flag_asset_url"].lower()
    assert "/flagdle/flag-asset?token=" in data["flag_asset_url"]


@pytest.mark.real_database
@pytest.mark.anyio
async def test_flagdle_guess_endpoint(daily_api_client, flag_day, daily_api_db):
    """A persisted guest guess returns visual clues and its first tile."""
    res = await daily_api_client.post(
        "/flagdle/guess", json={"country_id": 34, "guess": "Chad"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["answer"] is False
    assert data["guess"] == "Chad"
    assert "blue" in data["matched_colors"]
    assert "red" in data["matched_colors"]
    assert "yellow" in data["matched_colors"]
    assert data["distance_km"] is None
    assert data["bearing_direction"] is None
    assert data["revealed_tile"] == UNMASK_ORDER[0]
    async with daily_api_db() as session:
        participation = (await session.scalars(select(GuestParticipation))).one()
        guess = (await session.scalars(select(FlagdleGuess))).one()
        assert participation.guesses_made == 1
        assert participation.won is False
        assert participation.mode == "flagdle"
        assert guess.guest_id == participation.guest_id
        assert guess.user_id is None
        assert guess.id == data["id"]
        assert guess.revealed_tile == UNMASK_ORDER[0]
    reloaded = await daily_api_client.get("/flagdle/state")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["state"]["guesses_made"] == 1
    assert reloaded.json()["state"]["remaining_guesses"] == 11
    assert reloaded.json()["state"]["revealed_stage"] == 2
    assert reloaded.json()["guesses"][0]["id"] == data["id"]


@pytest.mark.real_database
@pytest.mark.anyio
async def test_flagdle_reveal_protection(daily_api_client, flag_day):
    """The target cannot be revealed before durable progress is terminal."""
    res = await daily_api_client.get("/flagdle/reveal")
    assert res.status_code == 400
    assert "Cannot reveal country before game is over" in res.json()["detail"]


@pytest.mark.real_database
@pytest.mark.anyio
async def test_flagdle_guess_correct_flow(daily_api_client, flag_day, daily_api_db):
    """A correct guest guess persists the win and reveals it on reload."""
    res = await daily_api_client.post(
        "/flagdle/guess", json={"country_id": 143, "guess": "Romania"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["answer"] is True
    assert data["guess"] == "Romania"
    assert data["distance_km"] == 0
    async with daily_api_db() as session:
        participation = (await session.scalars(select(GuestParticipation))).one()
        guess = (await session.scalars(select(FlagdleGuess))).one()
        assert participation.won is True
        assert participation.guesses_made == 1
        assert guess.guest_id == participation.guest_id
        assert guess.user_id is None
        assert guess.answer is True
        assert guess.id == data["id"]
    reloaded = await daily_api_client.get("/flagdle/state")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["state"]["won"] is True
    assert reloaded.json()["state"]["is_game_over"] is True
    assert reloaded.json()["state"]["revealed_stage"] == 12
    assert reloaded.json()["country"]["name"] == "Romania"
    assert len(reloaded.json()["guesses"]) == 1


@pytest.mark.anyio
async def test_flagdle_flag_asset_stream(async_client):
    """GET /flagdle/flag-asset with valid token returns SVG."""
    with (
        patch(
            "db.repositories.flagdle.FlagdleDayRepository.get_today_flag",
            new_callable=AsyncMock,
        ) as mock_get_today,
        patch(
            "db.repositories.country.CountryRepository.get",
            new_callable=AsyncMock,
        ) as mock_get_country,
    ):
        mock_country = MagicMock()
        mock_country.id = 61
        mock_country.name = "France"

        mock_day = MagicMock()
        mock_day.id = 55
        mock_day.country_id = 61
        mock_day.country = mock_country
        mock_day.date = date(2026, 9, 22)

        mock_get_today.return_value = mock_day
        mock_get_country.return_value = mock_country

        valid_token = generate_asset_token(55)
        res = await async_client.get(f"/flagdle/flag-asset?token={valid_token}")
        assert res.status_code == 200
        assert "image/svg+xml" in res.headers["content-type"]
        assert b"<svg" in res.content

        # Invalid token must be 403
        bad_res = await async_client.get("/flagdle/flag-asset?token=invalid_token")
        assert bad_res.status_code == 403

@pytest.mark.anyio
async def test_flagdle_history_endpoint(async_client):
    """GET /flagdle/history returns list of past flagdle days with country."""
    with patch(
        "db.repositories.flagdle.FlagdleDayRepository.get_history",
        new_callable=AsyncMock,
    ) as mock_get_history:
        mock_country = MagicMock()
        mock_country.id = 61
        mock_country.name = "France"
        mock_country.official_name = "French Republic"
        mock_country.md_file = "France.md"

        mock_day = MagicMock()
        mock_day.id = 55
        mock_day.country_id = 61
        mock_day.country = mock_country
        mock_day.date = date(2026, 9, 21)

        mock_get_history.return_value = [mock_day]

        res = await async_client.get("/flagdle/history")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["id"] == 55
        assert data[0]["date"] == "2026-09-21"
        assert data[0]["country"]["name"] == "France"


@pytest.mark.real_database
@pytest.mark.anyio
async def test_flagdle_named_facts_are_private_until_win_and_available_to_later_questions(daily_api_client, flag_day):
    active = await daily_api_client.post("/flagdle/question", json={"question": "Is it in Europe?"})
    assert active.status_code == 200, active.text
    assert active.json()["valid"] is True and active.json()["answer"] is True
    assert not active.json()["explanation"]

    win = await daily_api_client.post("/flagdle/guess", json={"country_id": 143, "guess": "Romania"})
    assert win.status_code == 200, win.text
    assert win.json()["answer"] is True

    later = await daily_api_client.post("/flagdle/question", json={"question": "Is it in Europe?"})
    assert later.status_code == 200, later.text
    assert later.json()["valid"] is True and later.json()["answer"] is True
    assert "Romania" in later.json()["explanation"]
    assert "Europe" in later.json()["explanation"]

    state = await daily_api_client.get("/flagdle/state")
    assert state.status_code == 200, state.text
    assert state.json()["state"]["is_game_over"] is True
    assert all("Romania" in question["explanation"] for question in state.json()["questions"])
