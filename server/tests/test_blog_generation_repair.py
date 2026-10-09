from copy import deepcopy
from datetime import date

import pytest
from pydantic import ValidationError

from schemas.blog import BlogPostUpdate
import utils.blog_generator as generator


@pytest.fixture
def provider_article(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "disposable-offline-fixture")
    monkeypatch.setattr(generator, "get_country_sqlite_facts", lambda _: {
        "capital": "Warsaw", "continent": "Europe", "region": "Central Europe",
        "borders": "Germany", "area_km2": "312,696 km²", "water_access": "Baltic Sea",
    })
    return {
        "title": "Poland: a geography recap",
        "subtitle": "A recap of the past puzzle.",
        "summary": "Poland is in Europe and shares a border with Germany.",
        "fun_facts": [{"title": "Shared border", "description": "Poland borders Germany."}],
        "trivia_quiz": {
            "question": "What is the capital of Poland?",
            "correct_answer": "Warsaw",
            "incorrect_distractor": "Berlin",
            "explanation": "Warsaw is the capital of Poland.",
        },
    }


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_quiz", [
    {"question": "What is the capital?"},
    {"question": " ", "correct_answer": "Warsaw", "incorrect_distractor": "Berlin", "explanation": "Capital."},
    {"question": "Capital?", "correct_answer": "Warsaw", "incorrect_distractor": " warsaw ", "explanation": "Capital."},
    {"question": "Capital?", "correct_answer": "Warsaw", "incorrect_distractor": "Berlin", "explanation": " "},
    None,
])
async def test_invalid_primary_quiz_is_rejected_before_valid_fallback_model_is_accepted(
    monkeypatch, provider_article, invalid_quiz,
):
    invalid_article = deepcopy(provider_article)
    invalid_article["title"] = "Invalid primary output"
    invalid_article["trivia_quiz"] = invalid_quiz
    calls = []

    def offline_provider(model, *args):
        calls.append(model)
        return deepcopy(invalid_article if len(calls) == 1 else provider_article)

    monkeypatch.setattr(generator, "_call_gemini_api", offline_provider)
    article = await generator.generate_blog_content_ai("Poland", [], date(2026, 9, 19))

    assert calls == [generator.PRIMARY_MODEL, generator.FALLBACK_MODEL]
    assert article["title"] == provider_article["title"]
    assert article["ai_assisted"] is True
    assert article["deduction_masterclass"]["quiz"] == provider_article["trivia_quiz"]
    assert article["source_links"] == []
    assert "No human editorial review" in article["editorial_note"]


@pytest.mark.anyio
async def test_all_invalid_provider_quizzes_use_fact_template_without_fabricated_quiz(
    monkeypatch, provider_article,
):
    provider_article["trivia_quiz"] = {"question": "An incomplete historical-style quiz"}
    monkeypatch.setattr(generator, "_call_gemini_api", lambda *args: deepcopy(provider_article))
    article = await generator.generate_blog_content_ai(
        "Poland",
        ["Poland contains an unsupported ancient superlative [citation needed]."],
        date(2026, 9, 19),
        [{"question": "Is it in Europe?", "answer": "YES", "explanation": "Poland is in Europe."}],
    )

    assert article["ai_assisted"] is False
    assert "quiz" not in article["deduction_masterclass"]
    assert article["fast_facts"]["capital"] == "Warsaw"
    assert article["deduction_masterclass"]["steps"][0]["answer"] == "YES"
    assert "unsupported ancient superlative" not in article["content_markdown"]
    assert "[citation needed]" in article["editorial_note"]
    assert article["source_links"] == []
    BlogPostUpdate.model_validate({field: article[field] for field in BlogPostUpdate.model_fields})


@pytest.mark.anyio
async def test_complete_quiz_does_not_allow_incompatible_assembled_editable_fields(
    monkeypatch, provider_article,
):
    invalid_article = deepcopy(provider_article)
    invalid_article["title"] = "x" * 241
    calls = []

    def offline_provider(model, *args):
        calls.append(model)
        return deepcopy(invalid_article if len(calls) == 1 else provider_article)

    monkeypatch.setattr(generator, "_call_gemini_api", offline_provider)
    article = await generator.generate_blog_content_ai("Poland", [], date(2026, 9, 19))
    assert calls == [generator.PRIMARY_MODEL, generator.FALLBACK_MODEL]
    assert article["title"] == provider_article["title"]
    assert len(article["title"]) <= 240


def test_fact_only_fallback_is_also_validated_before_it_can_be_saved(monkeypatch):
    monkeypatch.setattr(generator, "get_country_sqlite_facts", lambda _: {"capital": {"unexpected": "nested data"}})
    with pytest.raises(ValidationError):
        generator._generate_fallback_template("Poland", [], date(2026, 9, 19))


@pytest.mark.anyio
async def test_ai_article_with_omitted_quiz_remains_valid_and_ai_assisted(
    monkeypatch, provider_article,
):
    provider_article.pop("trivia_quiz")
    calls = []

    def offline_provider(model, *args):
        calls.append(model)
        return deepcopy(provider_article)

    monkeypatch.setattr(generator, "_call_gemini_api", offline_provider)
    article = await generator.generate_blog_content_ai("Poland", [], date(2026, 9, 19))
    assert calls == [generator.PRIMARY_MODEL]
    assert article["ai_assisted"] is True
    assert article["title"] == provider_article["title"]
    assert "quiz" not in article["deduction_masterclass"]
