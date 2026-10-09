"""Generation consumers must release PostgreSQL connections before provider I/O.

Set BLOG_TEST_DATABASE_URL to a disposable PostgreSQL database. Each test owns
an isolated schema and a single-slot pool; only the external provider is a fixture.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import blog
import db.models
import users.utils as auth
import utils
import utils.blog_generator as generator
from db import get_db
from db.base import Base
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.guest_participation import GuestParticipation
from db.models.guess import CountrydleGuess
from db.models.question import CountrydleQuestion
from db.models.user import User
from db.repositories.blog import BlogRepository
from scripts import backfill_blog_posts, regenerate_all_blog_posts, regenerate_recent_blog_posts

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]


@pytest.fixture
async def generation_store(monkeypatch):
    url = os.getenv("BLOG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set BLOG_TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = f"blog_generation_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        url, pool_size=1, max_overflow=0, pool_timeout=2,
        connect_args={"server_settings": {"search_path": schema}},
    )
    sessions = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=1), today - timedelta(days=2)]
    try:
        async with engine.begin() as connection:
            tables = [model.__table__ for model in (
                User, Country, DailyBlogPost, CountrydleDay, CountrydleState,
                CountrydleQuestion, CountrydleGuess, GuestParticipation,
            )]
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=tables))
            # Generation reads only stored text, not embeddings; do not require
            # the optional vector extension in a disposable PostgreSQL fixture.
            await connection.execute(text(
                "CREATE TABLE country_fragments (id SERIAL PRIMARY KEY, "
                "country_id INTEGER NOT NULL REFERENCES countries(id), text TEXT NOT NULL)"
            ))
        async with sessions() as session:
            session.add(User(id=1, username="generation_editor", email="generation@example.com",
                             is_admin=True, verified=True))
            session.add(Country(id=1, name="Poland", official_name="Republic of Poland", md_file="Poland.md"))
            await session.commit()
            session.add_all([CountrydleDay(id=index, country_id=1, date=day)
                             for index, day in enumerate(dates, 1)])
            await session.commit()
            session.add_all([CountrydleQuestion(
                day_id=index, original_question="Is it in Europe?", question="Is it in Europe?",
                valid=True, answer=True, explanation="Poland is in Europe.",
                fact_provenance=[{"provenance": {
                    "status": "cited", "citation": "Stored geographic evidence",
                    "source_url": "https://en.wikipedia.org/wiki/Poland",
                }}],
            ) for index in (1, 2)])
            await session.execute(text(
                "INSERT INTO country_fragments (country_id, text) VALUES (1, 'Poland is in Europe.')"
            ))
            await session.commit()

        monkeypatch.setattr(auth, "SECRET_KEY", "generation-fixture-signing-key")
        monkeypatch.setattr(auth, "ALGORITHM", "HS256")
        monkeypatch.setenv("GEMINI_API_KEY", "disposable-generation-fixture")
        monkeypatch.setattr(generator, "get_country_sqlite_facts", lambda _: {
            "capital": "Warsaw", "continent": "Europe", "region": "Central Europe",
            "borders": "Germany", "water_access": "Baltic Sea", "area_km2": "312,696 km²",
        })
        for consumer in (utils, backfill_blog_posts, regenerate_all_blog_posts, regenerate_recent_blog_posts):
            monkeypatch.setattr(consumer, "AsyncSessionLocal", sessions)

        async def database():
            async with sessions() as session:
                yield session

        app = FastAPI()
        app.include_router(blog.router)
        app.dependency_overrides[get_db] = database
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = jwt.encode(
                {"sub": "generation@example.com", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                "generation-fixture-signing-key", algorithm="HS256",
            )
            client.cookies.set("access_token", token, domain="test.local", path="/")
            yield SimpleNamespace(engine=engine, sessions=sessions, client=client, dates=dates)
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()


@pytest.fixture
async def paused_provider(monkeypatch):
    loop = asyncio.get_running_loop()
    entered = asyncio.Queue()
    release = Event()
    article = {
        "title": "Poland: stored geography recap", "subtitle": "A past puzzle's deduction path",
        "summary": "Poland is in Europe. Its capital is Warsaw, and it borders Germany.",
        "fun_facts": [{"title": "Capital", "description": "Warsaw is Poland's capital."}],
        "trivia_quiz": {"question": "What is Poland's capital?", "correct_answer": "Warsaw",
                        "incorrect_distractor": "Berlin", "explanation": "Warsaw is Poland's capital."},
    }

    def provider(*args):
        loop.call_soon_threadsafe(entered.put_nowait, None)
        if not release.wait(15):
            raise AssertionError("Test did not release the paused provider")
        return deepcopy(article)

    monkeypatch.setattr(generator, "_call_gemini_api", provider)
    try:
        yield SimpleNamespace(entered=entered, release=release, article=article)
    finally:
        release.set()


async def wait_for_provider_and_probe_pool(store, provider, calls=1):
    for _ in range(calls):
        await asyncio.wait_for(provider.entered.get(), timeout=5)
    assert store.engine.pool.checkedout() == 0
    async with store.sessions() as session:
        assert await asyncio.wait_for(session.scalar(text("SELECT 1")), timeout=3) == 1
    assert store.engine.pool.checkedout() == 0


async def test_concurrent_admin_generation_releases_auth_and_input_reads_before_provider(
    generation_store, paused_provider,
):
    store = generation_store
    tasks = [asyncio.create_task(store.client.post(
        "/blog/generate-daily", params={"target_date": day.isoformat()},
    )) for day in store.dates]
    try:
        await wait_for_provider_and_probe_pool(store, paused_provider, calls=len(tasks))
    finally:
        paused_provider.release.set()
        responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
    for response, day in zip(responses, store.dates):
        assert response.status_code == 200, response.text
        post = response.json()
        assert post["date"] == day.isoformat()
        assert post["title"] == paused_provider.article["title"]
        assert post["ai_assisted"] is True
        assert post["editorial_status"] == "unreviewed"
        assert post["deduction_masterclass"]["quiz"] == paused_provider.article["trivia_quiz"]
        assert post["source_links"][0]["url"] == "https://en.wikipedia.org/wiki/Poland"
        public = await store.client.get(f"/blog/{day.isoformat()}")
        assert public.status_code == 200, public.text
        assert public.json()["updated_at"] == post["updated_at"]
    # Existing posts are returned without another provider invocation.
    existing = await store.client.post("/blog/generate-daily", params={"target_date": store.dates[0].isoformat()})
    assert existing.status_code == 200
    assert paused_provider.entered.empty()


@pytest.mark.parametrize("consumer", ["scheduler", "backfill"])
async def test_background_generation_releases_discovery_reads_and_persists_real_article(
    generation_store, paused_provider, consumer,
):
    store = generation_store
    work = (utils.generate_yesterday_blog_post() if consumer == "scheduler"
            else backfill_blog_posts.backfill_blog_posts(days_count=2))
    task = asyncio.create_task(work)
    try:
        await wait_for_provider_and_probe_pool(store, paused_provider)
    finally:
        paused_provider.release.set()
        await asyncio.wait_for(task, timeout=10)
    async with store.sessions() as session:
        posts = list((await session.scalars(select(DailyBlogPost).order_by(DailyBlogPost.date.desc()))).all())
        assert len(posts) == (1 if consumer == "scheduler" else 2)
        assert [post.date for post in posts] == store.dates[:len(posts)]
        assert all(post.title == paused_provider.article["title"] for post in posts)
        assert all(post.ai_assisted is True and post.reviewed_at is None for post in posts)


@pytest.mark.parametrize("consumer", ["recent", "all"])
@pytest.mark.parametrize("intervening_review", [False, True])
async def test_regeneration_releases_pool_and_only_replaces_its_original_version(
    generation_store, paused_provider, consumer, intervening_review,
):
    store = generation_store
    original = generator._generate_fallback_template("Poland", [], store.dates[0])
    async with store.sessions() as session:
        post = DailyBlogPost(
            date=store.dates[0], country_id=1, slug=f"{store.dates[0]}-poland",
            **{key: value for key, value in original.items() if key != "reading_time_minutes"},
        )
        # The all-post consumer only regenerates articles without the clean marker.
        post.content_markdown = "## Historical recap\n\nPoland is in Europe. Its capital is Warsaw."
        session.add(post)
        await session.commit()
        post_id, old_version, old_title = post.id, post.updated_at, post.title
    work = (regenerate_recent_blog_posts.regenerate_recent(1) if consumer == "recent"
            else regenerate_all_blog_posts.regenerate_all())
    task = asyncio.create_task(work)
    try:
        await wait_for_provider_and_probe_pool(store, paused_provider)
        if intervening_review:
            async with store.sessions() as session:
                repo = BlogRepository(session)
                current = await repo.get_by_id(post_id)
                reviewed = await repo.set_review(current, 1)
                reviewed_version = reviewed.updated_at
    finally:
        paused_provider.release.set()
        await asyncio.wait_for(task, timeout=10)
    async with store.sessions() as session:
        current = await BlogRepository(session).get_by_id(post_id)
        if intervening_review:
            assert current.title == old_title
            assert current.updated_at == reviewed_version > old_version
            assert current.reviewed_by_id == 1
            assert current.reviewed_at is not None
        else:
            assert current.title == paused_provider.article["title"]
            assert current.updated_at > old_version
            assert current.ai_assisted is True
            assert current.reviewed_by_id is None and current.reviewed_at is None
            assert current.deduction_masterclass["quiz"] == paused_provider.article["trivia_quiz"]
            assert current.source_links[0]["url"] == "https://en.wikipedia.org/wiki/Poland"


async def test_generator_does_not_mutate_or_rollback_caller_pending_writes(
    generation_store, paused_provider,
):
    store = generation_store
    async with store.sessions() as caller:
        pending = Country(id=2, name="Germany", md_file="Germany.md")
        caller.add(pending)
        task = asyncio.create_task(generator.create_daily_blog_post(
            store.engine, 1, "Poland", store.dates[0],
        ))
        try:
            await wait_for_provider_and_probe_pool(store, paused_provider)
            assert pending in caller.new
            assert pending.name == "Germany"
        finally:
            paused_provider.release.set()
            generated = await asyncio.wait_for(task, timeout=10)
        assert generated.title == paused_provider.article["title"]
        assert pending in caller.new
        await caller.commit()
    async with store.sessions() as session:
        assert (await session.get(Country, 2)).name == "Germany"
