"""Durable reuse and report transaction contracts against real databases."""
from datetime import date, datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.base import Base
from db.models.fallback_answer import FallbackAnswer, FallbackAnswerBlock
from db.repositories import fallback_answers as cache

TABLES = [FallbackAnswer.__table__, FallbackAnswerBlock.__table__]
DAY = date(2026, 10, 4)
INPUTS = dict(mode='countrydle', entity_name='Poland', original_question='Did it host the event?',
              question='Did the country host the event?', context='Controlled event evidence.', game_date=DAY)


def identity(**changes):
    return cache.make_identity(**(INPUTS | dict(entity_id=31, system_prompt='Game policy.',
        question_prompt='Exact question.', model='test-model') | changes))


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "answers.sqlite"}')
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=TABLES))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def pg_sessions():
    url = os.getenv('QUESTION_TEST_DATABASE_URL')
    if not url:
        pytest.skip('QUESTION_TEST_DATABASE_URL must point to a disposable PostgreSQL database')
    engine = create_async_engine(url)
    schema = 'fallback_cache_' + uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = engine.execution_options(schema_translate_map={None: schema})
    try:
        async with scoped.begin() as connection:
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=TABLES))
        yield async_sessionmaker(scoped, expire_on_commit=False)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


@pytest.mark.anyio
async def test_false_answer_persists_across_connections_without_mutable_result_sharing(sessions):
    key = identity()
    async with sessions() as writer:
        await cache.store(writer, key, False, 'The event did not happen.')
        await writer.commit()
    async with sessions() as reader:
        first = await cache.lookup(reader, key)
        assert first == {'answer': False, 'explanation': 'The event did not happen.'}
        first['answer'] = True
    async with sessions() as reader:
        assert (await cache.lookup(reader, key))['answer'] is False


@pytest.mark.anyio
async def test_rolled_back_report_does_not_disable_a_valid_answer(sessions):
    key = identity()
    async with sessions() as writer:
        await cache.store(writer, key, True, 'The event happened.')
        await writer.commit()
    async with sessions() as reporter:
        await cache.invalidate(reporter, **INPUTS)
        await reporter.rollback()
    async with sessions() as reader:
        assert (await cache.lookup(reader, key))['answer'] is True


@pytest.mark.anyio
async def test_report_blocks_late_generation_until_evidence_changes(sessions):
    key = identity()
    async with sessions() as reporter:
        await cache.invalidate(reporter, **INPUTS)
        await reporter.commit()
    async with sessions() as generator:
        await cache.store(generator, key, False, 'Late disputed answer.')
        fresh = identity(context='Corrected event evidence.')
        await cache.store(generator, fresh, True, 'Corrected event happened.')
        await generator.commit()
    async with sessions() as reader:
        assert await cache.lookup(reader, key) is None
        assert (await cache.lookup(reader, fresh))['answer'] is True


@pytest.mark.anyio
async def test_daily_cleanup_preserves_current_answers_and_current_report_blocks(sessions):
    yesterday = DAY - timedelta(days=1)
    old = identity(game_date=yesterday)
    current = identity()
    blocked = identity(original_question='Did it win the event?')
    async with sessions() as writer:
        await cache.store(writer, old, False, 'Old answer.')
        await cache.store(writer, current, True, 'Current answer.')
        await cache.invalidate(writer, **(INPUTS | {'original_question': 'Did it win the event?'}))
        await cache.purge_old(writer, before=DAY)
        await cache.store(writer, blocked, False, 'Disputed current answer.')
        await writer.commit()
    async with sessions() as reader:
        assert await cache.lookup(reader, old) is None
        assert (await cache.lookup(reader, current))['answer'] is True
        assert await cache.lookup(reader, blocked) is None


@pytest.mark.anyio
async def test_postgres_report_commit_wins_over_an_insert_with_an_older_mvcc_snapshot(pg_sessions):
    key = identity()
    async with pg_sessions() as reporter, pg_sessions() as generator:
        # Store sees no uncommitted block; report has already deleted existing entries.
        await cache.invalidate(reporter, **INPUTS)
        await cache.store(generator, key, True, 'Late disputed result.')
        await reporter.commit()
        await generator.commit()
    async with pg_sessions() as reader:
        assert await cache.lookup(reader, key) is None


@pytest.mark.anyio
async def test_matching_daily_evidence_does_not_expire_after_five_minutes(sessions):
    key = identity()
    async with sessions() as writer:
        await cache.store(writer, key, True, "The event happened.")
        await writer.execute(
            update(FallbackAnswer).where(FallbackAnswer.key == key.key).values(
                created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            )
        )
        await writer.commit()
    async with sessions() as reader:
        assert (await cache.lookup(reader, key))["answer"] is True
