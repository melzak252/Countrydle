import sqlite3
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db import get_db
from db.base import Base
from db.models.heraldry_quiz import QuizRun, QuizSolve
from db.models.user import User
from powiatdle.plates_quiz import router as plates_quiz_router
from users.utils import get_current_or_guest_user

BASE = '/powiatdle/plates/quiz'


def _build_test_plates_db(path):
    """Build a small representative powiat_facts.sqlite with multi-code and shared-code powiaty."""
    powiats = [
        (1, 'Biała Podlaska', 'lubelskie', 1),
        (24, 'Kraków', 'małopolskie', 1),
        (165, 'Powiat krakowski', 'małopolskie', 0),
        (195, 'Powiat miński', 'mazowieckie', 0),
        (320, 'Powiat wałbrzyski', 'dolnośląskie', 0),
        (369, 'Warszawa', 'mazowieckie', 1),
        (370, 'Wałbrzych', 'dolnośląskie', 1),
    ]
    plates = [
        (1, 'LB'),
        (24, 'KR'),
        (24, 'KK'),
        (24, 'JK'),
        (24, 'JR'),
        (165, 'KRA'),
        (165, 'JRA'),
        (195, 'WM'),
        (195, 'WY'),
        (195, 'YY'),
        (320, 'DB'),
        (320, 'DBA'),
        (369, 'WA'),
        (369, 'WB'),
        (369, 'WD'),
        (369, 'WE'),
        (369, 'WF'),
        (369, 'WH'),
        (369, 'WI'),
        (369, 'WJ'),
        (369, 'WK'),
        (369, 'WN'),
        (369, 'WT'),
        (369, 'WU'),
        (369, 'WW'),
        (369, 'WX'),
        (369, 'WY'),
        (370, 'DB'),
    ]
    with sqlite3.connect(path) as conn:
        conn.execute(
            'CREATE TABLE powiats (id INTEGER PRIMARY KEY, name TEXT, voivodeship TEXT, is_city_county INTEGER)'
        )
        conn.execute(
            'CREATE TABLE powiat_registration_plates (powiat_id INTEGER NOT NULL, plate_code TEXT NOT NULL, PRIMARY KEY (powiat_id, plate_code))'
        )
        conn.executemany('INSERT INTO powiats VALUES (?, ?, ?, ?)', powiats)
        conn.executemany('INSERT INTO powiat_registration_plates VALUES (?, ?)', plates)


@pytest_asyncio.fixture
async def plates_client(tmp_path, monkeypatch):
    facts_path = tmp_path / 'powiat_facts.sqlite'
    _build_test_plates_db(facts_path)
    monkeypatch.setattr('powiatdle.plates_quiz.get_db_path', lambda: facts_path)

    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=[User.__table__, QuizRun.__table__, QuizSolve.__table__]
            )
        )

    app = FastAPI()
    app.state.quiz_factory = factory
    app.include_router(plates_quiz_router, prefix='/powiatdle')

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = session_override

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, app
    finally:
        await engine.dispose()


async def start_run(client) -> str:
    res = await client.post(f'{BASE}/runs', json={})
    assert res.status_code == 200
    return res.json()['run_id']


def finish_body(solves, status='given_up', elapsed=30.0):
    return {'status': status, 'elapsed_seconds': elapsed, 'solves': solves}


def solve_event(ids, answer, elapsed):
    return {'powiat_ids': ids, 'answer': answer, 'elapsed_seconds': elapsed}


@pytest.mark.asyncio
async def test_run_creation_and_multi_code_and_shared_code_solves(plates_client):
    client, app = plates_client
    run_id = await start_run(client)

    body = finish_body(
        [
            solve_event([369], 'wx', 4.0),          # Warszawa via one of its 15 codes (lowercase normalized)
            solve_event([320, 370], 'DB', 9.0),     # Shared code DB solves both Wałbrzych and Powiat wałbrzyski
            solve_event([24], ' kr ', 12.0),        # Multi-code Kraków with whitespace
            solve_event([165], 'KRA', 16.0),        # 3-letter prefix-colliding code
        ],
        status='given_up',
        elapsed=20.0,
    )
    res = await client.post(f'{BASE}/runs/{run_id}/finish', json=body)
    assert res.status_code == 200
    assert res.json() == {'run_id': run_id, 'status': 'given_up', 'solved_count': 5}

    async with app.state.quiz_factory() as session:
        saved = await session.get(QuizRun, run_id)
        assert saved.symbol_mode == 'plates'
        assert saved.entity_scope == 'county'
        assert saved.solved_count == 5


@pytest.mark.asyncio
async def test_shared_code_wy_solves_warszawa_and_minski(plates_client):
    client, _ = plates_client
    run_id = await start_run(client)
    res = await client.post(
        f'{BASE}/runs/{run_id}/finish',
        json=finish_body([solve_event([195, 369], 'WY', 5.0)], status='given_up', elapsed=10.0),
    )
    assert res.status_code == 200
    assert res.json()['solved_count'] == 2


@pytest.mark.asyncio
async def test_invalid_plate_finishes_rejected_without_finishing_run(plates_client):
    client, _ = plates_client
    run_id = await start_run(client)

    invalid_payloads = [
        finish_body([solve_event([1], 'WA', 2.0)]),                                          # wrong code for Biała Podlaska
        finish_body([solve_event([369], 'WA', 2.0), solve_event([369], 'WB', 4.0)]),          # duplicate powiat with another valid code
        finish_body([solve_event([1, 1], 'LB', 2.0)]),                                        # duplicate ID in same event
        finish_body([solve_event([1], 'LB', 8.0), solve_event([24], 'KR', 5.0)]),             # non-monotonic elapsed_seconds
        finish_body([solve_event([1], 'LB', 35.0)], elapsed=30.0),                            # solve elapsed > run elapsed
        finish_body([solve_event([999], 'LB', 2.0)]),                                         # unknown powiat_id
        finish_body([solve_event([1], 'LB', 2.0)], status='completed'),                       # incomplete completed run
        finish_body([solve_event([1], '   ', 2.0)]),                                          # empty after normalization
    ]
    for payload in invalid_payloads:
        res = await client.post(f'{BASE}/runs/{run_id}/finish', json=payload)
        assert res.status_code == 422

    nonfinite = await client.post(
        f'{BASE}/runs/{run_id}/finish',
        content='{"status":"given_up","elapsed_seconds":NaN,"solves":[]}',
        headers={'content-type': 'application/json'},
    )
    assert nonfinite.status_code == 422

    # Run is still started and can be finished cleanly
    stats_before = (await client.get(f'{BASE}/stats')).json()
    assert stats_before['finished_runs'] == 0
    ok = await client.post(f'{BASE}/runs/{run_id}/finish', json=finish_body([], status='given_up', elapsed=5.0))
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_completed_requires_all_catalog_powiats(plates_client):
    client, _ = plates_client
    run_id = await start_run(client)
    all_solves = [
        solve_event([1], 'LB', 2.0),
        solve_event([24], 'KR', 4.0),
        solve_event([165], 'KRA', 6.0),
        solve_event([195, 369], 'WY', 8.0),
        solve_event([320, 370], 'DB', 10.0),
    ]
    res = await client.post(
        f'{BASE}/runs/{run_id}/finish',
        json=finish_body(all_solves, status='completed', elapsed=12.0),
    )
    assert res.status_code == 200
    assert res.json() == {'run_id': run_id, 'status': 'completed', 'solved_count': 7}


@pytest.mark.asyncio
async def test_replay_idempotency_conflict_and_owner_isolation(plates_client):
    client, app = plates_client
    run_id = await start_run(client)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as stranger:
        stranger_res = await stranger.post(f'{BASE}/runs/{run_id}/finish', json=finish_body([]))
        assert stranger_res.status_code == 404

    body = finish_body([solve_event([1], 'LB', 5.0)], status='given_up', elapsed=10.0)
    first = await client.post(f'{BASE}/runs/{run_id}/finish', json=body)
    assert first.status_code == 200

    # Exact replay is idempotent
    replay = await client.post(f'{BASE}/runs/{run_id}/finish', json=body)
    assert replay.status_code == 200
    assert replay.json() == first.json()

    # Conflicting replay returns 409
    conflict = await client.post(
        f'{BASE}/runs/{run_id}/finish',
        json=finish_body([solve_event([24], 'KR', 5.0)], status='given_up', elapsed=10.0),
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_guest_run_claim_on_login(plates_client):
    client, app = plates_client
    async with app.state.quiz_factory() as session:
        user = User(email='plates-owner@example.com')
        session.add(user)
        await session.commit()
        user_id = user.id

    run_id = await start_run(client)
    app.dependency_overrides[get_current_or_guest_user] = lambda: SimpleNamespace(id=user_id)
    res = await client.post(
        f'{BASE}/runs/{run_id}/finish',
        json=finish_body([solve_event([1], 'LB', 3.0)], status='given_up', elapsed=5.0),
    )
    assert res.status_code == 200
    async with app.state.quiz_factory() as session:
        saved = await session.get(QuizRun, run_id)
        assert saved.user_id == user_id
        assert saved.guest_id is None


@pytest.mark.asyncio
async def test_stats_aggregation_excludes_abandoned_and_other_modes(plates_client):
    client, app = plates_client
    initial = (await client.get(f'{BASE}/stats')).json()
    assert initial['finished_runs'] == 0
    assert initial['tracking_started_at'] is None
    assert len(initial['powiats']) == 7

    # Abandoned plates run (status='started') must not count
    await start_run(client)

    # Another symbol_mode ('coat') must not leak into plates stats
    async with app.state.quiz_factory() as session:
        other_run = QuizRun(
            guest_id='other-mode-guest',
            status='given_up',
            solved_count=1,
            symbol_mode='coat',
            entity_scope='county',
            elapsed_seconds=10.0,
        )
        session.add(other_run)
        await session.flush()
        session.add(QuizSolve(run_id=other_run.id, powiat_id=1, elapsed_seconds=5.0))
        await session.commit()

    run1 = await start_run(client)
    assert (
        await client.post(
            f'{BASE}/runs/{run1}/finish',
            json=finish_body([solve_event([320, 370], 'DB', 6.0), solve_event([1], 'LB', 10.0)], elapsed=15.0),
        )
    ).status_code == 200

    run2 = await start_run(client)
    assert (
        await client.post(
            f'{BASE}/runs/{run2}/finish',
            json=finish_body([solve_event([370], 'DB', 14.0)], elapsed=20.0),
        )
    ).status_code == 200

    stats = (await client.get(f'{BASE}/stats')).json()
    assert stats['finished_runs'] == 2
    assert stats['tracking_started_at'] is not None
    by_id = {p['powiat_id']: p for p in stats['powiats']}
    assert by_id[370]['solved_count'] == 2
    assert by_id[370]['average_active_seconds'] == 10.0
    assert by_id[320]['solved_count'] == 1
    assert by_id[320]['average_active_seconds'] == 6.0
    assert by_id[1]['solved_count'] == 1
    assert by_id[1]['average_active_seconds'] == 10.0
    assert by_id[24]['solved_count'] == 0
    assert by_id[24]['average_active_seconds'] is None
