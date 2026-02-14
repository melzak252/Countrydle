import pytest
from httpx import AsyncClient, ASGITransport
from app import app
import os

# Use the existing database for tests (or a separate test DB if configured)
DATABASE_URL = os.getenv("DATABASE_URL")

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture(scope="session")
async def token(async_client):
    # Register a user for testing
    user_data = {
        "username": "pytest_user",
        "email": "pytest@example.com",
        "password": "TestPassword123!"
    }
    await async_client.post("/register", json=user_data)
    
    # Login to get token
    login_data = {
        "username": "pytest_user",
        "password": "TestPassword123!"
    }
    response = await async_client.post("/login", data=login_data)
    assert response.status_code == 200
    return response.cookies.get("access_token")