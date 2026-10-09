from datetime import date

import pytest

from utils.blog_generator import (
    _generate_fallback_template,
    _used_question_sources,
    generate_blog_content_ai,
    generate_slug,
    get_deduction_steps,
)


def test_generate_slug_normalizes_country_names():
    post_date = date(2026, 9, 20)
    assert generate_slug(post_date, "Madagascar") == "2026-09-20-madagascar"
    assert generate_slug(post_date, "United States of America") == "2026-09-20-united-states-of-america"
    assert generate_slug(post_date, "Côte d'Ivoire") == "2026-09-20-c-te-d-ivoire"


def test_short_actual_deduction_path_is_not_replaced_with_invented_questions():
    questions = [
        {"question": "Is the country in Africa?", "answer": "YES", "explanation": "South Sudan is in Africa."},
        {"question": "Does it have a coastline?", "answer": "NO", "explanation": "South Sudan is landlocked."},
    ]
    steps = get_deduction_steps("South Sudan", questions)
    assert len(steps) == 2
    assert [step["question"] for step in steps] == [question["question"] for question in questions]
    assert [step["answer"] for step in steps] == ["YES", "NO"]
    assert [step["explanation"] for step in steps] == [question["explanation"] for question in questions]


def test_deduction_path_without_player_history_does_not_invent_telemetry():
    assert get_deduction_steps("Poland", []) == []
    article = _generate_fallback_template("Poland", [], date(2026, 9, 19))
    assert article["deduction_masterclass"]["steps"] == []


def test_deduction_path_deduplicates_and_excludes_answer_revealing_questions():
    valid_question = {"question": "Does it border Germany?", "answer": "YES", "explanation": "They share a border."}
    questions = [
        {"question": "Is the country Poland?", "answer": "YES", "explanation": "Correct guess."},
        valid_question,
        dict(valid_question),
    ]
    steps = get_deduction_steps("Poland", questions)
    assert len(steps) == 1
    assert steps[0]["step"] == 1
    assert steps[0]["question"] == valid_question["question"]


@pytest.fixture(params=[
    " [citation needed].",
    " [citationneeded].",
    ". [citation needed]",
    ".[citationneeded]",
    ".\n[Citation Needed]",
    r". \[citation needed\]",
])
def hostile_wiki_excerpt(request):
    unsupported = "Poland contains the oldest continuously inhabited castle on Earth"
    supported = "Poland's capital city is Warsaw, situated along the Vistula River."
    return f"{unsupported}{request.param} {supported}", supported


def test_fallback_omits_marked_claim_but_keeps_other_content_and_source_warning(
    monkeypatch, hostile_wiki_excerpt,
):
    import utils.blog_generator as generator

    monkeypatch.setattr(generator, "get_country_sqlite_facts", lambda _: {
        "capital": "Warsaw", "continent": "Europe", "water_access": "Baltic Sea",
        "borders": "Germany", "area_km2": "312,696 km²",
    })
    fragment, supported = hostile_wiki_excerpt
    article = _generate_fallback_template("Poland", [fragment], date(2026, 9, 19))
    assert "oldest continuously inhabited castle" not in article["content_markdown"]
    descriptions = [fact["description"] for fact in article["fun_facts"]]
    assert all("oldest continuously inhabited castle" not in text for text in descriptions)
    assert supported in descriptions
    assert supported in article["content_markdown"]
    assert article["fast_facts"]["capital"] == "Warsaw"
    assert "citation needed" in article["editorial_note"].lower()
    assert article["source_links"] == []
    assert article["ai_assisted"] is False
    assert "reviewed_by_id" not in article
    assert "reviewed_at" not in article


@pytest.mark.anyio
async def test_missing_provider_key_uses_automated_template_without_human_review(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    article = await generate_blog_content_ai("Poland", [], date(2026, 9, 19))
    assert article["ai_assisted"] is False
    assert article["source_links"] == []
    assert article["editorial_note"]
    assert "reviewed_by_id" not in article
    assert "reviewed_at" not in article


def test_sources_include_only_valid_cited_evidence_from_displayed_questions():
    cited = {
        "provenance": {
            "status": "cited",
            "citation": "Poland borders Germany, according to the stored source excerpt.",
            "source_url": "https://en.wikipedia.org/wiki/Poland",
        }
    }
    questions = [
        {
            "question": "Does it border Germany?", "answer": "YES",
            "explanation": "Poland and Germany share a border.",
            "fact_provenance": [
                cited, dict(cited),
                {"provenance": {"status": "unknown", "citation": "Unverified", "source_url": "https://example.com/unknown"}},
                {"provenance": {"status": "cited", "citation": "Unsafe URL", "source_url": "javascript:alert(1)"}},
                {"provenance": {"status": "cited", "citation": "", "source_url": "https://example.com/no-evidence"}},
            ],
        },
        {
            "question": "Is the country Poland?", "answer": "YES", "explanation": "Correct guess.",
            "fact_provenance": [{
                "provenance": {"status": "cited", "citation": "Other evidence", "source_url": "https://example.com/not-used"}
            }],
        },
    ]
    sources = _used_question_sources(questions, get_deduction_steps("Poland", questions))
    assert len(sources) == 1
    assert sources[0]["url"] == "https://en.wikipedia.org/wiki/Poland"
    assert sources[0]["label"]


@pytest.mark.anyio
async def test_ai_output_cannot_invent_sources_or_human_review(monkeypatch):
    import utils.blog_generator as generator

    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-only")

    def offline_provider(*args, **kwargs):
        return {
            "title": "Countrydle recap: Poland",
            "summary": "Poland is in Europe and its capital is Warsaw.",
            "fun_facts": [{"title": "Capital", "description": "Warsaw is the capital of Poland."}],
            "source_links": [{"label": "Invented citation", "url": "https://example.com/not-retrieved"}],
            "reviewed_by_id": 1,
            "reviewed_at": "2026-09-19T12:00:00Z",
            "ai_assisted": False,
        }

    monkeypatch.setattr(generator, "_call_gemini_api", offline_provider)
    article = await generate_blog_content_ai(
        "Poland",
        ["Poland contains an unsupported historical superlative [citation needed]."],
        date(2026, 9, 19),
    )
    assert article["ai_assisted"] is True
    assert article["source_links"] == []
    assert "citation needed" in article["editorial_note"].lower()
    assert "reviewed_by_id" not in article
    assert "reviewed_at" not in article
