"""Suggestion submission, persistence, validation, and admin access contracts."""
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import app
from db import get_db
from db.base import Base
from db.models import User
from users.utils import get_current_or_guest_user, get_current_user
from utils.question_rate_limit import QuestionAttemptLimiter
import suggestions


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    def add(self, instance):
        self.session.add(instance)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()

    async def refresh(self, instance):
        self.session.refresh(instance)


@pytest.fixture
async def suggestions_api(monkeypatch):
    engine = create_engine("sqlite://")
    monkeypatch.setattr(suggestions, "submission_limiter", QuestionAttemptLimiter(), raising=False)
    tables = [User.__table__]
    if "suggestions" in Base.metadata.tables:
        tables.append(Base.metadata.tables["suggestions"])
    Base.metadata.create_all(engine, tables=tables)
    saved_overrides = app.dependency_overrides.copy()
    try:
        with Session(engine, expire_on_commit=False) as session:
            player = User(id=1, username="player", email="player@example.com", is_admin=False)
            admin = User(id=2, username="admin", email="admin@example.com", is_admin=True)
            session.add_all([player, admin])
            session.commit()

            async def database():
                yield AsyncSessionAdapter(session)

            app.dependency_overrides[get_db] = database
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield SimpleNamespace(client=client, engine=engine, player=player, admin=admin)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)
        engine.dispose()


def login(user):
    async def current_user():
        return user

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_current_or_guest_user] = current_user


@pytest.mark.anyio
async def test_guest_suggestion_is_committed_and_visible_only_to_admin(suggestions_api):
    api = suggestions_api
    response = await api.client.post("/suggestions", json={
        "topic": "feature", "name": "  Alex  ", "email": "  alex@example.com  ",
        "message": "  Please add a practice geography mode.\nWith a map.  ",
    })
    assert response.status_code == 201
    suggestion_id = response.json()["id"]
    # A separate session proves the POST committed, rather than merely adding to a unit of work.
    with Session(api.engine) as session:
        row = session.execute(select(Base.metadata.tables["suggestions"])).mappings().one()
        assert row["id"] == suggestion_id
        assert row["message"] == "Please add a practice geography mode.\nWith a map."
        assert row["name"] == "Alex"
        assert row["email"] == "alex@example.com"
        assert row["reporter_id"] is None
    assert (await api.client.get("/admin/suggestions")).status_code == 401
    assert (await api.client.get("/suggestions")).status_code == 405
    login(api.player)
    assert (await api.client.get("/admin/suggestions")).status_code == 403
    login(api.admin)
    response = await api.client.get("/admin/suggestions")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["id"] == suggestion_id
    assert item["topic"] == "feature"
    assert item["message"] == "Please add a practice geography mode.\nWith a map."
    assert item["name"] == "Alex"
    assert item["email"] == "alex@example.com"
    assert item["reporter_username"] is None
    assert item["created_at"]


@pytest.mark.anyio
async def test_authenticated_suggestions_have_server_identity_and_stable_pagination(suggestions_api):
    api = suggestions_api
    login(api.player)
    ids = []
    for message in ("Improve country clues", "Improve mobile maps", "Add keyboard controls"):
        response = await api.client.post("/suggestions", json={"message": message, "topic": "feedback"})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    login(api.admin)
    first = (await api.client.get("/admin/suggestions?page=1&limit=2")).json()
    second = (await api.client.get("/admin/suggestions?page=2&limit=2")).json()
    assert first["total"] == second["total"] == 3
    assert [item["id"] for item in first["items"] + second["items"]] == ids[::-1]
    assert all(item["reporter_username"] == "player" for item in first["items"] + second["items"])
    assert first["items"][0]["email"] is None
    assert first["items"][0]["name"] is None
    for query in ("page=0", "limit=0", "limit=101"):
        assert (await api.client.get(f"/admin/suggestions?{query}")).status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [
    {"message": " \n\t "}, {"message": "x" * 5001},
    {"message": "Idea", "topic": "invalid"},
    {"message": "Idea", "email": "not-an-email"},
    {"message": "Idea", "name": "x" * 101},
    {"message": "Idea", "reporter_id": 2},
])
async def test_invalid_suggestion_cannot_be_saved(suggestions_api, payload):
    api = suggestions_api
    assert (await api.client.post("/suggestions", json=payload)).status_code == 422
    login(api.admin)
    assert (await api.client.get("/admin/suggestions")).json() == {"items": [], "total": 0}


@pytest.mark.anyio
@pytest.mark.parametrize("message", ["x" * 5000, "😀" * 5000])
async def test_message_boundary_and_blank_optional_contact_fields(suggestions_api, message):
    api = suggestions_api
    response = await api.client.post("/suggestions", json={
        "topic": "data", "message": "  " + message + "  ", "name": " ", "email": " ",
    })
    assert response.status_code == 201
    login(api.admin)
    item = (await api.client.get("/admin/suggestions")).json()["items"][0]
    assert item["message"] == message
    assert item["name"] is None
    assert item["email"] is None


@pytest.mark.anyio
async def test_submission_limit_rejects_without_persisting_and_recovers(suggestions_api, monkeypatch):
    api = suggestions_api
    clock = [0.0]
    monkeypatch.setattr(
        suggestions,
        "submission_limiter",
        QuestionAttemptLimiter(max_requests=2, clock=lambda: clock[0]),
        raising=False,
    )
    for message in ("First suggestion", "Second suggestion"):
        assert (await api.client.post("/suggestions", json={"message": message})).status_code == 201

    blocked = await api.client.post("/suggestions", json={"message": "Blocked suggestion"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"

    transport = ASGITransport(app=app, client=("198.51.100.2", 1234))
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        assert (await other.post("/suggestions", json={"message": "Another client"})).status_code == 201

    clock[0] = 31.0
    blocked = await api.client.post("/suggestions", json={"message": "Still blocked"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "29"

    clock[0] = 60.0
    assert (await api.client.post("/suggestions", json={"message": "After cooldown"})).status_code == 201
    login(api.admin)
    saved = (await api.client.get("/admin/suggestions")).json()
    assert saved["total"] == 4
    assert {item["message"] for item in saved["items"]} == {
        "First suggestion", "Second suggestion", "Another client", "After cooldown",
    }
