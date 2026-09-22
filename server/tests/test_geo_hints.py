import pytest
from utils.geo import (
    calculate_distance_km,
    calculate_bearing,
    get_entity_coordinates,
    compute_guess_hint,
    enhance_guess_with_hint,
)


def test_calculate_distance_km():
    # Warsaw (52.2297, 21.0122) to London (51.5074, -0.1278) ~ 1449 km
    dist = calculate_distance_km(52.2297, 21.0122, 51.5074, -0.1278)
    assert 1440 <= dist <= 1460

    # Same point
    assert calculate_distance_km(52.0, 20.0, 52.0, 20.0) == 0


def test_calculate_bearing():
    # North
    deg, code, arrow = calculate_bearing(0.0, 0.0, 10.0, 0.0)
    assert code == "N"
    assert arrow == "↑"

    # East
    deg, code, arrow = calculate_bearing(0.0, 0.0, 0.0, 10.0)
    assert code == "E"
    assert arrow == "→"

    # South
    deg, code, arrow = calculate_bearing(10.0, 0.0, 0.0, 0.0)
    assert code == "S"
    assert arrow == "↓"

    # West
    deg, code, arrow = calculate_bearing(0.0, 10.0, 0.0, 0.0)
    assert code == "W"
    assert arrow == "←"

    # North-East
    deg, code, arrow = calculate_bearing(52.2297, 21.0122, 35.6762, 139.6503)
    assert code == "NE"
    assert arrow == "↗"


def test_get_entity_coordinates_all_modes():
    # Countrydle
    pl_coords = get_entity_coordinates("countrydle", name="Poland")
    assert pl_coords is not None
    assert round(pl_coords[0], 0) == 52.0

    # US Statedle
    tx_coords = get_entity_coordinates("us_statedle", name="Texas")
    assert tx_coords is not None
    assert round(tx_coords[0], 0) == 31.0

    # Wojewodztwodle
    maz_coords = get_entity_coordinates("wojewodztwodle", name="Mazowieckie")
    assert maz_coords is not None
    assert round(maz_coords[0], 0) == 52.0

    # Powiatdle
    bia_coords = get_entity_coordinates("powiatdle", name="Powiat bialski")
    assert bia_coords is not None
    assert round(bia_coords[0], 0) == 52.0


def test_progressive_hints_3_guess_mode():
    guessed = (40.4168, -3.7038)  # Madrid, Spain
    target = (52.2297, 21.0122)   # Warsaw, Poland

    # Guess 1: Incorrect in 3-guess mode -> distance only
    hint1 = compute_guess_hint(
        mode="countrydle",
        guess_number=1,
        max_guesses=3,
        is_correct=False,
        guessed_coords=guessed,
        target_coords=target,
    )
    assert hint1["distance_km"] > 2000
    assert hint1["bearing_direction"] is None
    assert hint1["bearing_degrees"] is None
    assert hint1["bearing_arrow"] is None

    # Guess 2: Incorrect in 3-guess mode -> distance AND direction
    hint2 = compute_guess_hint(
        mode="countrydle",
        guess_number=2,
        max_guesses=3,
        is_correct=False,
        guessed_coords=guessed,
        target_coords=target,
    )
    assert hint2["distance_km"] > 2000
    assert hint2["bearing_direction"] == "NE"
    assert hint2["bearing_arrow"] == "↗"
    assert hint2["bearing_degrees"] is not None

    # Correct guess -> distance = 0
    hint_correct = compute_guess_hint(
        mode="countrydle",
        guess_number=1,
        max_guesses=3,
        is_correct=True,
        guessed_coords=target,
        target_coords=target,
    )
    assert hint_correct["distance_km"] == 0
    assert hint_correct["bearing_direction"] is None


def test_progressive_hints_2_guess_mode_gives_direction_on_guess_1():
    guessed = (50.0647, 19.9450)  # Małopolskie (Kraków)
    target = (52.2297, 21.0122)   # Mazowieckie (Warszawa)

    # In 2-guess mode, guess 1 gives direction immediately
    hint = compute_guess_hint(
        mode="wojewodztwodle",
        guess_number=1,
        max_guesses=2,
        is_correct=False,
        guessed_coords=guessed,
        target_coords=target,
    )
    assert hint["distance_km"] > 0
    assert hint["bearing_direction"] is not None
    assert hint["bearing_arrow"] is not None


def test_enhance_guess_with_hint():
    # Madrid (Spain) guessing against Poland
    hint1 = enhance_guess_with_hint(
        mode="countrydle",
        guess_record={"guess": "Spain", "country_id": None, "answer": False},
        guess_number=1,
        max_guesses=3,
        target_id=1,  # Poland
        target_coords=(52.0, 20.0),
    )
    assert hint1["distance_km"] is not None
    assert hint1["distance_km"] > 1500
    assert hint1["bearing_direction"] is None

    hint2 = enhance_guess_with_hint(
        mode="countrydle",
        guess_record={"guess": "Spain", "country_id": None, "answer": False},
        guess_number=2,
        max_guesses=3,
        target_id=1,
        target_coords=(52.0, 20.0),
    )
    assert hint2["distance_km"] is not None
    assert hint2["bearing_direction"] is not None
    assert hint2["bearing_arrow"] is not None


@pytest.mark.anyio
async def test_countrydle_guess_endpoint_returns_hints(async_client):
    from unittest.mock import AsyncMock, patch, MagicMock

    day_mock = MagicMock(id=1, country_id=100)
    country_mock = MagicMock(id=100, name="Poland", official_name="Republic of Poland")

    with (
        patch("db.repositories.countrydle.CountrydleRepository.get_today_country", AsyncMock(return_value=day_mock)),
        patch("db.repositories.country.CountryRepository.get", AsyncMock(return_value=country_mock)),
        patch("utils.geo.get_entity_coordinates", side_effect=lambda mode, entity_id=None, name=None, **kw: (52.0, 20.0) if (entity_id == 100 or name == "Poland") else (40.4, -3.7)),
    ):
        # Guess 1: Spain (Incorrect) -> guest cookie path
        resp1 = await async_client.post("/countrydle/guess", json={"guess": "Spain"})
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["answer"] is False
        assert data1["distance_km"] is not None
        assert data1["distance_km"] > 1000
        assert data1["bearing_direction"] is None  # Guess 1 in 3-guess mode has no direction

        # Guess 2: with cookie -> should return distance AND direction
        cookie = resp1.headers.get("set-cookie", "")
        headers = {"cookie": cookie} if cookie else {}
        resp2 = await async_client.post("/countrydle/guess", json={"guess": "Germany"}, headers=headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["answer"] is False
        assert data2["distance_km"] is not None
        assert data2["bearing_direction"] is not None
        assert data2["bearing_arrow"] is not None
