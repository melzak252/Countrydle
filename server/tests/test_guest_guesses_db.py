"""Guest guesses persist without touching the application's shared database."""
import pytest

import db.models as models
from tests.test_guest_participation import participation_db
from tests.test_guest_participation_routes import solo_client


@pytest.mark.anyio
@pytest.mark.real_database
@pytest.mark.parametrize("mode,model_name,id_field,guess", [
    ("countrydle", "CountrydleGuess", "country_id", "Germany"),
    ("continental/europe", "ContinentalGuess", "country_id", "Germany"),
    ("flagdle", "FlagdleGuess", "country_id", "Germany"),
    ("us_statedle", "USStatedleGuess", "us_state_id", "Alaska"),
    ("powiatdle", "PowiatdleGuess", "powiat_id", "krakowski"),
    ("wojewodztwodle", "WojewodztwodleGuess", "wojewodztwo_id", "pomorskie"),
])
async def test_guest_guesses_saved_to_database_across_modes(
    solo_client, participation_db, mode, model_name, id_field, guess,
):
    response = await solo_client.post(f"/{mode}/guess", json={"guess": guess, id_field: 2})
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is False
    async with participation_db() as session:
        row = await session.get(getattr(models, model_name), response.json()["id"])
        assert row is not None
        assert row.user_id is None
        assert row.day_id == 1
        assert row.guess == guess
        assert row.answer is False
