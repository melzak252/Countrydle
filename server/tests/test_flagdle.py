from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from tests.test_question_accounting import accounting_db

from game_logic import calculate_flagdle_points
from flagdle.utils import (
    UNMASK_ORDER,
    evaluate_flag_clues,
    generate_asset_token,
    generate_shades_token,
    get_country_iso2,
    normalize_svg_for_grid,
    verify_asset_token,
    verify_shades_token,
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
        # Guess 1: No distance (starts at guess 3) and no direction (starts at guess 5)
        assert data["distance_km"] is None
        assert data["bearing_direction"] is None
        assert data["revealed_tile"] == UNMASK_ORDER[0]


@pytest.mark.anyio
async def test_flagdle_faster_hint_thresholds(async_client):
    """Verify distance appears at guess 3, and bearing appears at guess 5."""
    with (
        patch("db.repositories.flagdle.FlagdleDayRepository.get_today_flag", new_callable=AsyncMock) as mock_get_today,
        patch("db.repositories.country.CountryRepository.get", new_callable=AsyncMock) as mock_get_country,
    ):
        mock_target = MagicMock()
        mock_target.id = 143
        mock_target.name = "Romania"
        mock_target.official_name = "Romania"

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

        from utils.guest_session import create_guest_game_token

        # Guess 1: no distance, no direction
        async_client.cookies.set("guest_flagdle", create_guest_game_token("flagdle", 10, 0, False, False))
        res1 = await async_client.post("/flagdle/guess", json={"country_id": 34, "guess": "Chad"})
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["distance_km"] is None
        assert d1["bearing_direction"] is None

        # Guess 2: no distance, no direction
        async_client.cookies.set("guest_flagdle", create_guest_game_token("flagdle", 10, 1, False, False))
        res2 = await async_client.post("/flagdle/guess", json={"country_id": 34, "guess": "Chad"})
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["distance_km"] is None
        assert d2["bearing_direction"] is None

        # Guess 3: Distance appears! Direction still hidden.
        async_client.cookies.set("guest_flagdle", create_guest_game_token("flagdle", 10, 2, False, False))
        res3 = await async_client.post("/flagdle/guess", json={"country_id": 34, "guess": "Chad"})
        assert res3.status_code == 200
        d3 = res3.json()
        assert d3["distance_km"] is not None
        assert d3["distance_km"] > 0
        assert d3["bearing_direction"] is None

        # Guess 4: Distance present, direction still hidden.
        async_client.cookies.set("guest_flagdle", create_guest_game_token("flagdle", 10, 3, False, False))
        res4 = await async_client.post("/flagdle/guess", json={"country_id": 34, "guess": "Chad"})
        assert res4.status_code == 200
        d4 = res4.json()
        assert d4["distance_km"] is not None
        assert d4["bearing_direction"] is None

        # Guess 5: Direction appears!
        async_client.cookies.set("guest_flagdle", create_guest_game_token("flagdle", 10, 4, False, False))
        res5 = await async_client.post("/flagdle/guess", json={"country_id": 34, "guess": "Chad"})
        assert res5.status_code == 200
        d5 = res5.json()
        assert d5["distance_km"] is not None
        assert d5["bearing_direction"] is not None
        assert d5["bearing_arrow"] is not None


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
async def test_flagdle_flag_asset_stream(async_client, tmp_path, monkeypatch):
    """GET /flagdle/flag-asset with valid token returns SVG."""
    monkeypatch.setattr("flagdle.FLAG_SVG_CACHE_DIR", tmp_path)
    (tmp_path / "fr.svg").write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#fff"/></svg>'
    )
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


@pytest.fixture
async def flag_day(accounting_db):
    from db.models import Country, FlagdleDay
    async with accounting_db() as session:
        country = Country(id=143, name="Romania", official_name="Romania", md_file="romania.md")
        day = FlagdleDay(id=1, country=country, date=date.today())
        session.add_all([country, day])
        await session.commit()
    return day


@pytest.fixture
async def daily_api_client(accounting_db, flag_day):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from db import get_db
    from flagdle import router
    from users.utils import get_current_or_guest_user

    app = FastAPI()
    app.include_router(router)

    async def session_dependency():
        async with accounting_db() as session:
            yield session

    app.dependency_overrides[get_db] = session_dependency
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


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


def test_normalize_svg_for_grid_standard():
    """Verify preserveAspectRatio="none" is injected and existing attributes are handled."""
    raw_svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><path d="M0 0"/></svg>'
    result = normalize_svg_for_grid(raw_svg, "my")
    assert b'preserveAspectRatio="none"' in result
    assert b'<rect' not in result
    assert b'viewBox="0 0 100 60"' in result

    raw_svg_with_par = (
        b'<svg preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" '
        b'viewBox="0 0 100 60"><rect fill="#fff"/></svg>'
    )
    result_par = normalize_svg_for_grid(raw_svg_with_par, "qa")
    assert b'preserveAspectRatio="none"' in result_par
    assert b'xMidYMid meet' not in result_par


def test_normalize_svg_for_grid_nepal():
    """Verify Nepal flag gets opaque backdrop rect injected immediately after opening <svg>."""
    nepal_svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120"><path d="M0 0"/></svg>'
    result_nepal = normalize_svg_for_grid(nepal_svg, "np")
    assert b'preserveAspectRatio="none"' in result_nepal
    assert b'<rect x="0" y="0" width="100%" height="100%" fill="#1e293b"/>' in result_nepal

    nepal_no_vb = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
    result_nepal_no_vb = normalize_svg_for_grid(nepal_no_vb, "NP")
    assert b'<rect width="100%" height="100%" fill="#1e293b"/>' in result_nepal_no_vb


def test_shades_token_roundtrip_and_tamper():
    """Verify stateless HMAC token generation, verification, and anti-tamper."""
    token = generate_shades_token("daily-2026-10-26", 42)
    assert isinstance(token, str)
    verified = verify_shades_token(token)
    assert verified == ("daily-2026-10-26", 42)

    custom_token = generate_shades_token("my-challenge:seed#1", 99)
    assert verify_shades_token(custom_token) == ("my-challenge:seed#1", 99)

    assert verify_shades_token("invalid_token") is None
    assert verify_shades_token("") is None
    assert verify_shades_token(None) is None

    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert verify_shades_token(tampered) is None


@pytest.mark.anyio
async def test_flagdle_flag_asset_fit_grid(async_client, tmp_path, monkeypatch):
    """GET /flagdle/flag-asset?fit=grid transforms SVG to preserveAspectRatio="none"."""
    monkeypatch.setattr("flagdle.FLAG_SVG_CACHE_DIR", tmp_path)
    (tmp_path / "ch.svg").write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="#f00"/></svg>'
    )
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
        mock_country.id = 75
        mock_country.name = "Switzerland"

        mock_day = MagicMock()
        mock_day.id = 42
        mock_day.country_id = 75
        mock_day.country = mock_country
        mock_day.date = date(2026, 9, 22)

        mock_get_today.return_value = mock_day
        mock_get_country.return_value = mock_country

        valid_token = generate_asset_token(42)
        res = await async_client.get(f"/flagdle/flag-asset?token={valid_token}&fit=grid")
        assert res.status_code == 200
        assert b'preserveAspectRatio="none"' in res.content


@pytest.mark.anyio
async def test_flagdle_shades_challenge_endpoint(async_client):
    """GET /flagdle/shades/challenge generates challenge with token and asset URL."""
    c1 = SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland")
    c2 = SimpleNamespace(id=2, name="Germany", official_name="Federal Republic of Germany")

    with (
        patch(
            "db.repositories.country.CountryRepository.get_all_countries",
            new_callable=AsyncMock,
            return_value=[c1, c2],
        ),
        patch(
            "db.repositories.flagdle.FlagdleDayRepository.get_today_flag",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        res_daily = await async_client.get("/flagdle/shades/challenge")
        assert res_daily.status_code == 200
        data_daily = res_daily.json()
        assert data_daily["is_daily"] is True
        assert data_daily["seed"].startswith("daily-")
        assert data_daily["max_guesses"] == 8
        assert data_daily["hint_unlock_guesses"] == 3
        assert "/flagdle/shades/flag-asset?token=" in data_daily["flag_asset_url"]

        verified = verify_shades_token(data_daily["token"])
        assert verified is not None
        assert verified[0] == data_daily["seed"]
        assert verified[1] in (1, 2)

        res_custom = await async_client.get("/flagdle/shades/challenge?seed=player-seed-42")
        assert res_custom.status_code == 200
        data_custom = res_custom.json()
        assert data_custom["is_daily"] is False
        assert data_custom["seed"] == "player-seed-42"
        verified_custom = verify_shades_token(data_custom["token"])
        assert verified_custom is not None
        assert verified_custom[0] == "player-seed-42"


@pytest.mark.anyio
async def test_flagdle_shades_flag_asset_endpoint(async_client, tmp_path, monkeypatch):
    """GET /flagdle/shades/flag-asset returns SVG with valid token, 403 on invalid."""
    monkeypatch.setattr("flagdle.FLAG_SVG_CACHE_DIR", tmp_path)
    (tmp_path / "pl.svg").write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><rect fill="#fff"/></svg>'
    )
    poland = SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland")

    with patch(
        "db.repositories.country.CountryRepository.get",
        new_callable=AsyncMock,
        return_value=poland,
    ):
        valid_token = generate_shades_token("test-seed", 1)
        res = await async_client.get(f"/flagdle/shades/flag-asset?token={valid_token}&fit=grid")
        assert res.status_code == 200
        assert "image/svg+xml" in res.headers["content-type"]
        assert b'preserveAspectRatio="none"' in res.content

        res_bad = await async_client.get("/flagdle/shades/flag-asset?token=invalid")
        assert res_bad.status_code == 403


@pytest.mark.anyio
async def test_flagdle_shades_guess_endpoint(async_client):
    """POST /flagdle/shades/guess evaluates clue feedback, win status, and anti-cheat."""
    poland = SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland")
    germany = SimpleNamespace(id=2, name="Germany", official_name="Federal Republic of Germany")

    async def mock_get(cid):
        if cid == 1:
            return poland
        if cid == 2:
            return germany
        return None

    with (
        patch(
            "db.repositories.country.CountryRepository.get",
            side_effect=mock_get,
        ),
        patch(
            "db.repositories.country.CountryRepository.get_all_countries",
            new_callable=AsyncMock,
            return_value=[poland, germany],
        ),
    ):
        token = generate_shades_token("test-seed", 1)

        res_inc = await async_client.post(
            "/flagdle/shades/guess",
            json={
                "token": token,
                "guess": "Germany",
                "country_id": 2,
                "guesses_made": 1,
            },
        )
        assert res_inc.status_code == 200
        data_inc = res_inc.json()
        assert data_inc["answer"] is False
        assert data_inc["won"] is False
        assert data_inc["is_game_over"] is False
        assert data_inc["target_country"] is None
        assert data_inc["iso2"] == "de"
        assert "matched_colors" in data_inc
        assert "missed_colors" in data_inc

        res_loss = await async_client.post(
            "/flagdle/shades/guess",
            json={
                "token": token,
                "guess": "Germany",
                "country_id": 2,
                "guesses_made": 8,
            },
        )
        assert res_loss.status_code == 200
        data_loss = res_loss.json()
        assert data_loss["is_game_over"] is True
        assert data_loss["won"] is False
        assert data_loss["target_country"] == {"id": 1, "name": "Poland"}

        res_win = await async_client.post(
            "/flagdle/shades/guess",
            json={
                "token": token,
                "guess": "Poland",
                "country_id": 1,
                "guesses_made": 2,
            },
        )
        assert res_win.status_code == 200
        data_win = res_win.json()
        assert data_win["answer"] is True
        assert data_win["won"] is True
        assert data_win["is_game_over"] is True
        assert data_win["target_country"] == {"id": 1, "name": "Poland"}

        res_bad = await async_client.post(
            "/flagdle/shades/guess",
            json={
                "token": "bad-token",
                "guess": "Poland",
                "guesses_made": 1,
            },
        )
        assert res_bad.status_code == 403

        res_unknown = await async_client.post(
            "/flagdle/shades/guess",
            json={
                "token": token,
                "guess": "Atlantis",
                "guesses_made": 1,
            },
        )
        assert res_unknown.status_code == 400
