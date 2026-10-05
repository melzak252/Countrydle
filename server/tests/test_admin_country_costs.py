"""Admin access and request validation for the Countrydle cost report."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from admin.country_costs import router
from db import get_db
from users.utils import get_current_user

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    app = FastAPI()
    app.include_router(router, prefix="/admin")

    async def empty_session():
        yield object()

    app.dependency_overrides[get_db] = empty_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client, app


async def test_cost_report_requires_admin_authentication(client):
    test_client, _ = client

    response = await test_client.get("/admin/countrydle-costs")

    assert response.status_code == 401


async def test_cost_report_rejects_authenticated_non_admin(client):
    test_client, app = client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=False)

    response = await test_client.get("/admin/countrydle-costs")

    assert response.status_code == 403


@pytest.mark.parametrize("days", [0, 367])
async def test_cost_report_rejects_days_outside_supported_range(client, days):
    test_client, app = client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=True)

    response = await test_client.get("/admin/countrydle-costs", params={"days": days})

    assert response.status_code == 422


async def test_cost_report_hides_internal_errors(client, monkeypatch):
    test_client, app = client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=True)

    async def fail_report(*args, **kwargs):
        raise RuntimeError("database credentials must not be exposed")

    monkeypatch.setattr("admin.country_costs.build_country_cost_report", fail_report)
    response = await test_client.get("/admin/countrydle-costs")

    assert response.status_code == 503
    assert "database credentials" not in response.text
