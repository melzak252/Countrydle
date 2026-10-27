from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from powiatdle.heraldry import (
    PowiatHeraldryChallenge,
    PowiatHeraldryGuessRequest,
    PowiatHeraldryGuessResult,
    PowiatHeraldryItem,
    decrypt_session_token,
    encrypt_session_token,
    get_all_counties,
    get_or_fetch_herb_svg,
    get_registration_plates,
    resolve_guessed_county,
)


# ---------------------------------------------------------------------------
# 1. Token Encryption Unit Tests
# ---------------------------------------------------------------------------


def test_token_encryption_is_opaque_and_rejects_tampering():
    """Session token must be completely opaque and reject any tampering with 403."""
    payload = {
        "seed": "daily-2026-10-27",
        "is_daily": True,
        "date": "2026-10-27",
        "target_id": 369,
        "guesses": [24, 350],
    }
    token = encrypt_session_token(payload)

    # 1. Completely opaque: no plaintext target ID, seed, or guesses in token
    assert "369" not in token
    assert "daily-2026-10-27" not in token
    assert "target_id" not in token
    assert "guesses" not in token
    assert "Warszawa" not in token

    # 2. Decrypts accurately
    decrypted = decrypt_session_token(token)
    assert decrypted["target_id"] == 369
    assert decrypted["seed"] == "daily-2026-10-27"
    assert decrypted["guesses"] == [24, 350]

    # 3. Rejects tampered token with 403
    tampered_bytes = bytearray(token.encode("utf-8"))
    tampered_bytes[20] = (tampered_bytes[20] + 1) % 256
    tampered_token = tampered_bytes.decode("utf-8", errors="ignore")

    with pytest.raises(HTTPException) as exc_info:
        decrypt_session_token(tampered_token)
    assert exc_info.value.status_code == 403

    # 4. Rejects invalid / garbage token with 403
    with pytest.raises(HTTPException) as exc_info_garbage:
        decrypt_session_token("not-a-valid-token")
    assert exc_info_garbage.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info_empty:
        decrypt_session_token("")
    assert exc_info_empty.value.status_code == 403


# ---------------------------------------------------------------------------
# 2. Registration Plates & Hint Progression Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_guesses_hint_progression_registration_plates(async_client):
    """Guesses 1-4 return registration_plates=None.

    5th accepted wrong guess (and 6-8) returns the full list of plates (including
    multi-plate counties like Warszawa). 8th guess ends game.
    """
    # Create session with Warszawa (ID 369, multi-plate county with 15 plates)
    target_id = 369
    all_target_plates = get_registration_plates(target_id)
    assert len(all_target_plates) > 1  # Multi-plate county
    assert "WA" in all_target_plates

    # Distinct wrong counties to guess
    wrong_counties = [
        (24, "Kraków"),
        (350, "Poznań"),
        (11, "Gdańsk"),
        (371, "Wrocław"),
        (377, "Łódź"),
        (1, "Biała Podlaska"),
        (2, "Białystok"),
        (3, "Bielsko-Biała"),
    ]

    session_payload = {
        "seed": "test-plates-progression",
        "is_daily": False,
        "date": "2026-10-27",
        "target_id": target_id,
        "guesses": [],
    }
    current_token = encrypt_session_token(session_payload)

    # Guesses 1 to 4: registration_plates must be None
    for i in range(4):
        cid, cname = wrong_counties[i]
        res = await async_client.post(
            "/powiatdle/heraldry/guess",
            json={"token": current_token, "guess": cname, "powiat_id": cid},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] is False
        assert data["won"] is False
        assert data["is_game_over"] is False
        assert data["guesses_made"] == i + 1
        assert data["remaining_guesses"] == 8 - (i + 1)
        assert data["registration_plates"] is None, f"Guess {i+1} revealed plates prematurely"
        assert data["target_powiat"] is None
        current_token = data["token"]

    # 5th accepted wrong guess: registration_plates MUST unlock and contain all plates
    cid_5, cname_5 = wrong_counties[4]  # Łódź
    res_5 = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": current_token, "guess": cname_5, "powiat_id": cid_5},
    )
    assert res_5.status_code == 200
    data_5 = res_5.json()
    assert data_5["answer"] is False
    assert data_5["won"] is False
    assert data_5["is_game_over"] is False
    assert data_5["guesses_made"] == 5
    assert data_5["remaining_guesses"] == 3
    assert data_5["registration_plates"] is not None
    assert data_5["registration_plates"] == all_target_plates
    assert len(data_5["registration_plates"]) == 15
    current_token = data_5["token"]

    # 6th and 7th guesses: registration_plates remain available
    for i in range(5, 7):
        cid, cname = wrong_counties[i]
        res = await async_client.post(
            "/powiatdle/heraldry/guess",
            json={"token": current_token, "guess": cname, "powiat_id": cid},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["guesses_made"] == i + 1
        assert data["registration_plates"] == all_target_plates
        current_token = data["token"]

    # 8th guess: ends game and reveals target_powiat
    cid_8, cname_8 = wrong_counties[7]
    res_8 = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": current_token, "guess": cname_8, "powiat_id": cid_8},
    )
    assert res_8.status_code == 200
    data_8 = res_8.json()
    assert data_8["guesses_made"] == 8
    assert data_8["remaining_guesses"] == 0
    assert data_8["is_game_over"] is True
    assert data_8["won"] is False
    assert data_8["registration_plates"] == all_target_plates
    assert data_8["target_powiat"] is not None
    assert data_8["target_powiat"]["id"] == target_id
    assert data_8["target_powiat"]["name"] == "Warszawa"


# ---------------------------------------------------------------------------
# 3. Duplicate Guess Rejection Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_duplicate_guess_rejected_without_advancing_count(async_client):
    """Duplicate guesses return 400 and do not advance guess count toward 5th-guess hint."""
    target_id = 369  # Warszawa
    session_payload = {
        "seed": "test-duplicate-rejection",
        "is_daily": False,
        "date": "2026-10-27",
        "target_id": target_id,
        "guesses": [],
    }
    current_token = encrypt_session_token(session_payload)

    # 1. Make guess 1 (Kraków)
    res_1 = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": current_token, "guess": "Kraków", "powiat_id": 24},
    )
    assert res_1.status_code == 200
    data_1 = res_1.json()
    assert data_1["guesses_made"] == 1
    current_token = data_1["token"]

    # 2. Duplicate guess (Kraków again by name and ID)
    res_dup = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": current_token, "guess": "Kraków", "powiat_id": 24},
    )
    assert res_dup.status_code == 400
    assert "Ten powiat został już sprawdzony" in res_dup.json()["detail"]

    # 3. Duplicate guess by case-insensitive name without ID
    res_dup_case = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": current_token, "guess": "kraków"},
    )
    assert res_dup_case.status_code == 400
    assert "Ten powiat został już sprawdzony" in res_dup_case.json()["detail"]

    # 4. Make 3 more unique wrong guesses (Poznań, Gdańsk, Wrocław) -> total 4 guesses
    wrong_subsequent = [(350, "Poznań"), (11, "Gdańsk"), (371, "Wrocław")]
    for cid, cname in wrong_subsequent:
        res = await async_client.post(
            "/powiatdle/heraldry/guess",
            json={"token": current_token, "guess": cname, "powiat_id": cid},
        )
        assert res.status_code == 200
        current_token = res.json()["token"]

    # Token still has 4 guesses
    payload_after_4 = decrypt_session_token(current_token)
    assert len(payload_after_4["guesses"]) == 4

    # 5. Try duplicate of Kraków again (which was guess 1)
    res_dup_again = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": current_token, "guess": "Kraków"},
    )
    assert res_dup_again.status_code == 400

    # 6. Verify plates are STILL locked because only 4 valid guesses were made!
    res_challenge = await async_client.get(
        f"/powiatdle/heraldry/challenge?seed=test-duplicate-rejection&token={current_token}"
    )
    assert res_challenge.status_code == 200
    ch_data = res_challenge.json()
    assert len(ch_data["guesses"]) == 4
    assert ch_data["registration_plates"] is None


# ---------------------------------------------------------------------------
# 4. Correct Guess Wins Game Immediately
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_correct_guess_wins_game_and_reveals_target(async_client):
    """A correct guess immediately ends game, sets won=True, reveals target_powiat, and unlocks plates."""
    target_id = 24  # Kraków
    all_plates = get_registration_plates(target_id)
    session_payload = {
        "seed": "test-win-direct",
        "is_daily": False,
        "date": "2026-10-27",
        "target_id": target_id,
        "guesses": [],
    }
    token = encrypt_session_token(session_payload)

    # Correct guess on attempt 1
    res = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": token, "guess": "Kraków", "powiat_id": 24},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] is True
    assert data["won"] is True
    assert data["is_game_over"] is True
    assert data["distance_km"] == 0
    assert data["guesses_made"] == 1
    assert data["target_powiat"] == {"id": 24, "name": "Kraków", "voivodeship": "małopolskie"}
    assert data["registration_plates"] == all_plates

    # Subsequent guess when game is over returns 400
    post_win_token = data["token"]
    res_after = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": post_win_token, "guess": "Poznań", "powiat_id": 350},
    )
    assert res_after.status_code == 400
    assert "Gra jest już zakończona" in res_after.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Coat Asset Endpoint & Upstream Failure 503
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_coat_asset_invalid_token_and_missing_upstream_503(async_client, tmp_path):
    """GET /coat-asset returns 403 on bad token, 503 on upstream error, and never a fake image."""
    # 1. Invalid token returns 403
    res_bad = await async_client.get("/powiatdle/heraldry/coat-asset?token=invalid-token")
    assert res_bad.status_code == 403

    # 2. Valid token for an uncached county where upstream fails -> 503 Service Unavailable
    # Use a dummy isolated cache directory
    dummy_cache = tmp_path / "test_herb_cache"
    dummy_cache.mkdir(parents=True, exist_ok=True)

    session_payload = {
        "seed": "test-upstream-fail",
        "is_daily": False,
        "date": "2026-10-27",
        "target_id": 1,
        "guesses": [],
    }
    valid_token = encrypt_session_token(session_payload)

    with (
        patch("powiatdle.heraldry.get_herb_cache_dir", return_value=dummy_cache),
        patch("powiatdle.heraldry.resolve_and_fetch_heraldry", side_effect=RuntimeError("Wikipedia timeout")),
    ):
        res_503 = await async_client.get(f"/powiatdle/heraldry/coat-asset?token={valid_token}")
        assert res_503.status_code == 503
        assert res_503.json()["detail"] == "Coat of arms asset temporarily unavailable."

    # 3. When cache exists -> 200 image/svg+xml
    sample_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
    (dummy_cache / "1.svg").write_bytes(sample_svg)

    with patch("powiatdle.heraldry.get_herb_cache_dir", return_value=dummy_cache):
        res_200 = await async_client.get(f"/powiatdle/heraldry/coat-asset?token={valid_token}")
        assert res_200.status_code == 200
        assert "image/svg+xml" in res_200.headers["content-type"]
        assert res_200.content == sample_svg


# ---------------------------------------------------------------------------
# 6. Catalog Counties Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_counties_catalog_endpoint(async_client):
    """GET /counties returns all counties sorted alphabetically by name."""
    res = await async_client.get("/powiatdle/heraldry/counties")
    assert res.status_code == 200
    counties = res.json()
    assert len(counties) == 380

    for item in counties[:5]:
        assert "id" in item
        assert "name" in item
        assert "voivodeship" in item
        assert "is_city_county" in item

    # Check alphabetized ordering (e.g. Biała Podlaska, Białystok, ...)
    assert counties[0]["name"] == "Biała Podlaska"
    assert counties[1]["name"] == "Białystok"
    assert counties[2]["name"] == "Bielsko-Biała"


# ---------------------------------------------------------------------------
# 7. Challenge Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_challenge_endpoint_daily_and_resume(async_client):
    """GET /challenge returns seed, token, coat_asset_url and restores state when token provided."""
    # 1. Fresh daily challenge
    res = await async_client.get("/powiatdle/heraldry/challenge")
    assert res.status_code == 200
    data = res.json()
    assert data["is_daily"] is True
    assert data["seed"].startswith("daily-")
    assert data["max_guesses"] == 8
    assert data["hint_unlock_guesses"] == 5
    assert "token" in data
    assert "/powiatdle/heraldry/coat-asset?token=" in data["coat_asset_url"]
    assert data["is_game_over"] is False
    assert data["won"] is False
    assert data["guesses"] == []

    # 2. Resuming an active session with guesses restores them
    token = data["token"]
    res_g1 = await async_client.post(
        "/powiatdle/heraldry/guess",
        json={"token": token, "guess": "Kraków"},
    )
    assert res_g1.status_code == 200
    token_g1 = res_g1.json()["token"]

    # Call challenge with token
    res_resume = await async_client.get(f"/powiatdle/heraldry/challenge?seed={data['seed']}&token={token_g1}")
    assert res_resume.status_code == 200
    data_resume = res_resume.json()
    assert len(data_resume["guesses"]) == 1
    assert data_resume["guesses"][0]["guess"] == "Kraków"
