"""Editorial API behavior in an isolated PostgreSQL schema, never the app database."""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import blog
import db.models
import db.repositories.blog as blog_repository
import users.utils as auth
from db import get_db
from db.base import Base
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.guest_participation import GuestParticipation
from db.models.guess import CountrydleGuess
from db.models.question import CountrydleQuestion
from db.models.user import User
from schemas.blog import BlogPostUpdate

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]
UTC = timezone.utc


class EditorialClock(datetime):
    instant = datetime(2026, 10, 9, 0, 30, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.instant.astimezone(tz)
        return cls.instant.astimezone(timezone(timedelta(hours=-7))).replace(tzinfo=None)


def advance_clock():
    EditorialClock.instant += timedelta(seconds=1)


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def login(client, email):
    token = jwt.encode(
        {"sub": email, "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "isolated-editorial-test-signing-key",
        algorithm="HS256",
    )
    client.cookies.set("access_token", token, domain="test.local", path="/")



async def review_loaded_post(client, post_id=1):
    loaded = await client.get(f"/blog/admin/posts/{post_id}")
    assert loaded.status_code == 200, loaded.text
    return await client.post(
        f"/blog/admin/posts/{post_id}/review",
        json={"expected_updated_at": loaded.json()["updated_at"]},
    )


async def patch_loaded_post(client, patch, post_id=1):
    loaded = await client.get(f"/blog/admin/posts/{post_id}")
    assert loaded.status_code == 200, loaded.text
    return await client.patch(
        f"/blog/admin/posts/{post_id}",
        json={**patch, "expected_updated_at": loaded.json()["updated_at"]},
    )


async def wait_for_row_lock(sessions, blocked_pid):
    async def wait_until_blocked():
        async with sessions() as session:
            while not (await session.execute(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": blocked_pid},
            )).scalar_one():
                await asyncio.sleep(0.01)

    await asyncio.wait_for(wait_until_blocked(), timeout=5)

@pytest.fixture
async def editorial_store(monkeypatch):
    url = os.getenv("BLOG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set BLOG_TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = f"blog_editorial_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    sessions = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    EditorialClock.instant = datetime(2026, 10, 9, 0, 30, tzinfo=UTC)
    monkeypatch.setattr(blog, "datetime", EditorialClock)
    monkeypatch.setattr(blog_repository, "datetime", EditorialClock)
    monkeypatch.setattr(auth, "SECRET_KEY", "isolated-editorial-test-signing-key")
    monkeypatch.setattr(auth, "ALGORITHM", "HS256")
    try:
        async with engine.begin() as connection:
            tables = [model.__table__ for model in (
                User, Country, DailyBlogPost, CountrydleDay, CountrydleState,
                CountrydleQuestion, CountrydleGuess, GuestParticipation,
            )]
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=tables))
        async with sessions() as session:
            session.add_all([
                User(id=1, username="editor_one", email="editor-one@example.com", is_admin=True, verified=True),
                User(id=2, username="player", email="player@example.com", is_admin=False, verified=True),
                User(id=3, username="editor_two", email="editor-two@example.com", is_admin=True, verified=True),
            ])
            await session.commit()
            countries = [(1, "Poland", "Warsaw"), (2, "Germany", "Berlin"), (3, "Japan", "Tokyo"), (4, "France", "Paris")]
            for country_id, name, _ in countries:
                session.add(Country(id=country_id, name=name, official_name=name, md_file=f"data/countries/{name}.md"))
            await session.commit()
            today = EditorialClock.instant.date()
            dates = [today - timedelta(days=1), today, today + timedelta(days=1), today - timedelta(days=2)]
            for (country_id, name, capital), post_date in zip(countries, dates):
                session.add(DailyBlogPost(
                    id=country_id, date=post_date, country_id=country_id,
                    slug=f"{post_date.isoformat()}-{name.lower()}",
                    title=f"Countrydle recap: {name}", subtitle=f"The geography of {name}",
                    summary=f"The answer was {name}. Its capital is {capital}; the recap connects this fact with the available deduction history.",
                    reading_time_minutes=2, fast_facts={"capital": capital},
                    fun_facts=[{"title": "Capital", "description": f"{capital} is the capital of {name}."}],
                    deduction_masterclass={"steps": []},
                    content_markdown=f"## {name}\n\nThe capital of {name} is {capital}. This daily recap describes the country's geography and records the evidence available to the editor without inventing player questions. Readers can use capital clues alongside regional and border questions to narrow the country, but this article does not assert any unrecorded community statistics.",
                    source_links=[{"label": f"Wikipedia article: {name}", "url": f"https://en.wikipedia.org/wiki/{name}"}],
                    editorial_note="Automated draft awaiting an explicit review.", ai_assisted=True,
                    created_at=(EditorialClock.instant - timedelta(days=3)).replace(tzinfo=None),
                    updated_at=EditorialClock.instant - timedelta(days=3),
                ))
            await session.commit()

        async def database():
            async with sessions() as session:
                yield session

        app = FastAPI()
        app.include_router(blog.router)
        app.dependency_overrides[get_db] = database
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield SimpleNamespace(client=client, sessions=sessions, today=today, app=app)
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


@pytest.mark.parametrize("identity,expected", [(None, 401), ("player@example.com", 403)])
async def test_every_editorial_operation_requires_a_real_admin(editorial_store, identity, expected):
    client = editorial_store.client
    loaded = (await client.get("/blog/2026-10-08-poland")).json()
    if identity:
        login(client, identity)
    operations = [
        ("GET", "/blog/admin/posts", None),
        ("GET", "/blog/admin/posts/1", None),
        ("PATCH", "/blog/admin/posts/1", {
            "summary": "Unauthorized change", "expected_updated_at": loaded["updated_at"],
        }),
        ("POST", "/blog/admin/posts/1/review", {"expected_updated_at": "2026-10-06T00:30:00Z"}),
        ("POST", "/blog/admin/posts/1/unreview", None),
        ("POST", "/blog/generate-daily", None),
    ]
    for method, path, payload in operations:
        response = await client.request(method, path, json=payload)
        assert response.status_code == expected, (method, path, response.text)
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None
        assert post.reviewed_at is None
        assert post.summary != "Unauthorized change"


async def test_review_edit_and_revoke_are_persisted_and_publicly_visible(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    initial = (await client.get("/blog/2026-10-08-poland")).json()
    assert initial["editorial_status"] == "unreviewed"
    assert initial["reviewer_name"] is None
    assert initial["reviewed_at"] is None
    assert initial["ai_assisted"] is True

    advance_clock()
    reviewed = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": initial["updated_at"]},
    )
    assert reviewed.status_code == 200, reviewed.text
    result = reviewed.json()
    assert result["editorial_status"] == "reviewed"
    assert result["reviewer_name"] == "editor_one"
    assert timestamp(result["reviewed_at"]) == EditorialClock.instant
    assert timestamp(result["updated_at"]) > timestamp(initial["updated_at"])
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id == 1
        assert post.reviewed_at == EditorialClock.instant
    public = (await client.get("/blog/2026-10-08-poland")).json()
    assert public["reviewer_name"] == "editor_one"
    assert "editor-one@example.com" not in str(public)
    assert "reviewed_by_id" not in public
    listed = (await client.get("/blog")).json()["posts"][0]
    assert listed["editorial_status"] == "reviewed"
    assert listed["updated_at"] == public["updated_at"]

    advance_clock()
    edited = await patch_loaded_post(client, {
        "summary": "Poland's capital is Warsaw. The recap has been updated to distinguish stored geography from the logged deduction path.",
        "editorial_note": "The source attribution was checked; this edit awaits a new review.",
    })
    assert edited.status_code == 200, edited.text
    assert edited.json()["editorial_status"] == "unreviewed"
    assert edited.json()["reviewer_name"] is None
    assert edited.json()["reviewed_at"] is None
    assert timestamp(edited.json()["updated_at"]) > timestamp(result["updated_at"])
    after_edit = (await client.get("/blog/latest")).json()
    assert after_edit["summary"] == edited.json()["summary"]
    assert after_edit["editorial_status"] == "unreviewed"
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None
        assert post.reviewed_at is None

    login(client, "editor-two@example.com")
    advance_clock()
    rereviewed = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": after_edit["updated_at"]},
    )
    assert rereviewed.status_code == 200
    assert rereviewed.json()["reviewer_name"] == "editor_two"
    async with editorial_store.sessions() as session:
        assert (await session.get(DailyBlogPost, 1)).reviewed_by_id == 3
    advance_clock()
    revoked = await client.post("/blog/admin/posts/1/unreview")
    assert revoked.status_code == 200
    assert revoked.json()["reviewer_name"] is None
    assert revoked.json()["reviewed_at"] is None
    assert timestamp(revoked.json()["updated_at"]) > timestamp(rereviewed.json()["updated_at"])
    public = (await client.get("/blog/2026-10-08-poland")).json()
    assert public["editorial_status"] == "unreviewed"
    assert public["reviewed_at"] is None
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None and post.reviewed_at is None


@pytest.mark.parametrize("source", [
    {"label": "Script", "url": "javascript:alert(1)"},
    {"label": "Local file", "url": "file:///etc/passwd"},
    {"label": "Inline data", "url": "data:text/html,unsafe"},
    {"label": "Credentials", "url": "https://name:password@example.com/evidence"},
    {"label": "", "url": "https://en.wikipedia.org/wiki/Poland"},
    {"label": "x" * 201, "url": "https://en.wikipedia.org/wiki/Poland"},
    {"label": "Too long", "url": "https://example.com/" + "x" * 2048},
    {"label": "Normalized URL too long", "url": "https://example.com/" + "é" * 339},
])
async def test_invalid_source_patch_is_rejected_without_revoking_existing_review(editorial_store, source):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    initial = (await client.get("/blog/admin/posts/1")).json()
    advance_clock()
    response = await patch_loaded_post(client, {"source_links": [source]})
    assert response.status_code == 422, response.text
    assert any("source_links" in issue["loc"] for issue in response.json()["detail"])
    current = (await client.get("/blog/2026-10-08-poland")).json()
    assert current["source_links"] == initial["source_links"]
    assert current["updated_at"] == initial["updated_at"]
    assert current["editorial_status"] == "reviewed"
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id == 1


async def test_review_requires_sources_and_substantive_content(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await patch_loaded_post(client, {"source_links": []})).status_code == 200
    assert (await review_loaded_post(client)).status_code == 400
    assert (await patch_loaded_post(client, {
        "source_links": [{"label": "Poland", "url": "https://en.wikipedia.org/wiki/Poland"}],
        "content_markdown": "Short draft",
    })).status_code == 200
    assert (await review_loaded_post(client)).status_code == 400
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None and post.reviewed_at is None


async def test_utc_today_and_future_remain_secret_in_public_consumers(editorial_store):
    client = editorial_store.client
    # UTC is already Oct 9 while a western local timezone would still be Oct 8.
    response = await client.get("/blog?limit=1")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [post["id"] for post in response.json()["posts"]] == [1]
    second = (await client.get("/blog?page=2&limit=1")).json()
    assert [post["id"] for post in second["posts"]] == [4]
    latest = await client.get("/blog/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == 1
    detail = (await client.get("/blog/2026-10-08-poland")).json()
    assert [post["id"] for post in detail["related_posts"]] == [4]
    for post_id, name, post_date in [(2, "germany", editorial_store.today), (3, "japan", editorial_store.today + timedelta(days=1))]:
        for path in [f"/blog/{post_date.isoformat()}", f"/blog/{post_date.isoformat()}-{name}"]:
            assert (await client.get(path)).status_code == 404
        searched = (await client.get(f"/blog?search={name}")).json()
        assert searched["total"] == 0 and searched["posts"] == []
        login(client, "editor-one@example.com")
        assert (await client.get(f"/blog/admin/posts/{post_id}")).status_code == 200
        assert (await review_loaded_post(client, post_id)).status_code == 400
        assert (await client.post(f"/blog/generate-daily?target_date={post_date.isoformat()}")).status_code == 400
        client.cookies.clear()
    login(client, "editor-one@example.com")
    admin_list = (await client.get("/blog/admin/posts")).json()
    assert admin_list["total"] == 4
    assert [post["id"] for post in admin_list["posts"]] == [3, 2, 1, 4]


async def test_admin_missing_post_and_uneditable_attribution_do_not_mutate(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    loaded = (await client.get("/blog/admin/posts/1")).json()
    for method, path, body in [
        ("GET", "/blog/admin/posts/999", None),
        ("PATCH", "/blog/admin/posts/999", {
            "title": "Valid title", "expected_updated_at": loaded["updated_at"],
        }),
        ("POST", "/blog/admin/posts/999/review", {"expected_updated_at": "2026-10-06T00:30:00Z"}),
        ("POST", "/blog/admin/posts/999/unreview", None),
    ]:
        assert (await client.request(method, path, json=body)).status_code == 404
    for patch in [{}, {"reviewed_by_id": 1}, {"reviewed_at": "2026-10-08T12:00:00Z"}, {"date": "2026-10-07"}, {"ai_assisted": False}]:
        assert (await patch_loaded_post(client, patch)).status_code == 422
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None and post.reviewed_at is None
        assert post.ai_assisted is True


async def test_admin_editing_current_draft_never_makes_it_public(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    advance_clock()
    response = await patch_loaded_post(client, {
        "title": "Germany geography draft",
        "fast_facts": {"capital": "Berlin", "continent": "Europe"},
        "fun_facts": [{"title": "Federal capital", "description": "Berlin is Germany's capital."}],
        "deduction_masterclass": {"steps": []},
        "source_links": [{"label": "Germany source", "url": "https://en.wikipedia.org/wiki/Germany"}],
    }, post_id=2)
    assert response.status_code == 200, response.text
    assert response.json()["editorial_status"] == "unreviewed"
    admin_detail = (await client.get("/blog/admin/posts/2")).json()
    assert admin_detail["fast_facts"]["capital"] == "Berlin"
    assert admin_detail["fun_facts"][0]["description"] == "Berlin is Germany's capital."
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 2)
        assert post.fast_facts == {"capital": "Berlin", "continent": "Europe"}
        assert post.updated_at == EditorialClock.instant
        assert post.reviewed_by_id is None
    client.cookies.clear()
    assert (await client.get("/blog/2026-10-09-germany")).status_code == 404
    assert (await client.get("/blog?search=Germany")).json()["total"] == 0
    assert (await client.get("/blog/latest")).json()["id"] == 1


async def test_only_current_and_future_drafts_means_no_public_latest(editorial_store):
    async with editorial_store.sessions() as session:
        for post_id in (1, 4):
            await session.delete(await session.get(DailyBlogPost, post_id))
        await session.commit()
    client = editorial_store.client
    public_list = await client.get("/blog")
    assert public_list.status_code == 200
    assert public_list.json()["total"] == 0
    assert public_list.json()["posts"] == []
    assert (await client.get("/blog/latest")).status_code == 404
    login(client, "editor-one@example.com")
    admin_list = (await client.get("/blog/admin/posts")).json()
    assert admin_list["total"] == 2


async def test_review_rejects_another_editors_unseen_version_until_deliberate_reload(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    inspected = (await client.get("/blog/admin/posts/1")).json()

    login(client, "editor-two@example.com")
    advance_clock()
    changed = await patch_loaded_post(client, {
        "summary": "Poland's capital is Warsaw. Another editor has revised this recap's geography and source context.",
    })
    assert changed.status_code == 200, changed.text
    assert changed.json()["updated_at"] != inspected["updated_at"]

    login(client, "editor-one@example.com")
    stale = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": inspected["updated_at"]},
    )
    assert stale.status_code == 409, stale.text
    async with editorial_store.sessions() as session:
        saved = await session.get(DailyBlogPost, 1)
        assert saved.reviewed_by_id is None and saved.reviewed_at is None
        assert saved.summary == changed.json()["summary"]
        assert saved.updated_at == timestamp(changed.json()["updated_at"])
    public = await client.get("/blog/2026-10-08-poland")
    assert public.status_code == 200
    assert public.json()["editorial_status"] == "unreviewed"

    reloaded = (await client.get("/blog/admin/posts/1")).json()
    assert reloaded["summary"] == changed.json()["summary"]
    advance_clock()
    reviewed = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": reloaded["updated_at"]},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewer_name"] == "editor_one"


async def test_review_preserves_microsecond_version_and_normalizes_timezone(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    exact = EditorialClock.instant - timedelta(days=3) + timedelta(microseconds=123456)
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        post.updated_at = exact
        await session.commit()
    loaded = (await client.get("/blog/admin/posts/1")).json()
    assert timestamp(loaded["updated_at"]) == exact
    rounded = exact.replace(microsecond=123000).isoformat()
    rejected = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": rounded},
    )
    assert rejected.status_code == 409, rejected.text
    offset_token = exact.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    accepted = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": offset_token},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["reviewer_name"] == "editor_one"


@pytest.mark.parametrize("payload", [
    None, {}, {"expected_updated_at": "2026-10-06T00:30:00"},
    {"expected_updated_at": "not-a-date"},
    {"expected_updated_at": "2026-10-06T00:30:00Z", "reviewed_by_id": 3},
])
async def test_review_requires_a_timezone_aware_version_without_client_attribution(editorial_store, payload):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    response = await client.post("/blog/admin/posts/1/review", json=payload)
    assert response.status_code == 422, response.text
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None and post.reviewed_at is None


@pytest.mark.parametrize("patch", [
    {"fast_facts": {"population": {"estimate": 100}}},
    {"fast_facts": {"borders": ["Germany"]}},
    {"fast_facts": {"population": 10 ** 310}},
    {"fast_facts": {"population": -(10 ** 310)}},
    {"fun_facts": [{}]},
    {"fun_facts": [{"title": "Capital", "description": None}]},
    {"fun_facts": [{"title": 42, "description": "Warsaw is the capital."}]},
    {"deduction_masterclass": {"steps": [{}]}},
    {"deduction_masterclass": {"steps": [{"question": 123}]}},
    {"deduction_masterclass": {"steps": [{"question": "Is it in Europe?", "answer": None}]}},
    {"deduction_masterclass": {"steps": {}}},
    {"deduction_masterclass": {"pro_tip": ["Use evidence"]}},
    {"deduction_masterclass": {"quiz": {}}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": "Warsaw",
        "incorrect_distractor": "Berlin",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": "Warsaw",
        "incorrect_distractor": "Berlin", "explanation": 42,
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "   ", "correct_answer": "Warsaw",
        "incorrect_distractor": "Berlin", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": "",
        "incorrect_distractor": "Berlin", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": "Warsaw",
        "incorrect_distractor": " \t ", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": "Warsaw",
        "incorrect_distractor": "Berlin", "explanation": "\n ",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": " Warsaw ",
        "incorrect_distractor": "WARSAW", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": r"Warsaw\(Poland\)",
        "incorrect_distractor": "Warsaw(Poland)", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": "\ufeffWarsaw\\(Poland\\)\ufeff",
        "incorrect_distractor": "Warsaw(Poland)", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": r"Warsaw\_capital\_",
        "incorrect_distractor": "WARSAW_capital_", "explanation": "Warsaw is the capital.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": r"Warsaw\[1\]",
        "incorrect_distractor": "Warsaw[1]", "explanation": "Keep [citation needed] warnings.",
    }}},
    {"deduction_masterclass": {"quiz": {
        "question": "Which city is the capital?", "correct_answer": r"Warsaw\*",
        "incorrect_distractor": "Warsaw*", "explanation": "Warsaw is the capital.",
    }}},
])
async def test_malformed_editorial_json_never_bricks_public_or_admin_readers(editorial_store, patch):
    # Generation validates this same editable-content schema before persistence.
    with pytest.raises(ValidationError):
        BlogPostUpdate.model_validate(patch)
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    initial = (await client.get("/blog/admin/posts/1")).json()
    advance_clock()
    response = await patch_loaded_post(client, patch)
    assert response.status_code == 422, response.text
    assert all("expected_updated_at" not in issue["loc"] for issue in response.json()["detail"])
    for path in ["/blog/admin/posts/1", "/blog/2026-10-08-poland", "/blog/latest"]:
        readable = await client.get(path)
        assert readable.status_code == 200, readable.text
        current = readable.json()
        for field in ["fast_facts", "fun_facts", "deduction_masterclass", "updated_at", "editorial_status"]:
            assert current[field] == initial[field]
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id == 1
        assert post.fast_facts == initial["fast_facts"]
        assert post.fun_facts == initial["fun_facts"]
        assert post.deduction_masterclass == initial["deduction_masterclass"]

    # The persisted article remains editable after rejecting the malformed request.
    repaired = await patch_loaded_post(client, {"editorial_note": "Checked the rejected edit."})
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["editorial_status"] == "unreviewed"


@pytest.mark.parametrize(("answer", "distractor"), [
    (r"Warsaw\(Poland\)", "Berlin(Germany)"),
    (r"Warsaw\[citation needed\]", "Warsaw"),
    (r"Warsaw\[1\]", "Warsaw[2]"),
    (r"Warsaw\!", "Warsaw!"),
])
async def test_distinct_displayed_quiz_choices_preserve_raw_text_and_citation_markers(
    editorial_store, answer, distractor,
):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    quiz = {
        "question": "Which city is the capital?", "correct_answer": answer,
        "incorrect_distractor": distractor,
        "explanation": r"Check \[citation needed\] and \[1\] before editorial review.",
    }
    generated = BlogPostUpdate.model_validate({"deduction_masterclass": {"quiz": quiz}})
    assert generated.model_dump(exclude_unset=True)["deduction_masterclass"]["quiz"] == quiz
    response = await patch_loaded_post(client, {"deduction_masterclass": {"quiz": quiz}})
    assert response.status_code == 200, response.text
    for path in ["/blog/admin/posts/1", "/blog/2026-10-08-poland"]:
        readable = await client.get(path)
        assert readable.status_code == 200, readable.text
        assert readable.json()["deduction_masterclass"]["quiz"] == quiz
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.deduction_masterclass["quiz"] == quiz


async def test_valid_generated_nested_shapes_and_unknown_facts_round_trip_without_fabrication(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    patch = {
        "fast_facts": {"capital": "Warsaw", "population": None, "area": 312696, "coastline": True},
        "fun_facts": [{"title": "Capital", "description": "Warsaw is Poland's capital.", "source": "Stored geography"}],
        "deduction_masterclass": {
            "steps": [{
                "step": 1, "question": "Is it in Europe?", "answer": "Yes",
                "explanation": "Poland is in Europe.", "source_url": "https://en.wikipedia.org/wiki/Poland",
            }, {"question": "Does it border Germany?"}],
            "pro_tip": "Use border clues alongside the region.",
            "quiz": {
                "question": "Which city is Poland's capital?", "correct_answer": "Warsaw",
                "incorrect_distractor": "Berlin", "explanation": "Warsaw is the capital.",
            },
            "notes": "Retain legacy generator metadata.",
        },
        "editorial_note": "The population is unknown in the stored facts; no estimate was added.",
    }
    response = await patch_loaded_post(client, patch)
    assert response.status_code == 200, response.text
    for path in ["/blog/admin/posts/1", "/blog/2026-10-08-poland"]:
        readable = await client.get(path)
        assert readable.status_code == 200, readable.text
        for field, value in patch.items():
            assert readable.json()[field] == value
        assert readable.json()["fast_facts"]["population"] is None
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.fast_facts == patch["fast_facts"]
        assert post.fun_facts == patch["fun_facts"]
        assert post.deduction_masterclass == patch["deduction_masterclass"]


async def test_persisted_malformed_draft_is_admin_readable_but_requires_repair_before_review(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        post.fun_facts = [{}]
        post.deduction_masterclass = {"quiz": {"question": "Incomplete generated quiz"}}
        await session.commit()

    loaded = await client.get("/blog/admin/posts/1")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["fun_facts"] == [{}]
    assert loaded.json()["deduction_masterclass"]["quiz"]["question"] == "Incomplete generated quiz"
    rejected = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": loaded.json()["updated_at"]},
    )
    assert rejected.status_code == 400, rejected.text
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None and post.reviewed_at is None

    advance_clock()
    repaired = await patch_loaded_post(client, {
        "fun_facts": [{"title": "Capital", "description": "Warsaw is the capital of Poland."}],
        "deduction_masterclass": {"steps": []},
    })
    assert repaired.status_code == 200, repaired.text
    public = await client.get("/blog/2026-10-08-poland")
    assert public.status_code == 200, public.text
    assert public.json()["fun_facts"] == repaired.json()["fun_facts"]
    assert public.json()["deduction_masterclass"] == {"steps": []}
    reviewed = await client.post(
        "/blog/admin/posts/1/review", json={"expected_updated_at": repaired.json()["updated_at"]},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewer_name"] == "editor_one"


@pytest.mark.parametrize("version", ["missing", None, 1791246600, "not-a-date", "2026-10-06T00:30:00"])
async def test_save_requires_a_raw_timezone_aware_version_without_revoking_review(editorial_store, version):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    initial = (await client.get("/blog/admin/posts/1")).json()
    payload = {"summary": "This unsaved correction must not revoke the existing human review."}
    if version != "missing":
        payload["expected_updated_at"] = version
    advance_clock()
    response = await client.patch("/blog/admin/posts/1", json=payload)
    assert response.status_code == 422, response.text
    assert any("expected_updated_at" in issue["loc"] for issue in response.json()["detail"])
    current = (await client.get("/blog/admin/posts/1")).json()
    for field in ["summary", "updated_at", "reviewed_at", "reviewer_name", "editorial_status"]:
        assert current[field] == initial[field]


async def test_timestamp_only_save_is_not_an_edit_and_does_not_revoke_review(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    loaded = (await client.get("/blog/admin/posts/1")).json()
    advance_clock()
    response = await client.patch(
        "/blog/admin/posts/1", json={"expected_updated_at": loaded["updated_at"]},
    )
    assert response.status_code == 422, response.text
    current = (await client.get("/blog/admin/posts/1")).json()
    assert current["updated_at"] == loaded["updated_at"]
    assert current["reviewed_at"] == loaded["reviewed_at"]
    assert current["editorial_status"] == "reviewed"


async def test_save_preserves_microsecond_version_and_normalizes_timezone(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    exact = EditorialClock.instant - timedelta(days=3) + timedelta(microseconds=123456)
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        post.updated_at = exact
        await session.commit()
    loaded = (await client.get("/blog/admin/posts/1")).json()
    assert timestamp(loaded["updated_at"]) == exact
    correction = "Poland's capital is Warsaw. This correction must preserve the precise article version."
    rejected = await client.patch("/blog/admin/posts/1", json={
        "summary": correction,
        "expected_updated_at": exact.replace(microsecond=123000).isoformat(),
    })
    assert rejected.status_code == 409, rejected.text
    unchanged = (await client.get("/blog/admin/posts/1")).json()
    assert unchanged["summary"] == loaded["summary"]
    assert unchanged["updated_at"] == loaded["updated_at"]
    offset_token = exact.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    accepted = await client.patch("/blog/admin/posts/1", json={
        "summary": correction, "expected_updated_at": offset_token,
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["summary"] == correction
    assert "expected_updated_at" not in accepted.json()
    async with editorial_store.sessions() as session:
        saved = await session.get(DailyBlogPost, 1)
        assert saved.summary == correction
        assert saved.updated_at == EditorialClock.instant
        assert "expected_updated_at" not in saved.__dict__


async def test_concurrent_editors_preserve_saved_correction_and_reject_waiting_stale_save(editorial_store, monkeypatch):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    loaded = (await client.get("/blog/admin/posts/1")).json()
    locked, release, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    waiting_pid = None
    original_update = blog_repository.BlogRepository.update
    original_get = blog_repository.BlogRepository.get_by_id

    async def pause_first_save(repo, post, fields):
        locked.set()
        await release.wait()
        return await original_update(repo, post, fields)

    async def track_waiting_editor(repo, post_id, *, for_update=False):
        nonlocal waiting_pid
        if for_update and locked.is_set():
            waiting_pid = (await repo.session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            waiting.set()
        return await original_get(repo, post_id, for_update=for_update)

    monkeypatch.setattr(blog_repository.BlogRepository, "update", pause_first_save)
    monkeypatch.setattr(blog_repository.BlogRepository, "get_by_id", track_waiting_editor)
    correction = "Poland's capital is Warsaw. The first editor saved a checked correction which a stale draft must not overwrite."
    advance_clock()
    async with AsyncClient(transport=ASGITransport(app=editorial_store.app), base_url="http://test") as other:
        login(other, "editor-two@example.com")
        first = asyncio.create_task(client.patch("/blog/admin/posts/1", json={
            "summary": correction, "expected_updated_at": loaded["updated_at"],
        }))
        second = None
        try:
            await asyncio.wait_for(locked.wait(), timeout=5)
            second = asyncio.create_task(other.patch("/blog/admin/posts/1", json={
                "summary": "A stale second editor draft must never overwrite the saved correction.",
                "expected_updated_at": loaded["updated_at"],
            }))
            await asyncio.wait_for(waiting.wait(), timeout=5)
            await wait_for_row_lock(editorial_store.sessions, waiting_pid)
        finally:
            release.set()
            tasks = [task for task in [first, second] if task is not None]
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
    assert [response.status_code for response in responses] == [200, 409]
    saved = responses[0].json()
    current = (await client.get("/blog/admin/posts/1")).json()
    assert current["summary"] == correction
    assert current["updated_at"] == saved["updated_at"]
    assert current["editorial_status"] == "unreviewed"
    assert current["reviewer_name"] is None and current["reviewed_at"] is None
    async with editorial_store.sessions() as session:
        persisted = await session.get(DailyBlogPost, 1)
        assert persisted.summary == correction
        assert persisted.updated_at == timestamp(saved["updated_at"])
        assert persisted.reviewed_by_id is None and persisted.reviewed_at is None


async def test_regeneration_waiting_on_concurrent_review_fails_cas_without_changing_article(editorial_store, monkeypatch):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    loaded = (await client.get("/blog/admin/posts/1")).json()
    locked, release = asyncio.Event(), asyncio.Event()
    original_review = blog_repository.BlogRepository.set_review

    async def pause_review(repo, post, reviewer_id):
        locked.set()
        await release.wait()
        return await original_review(repo, post, reviewer_id)

    monkeypatch.setattr(blog_repository.BlogRepository, "set_review", pause_review)
    advance_clock()
    async with editorial_store.sessions() as generation_session:
        repo = blog_repository.BlogRepository(generation_session)
        original = await repo.get_by_id(1)
        expected_version = original.updated_at
        await generation_session.rollback()
        review = asyncio.create_task(client.post(
            "/blog/admin/posts/1/review", json={"expected_updated_at": loaded["updated_at"]},
        ))
        replacement = None
        try:
            await asyncio.wait_for(locked.wait(), timeout=5)
            generation_pid = (await generation_session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            replacement = asyncio.create_task(repo.replace_generated(
                1, {"summary": "An obsolete generated replacement must not erase a concurrently reviewed article."},
                expected_version,
            ))
            await wait_for_row_lock(editorial_store.sessions, generation_pid)
        finally:
            release.set()
            reviewed = await asyncio.wait_for(review, timeout=5)
            if replacement is not None:
                replaced = await asyncio.wait_for(replacement, timeout=5)
        assert reviewed.status_code == 200, reviewed.text
        assert replaced is False
        refreshed = await repo.get_by_id(1)
        assert refreshed is original
        assert refreshed.summary == loaded["summary"]
        assert refreshed.reviewed_by_id == 1
        assert refreshed.reviewed_at == timestamp(reviewed.json()["reviewed_at"])
        assert refreshed.updated_at == timestamp(reviewed.json()["updated_at"])
    current = (await client.get("/blog/2026-10-08-poland")).json()
    assert current["summary"] == loaded["summary"]
    assert current["editorial_status"] == "reviewed"
    assert current["reviewer_name"] == "editor_one"
    assert current["updated_at"] == reviewed.json()["updated_at"]


async def test_regeneration_clears_review_in_sql_and_refreshes_stale_identity(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    loaded = (await client.get("/blog/admin/posts/1")).json()
    async with editorial_store.sessions() as generation_session:
        repo = blog_repository.BlogRepository(generation_session)
        stale = await repo.get_by_id(1)
        expected_version = stale.updated_at
        assert stale.reviewed_by_id is None and stale.reviewed_at is None
        # Isolate unconditional SQL clearing from the CAS guard: simulate an older
        # reviewer which wrote attribution without advancing the version.
        async with editorial_store.sessions() as review_session:
            await review_session.execute(text("""
                UPDATE daily_blog_posts
                SET reviewed_by_id = 1, reviewed_at = :reviewed_at
                WHERE id = 1
            """), {"reviewed_at": EditorialClock.instant})
            await review_session.commit()
        advance_clock()
        payload = {
            "title": "Regenerated Poland geography",
            "subtitle": "Stored geography and recorded deduction",
            "summary": "Poland's capital is Warsaw. This regenerated article is an unreviewed draft based on stored geography.",
            "fast_facts": {"capital": "Warsaw", "population": None},
            "fun_facts": [{"title": "Capital", "description": "Warsaw is Poland's capital."}],
            "deduction_masterclass": {"steps": []},
            "content_markdown": loaded["content_markdown"],
            "source_links": [],
            "editorial_note": "Generated draft; source consultation and human review are not asserted.",
            "ai_assisted": True,
        }
        assert await repo.replace_generated(1, payload, expected_version) is True
        refreshed = await repo.get_by_id(1)
        assert refreshed is stale
        for name, value in payload.items():
            assert getattr(refreshed, name) == value
        assert refreshed.reviewed_by_id is None and refreshed.reviewed_at is None
        assert refreshed.reviewer is None
        assert refreshed.updated_at == EditorialClock.instant
        assert refreshed.created_at.replace(tzinfo=UTC) == timestamp(loaded["created_at"])
        assert refreshed.country_id == loaded["country_id"]
        assert refreshed.date.isoformat() == loaded["date"]
        assert refreshed.slug == loaded["slug"]
        assert refreshed.reading_time_minutes == loaded["reading_time_minutes"]
    public = (await client.get("/blog/2026-10-08-poland")).json()
    assert public["title"] == payload["title"]
    assert public["editorial_status"] == "unreviewed"
    assert public["reviewer_name"] is None and public["reviewed_at"] is None


@pytest.mark.parametrize("intervening_change", ["edit", "review", "delete"])
async def test_regeneration_failed_cas_preserves_current_row_and_review(editorial_store, intervening_change):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    loaded = (await client.get("/blog/admin/posts/1")).json()
    expected_version = timestamp(loaded["updated_at"])
    advance_clock()
    if intervening_change == "edit":
        changed = await patch_loaded_post(client, {"editorial_note": "A checked editorial correction."})
        assert changed.status_code == 200, changed.text
    elif intervening_change == "review":
        changed = await review_loaded_post(client)
        assert changed.status_code == 200, changed.text
    else:
        async with editorial_store.sessions() as session:
            await session.delete(await session.get(DailyBlogPost, 1))
            await session.commit()
    async with editorial_store.sessions() as session:
        before = await blog_repository.BlogRepository(session).get_by_id(1)
        snapshot = {
            column.name: getattr(before, column.name) for column in DailyBlogPost.__table__.columns
        } if before is not None else None
    advance_clock()
    async with editorial_store.sessions() as session:
        repo = blog_repository.BlogRepository(session)
        assert await repo.replace_generated(
            1, {"title": "Obsolete regeneration", "source_links": []}, expected_version,
        ) is False
        assert not session.in_transaction()
    async with editorial_store.sessions() as session:
        current = await blog_repository.BlogRepository(session).get_by_id(1)
        actual = {
            column.name: getattr(current, column.name) for column in DailyBlogPost.__table__.columns
        } if current is not None else None
        assert actual == snapshot


async def test_unknown_historical_creation_timestamp_stays_null_in_all_readers_and_edits(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    initial = (await client.get("/blog/admin/posts/1")).json()
    async with editorial_store.sessions() as session:
        # Raw SQL guarantees an actual historical NULL, not an ORM default on insert.
        await session.execute(text("UPDATE daily_blog_posts SET created_at = NULL WHERE id IN (1, 4)"))
        await session.commit()
    for path in ["/blog", "/blog/admin/posts"]:
        listed = await client.get(path)
        assert listed.status_code == 200, listed.text
        historical = [post for post in listed.json()["posts"] if post["id"] in (1, 4)]
        assert len(historical) == 2
        assert all(post["created_at"] is None for post in historical)
        assert all(timestamp(post["updated_at"]).tzinfo is not None for post in historical)
    for path in ["/blog/latest", "/blog/2026-10-08", "/blog/2026-10-08-poland", "/blog/admin/posts/1"]:
        detail = await client.get(path)
        assert detail.status_code == 200, detail.text
        assert detail.json()["created_at"] is None
        assert detail.json()["updated_at"] == initial["updated_at"]
        for related in detail.json()["related_posts"] or []:
            assert related["created_at"] is None
    advance_clock()
    reviewed = await review_loaded_post(client)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["created_at"] is None
    advance_clock()
    edited = await patch_loaded_post(client, {"editorial_note": "Historical publication time is unknown."})
    assert edited.status_code == 200, edited.text
    assert edited.json()["created_at"] is None
    assert edited.json()["editorial_status"] == "unreviewed"
    async with editorial_store.sessions() as session:
        historical = await session.get(DailyBlogPost, 1)
        assert historical.created_at is None
        assert historical.updated_at == timestamp(edited.json()["updated_at"])


async def test_stale_save_cannot_revoke_a_review_added_after_editor_loaded_draft(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    loaded = (await client.get("/blog/admin/posts/1")).json()
    advance_clock()
    reviewed = await review_loaded_post(client)
    assert reviewed.status_code == 200, reviewed.text
    advance_clock()
    rejected = await client.patch("/blog/admin/posts/1", json={
        "summary": "This older editor draft must not invalidate a later review.",
        "expected_updated_at": loaded["updated_at"],
    })
    assert rejected.status_code == 409, rejected.text
    current = (await client.get("/blog/admin/posts/1")).json()
    assert current == reviewed.json()
    async with editorial_store.sessions() as session:
        saved = await session.get(DailyBlogPost, 1)
        assert saved.summary == loaded["summary"]
        assert saved.reviewed_by_id == 1
        assert saved.reviewed_at == timestamp(reviewed.json()["reviewed_at"])
        assert saved.updated_at == timestamp(reviewed.json()["updated_at"])


@pytest.mark.parametrize("clock_delta", [timedelta(0), timedelta(seconds=-1)])
@pytest.mark.parametrize("mutation", ["edit", "review", "unreview", "regeneration"])
async def test_every_mutation_advances_version_despite_tied_or_backward_utc_clock(editorial_store, mutation, clock_delta):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    original_version = EditorialClock.instant
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        post.updated_at = original_version
        if mutation == "unreview":
            post.reviewed_by_id = 1
            post.reviewed_at = original_version
        await session.commit()
    loaded = (await client.get("/blog/admin/posts/1")).json()
    EditorialClock.instant += clock_delta
    if mutation == "edit":
        changed = await patch_loaded_post(client, {"editorial_note": "Checked editorial correction."})
    elif mutation == "review":
        changed = await review_loaded_post(client)
    elif mutation == "unreview":
        changed = await client.post("/blog/admin/posts/1/unreview")
    else:
        async with editorial_store.sessions() as session:
            assert await blog_repository.BlogRepository(session).replace_generated(
                1, {"editorial_note": "Regenerated draft."}, timestamp(loaded["updated_at"]),
            ) is True
        changed = await client.get("/blog/admin/posts/1")
    assert changed.status_code == 200, changed.text
    assert timestamp(changed.json()["updated_at"]) == original_version + timedelta(microseconds=1)
    rejected = await client.patch("/blog/admin/posts/1", json={
        "summary": "A stale timestamp must not authorize overwriting the latest article.",
        "expected_updated_at": loaded["updated_at"],
    })
    assert rejected.status_code == 409, rejected.text
    assert (await client.get("/blog/admin/posts/1")).json() == changed.json()
