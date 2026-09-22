"""Real row-lock/commit regressions; use FRIEND_TEST_DATABASE_URL for an isolated schema."""
import asyncio
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models.friend_match import FriendAction, FriendAdvisory, FriendMatch, FriendMove, FriendReport, FriendSeat
from friend_matches import service, worker
from friend_matches.schemas import ActionRequest, CreateRequest, JoinRequest, ReviewRequest

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]
POLAND = {"id": "POL", "name": "Poland", "code": "PL"}
GERMANY = {"id": "DEU", "name": "Germany", "code": "DE"}


@pytest.fixture
async def duel_db(monkeypatch):
    url = os.getenv("FRIEND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set FRIEND_TEST_DATABASE_URL to exercise PostgreSQL locking in an isolated schema")
    schema = f"friend_test_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, pool_size=1, max_overflow=3,
                                 connect_args={"server_settings": {"search_path": schema}})
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=[
                model.__table__ for model in (FriendMatch, FriendSeat, FriendMove, FriendAction, FriendAdvisory, FriendReport)
            ]))
        monkeypatch.setattr(service, "AsyncSessionLocal", factory)
        monkeypatch.setattr(worker, "AsyncSessionLocal", factory)
        monkeypatch.setattr(service, "list_entities", lambda mode: [POLAND, GERMANY])
        monkeypatch.setenv("FRIEND_MATCHES_ENABLED", "true")
        yield factory
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


async def send(match_id, digest, kind, **payload):
    state = await service.get_snapshot(match_id, digest)
    action = ActionRequest(action_id=uuid4(), expected_version=state["version"], type=kind, payload=payload)
    return await service.apply_action(match_id, digest, action)


async def room():
    first, second = service.credential_hash("first"), service.credential_hash("second")
    state = await service.create_match(CreateRequest(name="First", mode="countrydle", request_id=uuid4()), first)
    await service.join_match(state["invite_code"], JoinRequest(name="Second", request_id=uuid4()), second)
    for digest in (first, second):
        await send(state["id"], digest, "select_secret", entity_id="POL")
        state = await send(state["id"], digest, "ready", ready=True)
    return state, first, second


async def test_duplicate_create_and_duplicate_moves_commit_only_once(duel_db):
    digest = service.credential_hash("creator")
    body = CreateRequest(name="Creator", mode="countrydle", request_id=uuid4())
    created = await asyncio.gather(*(service.create_match(body, digest) for _ in range(2)))
    assert created[0]["id"] == created[1]["id"]
    with pytest.raises(HTTPException) as exc:
        await service.create_match(body, service.credential_hash("intruder"))
    assert exc.value.status_code == 403
    state, first, _ = await room()
    action = ActionRequest(action_id=uuid4(), expected_version=state["version"], type="guess", payload={"entity_id": "DEU"})
    outcomes = await asyncio.gather(*(service.apply_action(state["id"], first, action) for _ in range(2)))
    assert outcomes[0]["version"] == outcomes[1]["version"]
    assert outcomes[0]["players"][0]["guess_count"] == 1
    changed = action.model_copy(update={"payload": {"entity_id": "POL"}})
    with pytest.raises(HTTPException) as exc:
        await service.apply_action(state["id"], first, changed)
    assert exc.value.status_code == 409
    async with duel_db() as session:
        count = await session.scalar(select(func.count()).select_from(FriendMove).where(FriendMove.match_id == state["id"]))
        assert count == 1


async def test_draw_acceptance_racing_reply_cannot_overwrite_terminal_result(duel_db):
    state, first, second = await room()
    state = await send(state["id"], first, "guess", entity_id="POL")
    state = await send(state["id"], first, "offer_draw")
    actions = [ActionRequest(action_id=uuid4(), expected_version=state["version"], type="accept_draw"),
               ActionRequest(action_id=uuid4(), expected_version=state["version"], type="guess", payload={"entity_id": "DEU"})]
    outcomes = await asyncio.gather(*(service.apply_action(state["id"], second, a) for a in actions), return_exceptions=True)
    assert sum(isinstance(result, dict) for result in outcomes) == 1
    assert sum(isinstance(result, HTTPException) for result in outcomes) == 1
    final = await service.get_snapshot(state["id"], first)
    committed = next(result for result in outcomes if isinstance(result, dict))
    assert final["status"] == "finished"
    assert (final["result"], final["winner_id"]) == (committed["result"], committed["winner_id"])


async def test_late_ai_is_private_persisted_and_never_changes_gameplay_version(duel_db, monkeypatch):
    state, first, second = await room()
    state = await send(state["id"], first, "ask", question="Is it in Europe?")
    question = state["pending_question_id"]
    claim = await worker.claim_job()
    entered, release = asyncio.Event(), asyncio.Event()

    async def evaluate(mode, entity, question):
        entered.set()
        await release.wait()
        return {"answer": "YES", "explanation": "Poland is in Europe.", "source": "test_evidence",
                "evidence": {"fact": "Europe", "target": "POL"}}

    monkeypatch.setattr(worker, "evaluate_question", evaluate)
    task = asyncio.create_task(worker.run_job(claim))
    try:
        await entered.wait()
        async with duel_db() as session:
            await session.execute(text("SELECT 1"))
        with pytest.raises(HTTPException) as exc:
            await send(state["id"], first, "answer", question_id=question, answer="yes")
        assert exc.value.status_code == 403
        answered = await send(state["id"], second, "answer", question_id=question, answer="mostly_yes")
        version = answered["version"]
        release.set()
        await task
        asker = await service.get_snapshot(state["id"], first)
        owner = await service.get_snapshot(state["id"], second)
        assert asker["guidance"] == [] and asker["reveals"] is None
        assert owner["guidance"][0]["late"] is True
        assert owner["guidance"][0]["answer"] == "YES"
        assert owner["version"] == version == asker["version"]
        assert owner["history"][0]["answer"] == "mostly_yes"
        assert (await service.admin_questions("all", None, 0, 30))["items"] == []
        await send(state["id"], second, "leave")
        review = (await service.admin_questions("not_comparable", None, 0, 30))["items"][0]
        assert review["ai"]["evidence"]["target"] == "POL"
        assert review["ai_seen_before_answer"] is False
    finally:
        release.set()
        await task


async def test_rematch_reuses_only_own_credential_and_has_one_fresh_successor(duel_db):
    state, first, second = await room()
    await send(state["id"], first, "leave")
    await send(state["id"], first, "rematch")
    state = await service.get_snapshot(state["id"], second)
    action = ActionRequest(action_id=uuid4(), expected_version=state["version"], type="rematch")
    outcomes = await asyncio.gather(*(service.apply_action(state["id"], second, action) for _ in range(2)))
    successor = outcomes[0]["rematch_id"]
    assert successor == outcomes[1]["rematch_id"]
    for digest in (first, second):
        new = await service.get_snapshot(successor, digest)
        assert new["own_secret"] is None and new["status"] == "lobby"
        assert new["history"] == []
        assert not any(p["ready"] for p in new["players"])
    with pytest.raises(HTTPException) as exc:
        await service.get_snapshot(successor, service.credential_hash("outsider"))
    assert exc.value.status_code == 403
    async with duel_db() as session:
        assert await session.scalar(select(func.count()).select_from(FriendMatch).where(FriendMatch.parent_id == state["id"])) == 1


async def test_abandoned_lease_is_honest_and_old_output_is_retained(duel_db):
    state, first, second = await room()
    state = await send(state["id"], first, "ask", question="Is it in Europe?")
    first_claim = await worker.claim_job()
    async with duel_db() as session, session.begin():
        job = await session.get(FriendAdvisory, first_claim["question_id"])
        job.lease_until = service.utcnow() - timedelta(seconds=1)
    replacement = await worker.claim_job()
    await worker.store_completion(first_claim, {"answer": "YES", "explanation": "Old real output", "source": "old", "evidence": {"attempt": 1}})
    async with duel_db() as session:
        job = await session.get(FriendAdvisory, first_claim["question_id"])
        assert job.status == "running" and job.answer is None
        assert job.attempts[0]["status"] == "interrupted"
        assert job.attempts[1]["superseded"] is True
        assert job.attempts[1]["result"]["evidence"] == {"attempt": 1}
    await worker.store_completion(replacement, error="ProviderUnavailable: connection refused")
    owner = await service.get_snapshot(state["id"], second)
    assert owner["guidance"][0]["status"] == "failed"
    assert owner["guidance"][0]["answer"] is None


async def test_retention_deletes_old_ordinary_but_keeps_reported_and_pending_evidence(duel_db):
    state, first, _ = await room()
    await send(state["id"], first, "leave")
    async with duel_db() as session, session.begin():
        old = await session.get(FriendMatch, state["id"])
        old.finished_at = service.utcnow() - timedelta(days=31)
    await worker.prune_evidence()
    with pytest.raises(HTTPException) as exc:
        await service.get_snapshot(state["id"], first)
    assert exc.value.status_code == 404

    state, first, second = await room()
    state = await send(state["id"], first, "ask", question="Is it in Europe?")
    question = state["pending_question_id"]
    await send(state["id"], second, "answer", question_id=question, answer="yes")
    await send(state["id"], first, "leave")
    async with duel_db() as session, session.begin():
        match = await session.get(FriendMatch, state["id"])
        match.finished_at = service.utcnow() - timedelta(days=120)
    await worker.prune_evidence()
    assert (await service.get_snapshot(state["id"], first))["status"] == "finished"
    claim = await worker.claim_job()
    await worker.store_completion(claim, error="ProviderUnavailable")
    await service.report_question(state["id"], question, first, "Please review the source")
    await worker.prune_evidence()
    assert (await service.get_snapshot(state["id"], first))["status"] == "finished"


async def test_bootstrap_survives_lost_create_join_responses_without_seat_theft(duel_db):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from friend_matches.routes import COOKIE_NAME, router

    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    headers = {"Origin": "http://test"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as owner, \
            AsyncClient(transport=transport, base_url="http://test", headers=headers) as guest, \
            AsyncClient(transport=transport, base_url="http://test", headers=headers) as outsider:
        body = {"name": "Owner", "mode": "countrydle", "request_id": str(uuid4())}
        missing = await owner.post("/friend-matches", json=body)
        assert missing.status_code == 409
        assert missing.json()["detail"]["code"] == "friend_session_required"
        async with duel_db() as session:
            assert await session.scalar(select(func.count()).select_from(FriendMatch)) == 0
        bootstrap = await owner.post("/friend-matches/session")
        assert bootstrap.json() == {"ready": True}
        original_cookie = owner.cookies.get(COOKIE_NAME)
        await owner.post("/friend-matches/session")
        assert owner.cookies.get(COOKIE_NAME) == original_cookie

        # Discard the first admission response: possession was established before it.
        first = await owner.post("/friend-matches", json=body)
        assert first.status_code == 200
        assert "set-cookie" not in first.headers
        repeated = await owner.post("/friend-matches", json=body)
        assert repeated.status_code == 200
        assert repeated.json()["id"] == first.json()["id"]
        room = repeated.json()
        join_path = f"/friend-matches/invites/{room['invite_code']}/join"
        join_body = {"name": "Guest", "request_id": str(uuid4())}
        assert (await guest.post(join_path, json=join_body)).status_code == 409
        await guest.post("/friend-matches/session")
        joined = await guest.post(join_path, json=join_body)
        assert joined.status_code == 200 and "set-cookie" not in joined.headers
        replayed = await guest.post(join_path, json=join_body)
        assert replayed.status_code == 200 and replayed.json()["you"] == joined.json()["you"]
        assert joined.json()["you"] != room["you"]

        await outsider.post("/friend-matches/session")
        assert (await outsider.post("/friend-matches", json=body)).status_code == 403
        assert (await outsider.get(f"/friend-matches/{room['id']}")).status_code == 403
        assert (await outsider.post(join_path, json=join_body)).status_code == 409
        async with duel_db() as session:
            assert await session.scalar(select(func.count()).select_from(FriendMatch)) == 1
            assert await session.scalar(select(func.count()).select_from(FriendSeat)) == 2
