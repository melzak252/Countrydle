"""One supported backend process per PostgreSQL database, not a scaling lock."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


# Fixed across processes and schemas; do not derive this from a deployment name.
_RUNTIME_LEASE_KEY = 0x434F554E545259
_OWNER_CHECK_INTERVAL_SECONDS = 1
_OWNER_CHECK_TIMEOUT_SECONDS = 2


class RuntimeOwnershipError(RuntimeError):
    """Another backend already owns this database's process-local runtime."""


def validate_worker_configuration() -> None:
    workers = os.getenv("WEB_CONCURRENCY")
    if workers is not None and workers != "1":
        raise RuntimeError("WEB_CONCURRENCY must be absent or exactly '1'; only one backend worker/replica per database is supported.")


async def _watch_owner(connection, backend_pid: int, stopping: asyncio.Event) -> None:
    # Never reconnect or reacquire here: a replaced session is no longer owner.
    # A stalled event loop/network can delay detection; this is not distributed
    # fencing and must not be used to claim safe multi-process operation.
    while not stopping.is_set():
        try:
            async with asyncio.timeout(_OWNER_CHECK_INTERVAL_SECONDS):
                await stopping.wait()
            return
        except TimeoutError:
            pass
        try:
            async with asyncio.timeout(_OWNER_CHECK_TIMEOUT_SECONDS):
                held = await connection.scalar(text(
                    "SELECT pg_backend_pid() = :pid AND EXISTS ("
                    "SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                    "AND pid = pg_backend_pid() AND granted "
                    "AND classid = :high AND objid = :low AND objsubid = 1)"
                ), {"pid": backend_pid, "high": _RUNTIME_LEASE_KEY >> 32,
                    "low": _RUNTIME_LEASE_KEY & 0xFFFFFFFF})
            if not held:
                raise RuntimeOwnershipError("Backend runtime ownership was lost")
        except Exception:
            logging.critical("Runtime ownership lost; terminating all HTTP, scheduler and worker activity.", exc_info=True)
            # A lifespan exception/cancellation alone does not stop Uvicorn's
            # HTTP server. Hard termination is deliberately fail-closed, including
            # in-flight jobs, threads and process-local quota enforcement.
            os._exit(1)


@asynccontextmanager
async def singleton_owner(engine: AsyncEngine):
    """Hold a dedicated session advisory lease until owned shutdown completes."""
    if engine.dialect.name != "postgresql":
        raise RuntimeOwnershipError("The supported runtime requires PostgreSQL session ownership")

    async with engine.connect() as connection:
        # Session locks survive commits; avoid an idle transaction for the whole
        # server lifetime. Keep this connection checked out, never pool-returned.
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        try:
            acquired = await connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _RUNTIME_LEASE_KEY})
        except BaseException:
            # Acquisition may have reached PostgreSQL even if its response did
            # not arrive. Do not return a possibly locked session to the pool.
            await connection.invalidate()
            raise
        if not acquired:
            raise RuntimeOwnershipError("Another backend process already owns this database; only one worker/replica is supported")

        monitor = None
        stopping = asyncio.Event()
        try:
            backend_pid = await connection.scalar(text("SELECT pg_backend_pid()"))
            monitor = asyncio.create_task(_watch_owner(connection, backend_pid, stopping), name="runtime-owner-monitor")
            yield
        finally:
            try:
                if monitor is not None:
                    # Let a bounded in-flight check finish instead of cancelling
                    # SQL, which can invalidate the session before lock release.
                    stopping.set()
                    await monitor
            finally:
                try:
                    async with asyncio.timeout(_OWNER_CHECK_TIMEOUT_SECONDS):
                        released = await connection.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": _RUNTIME_LEASE_KEY})
                    if not released:
                        raise RuntimeOwnershipError("Runtime lease disappeared before release")
                except BaseException:
                    # Never return a possibly still-locked session to the pool.
                    await connection.invalidate()
                    raise
