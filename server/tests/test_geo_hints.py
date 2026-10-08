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


@pytest.mark.real_database
@pytest.mark.anyio
async def test_countrydle_guess_endpoint_returns_hints(daily_api_client, daily_api_db):
    from unittest.mock import patch
    from sqlalchemy import select

    from daily_clock import utc_today
    from db.models.countrydle import CountrydleDay
    from db.models.guess import CountrydleGuess
    from db.models.guest_participation import GuestParticipation

    async with daily_api_db() as session:
        session.add(CountrydleDay(id=1, country_id=1, date=utc_today()))
        await session.commit()

    def coordinates(mode, entity_id=None, name=None, **kwargs):
        return (52.0, 20.0) if entity_id == 1 or name == "Poland" else (40.4, -3.7)

    with patch("utils.geo.get_entity_coordinates", side_effect=coordinates):
        # The browser preserves its signed identity, not a raw Set-Cookie header.
        resp1 = await daily_api_client.post("/countrydle/guess", json={"guess": "Spain"})
        assert resp1.status_code == 200, resp1.text
        data1 = resp1.json()
        assert data1["answer"] is False
        assert data1["distance_km"] is not None
        assert data1["distance_km"] > 1000
        assert data1["bearing_direction"] is None

        # Per-mode projections are not authoritative for progressive disclosure.
        daily_api_client.cookies.delete("guest_countrydle")
        resp2 = await daily_api_client.post("/countrydle/guess", json={"guess": "Germany"})
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert data2["answer"] is False
        assert data2["distance_km"] is not None
        assert data2["bearing_direction"] is not None
        assert data2["bearing_arrow"] is not None

        reloaded = await daily_api_client.get("/countrydle/state")
        assert reloaded.status_code == 200, reloaded.text
        assert reloaded.json()["state"]["guesses_made"] == 2
        assert reloaded.json()["state"]["remaining_guesses"] == 1
        assert reloaded.json()["guesses"][0]["bearing_direction"] is None
        assert reloaded.json()["guesses"][1]["bearing_direction"] == data2["bearing_direction"]

    async with daily_api_db() as session:
        participation = (await session.scalars(select(GuestParticipation))).one()
        guesses = list((await session.scalars(
            select(CountrydleGuess).order_by(CountrydleGuess.id),
        )).all())
        assert participation.guesses_made == 2
        assert participation.mode == "countrydle"
        assert participation.won is False
        assert [guess.id for guess in guesses] == [data1["id"], data2["id"]]
        assert all(guess.guest_id == participation.guest_id for guess in guesses)
        assert all(guess.user_id is None for guess in guesses)
