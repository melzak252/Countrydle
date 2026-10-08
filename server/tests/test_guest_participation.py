"""Guest identities and participation; PostgreSQL tests use an explicit isolated schema."""
import asyncio
import os
from http.cookies import SimpleCookie
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.models.guest_participation import GuestParticipation
from db.models.user import User
from utils.guest_session import (
    GUEST_IDENTITY_COOKIE,
    get_guest_identity,
    read_guest_identity,
    record_guest_action,
)


def request_with_cookie(token=None):
    headers = [] if token is None else [(b"cookie", f"{GUEST_IDENTITY_COOKIE}={token}".encode())]
    return Request({
        "type": "http", "scheme": "https", "headers": headers,
        "path": "/", "query_string": b"", "server": ("test", 443),
    })


def identity_request():
    response = Response()
    identity = get_guest_identity(request_with_cookie(), response)
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return identity, request_with_cookie(cookie[GUEST_IDENTITY_COOKIE].value)


def test_signed_identity_is_reused_across_requests_and_cannot_be_forged():
    response = Response()
    identity = get_guest_identity(request_with_cookie(), response)
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    token = cookie[GUEST_IDENTITY_COOKIE].value
    assert cookie[GUEST_IDENTITY_COOKIE]["httponly"]
    assert cookie[GUEST_IDENTITY_COOKIE]["samesite"] == "lax"
    assert cookie[GUEST_IDENTITY_COOKIE]["secure"]
    assert get_guest_identity(request_with_cookie(token), Response()) == identity
    assert read_guest_identity(request_with_cookie(token + "tampered")) is None
    assert identity_request()[0] != identity


@pytest.fixture
async def participation_db():
    url = os.getenv("PARTICIPATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PARTICIPATION_TEST_DATABASE_URL; never uses the application database URL")
    schema = f"participation_test_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema}}
    )
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(User.__table__.create)
            await connection.execute(text(
                "INSERT INTO users (id, email, verified, is_admin) "
                "VALUES (1, 'first@example.com', true, false), (2, 'second@example.com', true, false)"
            ))
            await connection.run_sync(GuestParticipation.__table__.create)
        yield factory
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


@pytest.mark.real_database
@pytest.mark.anyio
async def test_concurrent_actions_count_one_guest_without_lost_updates(participation_db):
    identity, request = identity_request()

    async def act(question, won=None):
        async with participation_db() as session:
            participation = await record_guest_action(
                session, request, Response(), "countrydle", 7,
                max_guesses=3, max_questions=10, question=question, won=won,
            )
            assert participation.guest_id == identity
            assert participation.guesses_made >= int(not question)
            assert participation.questions_asked >= int(question)
            await session.commit()

    await asyncio.gather(act(True), act(True), act(False, False), act(False, False))
    await act(False, True)
    for question in (False, True):
        async with participation_db() as session:
            with pytest.raises(HTTPException) as rejected:
                await record_guest_action(
                    session, request, Response(), "countrydle", 7,
                    max_guesses=3, max_questions=10, question=question,
                )
            assert rejected.value.status_code == 400
            await session.rollback()
    async with participation_db() as session:
        row = (await session.scalars(select(GuestParticipation))).one()
        assert (row.guest_id, row.questions_asked, row.guesses_made, row.won) == (identity, 2, 3, True)


@pytest.mark.real_database
@pytest.mark.anyio
async def test_people_modes_and_days_remain_distinct(participation_db):
    identity, first = identity_request()
    other_identity, second = identity_request()
    async with participation_db() as session:
        for request, mode, day in (
            (first, "countrydle", 7), (second, "countrydle", 7),
            (first, "countrydle", 8), (first, "continental:europe", 7),
        ):
            await record_guest_action(
                session, request, Response(), mode, day,
                max_guesses=3, max_questions=8 if mode.startswith("continental:") else 10,
                question=True,
            )
        await session.commit()
        rows = (await session.scalars(select(GuestParticipation))).all()
        assert len(rows) == 4
        assert {(r.guest_id, r.mode, r.day_id) for r in rows if r.user_id is None} == {
            (identity, "countrydle", 7), (other_identity, "countrydle", 7), (identity, "countrydle", 8),
            (identity, "continental:europe", 7),
        }


@pytest.mark.real_database
@pytest.mark.anyio
async def test_failed_action_rolls_back_participation(participation_db):
    _, request = identity_request()
    async with participation_db() as session:
        await record_guest_action(session, request, Response(), "flagdle", 1, max_guesses=12, won=False)
        await session.rollback()
        assert await session.scalar(select(func.count()).select_from(GuestParticipation)) == 0
