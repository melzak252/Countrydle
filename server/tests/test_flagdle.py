from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from game_logic import calculate_flagdle_points
from flagdle.utils import (
    UNMASK_ORDER,
    evaluate_flag_clues,
    generate_asset_token,
    get_country_iso2,
    verify_asset_token,
)


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


@pytest.mark.anyio
async def test_flagdle_state_anti_cheat(async_client):
    """Verify target country ID, name, and ISO2 are NEVER returned during active game."""
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
        mock_country.id = 58
        mock_country.name = "France"
        mock_country.official_name = "French Republic"

        mock_day = MagicMock()
        mock_day.id = 1
        mock_day.country_id = 58
        mock_day.country = mock_country
        mock_day.date = date(2026, 9, 22)

        mock_get_today.return_value = mock_day
        mock_get_country.return_value = mock_country

        res = await async_client.get("/flagdle/state")
        assert res.status_code == 200
        data = res.json()

        # Target country MUST NOT be exposed while game is in progress
        assert data["country"] is None
        assert data["state"]["is_game_over"] is False
        assert data["state"]["remaining_guesses"] == 12
        assert data["state"]["revealed_stage"] == 1

        # The flag asset URL must be an obfuscated proxy token URL, NOT revealing "fr.svg"
        assert "fr.svg" not in data["flag_asset_url"]
        assert "france" not in data["flag_asset_url"].lower()
        assert "/flagdle/flag-asset?token=" in data["flag_asset_url"]


@pytest.mark.anyio
async def test_flagdle_guess_endpoint(async_client):
    """POST /flagdle/guess returns feedback with clues and tile reveal."""
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
        # Target: Romania (id 143)
        mock_target = MagicMock()
        mock_target.id = 143
        mock_target.name = "Romania"
        mock_target.official_name = "Romania"

        # Guess: Chad (id 34)
        mock_chad = MagicMock()
        mock_chad.id = 34
        mock_chad.name = "Chad"
        mock_chad.official_name = "Republic of Chad"

        mock_day = MagicMock()
        mock_day.id = 10
        mock_day.country_id = 143
        mock_day.country = mock_target
        mock_day.date = date(2026, 9, 22)

        mock_get_today.return_value = mock_day

        async def mock_get(cid):
            if cid == 143:
                return mock_target
            if cid == 34:
                return mock_chad
            return None

        mock_get_country.side_effect = mock_get

        guess_payload = {"country_id": 34, "guess": "Chad"}
        res = await async_client.post("/flagdle/guess", json=guess_payload)
        assert res.status_code == 200
        data = res.json()

        assert data["answer"] is False
        assert data["guess"] == "Chad"
        assert "blue" in data["matched_colors"]
        assert "red" in data["matched_colors"]
        assert "yellow" in data["matched_colors"]
        assert data["distance_km"] is not None
        assert data["bearing_direction"] in ["N", "NNE"]
        assert data["revealed_tile"] == UNMASK_ORDER[0]


@pytest.mark.anyio
async def test_flagdle_reveal_protection(async_client):
    """GET /flagdle/reveal returns 400 when game is not over."""
    with (
        patch(
            "db.repositories.flagdle.FlagdleDayRepository.get_today_flag",
            new_callable=AsyncMock,
        ) as mock_get_today,
    ):
        mock_day = MagicMock()
        mock_day.id = 10
        mock_day.country_id = 143
        mock_day.date = date(2026, 9, 22)
        mock_get_today.return_value = mock_day

        res = await async_client.get("/flagdle/reveal")
        assert res.status_code == 400
        assert "Cannot reveal country before game is over" in res.json()["detail"]

@pytest.mark.anyio
async def test_flagdle_guess_correct_flow(async_client):
    """POST /flagdle/guess with target country returns answer=True."""
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
        mock_target = MagicMock()
        mock_target.id = 143
        mock_target.name = "Romania"
        mock_target.official_name = "Romania"

        mock_day = MagicMock()
        mock_day.id = 10
        mock_day.country_id = 143
        mock_day.country = mock_target
        mock_day.date = date(2026, 9, 22)

        mock_get_today.return_value = mock_day
        mock_get_country.return_value = mock_target

        guess_payload = {"country_id": 143, "guess": "Romania"}
        res = await async_client.post("/flagdle/guess", json=guess_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] is True
        assert data["guess"] == "Romania"
        assert data["distance_km"] == 0


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
