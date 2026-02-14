import pytest
from httpx import AsyncClient
import uuid

@pytest.mark.anyio
async def test_register_user(async_client):
    random_suffix = str(uuid.uuid4())[:8]
    user_data = {
        "username": f"test_auth_{random_suffix}",
        "email": f"test_auth_{random_suffix}@example.com",
        "password": "Password123!"
    }
    response = await async_client.post("/register", json=user_data)
    assert response.status_code == 200
    assert response.json()["ok"] is True

@pytest.mark.anyio
async def test_login_user(async_client):
    # Ensure user exists (if running independently)
    user_data = {
        "username": "test_login_user",
        "email": "test_login@example.com",
        "password": "Password123!"
    }
    await async_client.post("/register", json=user_data)

    login_data = {
        "username": "test_login_user",
        "password": "Password123!"
    }
    response = await async_client.post("/login", data=login_data)
    assert response.status_code == 200
    assert "access_token" in response.cookies
    data = response.json()
    assert data["username"] == "test_login_user"

@pytest.mark.anyio
async def test_get_me_protected(async_client, token):
    response = await async_client.get("/users/me", cookies={"access_token": token})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "pytest_user"

@pytest.mark.anyio
async def test_logout(async_client, token):
    response = await async_client.post("/logout", cookies={"access_token": token})
    assert response.status_code == 200
    assert response.json()["success"] is True
    # Verify cookie is cleared (value is empty string or "")
    assert response.cookies["access_token"] in ["", '""']
