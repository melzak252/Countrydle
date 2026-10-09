from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from app import app
from db import get_db
from db.models.blog import DailyBlogPost
from db.models.country import Country


class SitemapSession:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, statement):
        return self.connection.execute(statement)


def sitemap_articles(response):
    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {
        node.find("sm:loc", namespace).text: node.find("sm:lastmod", namespace).text
        for node in root.findall("sm:url", namespace)
        if node.find("sm:lastmod", namespace) is not None
    }


@pytest.fixture
def publisher_connection():
    engine = create_engine("sqlite:///:memory:")
    Country.__table__.create(engine)
    DailyBlogPost.__table__.create(engine)
    try:
        with engine.begin() as connection:
            connection.execute(Country.__table__.insert(), {
                "id": 1, "name": "Poland", "md_file": "poland.md",
            })
            yield connection
    finally:
        engine.dispose()


def insert_recap(connection, post_date, slug, created_at, updated_at):
    connection.execute(DailyBlogPost.__table__.insert(), {
        "date": post_date,
        "slug": slug,
        "country_id": 1,
        "title": "Daily deduction recap",
        "subtitle": "Geography analysis",
        "summary": "A recap of a completed daily puzzle.",
        "fun_facts": [],
        "content_markdown": "The completed puzzle's deduction analysis.",
        "created_at": created_at,
        "updated_at": updated_at,
    })


def freeze_utc_clock(monkeypatch, instant):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    monkeypatch.setattr("app._publisher_datetime", FixedDatetime)


@pytest.mark.anyio
@pytest.mark.parametrize("instant", [
    datetime(2026, 10, 8, 23, 59, 59, tzinfo=timezone.utc),
    datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 9, 0, 0, 1, tzinfo=timezone.utc),
    # Local October 9 is still October 8 in UTC: do not publish a day early.
    datetime(2026, 10, 9, 1, 0, tzinfo=timezone(timedelta(hours=2))),
    # Local October 8 is October 9 in UTC: the completed day is now public.
    datetime(2026, 10, 8, 20, 0, tzinfo=timezone(timedelta(hours=-4))),
])
async def test_sitemap_only_reveals_completed_utc_days(
    monkeypatch, publisher_connection, instant,
):
    freeze_utc_clock(monkeypatch, instant)
    created_at = datetime(2026, 10, 7, 12, 0)
    for post_date, slug in [
        (date(2026, 10, 7), "2026-10-07-past-recap"),
        (date(2026, 10, 8), "2026-10-08-completed-recap"),
        (date(2026, 10, 9), "2026-10-09-secret-target"),
        (date(2026, 10, 10), "2026-10-10-future-target"),
    ]:
        insert_recap(publisher_connection, post_date, slug, created_at, created_at)

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: SitemapSession(publisher_connection)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sitemap.xml")
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    articles = sitemap_articles(response)
    assert "https://countrydle.online/blog/2026-10-07-past-recap" in articles
    assert (
        "https://countrydle.online/blog/2026-10-08-completed-recap" in articles
    ) == (instant.astimezone(timezone.utc).date() > date(2026, 10, 8))
    assert "secret-target" not in response.text
    assert "future-target" not in response.text


@pytest.mark.anyio
async def test_sitemap_lastmod_tracks_real_editorial_changes_without_changing_puzzle_date(
    monkeypatch, publisher_connection,
):
    freeze_utc_clock(monkeypatch, datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc))
    created_at = datetime(2026, 10, 7, 18, 15, 0)
    edited_at = datetime(2026, 10, 8, 23, 30, 45)
    insert_recap(
        publisher_connection, date(2026, 10, 6), "2026-10-06-rock&roll",
        created_at, created_at,
    )

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: SitemapSession(publisher_connection)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = sitemap_articles(await client.get("/sitemap.xml"))
            publisher_connection.execute(
                DailyBlogPost.__table__.update()
                .where(DailyBlogPost.slug == "2026-10-06-rock&roll")
                .values(summary="Corrected deduction analysis.", updated_at=edited_at)
            )
            second = sitemap_articles(await client.get("/sitemap.xml"))
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    url = "https://countrydle.online/blog/2026-10-06-rock&roll"
    assert datetime.fromisoformat(first[url]) == created_at.replace(tzinfo=timezone.utc)
    assert datetime.fromisoformat(second[url]) == edited_at.replace(tzinfo=timezone.utc)
    assert first[url] != second[url]
