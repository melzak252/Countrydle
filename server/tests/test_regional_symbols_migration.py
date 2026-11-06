"""Exercise the geography migration against isolated PostgreSQL legacy rows."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.anyio
@pytest.mark.real_database
async def test_legacy_rows_survive_scope_upgrade_and_regional_history_blocks_downgrade():
    url = os.getenv('PARTICIPATION_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set PARTICIPATION_TEST_DATABASE_URL to a disposable PostgreSQL database')
    schema = 'regional_migration_' + uuid4().hex
    engine = create_async_engine(url)
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/h4f5a6b7c8d9_add_heraldry_geography_scope.py'
    spec = importlib.util.spec_from_file_location('regional_scope_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def run_migration(connection, method):
        with Operations.context(MigrationContext.configure(connection)):
            method()

    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await conn.execute(text('CREATE TABLE heraldry_daily_sessions (id TEXT PRIMARY KEY, user_id INT, guest_id TEXT, date DATE NOT NULL, symbol_mode TEXT NOT NULL, target_id INT NOT NULL, guesses JSON NOT NULL)'))
            await conn.execute(text('CREATE TABLE heraldry_quiz_runs (id TEXT PRIMARY KEY, symbol_mode TEXT NOT NULL)'))
            await conn.execute(text('CREATE UNIQUE INDEX uq_heraldry_daily_user_date ON heraldry_daily_sessions (user_id, date, symbol_mode) WHERE user_id IS NOT NULL'))
            await conn.execute(text('CREATE UNIQUE INDEX uq_heraldry_daily_guest_date ON heraldry_daily_sessions (guest_id, date, symbol_mode) WHERE user_id IS NULL AND guest_id IS NOT NULL'))
            await conn.execute(text("INSERT INTO heraldry_daily_sessions VALUES ('legacy', NULL, 'guest', '2026-11-06', 'flag', 1, '[2]')"))
            await conn.execute(text("INSERT INTO heraldry_quiz_runs VALUES ('legacy-quiz', 'coat')"))
            await conn.run_sync(run_migration, migration.upgrade)
            row = (await conn.execute(text("SELECT entity_scope, target_id, guesses FROM heraldry_daily_sessions WHERE id='legacy'"))).one()
            assert row == ('county', 1, [2])
            assert (await conn.execute(text("SELECT entity_scope FROM heraldry_quiz_runs WHERE id='legacy-quiz'"))).scalar_one() == 'county'
            await conn.execute(text("INSERT INTO heraldry_daily_sessions (id, guest_id, date, symbol_mode, target_id, guesses, entity_scope) VALUES ('regional', 'guest', '2026-11-06', 'flag', 1, '[]', 'voivodeships')"))
            with pytest.raises(RuntimeError, match='regional history exists'):
                await conn.run_sync(run_migration, migration.downgrade)
            assert (await conn.execute(text('SELECT count(*) FROM heraldry_daily_sessions'))).scalar_one() == 2
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
