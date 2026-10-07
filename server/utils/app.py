import asyncio
import logging
from contextlib import asynccontextmanager

import users.crud as ucrud
from db import AsyncSessionLocal, get_engine

from db.models import *  # noqa: F403
from db.base import Base
from fastapi import FastAPI
from qdrant import close_qdrant_client, init_qdrant
from sqlalchemy.ext.asyncio import AsyncEngine
import utils
from friend_matches import start_workers, stop_workers
from countrydle.local_answering import DEFAULT_DB_PATH
from scripts.country_additions import provision_country_additions
from utils.ai_clients import close_ai_clients
from utils.runtime_topology import singleton_owner, validate_worker_configuration
import runtime_configuration  # Validate signing/origin configuration at startup.


async def init_models(engine: AsyncEngine):
    import os
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        db_url = db_url.replace("+asyncpg", "")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    try:
        print("Starting database migrations...", flush=True)
        # Run in a thread to avoid blocking the event loop
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        print("Database migrations applied successfully.", flush=True)
    except Exception as e:
        print(f"Error applying migrations: {e}", flush=True)
        raise e


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_worker_configuration()
    engine = get_engine()
    owned = False
    scheduler_started = False
    workers_started = False
    providers_started = False
    blog_task = None
    try:
        async with singleton_owner(engine):
            owned = True
            try:
                await init_models(engine)
                await asyncio.to_thread(provision_country_additions, DEFAULT_DB_PATH.parent)

                async with AsyncSessionLocal() as session:
                    await ucrud.add_base_permissions(session)
                    providers_started = True
                    await init_qdrant(session)
                await utils.purge_old_fallback_answers()

                # Catch up the existing UTC generation horizon before readiness;
                # each generator preserves already selected targets.
                await utils.generate_day_countries()
                await utils.generate_day_flags()
                await utils.run_generate_continental_days()

                scheduler_started = True
                utils.scheduler.start()
                blog_task = asyncio.create_task(utils.generate_yesterday_blog_post())
                workers_started = True
                await start_workers()
                yield
            finally:
                # A rejected competitor must not touch global resource aliases.
                # Retain the database lease throughout owned runtime shutdown.
                logging.info("Shutting down owned application runtime...")
                try:
                    if workers_started:
                        await stop_workers()
                finally:
                    try:
                        if scheduler_started:
                            utils.scheduler.shutdown(wait=True)
                            await asyncio.sleep(0)
                    finally:
                        try:
                            if blog_task is not None:
                                blog_task.cancel()
                                try:
                                    await blog_task
                                except asyncio.CancelledError:
                                    pass
                        finally:
                            if providers_started:
                                try:
                                    close_qdrant_client()
                                finally:
                                    await asyncio.to_thread(close_ai_clients)
    except Exception:
        logging.error("Exiting application due to startup/runtime failure.", exc_info=True)
        raise
    finally:
        if owned:
            await engine.dispose()
            logging.info("Owned application shutdown complete.")
