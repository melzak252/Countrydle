import asyncio
import os
import sqlite3
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db import get_db
from db.base import Base
from db.models.user import User
from db.models.heraldry_quiz import QuizRun, QuizSolve
from powiatdle.heraldry_quiz import router, flags_quiz_router, regional_quiz_router

CATALOG = {id_: f'Powiat Testowy {id_}' for id_ in range(1, 381)}
CATALOG.update({
    1: 'Biała Podlaska', 2: 'Białystok', 3: 'Powiat dąbrowski (małopolski)',
    44: 'Powiat bielski', 45: 'Powiat bielski',
})

pytestmark = pytest.mark.real_database


@pytest_asyncio.fixture(loop_scope='function')
async def quiz_client(tmp_path, monkeypatch):
    url = os.getenv('HERALDRY_QUIZ_TEST_DATABASE_URL') or os.getenv('PROFILE_STATS_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set HERALDRY_QUIZ_TEST_DATABASE_URL to a disposable PostgreSQL database')
    schema = 'quiz_' + uuid4().hex
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    facts = tmp_path / 'powiat_facts.sqlite'
    with sqlite3.connect(facts) as conn:
        conn.execute('CREATE TABLE powiats (id INTEGER, name TEXT, voivodeship TEXT, is_city_county INTEGER, latitude REAL, longitude REAL)')
        conn.executemany('INSERT INTO powiats VALUES (?, ?, ?, 0, NULL, NULL)',
                         [(id_, name, 'test') for id_, name in CATALOG.items()])
    monkeypatch.setattr('powiatdle.heraldry.get_db_path', lambda: facts)
    app_factory = factory
    app = FastAPI()
    app.state.quiz_factory = app_factory
    app.include_router(router, prefix='/powiatdle/heraldry')
    app.include_router(flags_quiz_router, prefix='/powiatdle/flags')
    app.include_router(regional_quiz_router, prefix='/regional-symbols/{scope}/{mode}')
    monkeypatch.setattr('powiatdle.flag_catalog.load_catalog',
                        lambda: {id_: {'id': id_} for id_ in (1, 3)})

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = session_override
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: Base.metadata.create_all(
                conn, tables=[User.__table__, QuizRun.__table__, QuizSolve.__table__]))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, app
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        await bootstrap.dispose()


BASE = '/powiatdle/heraldry/quiz'
FLAGS = '/powiatdle/flags/quiz'


async def start(client):
    response = await client.post(BASE + '/runs', json={})
    assert response.status_code == 200
    return response.json()['run_id']


def result(solves, status='given_up', elapsed=20):
    return {'status': status, 'elapsed_seconds': elapsed, 'solves': solves}


def solve(ids, answer, elapsed):
    return {'powiat_ids': ids, 'answer': answer, 'elapsed_seconds': elapsed}


@pytest.mark.asyncio
async def test_aggregate_excludes_abandoned_and_uses_active_time_for_each_matching_coat(quiz_client):
    client, _ = quiz_client
    initial = (await client.get(BASE + '/stats')).json()
    assert initial['finished_runs'] == 0 and initial['tracking_started_at'] is None
    assert len(initial['coats']) == 380
    assert all(c['solved_count'] == 0 and c['average_active_seconds'] is None for c in initial['coats'])
    await start(client)
    run = await start(client)
    body = result([solve([44, 45], 'Pow. BIELSKI', 5), solve([1], 'miasto Biala-Podlaska', 10)])
    finished = await client.post(f'{BASE}/runs/{run}/finish', json=body)
    assert finished.json() == {'run_id': run, 'status': 'given_up', 'solved_count': 3}
    run2 = await start(client)
    assert (await client.post(f'{BASE}/runs/{run2}/finish', json=result([solve([44], 'bielski', 15)]))).status_code == 200
    stats = (await client.get(BASE + '/stats')).json()
    assert stats['finished_runs'] == 2
    assert stats['tracking_started_at'] is not None
    coats = {c['powiat_id']: c for c in stats['coats']}
    assert coats[44]['solved_count'] == 2 and coats[44]['average_active_seconds'] == 10
    assert coats[45]['solved_count'] == 1 and coats[45]['average_active_seconds'] == 5
    assert coats[1]['average_active_seconds'] == 10
    assert coats[2]['solved_count'] == 0 and coats[2]['average_active_seconds'] is None


@pytest.mark.asyncio
async def test_owner_isolation_idempotence_and_conflicting_concurrent_finishes(quiz_client):
    client, app = quiz_client
    run = await start(client)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as stranger:
        assert (await stranger.post(f'{BASE}/runs/{run}/finish', json=result([]))).status_code == 404
    body = result([solve([1], 'm biala podlaska', 5)])
    first, second = await asyncio.gather(*(client.post(f'{BASE}/runs/{run}/finish', json=body) for _ in range(2)))
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert (await client.post(f'{BASE}/runs/{run}/finish', json=result([]))).status_code == 409
    assert (await client.get(BASE + '/stats')).json()['finished_runs'] == 1
    other = await start(client)
    a, b = await asyncio.gather(
        client.post(f'{BASE}/runs/{other}/finish', json=result([solve([1], 'Biała Podlaska', 5)])),
        client.post(f'{BASE}/runs/{other}/finish', json=result([solve([2], 'Białystok', 5)])),
    )
    assert sorted((a.status_code, b.status_code)) == [200, 409]


@pytest.mark.asyncio
async def test_invalid_events_do_not_finish_run(quiz_client):
    client, _ = quiz_client
    run = await start(client)
    invalid = [
        result([solve([1], 'Białystok', 1)]),
        result([solve([1, 1], 'Biała Podlaska', 1)]),
        result([solve([1], 'Biała Podlaska', 2), solve([2], 'Białystok', 1)]),
        result([solve([1], 'Biała Podlaska', 21)]),
        result([solve([1], 'Biała Podlaska', -1)]),
        result([solve([999], 'Biała Podlaska', 1)]),
        result([solve([1], 'Biała Podlaska', 1)], status='completed'),
        result([solve([1], 'Biała Podlaska', 1)] * 381),
        result([solve(list(range(381)), 'Biała Podlaska', 1)]),
        result([solve([1], 'x' * 201, 1)]),
        result([solve([], 'Biała Podlaska', 1)]),
    ]
    for body in invalid:
        assert (await client.post(f'{BASE}/runs/{run}/finish', json=body)).status_code == 422
    nonfinite = await client.post(f'{BASE}/runs/{run}/finish',
                                  content='{\"status\":\"given_up\",\"elapsed_seconds\":NaN,\"solves\":[]}',
                                  headers={'content-type': 'application/json'})
    assert nonfinite.status_code == 422
    assert (await client.get(BASE + '/stats')).json()['finished_runs'] == 0
    assert (await client.post(f'{BASE}/runs/{run}/finish', json=result([]))).status_code == 200


@pytest.mark.asyncio
async def test_parenthetical_and_city_aliases_are_accepted(quiz_client):
    client, _ = quiz_client
    run = await start(client)
    body = result([solve([3], 'pow dabrowski', 3), solve([1], 'm biala-podlaska', 5)])
    response = await client.post(f'{BASE}/runs/{run}/finish', json=body)
    assert response.status_code == 200 and response.json()['solved_count'] == 2


@pytest.mark.asyncio
async def test_completed_requires_and_accepts_entire_catalog(quiz_client):
    client, _ = quiz_client
    run = await start(client)
    solves = [solve([id_], name, i) for i, (id_, name) in enumerate(CATALOG.items())]
    response = await client.post(f'{BASE}/runs/{run}/finish', json=result(solves, 'completed', 380))
    assert response.status_code == 200
    assert response.json()['solved_count'] == 380




@pytest.mark.asyncio
async def test_signed_account_and_guest_cannot_finish_each_others_runs(quiz_client, monkeypatch):
    from jose import jwt
    from users import utils as auth

    client, app = quiz_client
    monkeypatch.setattr(auth, 'SECRET_KEY', 'quiz-test-secret')
    monkeypatch.setattr(auth, 'ALGORITHM', 'HS256')
    async with app.state.quiz_factory() as session:
        session.add(User(email='quiz@example.test'))
        await session.commit()
    guest_run = await start(client)
    token = jwt.encode({'sub': 'quiz@example.test'}, auth.SECRET_KEY, algorithm=auth.ALGORITHM)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                 cookies={'access_token': token}) as account:
        account_run = await start(account)
        assert (await account.post(f'{BASE}/runs/{guest_run}/finish', json=result([]))).status_code == 404
        assert (await client.post(f'{BASE}/runs/{account_run}/finish', json=result([]))).status_code == 404
        assert (await account.post(f'{BASE}/runs/{account_run}/finish', json=result([]))).status_code == 200


@pytest.mark.asyncio
async def test_guest_run_can_finish_after_owner_logs_in(quiz_client):
    from types import SimpleNamespace
    from users.utils import get_current_or_guest_user

    client, app = quiz_client
    async with app.state.quiz_factory() as session:
        user = User(email='quiz-owner@example.com')
        session.add(user)
        await session.commit()
        user_id = user.id
    run = await start(client)
    app.dependency_overrides[get_current_or_guest_user] = lambda: SimpleNamespace(id=user_id)
    response = await client.post(f'{BASE}/runs/{run}/finish', json=result([solve([1], 'Biała Podlaska', 5)]))
    assert response.status_code == 200 and response.json()['solved_count'] == 1
    async with app.state.quiz_factory() as session:
        saved = await session.get(QuizRun, run)
        assert saved.user_id == user_id and saved.guest_id is None


@pytest.mark.asyncio
async def test_flag_subset_validation_completion_and_mode_isolation(quiz_client):
    client, app = quiz_client
    flag_run = (await client.post(FLAGS + '/runs', json={})).json()['run_id']
    coat_run = await start(client)
    assert (await client.post(f'{BASE}/runs/{flag_run}/finish', json=result([]))).status_code == 404
    assert (await client.post(f'{FLAGS}/runs/{coat_run}/finish', json=result([]))).status_code == 404
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as stranger:
        assert (await stranger.post(f'{FLAGS}/runs/{flag_run}/finish', json=result([]))).status_code == 404
    for invalid in (
        result([solve([2], 'Białystok', 1)]),
        result([solve([1], 'Białystok', 1)]),
        result([solve([1], 'Biała Podlaska', 1)], status='completed'),
    ):
        assert (await client.post(f'{FLAGS}/runs/{flag_run}/finish', json=invalid)).status_code == 422
    body = result([solve([1], 'm biala podlaska', 5), solve([3], 'pow dabrowski', 10)], 'completed')
    first = await client.post(f'{FLAGS}/runs/{flag_run}/finish', json=body)
    assert first.status_code == 200 and first.json()['solved_count'] == 2
    assert (await client.post(f'{FLAGS}/runs/{flag_run}/finish', json=body)).json() == first.json()
    assert (await client.post(f'{FLAGS}/runs/{flag_run}/finish', json=result([]))).status_code == 409
    assert (await client.post(f'{BASE}/runs/{coat_run}/finish', json=result([solve([1], 'Biała Podlaska', 15)]))).status_code == 200
    flags = (await client.get(FLAGS + '/stats')).json()
    coats = (await client.get(BASE + '/stats')).json()
    assert flags['finished_runs'] == coats['finished_runs'] == 1
    assert {item['powiat_id'] for item in flags['flags']} == {1, 3}
    assert flags['flags'][0]['average_active_seconds'] == 5
    assert coats['coats'][0]['average_active_seconds'] == 15
    async with app.state.quiz_factory() as session:
        saved = await session.get(QuizRun, flag_run)
        assert saved.symbol_mode == 'flag' and saved.elapsed_seconds == 20


@pytest.mark.asyncio
async def test_flag_stats_exclude_started_runs_and_average_only_solves(quiz_client):
    client, _ = quiz_client
    await client.post(FLAGS + '/runs', json={})
    for solves in ([solve([1], 'Biała Podlaska', 5)], [], [solve([1], 'Biała Podlaska', 15)]):
        run = (await client.post(FLAGS + '/runs', json={})).json()['run_id']
        assert (await client.post(f'{FLAGS}/runs/{run}/finish', json=result(solves))).status_code == 200
    stats = (await client.get(FLAGS + '/stats')).json()
    assert stats['finished_runs'] == 3
    assert stats['flags'][0]['solved_count'] == 2
    assert stats['flags'][0]['average_active_seconds'] == 10


@pytest.mark.asyncio
async def test_empty_flag_catalog_returns_unavailable(quiz_client, monkeypatch):
    client, _ = quiz_client
    monkeypatch.setattr('powiatdle.flag_catalog.load_catalog', lambda: {})
    assert (await client.post(FLAGS + '/runs', json={})).status_code == 503
    assert (await client.get(FLAGS + '/stats')).status_code == 503


@pytest.mark.asyncio
async def test_regional_quiz_completion_and_stats_are_isolated_by_scope_and_mode(quiz_client, monkeypatch, tmp_path):
    from regional_symbols import catalog
    from tests.test_regional_symbols_api import _write_scope

    client, _ = quiz_client
    _write_scope(tmp_path, 'voivodeships', [('Alpha', 'Álpha district'), ('Beta', 'Beta'), ('Gamma', 'Gamma')])
    _write_scope(tmp_path, 'london_boroughs', [('London', 'London'), ('Brent', 'Brent'), ('Camden', 'Camden')])
    monkeypatch.setattr(catalog, 'DATA_ROOT', tmp_path)
    catalog.clear_caches()
    try:
        base = '/regional-symbols/voivodeships/coat/quiz'
        other = '/regional-symbols/london_boroughs/coat/quiz'
        flag = '/regional-symbols/voivodeships/flag/quiz'
        run = (await client.post(base + '/runs', json={})).json()['run_id']
        partial = result([solve([1], 'alpha district', 5)], status='completed')
        body = result([solve([1], 'alpha district', 5), solve([3], 'Gamma', 10)], status='completed')
        assert (await client.post(other + f'/runs/{run}/finish', json=body)).status_code == 404
        assert (await client.post(flag + f'/runs/{run}/finish', json=body)).status_code == 404
        assert (await client.post(base + f'/runs/{run}/finish', json=partial)).status_code == 422
        assert (await client.post(base + f'/runs/{run}/finish', json=body)).json()['solved_count'] == 2
        assert (await client.post(base + f'/runs/{run}/finish', json=body)).status_code == 200
        stats = (await client.get(base + '/stats')).json()
        assert stats['finished_runs'] == 1
        assert stats['coats'][0]['solved_count'] == 1
        assert stats['coats'][0]['average_active_seconds'] == 5
        assert (await client.get(other + '/stats')).json()['coats'][0]['solved_count'] == 0
        assert (await client.get(FLAGS + '/stats')).json()['finished_runs'] == 0
    finally:
        catalog.clear_caches()
