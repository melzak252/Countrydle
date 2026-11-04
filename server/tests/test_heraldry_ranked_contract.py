"""Heraldry's persisted daily contract at the public API boundary."""
import pytest


@pytest.mark.anyio
async def test_legacy_daily_history_is_unranked(async_client, monkeypatch):
    from powiatdle import heraldry

    county = {"id": 1, "name": "Kraków", "voivodeship": "małopolskie", "is_city_county": True, "latitude": 50.0, "longitude": 20.0}
    monkeypatch.setattr(heraldry, "get_all_counties", lambda: [county])
    monkeypatch.setattr(heraldry, "get_county_by_id", lambda _: county)
    token = heraldry.encrypt_session_token({
        "seed": "legacy-practice", "is_daily": False, "date": "2026-01-01",
        "target_id": 1, "guesses": [],
    })
    result = await async_client.get("/powiatdle/heraldry/challenge", params={"seed": "legacy-practice", "token": token})
    assert result.status_code == 200
    assert result.json()["ranked"] is False
    assert result.json()["points"] is None
