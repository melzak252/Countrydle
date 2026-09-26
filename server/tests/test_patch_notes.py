import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db import get_db
from db.models.patch_note import PatchNote
from patch_notes import router
from scripts import publish_patch_notes


@pytest.fixture
async def patch_notes_store():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(PatchNote.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def database():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = database
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, sessions
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_public_history_orders_paginates_and_preserves_plain_text(patch_notes_store):
    client, sessions = patch_notes_store
    published = datetime(2026, 1, 2, tzinfo=timezone.utc)
    async with sessions.begin() as session:
        session.add_all([
            PatchNote(id=1, version="1.1.0", title="Older", body="Old", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            PatchNote(id=2, version="1.2.0", title="First at same time", body="One\nTwo", published_at=published),
            PatchNote(id=3, version="1.3.0", title="Second at same time", body='<script>alert("not HTML")</script>\n- Plain text', published_at=published),
        ])
    first = await client.get("/patch-notes?limit=2")
    assert first.status_code == 200
    assert [item["version"] for item in first.json()["items"]] == ["1.3.0", "1.2.0"]
    assert first.json()["items"][0]["body"].startswith("<script>")
    timestamp = datetime.fromisoformat(first.json()["items"][0]["published_at"].replace("Z", "+00:00"))
    assert timestamp == published
    second = (await client.get("/patch-notes?page=2&limit=2")).json()
    assert [item["version"] for item in second["items"]] == ["1.1.0"]
    assert (second["total"], second["page"], second["limit"]) == (3, 2, 2)


@pytest.mark.anyio
async def test_empty_history_and_invalid_pagination(patch_notes_store):
    client, _ = patch_notes_store
    assert (await client.get("/patch-notes")).json() == {"items": [], "total": 0, "page": 1, "limit": 10}
    for query in ("page=0", "limit=51", "limit=0"):
        assert (await client.get(f"/patch-notes?{query}")).status_code == 422
    assert (await client.post("/patch-notes", json={})).status_code == 405


@pytest.mark.anyio
async def test_repeat_and_conflicting_publications_preserve_original_release(patch_notes_store):
    _, sessions = patch_notes_store
    payload = {"version": "1.8.0", "title": "Title", "body": "Body"}
    async with sessions() as session:
        await publish_patch_notes.publish(session, payload)
    async with sessions() as session:
        first = (await session.scalars(select(PatchNote))).one()
        original = (first.id, first.title, first.body, first.published_at)
    async with sessions() as session:
        await publish_patch_notes.publish(session, payload)
    async with sessions() as session:
        with pytest.raises(publish_patch_notes.ManifestError):
            await publish_patch_notes.publish(session, {**payload, "body": "Changed"})
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PatchNote)) == 1
        stored = (await session.scalars(select(PatchNote))).one()
        assert (stored.id, stored.title, stored.body, stored.published_at) == original


def test_check_works_without_database_configuration(tmp_path):
    manifest = tmp_path / "release.json"
    manifest.write_text(json.dumps({"version": publish_patch_notes.SERVER_VERSION, "title": "Title", "body": "Body"}))
    result = subprocess.run(
        [sys.executable, "-m", "scripts.publish_patch_notes", "--file", str(manifest), "--check"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": "deliberately-invalid-database-url"},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("changes", [
    {"version": "9.9.9"}, {"version": "01.8.0"}, {"body": "   "},
    {"body": None}, {"title": "x" * 201}, {"body": "x" * 20001}, {"extra": True},
])
def test_invalid_manifest_is_rejected(tmp_path, changes):
    manifest = tmp_path / "invalid.json"
    payload = {"version": publish_patch_notes.SERVER_VERSION, "title": "Title", "body": "Body", **changes}
    manifest.write_text(json.dumps(payload))
    with pytest.raises(publish_patch_notes.ManifestError):
        publish_patch_notes.load_manifest(manifest)


def test_manifest_requires_all_fields(tmp_path):
    manifest = tmp_path / "invalid.json"
    manifest.write_text(json.dumps({"version": publish_patch_notes.SERVER_VERSION}))
    with pytest.raises(publish_patch_notes.ManifestError):
        publish_patch_notes.load_manifest(manifest)
