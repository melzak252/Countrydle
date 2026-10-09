"""Editorial API behavior in an isolated PostgreSQL schema, never the app database."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
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
            yield SimpleNamespace(client=client, sessions=sessions, today=today)
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


@pytest.mark.parametrize("identity,expected", [(None, 401), ("player@example.com", 403)])
async def test_every_editorial_operation_requires_a_real_admin(editorial_store, identity, expected):
    client = editorial_store.client
    if identity:
        login(client, identity)
    operations = [
        ("GET", "/blog/admin/posts", None),
        ("GET", "/blog/admin/posts/1", None),
        ("PATCH", "/blog/admin/posts/1", {"summary": "Unauthorized change"}),
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
    edited = await client.patch("/blog/admin/posts/1", json={
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
])
async def test_invalid_source_patch_is_rejected_without_revoking_existing_review(editorial_store, source):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    initial = (await client.get("/blog/admin/posts/1")).json()
    advance_clock()
    response = await client.patch("/blog/admin/posts/1", json={"source_links": [source]})
    assert response.status_code == 422, response.text
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
    assert (await client.patch("/blog/admin/posts/1", json={"source_links": []})).status_code == 200
    assert (await review_loaded_post(client)).status_code == 400
    assert (await client.patch("/blog/admin/posts/1", json={
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
    for method, path, body in [
        ("GET", "/blog/admin/posts/999", None),
        ("PATCH", "/blog/admin/posts/999", {"title": "Valid title"}),
        ("POST", "/blog/admin/posts/999/review", {"expected_updated_at": "2026-10-06T00:30:00Z"}),
        ("POST", "/blog/admin/posts/999/unreview", None),
    ]:
        assert (await client.request(method, path, json=body)).status_code == 404
    for patch in [{}, {"reviewed_by_id": 1}, {"reviewed_at": "2026-10-08T12:00:00Z"}, {"date": "2026-10-07"}, {"ai_assisted": False}]:
        assert (await client.patch("/blog/admin/posts/1", json=patch)).status_code == 422
    async with editorial_store.sessions() as session:
        post = await session.get(DailyBlogPost, 1)
        assert post.reviewed_by_id is None and post.reviewed_at is None
        assert post.ai_assisted is True


async def test_admin_editing_current_draft_never_makes_it_public(editorial_store):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    advance_clock()
    response = await client.patch("/blog/admin/posts/2", json={
        "title": "Germany geography draft",
        "fast_facts": {"capital": "Berlin", "continent": "Europe"},
        "fun_facts": [{"title": "Federal capital", "description": "Berlin is Germany's capital."}],
        "deduction_masterclass": {"steps": []},
        "source_links": [{"label": "Germany source", "url": "https://en.wikipedia.org/wiki/Germany"}],
    })
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
    changed = await client.patch("/blog/admin/posts/1", json={
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
])
async def test_malformed_editorial_json_never_bricks_public_or_admin_readers(editorial_store, patch):
    client = editorial_store.client
    login(client, "editor-one@example.com")
    assert (await review_loaded_post(client)).status_code == 200
    initial = (await client.get("/blog/admin/posts/1")).json()
    advance_clock()
    response = await client.patch("/blog/admin/posts/1", json=patch)
    assert response.status_code == 422, response.text
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
    repaired = await client.patch("/blog/admin/posts/1", json={"editorial_note": "Checked the rejected edit."})
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["editorial_status"] == "unreviewed"


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
    response = await client.patch("/blog/admin/posts/1", json=patch)
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
    repaired = await client.patch("/blog/admin/posts/1", json={
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
