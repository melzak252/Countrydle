"""Daily Powiat map quiz persistence against an explicitly disposable PostgreSQL schema."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from db import get_db
from db.models.powiat import Powiat
from db.models.powiat_map_quiz import PowiatMapQuizSession
from tests.test_guest_participation import participation_db
from users.utils import get_current_or_guest_user, get_current_user

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]


TODAY = date(2026, 6, 1)


@pytest.fixture
async def map_quiz_client(participation_db, monkeypatch):
    from powiatdle import map_quiz

    async with participation_db() as session:
        connection = await session.connection()
        await connection.run_sync(lambda conn: Powiat.__table__.create(conn))
        await connection.run_sync(lambda conn: PowiatMapQuizSession.__table__.create(conn))
        session.add_all([Powiat(id=i, nazwa=f"Powiat {i}") for i in range(1, 13)])
        await session.commit()

    monkeypatch.setattr(map_quiz, "utc_today", lambda: TODAY)
    app = FastAPI()
    app.state.player = None
    app.include_router(map_quiz.router, prefix="/powiatdle")

    async def db_override():
        async with participation_db() as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_or_guest_user] = lambda: app.state.player
    app.dependency_overrides[get_current_user] = lambda: app.state.player
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        yield client, app, map_quiz


async def session_row(participation_db, *, user_id=None):
    async with participation_db() as session:
        statement = select(PowiatMapQuizSession)
        if user_id is not None:
            statement = statement.where(PowiatMapQuizSession.user_id == user_id)
        return (await session.scalars(statement)).one()


async def answer_all(client, targets):
    result = None
    for round_index, target in enumerate(targets):
        result = await client.post(
            "/powiatdle/map-quiz/daily/answer",
            json={"guess_id": target["id"], "expected_round": round_index},
        )
        assert result.status_code == 200, result.text
    return result.json()


async def test_daily_sequence_is_shared_and_only_current_target_is_exposed(map_quiz_client, participation_db):
    client, app, _ = map_quiz_client
    guest = await client.get("/powiatdle/map-quiz/daily")
    assert guest.status_code == 200, guest.text
    guest_state = guest.json()
    assert guest_state["date"] == TODAY.isoformat()
    assert guest_state["round_count"] == 10
    assert guest_state["expected_round"] == 0
    assert isinstance(guest_state["current_target"], str)
    assert guest_state["score"] == 0
    assert guest_state["is_complete"] is False
    assert guest_state["answers"] == []
    assert "targets" not in guest_state

    guest_row = await session_row(participation_db)
    assert len(guest_row.targets) == 10
    assert len({target["id"] for target in guest_row.targets}) == 10
    client.cookies.clear()
    app.state.player = SimpleNamespace(id=1, username="Alice")
    account = await client.get("/powiatdle/map-quiz/daily")
    assert account.status_code == 200, account.text
    account_row = await session_row(participation_db, user_id=1)
    assert account_row.targets == guest_row.targets
    assert account.json()["current_target"] == guest_state["current_target"]
    assert account.json()["expected_round"] == 0
    app.state.player = SimpleNamespace(id=2, username="Bob")
    another_account = await client.get("/powiatdle/map-quiz/daily")
    assert another_account.status_code == 200, another_account.text
    another_account_row = await session_row(participation_db, user_id=2)
    assert another_account_row.targets == guest_row.targets
    assert another_account.json()["current_target"] == guest_state["current_target"]
    client.cookies.clear()
    app.state.player = None
    another_guest = await client.get("/powiatdle/map-quiz/daily")
    assert another_guest.status_code == 200, another_guest.text
    async with participation_db() as session:
        rows = (
            await session.scalars(
                select(PowiatMapQuizSession).where(PowiatMapQuizSession.date == TODAY)
            )
        ).all()
    assert len(rows) == 4
    assert all(row.targets == guest_row.targets for row in rows)
    assert another_guest.json()["current_target"] == guest_state["current_target"]


async def test_answer_is_server_scored_idempotent_and_conflicting_replay_is_rejected(map_quiz_client, participation_db):
    client, _, _ = map_quiz_client
    start = await client.get("/powiatdle/map-quiz/daily")
    assert start.status_code == 200, start.text
    row = await session_row(participation_db)
    target = row.targets[0]
    body = {"guess_id": target["id"], "expected_round": 0}

    first = await client.post("/powiatdle/map-quiz/daily/answer", json=body)
    assert first.status_code == 200, first.text
    first_result = first.json()
    assert first_result["last_answer"] == {"round": 0, "guess_id": target["id"], "correct": True}
    assert first_result["score"] == 1
    assert first_result["expected_round"] == 1
    assert first_result["current_target"] == row.targets[1]["name"]

    replay = await client.post("/powiatdle/map-quiz/daily/answer", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["score"] == 1
    assert replay.json()["expected_round"] == 1
    assert len(replay.json()["answers"]) == 1

    conflicting = await client.post(
        "/powiatdle/map-quiz/daily/answer",
        json={"guess_id": row.targets[2]["id"], "expected_round": 0},
    )
    assert conflicting.status_code == 409
    future = await client.post(
        "/powiatdle/map-quiz/daily/answer",
        json={"guess_id": row.targets[1]["id"], "expected_round": 2},
    )
    assert future.status_code == 409


async def test_guest_and_account_history_are_owner_scoped_and_claimable(map_quiz_client, participation_db):
    client, app, _ = map_quiz_client
    started = await client.get("/powiatdle/map-quiz/daily")
    assert started.status_code == 200, started.text
    guest_row = await session_row(participation_db)
    completed = await answer_all(client, guest_row.targets)
    assert completed["is_complete"] is True
    assert completed["score"] == 10

    guest_history = await client.get("/powiatdle/map-quiz/history")
    assert guest_history.status_code == 200, guest_history.text
    assert guest_history.json()["total"] == 1
    assert guest_history.json()["items"][0]["score"] == 10
    assert guest_history.json()["items"][0]["answers"][0]["target_name"] == guest_row.targets[0]["name"]

    app.state.player = SimpleNamespace(id=1, username="Alice")
    claim = await client.post("/powiatdle/map-quiz/daily/claim", json={})
    assert claim.status_code == 200, claim.text
    assert claim.json()["score"] == 10
    account_history = await client.get("/powiatdle/map-quiz/history")
    assert account_history.status_code == 200, account_history.text
    assert account_history.json()["total"] == 1
    async with participation_db() as session:
        claimed = await session.get(PowiatMapQuizSession, guest_row.id)
        assert claimed.user_id == 1 and claimed.guest_id is None


async def test_daily_stats_are_aggregate_only_and_hide_small_cohorts(map_quiz_client, participation_db):
    client, _, _ = map_quiz_client
    row = await client.get("/powiatdle/map-quiz/daily")
    assert row.status_code == 200, row.text
    template = await session_row(participation_db)
    await answer_all(client, template.targets)
    one = await client.get("/powiatdle/map-quiz/daily/stats")
    assert one.status_code == 200, one.text
    assert one.json() == {
        "date": TODAY.isoformat(),
        "completed_count": None,
        "average_score": None,
        "score_distribution": None,
    }

    async with participation_db() as session:
        completed_row = await session.get(PowiatMapQuizSession, template.id)
        await session.delete(completed_row)
        await session.commit()

    now = datetime.now(timezone.utc)
    scores = [4, 6, 8, 8, 9]
    async with participation_db() as session:
        session.add_all([
            PowiatMapQuizSession(
                id=str(uuid4()), date=TODAY,
                user_id=(index + 1 if index < 2 else None),
                guest_id=None if index < 2 else str(uuid4()),
                targets=template.targets,
                answers=[
                    {"round": round_index, "guess_id": target["id"], "correct": round_index < score}
                    for round_index, target in enumerate(template.targets)
                ],
                score=score, started_at=now, completed_at=now,
            )
            for index, score in enumerate(scores)
        ])
        await session.commit()

    aggregate = await client.get("/powiatdle/map-quiz/daily/stats")
    assert aggregate.status_code == 200, aggregate.text
    assert aggregate.json() == {
        "date": TODAY.isoformat(),
        "completed_count": 5,
        "average_score": 7.0,
        "score_distribution": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 1,
                               "5": 0, "6": 1, "7": 0, "8": 2, "9": 1, "10": 0},
    }


async def test_utc_day_change_starts_new_run_and_keeps_previous_history(map_quiz_client, participation_db, monkeypatch):
    client, _, map_quiz = map_quiz_client
    first_day = await client.get("/powiatdle/map-quiz/daily")
    assert first_day.status_code == 200, first_day.text
    first_row = await session_row(participation_db)
    await answer_all(client, first_row.targets)

    next_date = date(2026, 6, 2)
    monkeypatch.setattr(map_quiz, "utc_today", lambda: next_date)
    next_day = await client.get("/powiatdle/map-quiz/daily")
    assert next_day.status_code == 200, next_day.text
    assert next_day.json()["date"] == next_date.isoformat()
    assert next_day.json()["expected_round"] == 0
    assert next_day.json()["score"] == 0

    history = await client.get("/powiatdle/map-quiz/history")
    assert history.status_code == 200, history.text
    assert [item["date"] for item in history.json()["items"]] == [TODAY.isoformat()]
