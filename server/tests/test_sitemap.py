from datetime import date, datetime, timezone
from xml.etree import ElementTree

import pytest
from sqlalchemy import create_engine

from app import dynamic_sitemap
from db.models.blog import DailyBlogPost
from db.models.country import Country


class SitemapSession:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, statement):
        return self.connection.execute(statement)


@pytest.mark.anyio
async def test_sitemap_includes_current_posts_and_excludes_future_posts(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 26, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr("datetime.datetime", FixedDatetime)
    engine = create_engine("sqlite:///:memory:")
    Country.__table__.create(engine)
    DailyBlogPost.__table__.create(engine)
    try:
        with engine.begin() as connection:
            connection.execute(Country.__table__.insert(), {
                "id": 1, "name": "Poland", "md_file": "poland.md",
            })
            connection.execute(DailyBlogPost.__table__.insert(), [
                {
                    "date": post_date, "slug": slug, "country_id": 1,
                    "title": "Daily recap", "subtitle": "Geography",
                    "summary": "Country recap", "fun_facts": [],
                    "content_markdown": "Daily geography recap.",
                }
                for post_date, slug in [
                    (date(2026, 9, 25), "daily-recap-rock&roll"),
                    (date(2026, 9, 26), "current-recap"),
                    (date(2026, 9, 27), "future-recap"),
                ]
            ])
            response = await dynamic_sitemap(SitemapSession(connection))

        root = ElementTree.fromstring(response.body)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url", namespace)
        locations = {node.find("sm:loc", namespace).text for node in urls}
        expected_modes = {
            "/game", "/flagdle", "/europe", "/asia", "/africa", "/americas",
            "/us-states", "/wojewodztwa", "/powiaty",
        }

        assert expected_modes <= {
            url.removeprefix("https://countrydle.online") for url in locations
        }
        assert "https://countrydle.online/blog/daily-recap-rock&roll" in locations
        assert "https://countrydle.online/blog/current-recap" in locations
        assert "https://countrydle.online/blog/future-recap" not in locations
        assert "https://countrydle.online/friends" in locations
        assert not any(
            "/admin" in url or "/duel/" in url or "/login" in url
            for url in locations
        )
        article_dates = {
            node.find("sm:loc", namespace).text: node.find("sm:lastmod", namespace).text
            for node in urls if node.find("sm:lastmod", namespace) is not None
        }
        assert article_dates == {
            "https://countrydle.online/blog/current-recap": "2026-09-26",
            "https://countrydle.online/blog/daily-recap-rock&roll": "2026-09-25",
        }
    finally:
        engine.dispose()
