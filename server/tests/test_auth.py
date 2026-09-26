import pytest
from httpx import AsyncClient
import uuid

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from httpx import ASGITransport
from types import SimpleNamespace
from unittest.mock import AsyncMock
from jose import jwt
from app import app
from users import utils as auth_utils


@pytest.fixture
async def session_client(monkeypatch):
    monkeypatch.setattr(auth_utils, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    monkeypatch.setattr(auth_utils, "REMEMBER_ME_EXPIRE_DAYS", 90)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        yield client


@pytest.fixture
def auth_clock(monkeypatch):
    current = [datetime.now(UTC).replace(microsecond=0)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(current[0].timestamp(), tz)

    monkeypatch.setattr(auth_utils, "datetime", Clock)
    monkeypatch.setattr(jwt, "datetime", Clock)
    return current


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["password", "google"])
@pytest.mark.parametrize("remember_me", [None, False, True])
async def test_login_session_lifetime_matches_explicit_choice(
    session_client, monkeypatch, auth_clock, method, remember_me,
):
    choice = {} if remember_me is None else {"remember_me": remember_me}
    if method == "password":
        response = await session_client.post(
            "/login", data={"username": "remember_user", "password": "Password123!", **choice},
        )
    else:
        monkeypatch.setattr("app.verify_google_token", lambda _: {"email": "remember_user@example.com"})
        response = await session_client.post(
            "/google-signin", json={"credential": "provider-token", **choice},
        )
    assert response.status_code == 200
    token = response.cookies["access_token"]
    claims = jwt.decode(token, auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
    lifetime = 90 * 86400 if remember_me else auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert claims["exp"] == int(auth_clock[0].timestamp()) + lifetime
    assert claims.get("remember_me", False) is bool(remember_me)
    cookie = SimpleCookie(response.headers["set-cookie"])["access_token"]
    assert int(cookie["max-age"]) == lifetime
    assert cookie["httponly"] and cookie["secure"]
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/"


@pytest.mark.anyio
async def test_remembered_session_survives_normal_expiry_and_renews_its_idle_window(session_client, auth_clock):
    login = await session_client.post("/login", data={
        "username": "remember_user", "password": "Password123!", "remember_me": "true",
    })
    assert login.status_code == 200
    auth_clock[0] += timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES + 1)
    response = await session_client.get("/users/me")
    assert response.status_code == 200
    claims = jwt.decode(response.cookies["access_token"], auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
    assert claims["remember_me"] is True
    assert claims["exp"] == int((auth_clock[0] + timedelta(days=90)).timestamp())

    auth_clock[0] += timedelta(days=90, minutes=-1)
    assert (await session_client.get("/users/me")).status_code == 200
    auth_clock[0] += timedelta(days=90, seconds=1)
    assert (await session_client.get("/users/me")).status_code == 401


@pytest.mark.anyio
async def test_ordinary_session_still_expires_without_activity(session_client, auth_clock):
    login = await session_client.post("/login", data={"username": "normal_user", "password": "Password123!"})
    assert login.status_code == 200
    auth_clock[0] += timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES, seconds=1)
    assert (await session_client.get("/users/me")).status_code == 401


@pytest.mark.anyio
async def test_logout_removes_remembered_cookie_and_protected_access(session_client):
    login = await session_client.post("/login", data={
        "username": "remember_user", "password": "Password123!", "remember_me": "true",
    })
    assert login.status_code == 200
    response = await session_client.post("/logout")
    assert response.status_code == 200
    assert SimpleCookie(response.headers["set-cookie"])["access_token"]["max-age"] == "0"
    assert "access_token" not in session_client.cookies
    assert (await session_client.get("/users/me")).status_code == 401


@pytest.mark.anyio
async def test_login_without_remember_replaces_previous_long_session(session_client, auth_clock):
    remembered = await session_client.post("/login", data={
        "username": "remember_user", "password": "Password123!", "remember_me": "true",
    })
    assert remembered.status_code == 200
    ordinary = await session_client.post("/login", data={"username": "remember_user", "password": "Password123!"})
    assert ordinary.status_code == 200
    response = await session_client.get("/users/me")
    claims = jwt.decode(response.cookies["access_token"], auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
    assert claims.get("remember_me", False) is False
    assert claims["exp"] == int(auth_clock[0].timestamp()) + auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.anyio
async def test_remembered_lifetime_uses_server_configuration(session_client, auth_clock, monkeypatch):
    monkeypatch.setattr(auth_utils, "REMEMBER_ME_EXPIRE_DAYS", 14)
    response = await session_client.post("/login", data={
        "username": "remember_user", "password": "Password123!", "remember_me": "true",
    })
    assert response.status_code == 200
    claims = jwt.decode(response.cookies["access_token"], auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
    assert claims["exp"] == int((auth_clock[0] + timedelta(days=14)).timestamp())
    assert SimpleCookie(response.headers["set-cookie"])["access_token"]["max-age"] == str(14 * 86400)


@pytest.mark.anyio
async def test_profile_update_preserves_remembered_session(session_client, auth_clock, monkeypatch):
    login = await session_client.post("/login", data={
        "username": "remember_user", "password": "Password123!", "remember_me": "true",
    })
    assert login.status_code == 200
    monkeypatch.setattr(auth_utils.UserRepository, "get_last_user_update", AsyncMock(return_value=None))
    monkeypatch.setattr(
        auth_utils.UserRepository, "update_user_email_username",
        AsyncMock(return_value=SimpleNamespace(verified=True)),
    )
    response = await session_client.post("/users/update", json={
        "username": "new_name", "email": "remember_user@example.com",
    })
    assert response.status_code == 200
    claims = jwt.decode(response.cookies["access_token"], auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
    assert claims["remember_me"] is True
    auth_clock[0] += timedelta(hours=2)
    assert (await session_client.get("/users/me")).status_code == 200


@pytest.mark.anyio
async def test_existing_token_without_remember_claim_renews_as_short_session(session_client, auth_clock):
    token = jwt.encode(
        {"sub": "existing@example.com", "exp": int((auth_clock[0] + timedelta(minutes=30)).timestamp())},
        auth_utils.SECRET_KEY, algorithm=auth_utils.ALGORITHM,
    )
    response = await session_client.get("/users/me", headers={"Cookie": f"access_token={token}"})
    assert response.status_code == 200
    claims = jwt.decode(response.cookies["access_token"], auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
    assert claims["remember_me"] is False
    assert claims["exp"] == int(auth_clock[0].timestamp()) + auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.anyio
async def test_invalid_signature_cannot_enable_remembered_session(session_client, auth_clock):
    token = jwt.encode(
        {"sub": "existing@example.com", "remember_me": True,
         "exp": int((auth_clock[0] + timedelta(days=90)).timestamp())},
        "wrong-signing-key", algorithm=auth_utils.ALGORITHM,
    )
    response = await session_client.get("/users/me", headers={"Cookie": f"access_token={token}"})
    assert response.status_code == 401
    assert "access_token" not in response.cookies


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
async def test_get_me_protected(auth_client):
    response = await auth_client.get("/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "pytest_user"

