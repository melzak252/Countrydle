"""Ranked daily gameplay against disposable PostgreSQL and the public router."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from db import get_db
from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun, QuizSolve
from db.models.user import User, UserPoints
from tests.test_guest_participation import participation_db
from users.utils import get_admin_user, get_current_or_guest_user, get_current_user

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]


@pytest.fixture
async def daily_client(participation_db, monkeypatch):
    from powiatdle import heraldry
    from admin import router as admin_router

    counties = [
        {"id": 1, "name": "Kraków", "voivodeship": "małopolskie", "is_city_county": True, "latitude": 50.0, "longitude": 20.0},
        {"id": 2, "name": "Warszawa", "voivodeship": "mazowieckie", "is_city_county": True, "latitude": 52.0, "longitude": 21.0},
    ]
    monkeypatch.setattr(heraldry, "get_all_counties", lambda: counties)
    monkeypatch.setattr(heraldry, "get_county_by_id", lambda id_: next((c for c in counties if c['id'] == id_), None))
    monkeypatch.setattr(heraldry, "resolve_guessed_county", lambda guess, id_: next((c for c in counties if c['id'] == id_), None))
    monkeypatch.setattr(heraldry, "get_registration_plates", lambda _: [])
    monkeypatch.setattr(heraldry, "get_source_attribution", lambda *_: None)
    async with participation_db() as session:
        conn = await session.connection()
        await conn.run_sync(UserPoints.__table__.create)
        await conn.run_sync(HeraldryDailySession.__table__.create)
        await conn.run_sync(QuizRun.__table__.create)
        await conn.run_sync(QuizSolve.__table__.create)
        await session.execute(update(User).where(User.id == 1).values(username='Alice'))
        await session.execute(update(User).where(User.id == 2).values(username='Bob'))
        await session.commit()

    app = FastAPI()
    app.include_router(heraldry.router, prefix='/powiatdle')
    app.include_router(admin_router)
    async def db_override():
        async with participation_db() as session:
            yield session
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=1, is_admin=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='https://test') as client:
        yield client, app, counties


def sign_in(app, user_id=1):
    user = SimpleNamespace(id=user_id, username='Alice' if user_id == 1 else 'Bob')
    app.dependency_overrides[get_current_or_guest_user] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user


async def test_guest_win_claim_and_replayed_completion_are_idempotent(daily_client, participation_db):
    from powiatdle.heraldry import decrypt_session_token
    client, app, counties = daily_client
    async with participation_db() as session:
        session.add(UserPoints(user_id=1, points=123, streak=7))
        await session.commit()
    start = (await client.get('/powiatdle/heraldry/challenge')).json()
    assert start['ranked'] is True and start['points'] is None
    target = decrypt_session_token(start['token'])['target_id']
    county = next(c for c in counties if c['id'] == target)
    body = {'token': start['token'], 'guess': county['name'], 'powiat_id': target}
    a, b = await asyncio.gather(*(client.post('/powiatdle/heraldry/guess', json=body) for _ in range(2)))
    assert sorted((a.status_code, b.status_code)) == [200, 409]
    result = (a if a.status_code == 200 else b).json()
    assert result['won'] and result['ranked'] and result['points'] > 0
    assert (await client.get('/powiatdle/heraldry/challenge', params={'token': start['token']})).json()['won']
    sign_in(app)
    claim = await client.post('/powiatdle/heraldry/sync', json={})
    repeat = await client.post('/powiatdle/heraldry/sync', json={})
    assert claim.status_code == repeat.status_code == 200
    assert claim.json()['won'] and claim.json()['points'] == repeat.json()['points']
    async with participation_db() as session:
        rows = (await session.scalars(select(HeraldryDailySession))).all()
        assert len(rows) == 1 and rows[0].user_id == 1 and len(rows[0].guesses) == 1
        points = await session.get(UserPoints, 1)
        assert points.points == 123 + claim.json()['points'] and points.streak == 7
    leaders = (await client.get('/powiatdle/heraldry/leaderboard?type=monthly')).json()
    assert len(leaders) == 1 and leaders[0]['id'] == 1 and leaders[0]['points'] == claim.json()['points']


async def test_existing_account_wins_claim_conflict_and_guest_history_remains(daily_client, participation_db):
    from powiatdle.heraldry import decrypt_session_token
    client, app, counties = daily_client
    sign_in(app)
    account = (await client.get('/powiatdle/heraldry/challenge')).json()
    target = decrypt_session_token(account['token'])['target_id']
    wrong = next(c for c in counties if c['id'] != target)
    account_guess = await client.post('/powiatdle/heraldry/guess', json={
        'token': account['token'], 'guess': wrong['name'], 'powiat_id': wrong['id'],
    })
    assert account_guess.status_code == 200
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    guest = (await client.get('/powiatdle/heraldry/challenge')).json()
    assert guest['token'] != account['token']
    sign_in(app)
    claimed = await client.post('/powiatdle/heraldry/sync', json={})
    assert claimed.status_code == 200
    assert len(claimed.json()['guesses']) == 1
    assert decrypt_session_token(claimed.json()['token'])['session_id'] == decrypt_session_token(account['token'])['session_id']
    async with participation_db() as session:
        rows = (await session.scalars(select(HeraldryDailySession))).all()
        assert len(rows) == 2 and {row.user_id for row in rows} == {1, None}


async def test_legacy_token_stays_unranked_after_login(daily_client):
    from powiatdle.heraldry import encrypt_session_token
    client, app, _ = daily_client
    today = datetime.now(timezone.utc).date().isoformat()
    token = encrypt_session_token({'seed': f'daily-{today}', 'is_daily': True, 'date': today, 'target_id': 1, 'guesses': [2]})
    sign_in(app)
    response = await client.get('/powiatdle/heraldry/challenge', params={'token': token})
    assert response.status_code == 200
    result = response.json()
    assert not result['ranked'] and result['points'] is None and len(result['guesses']) == 1
    assert (await client.post('/powiatdle/heraldry/sync', json={})).status_code == 404


async def test_empty_account_session_does_not_discard_guest_win(daily_client, participation_db):
    from powiatdle.heraldry import decrypt_session_token
    client, app, counties = daily_client
    sign_in(app)
    account = (await client.get('/powiatdle/heraldry/challenge')).json()
    assert account['guesses'] == []
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    guest = (await client.get('/powiatdle/heraldry/challenge')).json()
    target = decrypt_session_token(guest['token'])['target_id']
    county = next(c for c in counties if c['id'] == target)
    won = await client.post('/powiatdle/heraldry/guess', json={
        'token': guest['token'], 'guess': county['name'], 'powiat_id': target,
    })
    assert won.status_code == 200 and won.json()['won']
    sign_in(app)
    claimed = await client.post('/powiatdle/heraldry/sync', json={})
    assert claimed.status_code == 200 and claimed.json()['won']
    assert len(claimed.json()['guesses']) == 1 and claimed.json()['points'] > 0
    assert (await client.post('/powiatdle/heraldry/sync', json={})).json()['points'] == claimed.json()['points']
    restored = await client.get('/powiatdle/heraldry/challenge', params={'token': account['token']})
    assert restored.status_code == 200 and restored.json()['won']
    assert restored.json()['points'] == claimed.json()['points'] and len(restored.json()['guesses']) == 1
    sign_in(app, user_id=2)
    assert (await client.get('/powiatdle/heraldry/challenge', params={'token': account['token']})).status_code == 403
    sign_in(app)
    async with participation_db() as session:
        rows = (await session.scalars(select(HeraldryDailySession))).all()
        assert len(rows) == 1 and rows[0].user_id == 1 and len(rows[0].guesses) == 1
        assert (await session.get(UserPoints, 1)).points == claimed.json()['points']


def test_subsecond_speed_bonus_is_not_lost():
    from game_logic import calculate_flagdle_points
    from powiatdle.heraldry_daily import scoring_elapsed
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fast = scoring_elapsed(started, started + timedelta(milliseconds=900))
    slower = scoring_elapsed(started, started + timedelta(milliseconds=1100))
    assert fast == 1 and slower == 2
    assert calculate_flagdle_points(True, 1, fast, 1) >= calculate_flagdle_points(True, 1, slower, 1)


async def test_admin_heraldry_and_quiz_filters_paginate_real_results(daily_client, participation_db, monkeypatch):
    client, _, _ = daily_client
    now = datetime.now(timezone.utc)
    day = now.date()
    from powiatdle import heraldry
    names = {i: f'Powiat {i}' for i in range(1, 381)}
    names.update({1: 'Kraków', 2: 'Warszawa', 3: 'Poznań'})
    monkeypatch.setattr(heraldry, 'get_all_counties', lambda: [{'id': i, 'name': name} for i, name in names.items()])
    async with participation_db() as session:
        session.add_all([
            HeraldryDailySession(id='daily-won', date=day, guest_id='a', target_id=1, target_name='Kraków',
                                 guesses=[{'id': 1, 'name': 'Kraków', 'at': now.isoformat()}],
                                 started_at=now, completed_at=now, won=True, points=2050),
            HeraldryDailySession(id='daily-progress', date=day, guest_id='b', target_id=1, target_name='Kraków',
                                 guesses=[{'id': 2, 'name': 'Warszawa', 'at': now.isoformat()}],
                                 started_at=now, won=False),
            QuizRun(id='quiz-done', guest_id='a', started_at=now, finished_at=now,
                    status='completed', solved_count=380, elapsed_seconds=400.5),
            QuizRun(id='quiz-stopped', guest_id='a', started_at=now, finished_at=now,
                    status='given_up', solved_count=3, elapsed_seconds=32),
            QuizRun(id='quiz-open', user_id=1, started_at=now, status='started', solved_count=0),
        ])
        await session.flush()
        session.add_all([
            *(QuizSolve(run_id='quiz-done', powiat_id=i, elapsed_seconds=float(i)) for i in range(1, 381)),
            QuizSolve(run_id='quiz-stopped', powiat_id=1, elapsed_seconds=4),
            QuizSolve(run_id='quiz-stopped', powiat_id=2, elapsed_seconds=8),
            QuizSolve(run_id='quiz-stopped', powiat_id=3, elapsed_seconds=12),
        ])
        await session.commit()
    base = '/admin/game-sessions'
    daily = await client.get(base, params={'mode': 'heraldry', 'date': str(day), 'status': 'won', 'limit': 1})
    assert daily.status_code == 200
    assert daily.json()['total'] == 1 and daily.json()['items'][0]['points'] == 2050
    assert daily.json()['items'][0]['timeline'][0]['guess'] == 'Kraków'
    quiz = await client.get(base, params={'mode': 'coats_quiz', 'date': str(day), 'player_type': 'guest', 'limit': 1})
    assert quiz.status_code == 200 and quiz.json()['total'] == 2 and len(quiz.json()['items']) == 1
    stopped = await client.get(base, params={'mode': 'coats_quiz', 'date': str(day), 'status': 'lost'})
    assert stopped.json()['total'] == 1
    assert stopped.json()['items'][0]['quiz_status'] == 'given_up'
    assert stopped.json()['items'][0]['solved_count'] == 3
    assert stopped.json()['items'][0]['active_elapsed_seconds'] == 32
    assert stopped.json()['items'][0]['quiz_solves'] == [
        {'powiat_id': 1, 'name': 'Kraków', 'active_elapsed_seconds': 4},
        {'powiat_id': 2, 'name': 'Warszawa', 'active_elapsed_seconds': 8},
        {'powiat_id': 3, 'name': 'Poznań', 'active_elapsed_seconds': 12},
    ]
    stats = await client.get(base + '/stats', params={'mode': 'coats_quiz', 'date': str(day)})
    assert stats.status_code == 200 and stats.json()['total_players'] == 2
    assert stats.json()['win_rate_pct'] == 33.3
    no_results = await client.get(base, params={'mode': 'heraldry', 'date': str(day - timedelta(days=1))})
    assert no_results.json()['total'] == 0
