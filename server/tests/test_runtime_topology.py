"""H14: one admitted lifespan per disposable PostgreSQL deployment database.

Only migration/provisioning/provider/job execution boundaries are replaced. The
application lifespan, ownership guard, PostgreSQL lease and daily generators
remain real. Subprocesses own separate schemas in the same test database so a
schema-local or process-local lock cannot accidentally satisfy the contract.
"""
from datetime import date, timedelta
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import Country, CountrydleDay
from db.models.continental import ContinentCode, ContinentalDay
from db.models.flagdle import FlagdleDay


pytestmark = [pytest.mark.real_database, pytest.mark.anyio]
SERVER_ROOT = Path(__file__).resolve().parents[1]
FIRST_DAY = date(2026, 3, 28)
RESTART_DAY = FIRST_DAY + timedelta(days=8)
EVENT_PREFIX = "TOPOLOGY_EVENT "
COUNTRIES = [(1, "Poland", "Europe"), (2, "Japan", "Asia"),
             (3, "Kenya", "Africa"), (4, "Canada", "North America"),
             (5, "Germany", "Europe")]


def _isolated_engine(url, schema, application_name):
    return create_async_engine(
        url, pool_size=4, max_overflow=2,
        connect_args={"server_settings": {"search_path": schema, "application_name": application_name}},
    )


def _configure_startup(monkeypatch, engine, facts, today, record, fail_at=None):
    """Sandbox effects, without replacing lifespan, lease or catch-up functions."""
    import db
    import daily_clock
    import utils
    from utils import app as lifecycle
    from continental import scheduler as continental_scheduler
    from continental import utils as continental_utils
    from flagdle import scheduler as flag_scheduler
    from db.repositories import flagdle as flag_repository

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "engine", engine)
    for module in (db, lifecycle, utils, flag_scheduler):
        monkeypatch.setattr(module, "AsyncSessionLocal", factory)
    monkeypatch.setattr(lifecycle, "get_engine", lambda: engine)
    monkeypatch.setattr(continental_utils, "DEFAULT_DB_PATH", facts)
    for module in (daily_clock, utils, continental_scheduler, flag_scheduler, flag_repository):
        monkeypatch.setattr(module, "utc_today", today)

    started = set()

    def effect(name):
        record(name)
        started.add(name)
        if fail_at == name:
            raise RuntimeError(f"Injected isolated startup failure: {name}")

    def asynchronous_effect(name):
        async def run(*args, **kwargs):
            effect(name)
        return run

    async def stop_workers():
        record("workers-stopped")
        if "workers" in started:
            async with engine.connect() as connection:
                held = await connection.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks AS locks "
                    "JOIN pg_stat_activity AS activity ON activity.pid = locks.pid "
                    "WHERE locks.locktype = 'advisory' AND locks.granted "
                    "AND activity.application_name = current_setting('application_name'))"
                ))
            record("workers-stopped-with-lease" if held else "workers-stopped-without-lease")

    class IsolatedScheduler:
        def start(self):
            effect("scheduler")

        def shutdown(self, wait=True):
            record("scheduler-stopped")

    monkeypatch.setattr(lifecycle, "init_models", asynchronous_effect("migrations"))
    monkeypatch.setattr(lifecycle, "provision_country_additions", lambda *args: effect("provision"))
    monkeypatch.setattr(lifecycle.ucrud, "add_base_permissions", asynchronous_effect("permissions"))
    monkeypatch.setattr(lifecycle, "init_qdrant", asynchronous_effect("qdrant"))
    monkeypatch.setattr(utils, "purge_old_fallback_answers", asynchronous_effect("purge"))
    monkeypatch.setattr(utils, "generate_yesterday_blog_post", asynchronous_effect("blog"))
    monkeypatch.setattr(utils, "scheduler", IsolatedScheduler())
    monkeypatch.setattr(lifecycle, "start_workers", asynchronous_effect("workers"))
    monkeypatch.setattr(lifecycle, "stop_workers", stop_workers)
    monkeypatch.setattr(lifecycle, "close_qdrant_client", lambda: record("qdrant-closed"))
    monkeypatch.setattr(lifecycle, "close_ai_clients", lambda: record("ai-closed"))
    return factory


@pytest.mark.parametrize("workers", ["", "0", "2", "-1", "01", "1.0", " 1 ", "many"])
async def test_unsupported_worker_configuration_is_rejected_before_engine_or_startup_effects(monkeypatch, workers):
    from utils import app as lifecycle

    engine_requests = []

    def forbidden_engine():
        engine_requests.append(True)
        raise AssertionError("Unsupported topology reached database startup")

    monkeypatch.setenv("WEB_CONCURRENCY", workers)
    monkeypatch.setattr(lifecycle, "get_engine", forbidden_engine)
    with pytest.raises(RuntimeError, match="WEB_CONCURRENCY"):
        async with lifecycle.lifespan(FastAPI()):
            pytest.fail("Unsupported topology became ready")
    assert engine_requests == []


@pytest.fixture
async def topology_db(tmp_path):
    configured = os.getenv("QUESTION_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("Set QUESTION_TEST_DATABASE_URL to a disposable loopback PostgreSQL database")
    target = make_url(configured)
    if target.get_backend_name() != "postgresql" or target.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Topology regressions require explicit disposable loopback PostgreSQL, never DATABASE_URL")
    if not target.database or not (target.database == "hardening" or target.database.endswith(("_test", "_tests", "_e2e"))):
        pytest.fail("Topology regressions require database hardening or a named _test/_tests/_e2e database")
    url = target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    prefix = f"topology_{uuid4().hex}"
    schemas = [f"{prefix}_first", f"{prefix}_second"]
    bootstrap = create_async_engine(url)
    facts = tmp_path / "country_facts.sqlite"
    with sqlite3.connect(facts) as connection:
        connection.executescript(
            "CREATE TABLE countries (id INTEGER PRIMARY KEY, app_country_name TEXT);"
            "CREATE TABLE country_continents (country_id INTEGER, continent TEXT);"
        )
        connection.executemany("INSERT INTO countries VALUES (?, ?)", [(id_, name) for id_, name, _ in COUNTRIES])
        connection.executemany("INSERT INTO country_continents VALUES (?, ?)", [(id_, continent) for id_, _, continent in COUNTRIES])

    created = []
    engines = []
    try:
        for schema in schemas:
            async with bootstrap.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created.append(schema)
            engine = _isolated_engine(url, schema, f"{prefix}_fixture")
            engines.append(engine)
            factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with engine.begin() as connection:
                await connection.run_sync(lambda sync: Base.metadata.create_all(
                    sync, tables=[model.__table__ for model in (Country, CountrydleDay, FlagdleDay, ContinentalDay)],
                ))
            async with factory() as session:
                session.add_all([Country(id=id_, name=name, md_file=f"{name}.md") for id_, name, _ in COUNTRIES])
                await session.flush()
                for preserved_day in (FIRST_DAY, FIRST_DAY + timedelta(days=2), RESTART_DAY + timedelta(days=2)):
                    session.add(CountrydleDay(date=preserved_day, country_id=5))
                    session.add(FlagdleDay(date=preserved_day, country_id=5))
                    for index, continent in enumerate(ContinentCode, start=1):
                        session.add(ContinentalDay(date=preserved_day, continent=continent, country_id=index))
                await session.commit()
        yield SimpleNamespace(url=url, schemas=schemas, bootstrap=bootstrap, engines=engines,
                              prefix=prefix, facts=facts)
    finally:
        for engine in engines:
            await engine.dispose()
        for schema in created:
            async with bootstrap.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


async def test_singleton_lease_retains_a_dedicated_session_and_releases_even_when_pool_stays_open(topology_db):
    from utils.runtime_topology import RuntimeOwnershipError, singleton_owner

    engine = topology_db.engines[0]
    async with singleton_owner(engine):
        assert len(await _lease_pids(topology_db)) == 1
        # Ordinary application work may commit or roll back without releasing
        # ownership, and a pooled session must not reenter a returned lease.
        async with engine.begin() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
            await connection.rollback()
        with pytest.raises(RuntimeOwnershipError):
            async with singleton_owner(engine):
                pytest.fail("The lease connection returned to the pool and allowed reentrant ownership")
        assert len(await _lease_pids(topology_db)) == 1
    assert await _lease_pids(topology_db) == []
    # Releasing the context, rather than disposing the pool or exiting Python,
    # must suffice for a subsequent owner on that same engine.
    async with singleton_owner(engine):
        assert len(await _lease_pids(topology_db)) == 1
    assert await _lease_pids(topology_db) == []


async def _lease_pids(database):
    async with database.bootstrap.connect() as connection:
        result = await connection.execute(text(
            "SELECT DISTINCT locks.pid FROM pg_locks AS locks "
            "JOIN pg_stat_activity AS activity ON activity.pid = locks.pid "
            "WHERE locks.locktype = 'advisory' AND locks.granted "
            "AND activity.application_name LIKE :application"
        ), {"application": f"{database.prefix}%"})
        return list(result.scalars())


async def _await_lease_release(database):
    deadline = asyncio.get_running_loop().time() + 10
    while await _lease_pids(database):
        assert asyncio.get_running_loop().time() < deadline, "Exited owner retained its PostgreSQL advisory lease"
        await asyncio.sleep(0.02)


def _effects(path):
    return path.read_text().splitlines() if path.exists() else []


async def _next_event(process):
    diagnostics = []
    async with asyncio.timeout(60):
        while True:
            line = await process.stdout.readline()
            if not line:
                pytest.fail("Owned lifespan exited without an event:\n" + "".join(diagnostics))
            decoded = line.decode(errors="replace")
            if decoded.startswith(EVENT_PREFIX):
                return json.loads(decoded[len(EVENT_PREFIX):])
            diagnostics.append(decoded)


@pytest.fixture
async def owned_process(topology_db, tmp_path):
    processes = []

    async def start(schema_index=0, fail_at=None):
        effects = tmp_path / f"startup_{uuid4().hex}.log"
        configuration = dict(url=topology_db.url, schema=topology_db.schemas[schema_index],
                             application_name=f"{topology_db.prefix}_{uuid4().hex}", facts=str(topology_db.facts),
                             effects=str(effects), fail_at=fail_at)
        environment = dict(os.environ, DATABASE_URL=topology_db.url, WEB_CONCURRENCY="1",
                           TOPOLOGY_TEST_WORKER=json.dumps(configuration),
                           PYTHONPATH=str(SERVER_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
            environment[key] = ""
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).resolve()), "--owned-lifespan",
            cwd=SERVER_ROOT, env=environment, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        processes.append(process)
        return SimpleNamespace(process=process, effects=effects, event=await _next_event(process))

    try:
        yield start
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await process.wait()


@pytest.mark.parametrize("owner_exit", ["graceful", "killed"])
async def test_competing_process_lifespan_refuses_before_effects_and_owner_exit_allows_restart(
    topology_db, owned_process, owner_exit,
):
    first = await owned_process(0)
    assert first.event == {"status": "ready"}
    competing = await owned_process(1)
    assert competing.event["status"] == "error", "A second process became ready against the same deployment database"
    assert competing.event["type"] == "RuntimeOwnershipError"
    assert not set(_effects(competing.effects)) & {"migrations", "provision", "permissions", "qdrant", "purge", "scheduler", "blog", "workers"}
    assert await competing.process.wait() != 0
    assert len(await _lease_pids(topology_db)) == 1
    assert _effects(first.effects).count("migrations") == 1
    assert _effects(first.effects).count("scheduler") == 1
    assert _effects(first.effects).count("workers") == 1

    if owner_exit == "graceful":
        first.process.stdin.write(b"stop\n")
        await first.process.stdin.drain()
        assert await _next_event(first.process) == {"status": "stopped"}
        assert await first.process.wait() == 0
        assert "workers-stopped-with-lease" in _effects(first.effects)
        assert "workers-stopped-without-lease" not in _effects(first.effects)
    else:
        first.process.kill()
        assert await first.process.wait() != 0
    await _await_lease_release(topology_db)

    replacement = await owned_process(1)
    assert replacement.event == {"status": "ready"}
    assert len(await _lease_pids(topology_db)) == 1
    assert _effects(replacement.effects).count("migrations") == 1
    assert _effects(replacement.effects).count("scheduler") == 1
    assert _effects(replacement.effects).count("workers") == 1


@pytest.mark.parametrize("fail_at", ["migrations", "qdrant", "workers"])
async def test_startup_failure_releases_real_lease_for_a_replacement(topology_db, owned_process, fail_at):
    failed = await owned_process(0, fail_at=fail_at)
    assert failed.event == {"status": "error", "type": "RuntimeError",
                            "message": f"Injected isolated startup failure: {fail_at}"}
    assert await failed.process.wait() != 0
    assert fail_at in _effects(failed.effects)
    await _await_lease_release(topology_db)
    replacement = await owned_process(1)
    assert replacement.event == {"status": "ready"}
    assert len(await _lease_pids(topology_db)) == 1


async def _target_snapshot(factory):
    result = {}
    async with factory() as session:
        for model in (CountrydleDay, FlagdleDay, ContinentalDay):
            rows = (await session.execute(select(model))).scalars().all()
            for row in rows:
                continent = row.continent.value if model is ContinentalDay else None
                result[(model.__tablename__, row.date, continent)] = (row.id, row.country_id)
    return result


def _assert_current_generation_window(snapshot, today):
    for offset in range(5):
        day = today + timedelta(days=offset)
        assert (CountrydleDay.__tablename__, day, None) in snapshot, f"Countrydle skipped {day}"
        assert (FlagdleDay.__tablename__, day, None) in snapshot, f"Flagdle skipped {day}"
        for continent in ContinentCode:
            assert (ContinentalDay.__tablename__, day, continent.value) in snapshot, f"{continent.value} skipped {day}"


@pytest.mark.parametrize("workers", [None, "1"])
async def test_lifespan_awaits_existing_generators_and_recovers_missed_rotation_without_reassigning_targets(
    topology_db, monkeypatch, workers,
):
    from utils import app as lifecycle

    if workers is None:
        monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("WEB_CONCURRENCY", workers)
    today = [FIRST_DAY]
    effects = []
    factory = _configure_startup(monkeypatch, topology_db.engines[0], topology_db.facts,
                                 lambda: today[0], effects.append)
    preserved = await _target_snapshot(factory)
    async with lifecycle.lifespan(FastAPI()):
        at_readiness = await _target_snapshot(factory)
        _assert_current_generation_window(at_readiness, FIRST_DAY)
        assert all(at_readiness[key] == value for key, value in preserved.items())
        assert len(await _lease_pids(topology_db)) == 1
    await _await_lease_release(topology_db)

    # Eight days offline exceed the normal five-day generation horizon. The
    # scheduler deliberately never runs: readiness itself must repair the gap.
    today[0] = RESTART_DAY
    async with lifecycle.lifespan(FastAPI()):
        recovered = await _target_snapshot(factory)
        _assert_current_generation_window(recovered, RESTART_DAY)
        assert all(recovered[key] == value for key, value in at_readiness.items())
        assert len(await _lease_pids(topology_db)) == 1
    await _await_lease_release(topology_db)
    assert effects.count("scheduler") == 2
    assert effects.count("workers") == 2


async def test_incomplete_continental_catchup_refuses_readiness_and_recovers_after_catalog_repair(
    topology_db, monkeypatch,
):
    from utils import app as lifecycle

    factory = _configure_startup(monkeypatch, topology_db.engines[0], topology_db.facts,
                                 lambda: FIRST_DAY, lambda _: None)
    preserved = await _target_snapshot(factory)
    async with factory() as session:
        await session.execute(text("UPDATE countries SET name = 'Unmapped fixture' WHERE name = 'Kenya'"))
        await session.commit()
    with pytest.raises(ValueError):
        async with lifecycle.lifespan(FastAPI()):
            pytest.fail("Missing African UTC targets must not declare the API ready")
    failed = await _target_snapshot(factory)
    assert all(failed[key] == value for key, value in preserved.items())
    assert (ContinentalDay.__tablename__, FIRST_DAY + timedelta(days=1), "africa") not in failed
    assert await _lease_pids(topology_db) == []

    async with factory() as session:
        await session.execute(text("UPDATE countries SET name = 'Kenya' WHERE name = 'Unmapped fixture'"))
        await session.commit()
    async with lifecycle.lifespan(FastAPI()):
        repaired = await _target_snapshot(factory)
        _assert_current_generation_window(repaired, FIRST_DAY)
        assert all(repaired[key] == value for key, value in preserved.items())
    assert await _lease_pids(topology_db) == []


async def _worker_lifespan(configuration):
    from utils import app as lifecycle

    engine = _isolated_engine(configuration["url"], configuration["schema"], configuration["application_name"])
    patches = pytest.MonkeyPatch()
    effects = Path(configuration["effects"])

    def record(name):
        with effects.open("a") as stream:
            stream.write(name + "\n")

    def emit(payload):
        print(EVENT_PREFIX + json.dumps(payload), flush=True)

    _configure_startup(patches, engine, Path(configuration["facts"]), lambda: FIRST_DAY,
                       record, configuration["fail_at"])
    try:
        async with lifecycle.lifespan(FastAPI()):
            emit({"status": "ready"})
            command = await asyncio.to_thread(sys.stdin.readline)
            if command.strip() != "stop":
                raise RuntimeError("Owned topology worker expected an explicit stop command")
        emit({"status": "stopped"})
        return 0
    except Exception as error:
        emit({"status": "error", "type": type(error).__name__, "message": str(error)})
        return 1
    finally:
        await engine.dispose()
        patches.undo()


if __name__ == "__main__":
    if sys.argv[1:] != ["--owned-lifespan"] or "TOPOLOGY_TEST_WORKER" not in os.environ:
        raise SystemExit("This module is a pytest-owned isolated lifespan worker, not an application entrypoint")
    raise SystemExit(asyncio.run(_worker_lifespan(json.loads(os.environ["TOPOLOGY_TEST_WORKER"]))))
