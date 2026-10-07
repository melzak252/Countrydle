"""Test-only real API launcher. Never import this from the production application.

Requires a loopback PostgreSQL database named exactly countrydle_e2e and a
non-superuser e2e role that owns that disposable database. The database must
already have pgvector installed. Each invocation CREATEs a fresh random schema
(no IF NOT EXISTS), uses it exclusively, and DROP SCHEMA CASCADEs only that
schema on graceful exit. It never drops a database or a preexisting schema.
SIGKILL cannot clean up: remove the printed schema in the disposable DB only.
All source is copied to a temporary directory; a private SQLite fact snapshot is
built from the canonical schema and reviewed textual seed in scripts/. No
.env, shared SQLite caches, Qdrant, schedulers, workers or paid calls are used.
The app's handlers, dependencies, auth and repositories are otherwise unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

from sqlalchemy.engine import make_url

SERVER = Path(__file__).resolve().parents[1]
SCHEMA_PATTERN = re.compile(r"countrydle_e2e_[0-9a-f]{16}\Z")
PASSWORD = "browser-only-disposable-password"
SCENARIOS = ("sync", "recovery", "auth", "expired", "win", "loss", "unresolved")


def validate_database_target(value: str, schema: str):
    target = make_url(value)
    if (target.drivername != "postgresql+asyncpg"
            or target.host not in {"127.0.0.1", "localhost", "::1"}
            or target.database != "countrydle_e2e"
            or target.username != "e2e"
            or not target.password
            or target.query
            or not SCHEMA_PATTERN.fullmatch(schema)):
        raise ValueError("E2E requires loopback countrydle_e2e, role e2e, no URL options, and a fresh countrydle_e2e_<16 hex> schema")
    return target


def validate_port(port: int) -> int:
    if not 1024 <= port <= 65535 or port in {8080, 8086, 5179}:
        raise ValueError("Use a dedicated unprivileged E2E port, not an existing preview port")
    return port


def server_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.suffix in {".py", ".sql"}
                   and "tests" not in path.relative_to(directory).parts
                   and "__pycache__" not in path.parts)
    for path in files:
        digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def build_private_fact_snapshot(directory: Path, source: Path = SERVER) -> Path:
    """Create owned SQLite facts from checked-in text, never adopt a live file."""
    import sqlite3
    destination = directory / "country_facts.sqlite"
    # Exclusive creation refuses existing files before SQLite can modify them.
    with destination.open("xb"):
        pass
    with sqlite3.connect(destination) as connection:
        connection.executescript((source / "countrydle" / "local_kb" / "schema.sql").read_text())
        connection.executescript((source / "scripts" / "e2e_country_facts.sql").read_text())
    return destination


def safe_environment(directory: Path) -> dict[str, str]:
    # Deliberately allowlist process settings: no inherited provider/mail secrets.
    result = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL") if key in os.environ}
    for key in ("E2E_DATABASE_URL", "E2E_SCHEMA", "E2E_API_PORT", "E2E_WEB_PORT", "E2E_SERVER_DIGEST", "E2E_CLIENT_DIGEST", "E2E_REVISION", "E2E_CLIENT_VERSION"):
        if key in os.environ:
            result[key] = os.environ[key]
    result.update({
        "PYTHONPATH": str(directory), "PYTHON_DOTENV_DISABLED": "1",
        "DATABASE_URL": os.environ["E2E_DATABASE_URL"],
        "SECRET_KEY": "isolated-browser-suite-signing-key-not-for-deployment-0123456789",
        "CORS_ALLOWED_ORIGINS": f"http://127.0.0.1:{os.environ.get('E2E_WEB_PORT', '5181')}",
        "EMAIL_USERNAME": "e2e@example.com", "EMAIL_PASSWORD": "not-a-mail-password",
        "NOREPLY_EMAIL": "e2e@example.com", "QDRANT_HOST": "127.0.0.1", "QDRANT_PORT": "1",
        "GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_API_KEY": "",
        "COUNTRYDLE_COST_METRICS_DB": str(directory / "data" / "e2e-costs.sqlite3"),
    })
    return result


def launch() -> None:
    validate_database_target(os.environ.get("E2E_DATABASE_URL", ""), os.environ.get("E2E_SCHEMA", ""))
    validate_port(int(os.environ.get("E2E_API_PORT", "8087")))
    validate_port(int(os.environ.get("E2E_WEB_PORT", "5181")))
    expected = os.environ.get("E2E_SERVER_DIGEST")
    if not expected or expected != server_digest(SERVER):
        raise RuntimeError("Managed API source changed after Playwright configuration was loaded")
    with tempfile.TemporaryDirectory(prefix="countrydle-e2e-") as temporary:
        sandbox = Path(temporary) / "server"
        shutil.copytree(SERVER, sandbox, ignore=shutil.ignore_patterns(
            ".env*", "data", "__pycache__", ".pytest_cache", "tests", "test_reports"))
        data = sandbox / "data"
        data.mkdir()
        build_private_fact_snapshot(data, sandbox)
        if server_digest(sandbox) != expected:
            raise RuntimeError("Source changed during sandbox copy; rerun the suite")
        import sys
        child = subprocess.Popen([sys.executable, "scripts/e2e_server.py", "--serve"], cwd=sandbox, env=safe_environment(sandbox))
        previous = {}
        def stop(signum, frame):
            if child.poll() is None:
                child.send_signal(signum)
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, stop)
        try:
            code = child.wait()
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=20)
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        if code:
            raise SystemExit(code)


def serve() -> None:
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime, timedelta
    import sqlite3
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    import uvicorn

    url = validate_database_target(os.environ["E2E_DATABASE_URL"], os.environ["E2E_SCHEMA"])
    schema = os.environ["E2E_SCHEMA"]
    if server_digest(SERVER) != os.environ["E2E_SERVER_DIGEST"]:
        raise RuntimeError("Sandbox revision mismatch")
    admin_engine = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": f"{schema},public"}})
    # Replace the engine before importing any router/repository consumers. This is
    # database isolation, not a dependency override or an in-memory repository.
    import db
    db.engine = engine
    db.AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    from db.base import Base
    from db.models import Country, CountrydleDay, User, UserPoints
    from users.utils import SECRET_KEY, ALGORITHM
    from jose import jwt
    import utils.ai_clients as providers
    import qdrant.vectorize as vectors
    import qdrant.utils as retrieval

    def offline_unresolved(*args, **kwargs):
        # A model's normal unknown result; no country/question-specific answer.
        return {"answer": None, "explanation": "The offline provider cannot establish this fact."}

    def unavailable_provider(*args, **kwargs):
        raise RuntimeError("Provider/embedding network is disabled in the browser harness")

    # Only external provider boundaries are replaced. Europe still uses the real
    # template compiler, planner, local evaluator and private facts. Unsupported
    # questions traverse the normal planner/fallback/route unknown semantics.
    providers.generate_gemini_json = unavailable_provider
    providers.gemini_json = offline_unresolved
    vectors.get_embedding = unavailable_provider
    retrieval.get_embedding = unavailable_provider
    from app import app
    import countrydle.utils as country_utils
    country_utils.gemini_json = offline_unresolved
    import utils.fallback_answers as fallback_provider
    fallback_provider.gemini_json = offline_unresolved
    from version import SERVER_VERSION

    expired_tokens = {}
    manifest = {
        "revision": os.environ["E2E_REVISION"],
        "serverDigest": os.environ["E2E_SERVER_DIGEST"],
        "clientDigest": os.environ["E2E_CLIENT_DIGEST"],
        "clientVersion": os.environ["E2E_CLIENT_VERSION"], "serverVersion": SERVER_VERSION,
        "schema": schema, "database": "countrydle_e2e", "provider": "offline-unresolved",
        "factsDigest": hashlib.sha256((SERVER / "data" / "country_facts.sqlite").read_bytes()).hexdigest(),
        "expiredTokens": expired_tokens,
    }

    @asynccontextmanager
    async def isolated_lifespan(application):
        owned = False
        try:
            async with admin_engine.begin() as connection:
                if await connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")):
                    raise RuntimeError("E2E refuses a superuser database role")
                if not await connection.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")):
                    raise RuntimeError("Install pgvector in the disposable database before running E2E")
                # Never adopt/clean an existing schema, even one with our prefix.
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            owned = True
            print(f"E2E owns disposable schema {schema}", flush=True)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            with sqlite3.connect(SERVER / "data" / "country_facts.sqlite") as facts:
                rows = facts.execute("SELECT id, app_country_name, official_name FROM countries ORDER BY id").fetchall()
                continents = facts.execute("SELECT continent FROM country_continents WHERE country_id = (SELECT id FROM countries WHERE app_country_name = 'Poland')").fetchall()
                if ("Europe",) not in continents:
                    raise RuntimeError("Reviewed textual seed must establish Poland's Europe membership")
            async with db.AsyncSessionLocal() as session:
                session.add_all(Country(id=id_, name=name, official_name=official, md_file="e2e-owned") for id_, name, official in rows)
                await session.flush()
                poland = next(id_ for id_, name, _ in rows if name == "Poland")
                today = datetime.now(UTC).date()
                session.add(CountrydleDay(country_id=poland, date=today))
                # Logout's existing global reset loads every mode; seed days so
                # those genuine GETs cannot invoke target generation/provisioning.
                from db.models import (
                    Powiat, PowiatdleDay, Wojewodztwo, WojewodztwodleDay,
                    USState, USStatedleDay, FlagdleDay,
                )
                from db.models.continental import ContinentCode, ContinentalDay
                session.add_all([
                    Powiat(id=1, nazwa="powiat krakowski"),
                    Wojewodztwo(id=1, nazwa="małopolskie"),
                    USState(id=1, name="Texas", code="TX"),
                ])
                await session.flush()
                session.add_all([
                    PowiatdleDay(powiat_id=1, date=today),
                    WojewodztwodleDay(wojewodztwo_id=1, date=today),
                    USStatedleDay(us_state_id=1, date=today),
                    FlagdleDay(country_id=poland, date=today),
                ])
                by_name = {name: id_ for id_, name, _ in rows}
                for continent, country_id in (
                    (ContinentCode.EUROPE, poland), (ContinentCode.ASIA, by_name["Japan"]),
                    (ContinentCode.AFRICA, by_name["Egypt"]), (ContinentCode.AMERICAS, by_name["Brazil"]),
                ):
                    session.add(ContinentalDay(continent=continent, country_id=country_id, date=today))
                password_hash = User.hash_password(PASSWORD)
                for project in ("desktop", "mobile"):
                    for scenario in SCENARIOS:
                        username = f"e2e_{project}_{scenario}"
                        email = f"{username}@example.com"
                        user = User(username=username, email=email, verified=True, is_admin=False, hashed_password=password_hash)
                        session.add(user)
                        await session.flush()
                        session.add(UserPoints(user_id=user.id, points=0, streak=0, longest_streak=0))
                        expired_tokens[username] = jwt.encode({"sub": email, "exp": datetime.now(UTC) - timedelta(minutes=1)}, SECRET_KEY, algorithm=ALGORITHM)
                await session.commit()
            yield
        finally:
            await engine.dispose()
            if owned:
                async with admin_engine.begin() as connection:
                    await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                print(f"E2E cleaned disposable schema {schema}", flush=True)
            await admin_engine.dispose()

    # Explicitly replace only startup: no migrations against public, production
    # seed/provisioning, Qdrant init, mail, AI warmups, schedulers or duel workers.
    app.router.lifespan_context = isolated_lifespan

    @app.get("/__e2e__/revision", include_in_schema=False)
    async def revision():
        return manifest

    uvicorn.run(app, host="127.0.0.1", port=validate_port(int(os.environ.get("E2E_API_PORT", "8087"))), log_level="warning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        if os.environ.get("PYTHON_DOTENV_DISABLED") != "1" or not SERVER.parent.name.startswith("countrydle-e2e-"):
            raise RuntimeError("--serve is allowed only in a launcher-owned temporary sandbox")
        serve()
    else:
        launch()
