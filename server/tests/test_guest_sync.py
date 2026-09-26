import pytest


@pytest.mark.anyio
async def test_sync_guest_data_invalid_date(auth_client):
    response = await auth_client.post("/countrydle/sync", json={
        "date": "invalid-date",
        "state": {
            "remaining_questions": 10,
            "remaining_guesses": 3,
            "questions_asked": 0,
            "guesses_made": 0,
            "is_game_over": False,
            "won": False,
        },
        "questions": [],
        "guesses": [],
    })
    assert response.status_code == 400
