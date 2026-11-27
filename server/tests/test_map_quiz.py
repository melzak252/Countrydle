"""Tests for 10-per-day regional map quizzes (/map-quiz/{scope})."""

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from db import get_db
from db.models.map_quiz import MapQuizDailySession
from db.models.user import User, UserPoints
from map_quiz import router as map_quiz_router
from map_quiz.service import (
    DAILY_ROUND_COUNT,
    calculate_map_quiz_points,
    select_daily_targets,
)
from tests.test_guest_participation import participation_db
from users.utils import get_current_or_guest_user, get_current_user


def test_daily_target_selection_is_deterministic_and_distinct():
    day_a = date(2026, 11, 27)
    day_b = date(2026, 11, 28)

    for scope in ("london_boroughs", "england_counties"):
        first = select_daily_targets(scope, day_a)
        second = select_daily_targets(scope, day_a)
        other_day = select_daily_targets(scope, day_b)

        assert first == second
        assert len(first) == DAILY_ROUND_COUNT
        assert len(set(first)) == DAILY_ROUND_COUNT
        assert first != other_day


def test_scoring_formula_is_monotonic():
    assert calculate_map_quiz_points(0, 10, 5) == 0
    low = calculate_map_quiz_points(5, 60, 0)
    mid = calculate_map_quiz_points(7, 60, 1)
    high = calculate_map_quiz_points(10, 20, 3)
    slow_perfect = calculate_map_quiz_points(10, 180, 0)
    fast_perfect = calculate_map_quiz_points(10, 15, 0)

    assert 0 < low < mid < high
    assert fast_perfect > slow_perfect


@pytest.fixture
async def map_quiz_client(participation_db):
    async with participation_db() as session:
        conn = await session.connection()
        await conn.run_sync(UserPoints.__table__.create)
        await conn.run_sync(MapQuizDailySession.__table__.create)
        await session.execute(update(User).where(User.id == 1).values(username="Alice"))
        await session.execute(update(User).where(User.id == 2).values(username="Bob"))
        await session.commit()

    app = FastAPI()
    app.include_router(map_quiz_router)

    async def db_override():
        async with participation_db() as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_or_guest_user] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        yield client, app


def sign_in(app: FastAPI, user_id: int = 1):
    user = SimpleNamespace(id=user_id, username="Alice" if user_id == 1 else "Bob")
    app.dependency_overrides[get_current_or_guest_user] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.mark.real_database
@pytest.mark.anyio
async def test_entities_endpoint_and_unknown_scope(map_quiz_client):
    client, _ = map_quiz_client
    london = await client.get("/map-quiz/london_boroughs/entities")
    england = await client.get("/map-quiz/england_counties/entities")
    unknown = await client.get("/map-quiz/narnia/entities")

    assert london.status_code == 200 and len(london.json()) == 32
    assert england.status_code == 200 and len(england.json()) == 48
    assert unknown.status_code == 404


@pytest.mark.real_database
@pytest.mark.anyio
async def test_ten_rounds_guest_play_sync_points_and_leaderboard(map_quiz_client, participation_db):
    client, app = map_quiz_client
    async with participation_db() as session:
        session.add(UserPoints(user_id=1, points=50, streak=2))
        await session.commit()

    # Guest starts daily London boroughs quiz
    daily_resp = await client.get("/map-quiz/london_boroughs/daily")
    assert daily_resp.status_code == 200
    state = daily_resp.json()
    assert state["total_rounds"] == 10
    assert state["current_round"] == 1
    assert state["score"] == 0
    assert state["is_completed"] is False
    assert state["points"] is None
    assert state["current_target"] is not None

    entities = (await client.get("/map-quiz/london_boroughs/entities")).json()
    all_ids = [e["id"] for e in entities]

    # Play 10 rounds: 8 correct, 2 wrong
    for round_idx in range(1, 11):
        target_id = state["current_target"]["id"]
        if round_idx in (3, 7):
            clicked_id = next(eid for eid in all_ids if eid != target_id)
            expected_correct = False
        else:
            clicked_id = target_id
            expected_correct = True

        # Wrong round optimistic lock check on round 2
        if round_idx == 2:
            conflict = await client.post(
                "/map-quiz/london_boroughs/answer",
                json={"entity_id": clicked_id, "round": 1},
            )
            assert conflict.status_code == 409

        resp = await client.post(
            "/map-quiz/london_boroughs/answer",
            json={"entity_id": clicked_id, "round": round_idx},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["round"] == round_idx
        assert body["result"]["correct"] is expected_correct
        state = body["state"]

    assert state["is_completed"] is True
    assert state["score"] == 8
    assert len(state["answers"]) == 10
    assert state["current_target"] is None
    assert state["points"] is not None and state["points"] > 800

    # Extra answer after completion is rejected
    extra = await client.post(
        "/map-quiz/london_boroughs/answer",
        json={"entity_id": all_ids[0]},
    )
    assert extra.status_code == 400

    # Sign in and sync guest session -> claims session & awards UserPoints idempotently
    sign_in(app, user_id=1)
    sync_1 = await client.post("/map-quiz/london_boroughs/sync")
    sync_2 = await client.post("/map-quiz/london_boroughs/sync")
    assert sync_1.status_code == 200 and sync_2.status_code == 200
    assert sync_1.json()["score"] == 8
    assert sync_1.json()["points"] == sync_2.json()["points"]

    async with participation_db() as session:
        rows = (await session.scalars(select(MapQuizDailySession))).all()
        assert len(rows) == 1
        assert rows[0].user_id == 1
        user_points = await session.get(UserPoints, 1)
        assert user_points.points == 50 + sync_1.json()["points"]

    # Monthly leaderboard includes Alice; average requires >= 5 completed days
    monthly = await client.get("/map-quiz/london_boroughs/leaderboard?type=monthly")
    average = await client.get("/map-quiz/london_boroughs/leaderboard?type=average")
    assert monthly.status_code == 200
    assert len(monthly.json()) == 1
    assert monthly.json()[0]["username"] == "Alice"
    assert monthly.json()[0]["points"] == sync_1.json()["points"]
    assert monthly.json()[0]["wins"] == 1
    assert average.status_code == 200 and average.json() == []


@pytest.mark.real_database
@pytest.mark.anyio
async def test_england_counties_auth_play_and_invalid_entity(map_quiz_client):
    client, app = map_quiz_client
    sign_in(app, user_id=2)

    daily = (await client.get("/map-quiz/england_counties/daily")).json()
    assert daily["scope"] == "england_counties"
    assert daily["total_rounds"] == 10

    bad = await client.post(
        "/map-quiz/england_counties/answer",
        json={"entity_id": 999999},
    )
    assert bad.status_code == 400

    target_id = daily["current_target"]["id"]
    ok = await client.post(
        "/map-quiz/england_counties/answer",
        json={"entity_id": target_id, "round": 1},
    )
    assert ok.status_code == 200
    assert ok.json()["result"]["correct"] is True
    assert ok.json()["state"]["score"] == 1
    assert ok.json()["state"]["current_round"] == 2
