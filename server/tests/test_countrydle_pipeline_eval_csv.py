import pathlib
import os
from types import SimpleNamespace

import pytest

from countrydle import local_answering
from countrydle.local_answering import LocalCountryFacts, execute_local_plan
from countrydle.utils import ask_question
from db import AsyncSessionLocal
from db.repositories.country import CountryRepository
from schemas.countrydle import QuestionEnhanced


DB_PATH = pathlib.Path(__file__).resolve().parents[2] / "data" / "country_facts.sqlite"


pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="Countrydle local SQLite KB is missing")
local_answering.DEFAULT_DB_PATH = DB_PATH


def contains_plan(relation: str, value: str) -> dict:
    return {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": relation},
        "right": {"value": value},
    }


def scalar_plan(operator: str, relation: str, value) -> dict:
    return {
        "operator": operator,
        "left": {"entity": "target_country", "relation": relation},
        "right": {"value": value},
    }


def area_greater_than_poland_plan() -> dict:
    return {
        "operator": "greater_than",
        "left": {"entity": "target_country", "relation": "area"},
        "right": {"entity": "Poland", "relation": "area"},
    }


def coordinate_comparison_against_china_plan(operator: str) -> dict:
    relation = "coordinates.longitude" if operator in {"west_of", "east_of"} else "coordinates.latitude"
    return {
        "operator": operator,
        "left": {"entity": "target_country", "relation": relation},
        "right": {"entity": "China", "relation": relation},
    }


def unsupported_plan(relation: str, value: str = "true") -> dict:
    return contains_plan(relation, value)


DIRECT_QUESTION_CASES = [
    ("Is the country in Oceania?", country, True)
    for country in ["Australia", "New Zealand", "Samoa", "Tonga", "Tuvalu", "Fiji"]
] + [
    ("Is the country in Polynesia?", country, True)
    for country in ["New Zealand", "Samoa", "Tonga", "Tuvalu"]
] + [
    ("Is the country Mediterranean?", "Portugal", True),
    ("Is the country in the Iberian Peninsula?", "Portugal", True),
    ("Is the country in the Balkans?", "Croatia", True),
    ("Is the country in Central Europe?", "Croatia", True),
    ("Is the country in the Middle East?", "United Arab Emirates", True),
    ("Is it Caribean country?", "Grenada", True),
    ("Is the country Catholic?", "Poland", True),
    ("Is the dominant religion Islam?", "Turkey", True),
    ("Is the country religiously mixed?", "Japan", True),
    ("Is the country Jewish?", "Israel", True),
    ("Is the country Orthodox?", "Greece", True),
    ("Is the country an absolute monarchy?", "Saudi Arabia", True),
    ("Is the country a parliamentary republic?", "Poland", True),
    ("Is the country a monarchy?", "United Kingdom", True),
    ("Is the country in Oceania?", "Poland", False),
    ("Is the country in Polynesia?", "Australia", False),
    ("Is the country in the Caribbean?", "Poland", False),
    ("Is it Caribean country?", "Poland", False),
    ("Is the country Mediterranean?", "Norway", False),
    ("Is the country in the Middle East?", "Germany", False),
    ("Is the country Catholic?", "Turkey", False),
    ("Is the dominant religion Islam?", "Poland", False),
    ("Is the country Jewish?", "Poland", False),
    ("Is the country Orthodox?", "Saudi Arabia", False),
    ("Is the country an absolute monarchy?", "Poland", False),
    ("Is the country a monarchy?", "France", False),
]


PLAN_CASES = [
    (f"Is the country in {area}?", country, True, contains_plan("subregion", area))
    for country, area in [
        ("Poland", "Central Europe"),
        ("Poland", "Eastern Europe"),
        ("Lithuania", "Baltic states"),
        ("Lithuania", "Northern Europe"),
        ("Montenegro", "Balkans"),
        ("Montenegro", "Southern Europe"),
        ("Portugal", "Iberia"),
        ("Portugal", "Iberian Peninsula"),
        ("Portugal", "Mediterranean"),
        ("Croatia", "Balkans"),
        ("Croatia", "Central Europe"),
        ("Cambodia", "South-Eastern Asia"),
        ("Cambodia", "Southeast Asia"),
        ("United Arab Emirates", "Arabian Peninsula"),
        ("United Arab Emirates", "Middle East"),
        ("United Arab Emirates", "Western Asia"),
        ("Somalia", "Horn of Africa"),
    ]
] + [
    (f"Is the country in {area}?", country, False, contains_plan("subregion", area))
    for country, area in [
        ("Poland", "Balkans"),
        ("United Arab Emirates", "South-Eastern Asia"),
        ("Cambodia", "Middle East"),
        ("Somalia", "Arabian Peninsula"),
        ("India", "Western Asia"),
    ]
] + [
    (f"Is the country in {area}?", country, True, contains_plan("region", area))
    for country, area in [
        ("Poland", "Europe"),
        ("Cambodia", "Asia"),
        ("United Arab Emirates", "Asia"),
        ("Australia", "Oceania"),
        ("Brazil", "Americas"),
    ]
] + [
    ("Is the country in the Caribbean region?", "Grenada", True, contains_plan("region", "Caribbean")),
    ("Is the country in Europe or Asia?", "Turkey", True, {
        "operator": "or",
        "conditions": [contains_plan("continent", "Europe"), contains_plan("continent", "Asia")],
    }),
    ("Does the country name end with stan?", "Afghanistan", True, {
        "operator": "ends_with",
        "left": {"entity": "target_country", "relation": "name"},
        "right": {"value": "stan"},
    }),
    ("Does the country name end with stan?", "Poland", False, {
        "operator": "ends_with",
        "left": {"entity": "target_country", "relation": "name"},
        "right": {"value": "stan"},
    }),
    ("Does the country border itself?", "Poland", True, contains_plan("borders_country", "Poland")),
    ("Is the country in NATO or the EU?", "Poland", True, {
        "operator": "or",
        "conditions": [contains_plan("membership", "NATO"), contains_plan("membership", "EU")],
    }),
    ("Is the country in NATO or the EU?", "Germany", True, {
        "operator": "or",
        "conditions": [contains_plan("membership", "NATO"), contains_plan("membership", "EU")],
    }),
    ("Is the country in NATO or the EU?", "Norway", True, {
        "operator": "or",
        "conditions": [contains_plan("membership", "NATO"), contains_plan("membership", "EU")],
    }),
    ("Is the country in NATO or the EU?", "Switzerland", False, {
        "operator": "or",
        "conditions": [contains_plan("membership", "NATO"), contains_plan("membership", "EU")],
    }),
    ("Is the country in NATO or the EU?", "Cuba", False, {
        "operator": "or",
        "conditions": [contains_plan("membership", "NATO"), contains_plan("membership", "EU")],
    }),
] + [
    (f"Is the country {value}?", country, expected, scalar_plan("equals", relation, value))
    for country, relation, value, expected in [
        ("Poland", "dominant_religion", "Catholic", True),
        ("Poland", "dominant_religion", "Islam", False),
        ("Japan", "dominant_religion", "Mixed", True),
        ("Turkey", "government_type", "Republic", True),
        ("Saudi Arabia", "government_type", "Republic", False),
        ("United Kingdom", "government_type", "Monarchy", True),
    ]
] + [
    ("Does the country have more than 1 million people?", country, expected, scalar_plan("greater_than", "population", 1_000_000))
    for country, expected in [("Poland", True), ("Vatican City", False), ("Germany", True)]
] + [
    ("Is the country larger than Poland?", country, expected, area_greater_than_poland_plan())
    for country, expected in [
        ("Poland", False),
        ("Germany", True),
        ("Ukraine", True),
        ("Czech Republic", False),
        ("Russia", True),
    ]
] + [
    (f"Is the country {operator.replace('_', ' ')} China?", country, expected, coordinate_comparison_against_china_plan(operator))
    for country, operator, expected in [
        ("Kazakhstan", "west_of", True),
        ("Germany", "west_of", True),
        ("Japan", "west_of", False),
        ("Mongolia", "east_of", False),
        ("Japan", "east_of", True),
        ("Mongolia", "north_of", True),
        ("India", "south_of", True),
    ]
]


FALLBACK_CASES = [
    # These should be valid game questions, but not answerable from the curated
    # SQLite facts. In production they should continue to the Qdrant/Wikipedia
    # fragment + Gemini answering path.
    ("Is the country famous for the Eiffel Tower?", "France", True, unsupported_plan("landmark", "Eiffel Tower")),
    ("Is the country known for Machu Picchu?", "Peru", True, unsupported_plan("landmark", "Machu Picchu")),
    ("Does the country host the city of Rio de Janeiro?", "Brazil", True, unsupported_plan("notable_city", "Rio de Janeiro")),
    ("Is the country famous for fjords?", "Norway", True, unsupported_plan("notable_geography", "fjords")),
    ("Is the country associated with the Sahara Desert?", "Algeria", True, unsupported_plan("desert", "Sahara")),
    ("Does the country contain Mount Fuji?", "Japan", True, unsupported_plan("mountain", "Mount Fuji")),
    ("Is the country known for the Great Barrier Reef?", "Australia", True, unsupported_plan("landmark", "Great Barrier Reef")),
    ("Was the country part of the former Yugoslavia?", "Croatia", True, unsupported_plan("former_yugoslavia_member", "true")),
    ("Was the country part of the Soviet Union?", "Lithuania", True, unsupported_plan("former_ussr_member", "true")),
    ("Is the country historically part of the British Empire?", "India", True, unsupported_plan("colonial_history", "British Empire")),
    ("Is the country famous for tango?", "Argentina", True, unsupported_plan("cultural_association", "tango")),
    ("Is the country known for tulips?", "Netherlands", True, unsupported_plan("cultural_association", "tulips")),
    ("Is the country home to the Serengeti?", "Tanzania", True, unsupported_plan("landmark", "Serengeti")),
    ("Is the country associated with the Amazon rainforest?", "Brazil", True, unsupported_plan("biome", "Amazon rainforest")),
    ("Did the country host the 2016 Summer Olympics?", "Brazil", True, unsupported_plan("sports_event_host", "2016 Summer Olympics")),
    ("Is the country famous for the pyramids of Giza?", "Egypt", True, unsupported_plan("landmark", "Pyramids of Giza")),
    ("Is the country known for the Acropolis?", "Greece", True, unsupported_plan("landmark", "Acropolis")),
    ("Is the country associated with Dracula?", "Romania", True, unsupported_plan("cultural_association", "Dracula")),
    ("Is the country famous for maple syrup?", "Canada", True, unsupported_plan("cultural_association", "maple syrup")),
    ("Is the country known for the Angkor Wat temple complex?", "Cambodia", True, unsupported_plan("landmark", "Angkor Wat")),
]


@pytest.mark.parametrize(("question", "country", "expected_answer"), DIRECT_QUESTION_CASES)
def test_countrydle_direct_question_eval_rows_are_recorded(
    question,
    country,
    expected_answer,
    record_countrydle_eval,
):
    local_answer = LocalCountryFacts(db_path=DB_PATH).try_answer(question, country)
    record_eval_row(record_countrydle_eval, question, country, expected_answer, local_answer, "sqlite_direct")
    assert (local_answer.answer if local_answer is not None else None) is expected_answer


@pytest.mark.parametrize(("question", "country", "expected_answer", "plan"), PLAN_CASES)
def test_countrydle_plan_eval_rows_are_recorded(
    question,
    country,
    expected_answer,
    plan,
    record_countrydle_eval,
):
    local_answer = execute_local_plan(
        plan,
        country,
        question,
        "Pytest Countrydle pipeline evaluation.",
    )
    record_eval_row(record_countrydle_eval, question, country, expected_answer, local_answer, "sqlite_plan")
    assert (local_answer.answer if local_answer is not None else None) is expected_answer


@pytest.mark.parametrize(("question", "country", "expected_answer", "plan"), FALLBACK_CASES)
def test_countrydle_fallback_eval_rows_are_recorded(
    question,
    country,
    expected_answer,
    plan,
    record_countrydle_eval,
):
    local_answer = execute_local_plan(
        plan,
        country,
        question,
        "Pytest Countrydle fallback-path evaluation.",
    )
    record_eval_row(record_countrydle_eval, question, country, expected_answer, local_answer, "fallback_route_only")
    assert local_answer is None


@pytest.mark.skipif(
    os.getenv("COUNTRYDLE_RUN_LIVE_FALLBACK_EVAL") != "1",
    reason="Live fallback evaluation requires COUNTRYDLE_RUN_LIVE_FALLBACK_EVAL=1, PostgreSQL, Qdrant, OpenAI, and Gemini.",
)
@pytest.mark.real_database
@pytest.mark.anyio
async def test_countrydle_live_fallback_answering_eval_rows_are_recorded(record_countrydle_eval):
    """Record real fallback answers without failing the evaluation on wrong answers.

    This is intentionally one async test (instead of one parametrized async test per
    question) so SQLAlchemy's asyncpg pool is used within a single event loop.
    """
    for question, country, expected_answer, _plan in FALLBACK_CASES:
        try:
            async with AsyncSessionLocal() as session:
                country_obj = await CountryRepository(session).get_country_by_name(country)
                if country_obj is None:
                    raise AssertionError(f"Country not found in PostgreSQL: {country}")

                day_country = SimpleNamespace(id=-1, country_id=country_obj.id)
                enhanced = QuestionEnhanced(
                    original_question=question,
                    question=question,
                    valid=True,
                    explanation=None,
                    intent="Pytest live fallback evaluation for Countrydle.",
                    required_info="Relevant Wikipedia/Qdrant fragments for the requested fact.",
                )

                question_create, _question_vector = await ask_question(enhanced, day_country, None, session)

            record_countrydle_eval(
                question=question,
                country=country,
                expected_answer=expected_answer,
                pipeline_answer=question_create.answer,
                is_correct=question_create.answer is expected_answer,
                evaluation_mode="live_fallback_answering",
                answering_executed=True,
                source="live_fallback:wikipedia_fragments",
                went_further=True,
                enhanced_question=question_create.question or "",
                relation="",
                explanation=question_create.explanation or "",
            )
        except Exception as exc:
            record_countrydle_eval(
                question=question,
                country=country,
                expected_answer=expected_answer,
                pipeline_answer="",
                is_correct=f"error:{type(exc).__name__}",
                evaluation_mode="live_fallback_answering",
                answering_executed=False,
                source="live_fallback:error",
                went_further=True,
                enhanced_question=question,
                relation="",
                explanation=str(exc),
            )


def record_eval_row(record_countrydle_eval, question, country, expected_answer, local_answer, evaluation_mode):
    pipeline_answer = local_answer.answer if local_answer is not None else None
    record_countrydle_eval(
        question=question,
        country=country,
        expected_answer=expected_answer,
        pipeline_answer=pipeline_answer if local_answer is not None else "",
        is_correct=pipeline_answer is expected_answer if local_answer is not None else "not_run_sqlite_fallback_expected",
        evaluation_mode=evaluation_mode,
        answering_executed=local_answer is not None,
        source=f"sqlite:{local_answer.relation}" if local_answer is not None else "fallback:wikipedia_fragments",
        went_further=local_answer is None,
        enhanced_question=local_answer.question if local_answer is not None else "",
        relation=local_answer.relation if local_answer is not None else "",
        explanation=local_answer.explanation if local_answer is not None else "",
    )
