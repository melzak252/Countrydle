import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from db.models.blog import DailyBlogPost
from db.models.country import Country
from utils.blog_generator import generate_slug, _generate_fallback_template


def test_generate_slug():
    d = date(2026, 9, 20)
    assert generate_slug(d, "Madagascar") == "2026-09-20-madagascar"
    assert generate_slug(d, "United States of America") == "2026-09-20-united-states-of-america"
    assert generate_slug(d, "Côte d'Ivoire") == "2026-09-20-c-te-d-ivoire"


def test_generate_fallback_template():
    d = date(2026, 9, 19)
    fragments = [
        "Poland is a country in Central Europe with Warsaw as its capital.",
        "Malbork Castle is the largest castle in the world by land area.",
        "Over 70% of Poland's terrain is lowlands."
    ]
    article = _generate_fallback_template("Poland", fragments, d)

    assert "Poland" in article["title"]
    assert len(article["fun_facts"]) >= 3
    assert "Malbork Castle" in article["content_markdown"]
    assert "Main Facts at a Glance" in article["content_markdown"]
    assert "Did You Know?" in article["content_markdown"]
    assert "Countrydle Pro Deduction Tip" in article["content_markdown"]
    assert "deduction_masterclass" in article
    assert article["reading_time_minutes"] == 2


@pytest.mark.anyio
async def test_get_blog_posts_empty(async_client: AsyncClient):
    with patch("db.repositories.blog.BlogRepository.list_posts", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = ([], 0)
        resp = await async_client.get("/blog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["posts"] == []


@pytest.mark.anyio
async def test_get_blog_post_by_slug_success(async_client: AsyncClient):
    mock_post = MagicMock(spec=DailyBlogPost)
    mock_post.id = 1
    mock_post.date = date(2026, 9, 19)
    mock_post.country_id = 10
    mock_post.slug = "2026-09-19-poland"
    mock_post.title = "Countrydle Recap: Poland"
    mock_post.subtitle = "Exploring Polish history and geography."
    mock_post.reading_time_minutes = 2
    mock_post.summary = "A great deduction game yesterday."
    mock_post.fast_facts = {"capital": "Warsaw"}
    mock_post.fun_facts = [{"title": "Fact 1", "description": "Desc 1"}]
    mock_post.deduction_masterclass = {"step_1": "Hemisphere check"}
    mock_post.content_markdown = "## Poland\nFull article."
    mock_post.created_at = datetime.now()

    mock_country = MagicMock(spec=Country)
    mock_country.id = 10
    mock_country.name = "Poland"
    mock_country.official_name = "Republic of Poland"
    mock_country.wiki = ""
    mock_country.md_file = ""
    mock_post.country = mock_country

    with patch("db.repositories.blog.BlogRepository.get_by_slug", new_callable=AsyncMock) as mock_get_slug, \
         patch("db.repositories.blog.BlogRepository.get_day_player_stats", new_callable=AsyncMock, return_value={"win_rate_pct": 72.5, "total_players": 150}), \
         patch("db.repositories.blog.BlogRepository.list_posts", new_callable=AsyncMock, return_value=([], 0)):
        mock_get_slug.return_value = mock_post

        resp = await async_client.get("/blog/2026-09-19-poland")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Countrydle Recap: Poland"
        assert data["slug"] == "2026-09-19-poland"
        assert data["country_name"] == "Poland"
        assert data["continent"] == "Europe"
        assert data["difficulty"] == "Easy"
        assert data["win_rate_pct"] == 72.5
        assert data["total_players"] == 150

@pytest.mark.anyio
async def test_get_blog_post_not_found(async_client: AsyncClient):
    with patch("db.repositories.blog.BlogRepository.get_by_slug", new_callable=AsyncMock) as mock_get_slug, \
         patch("db.repositories.blog.BlogRepository.get_by_date", new_callable=AsyncMock) as mock_get_date:
        mock_get_slug.return_value = None
        mock_get_date.return_value = None

        resp = await async_client.get("/blog/non-existent-slug")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_daily_blog_post_incorporates_player_questions():
    from utils.blog_generator import _generate_fallback_template
    d = date(2026, 9, 29)
    fragments = ["South Sudan is a landlocked country in East-Central Africa."]
    sample_questions = [
        {"question": "Is the country in Africa?", "answer": "YES", "explanation": "South Sudan is located in Africa."},
        {"question": "Does the country have access to the sea?", "answer": "NO", "explanation": "South Sudan is completely landlocked."},
    ]
    template = _generate_fallback_template("South Sudan", fragments, d, actual_questions=sample_questions)
    assert "Is the country in Africa?" in template["content_markdown"]
    assert "Does the country have access to the sea?" in template["content_markdown"]
    assert "The Deduction Breakdown (Real Player Questions)" in template["content_markdown"]
    assert "Main Facts at a Glance" in template["content_markdown"]
    assert "Did You Know?" in template["content_markdown"]
    assert "Countrydle Pro Deduction Tip" in template["content_markdown"]
