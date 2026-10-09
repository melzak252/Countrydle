"""Consumer-visible regressions from the English contrastive planner audit."""
import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from countrydle import local_answering, local_planner, utils
from utils import ai_clients


def reference(entity, relation):
    return {"entity": entity, "relation": relation}


def predicate(operator, relation, right, entity="target_country"):
    return {"operator": operator, "left": reference(entity, relation), "right": right}


@pytest.fixture
def audit_facts(tmp_path, monkeypatch):
    path = tmp_path / "country_facts.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE countries (
                id INTEGER PRIMARY KEY, app_country_name TEXT, official_name TEXT,
                population INTEGER, area_km2 REAL, latitude REAL, longitude REAL,
                is_island INTEGER
            );
            INSERT INTO countries VALUES
                (1, 'Pakistan', 'Islamic Republic of Pakistan', 241499431, 881913, 30, 70, 0),
                (2, 'Germany', 'Federal Republic of Germany', 83491249, 357114, 51, 9, 0),
                (3, 'France', 'French Republic', 66351959, 551695, 46, 2, 0),
                (4, 'Japan', 'Japan', 125000000, 377930, 36, 138, 1),
                (5, 'Senegal', 'Republic of Senegal', 18000000, 196722, 14, -14, 0),
                (6, 'Albania', 'Republic of Albania', 2363314, 28748, 41, 20, 0),
                (7, 'Luxembourg', 'Grand Duchy of Luxembourg', 660000, 2586, 49, 6, 0);
            CREATE TABLE country_continents (country_id INTEGER, continent TEXT);
            INSERT INTO country_continents VALUES
                (1, 'Asia'), (2, 'Europe'), (3, 'Europe'), (4, 'Asia'),
                (5, 'Africa'), (6, 'Europe'), (7, 'Europe');
        """)
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", path)
    monkeypatch.setattr(local_planner, "load_dotenv_if_present", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-provider-fixture")
    return path


@pytest.fixture
def provider(monkeypatch):
    def respond(nodes, improved_question=None):
        monkeypatch.setattr(ai_clients, "generate_gemini_json", lambda *args, **kwargs: {
            "route": "local", "plan": nodes, "improved_question": improved_question,
        })
    return respond


def answer(question, target):
    plan = local_planner.analyze_question_for_local_plan(question, use_cache=False)
    assert plan.valid and plan.supported
    result = local_answering.execute_local_plan(plan.plan, target, plan.improved_question or question)
    assert result is not None
    return result


@pytest.mark.parametrize("target, expected", [("Pakistan", True), ("Germany", False), ("France", False)])
def test_named_subject_keeps_hidden_target_and_named_comparison(audit_facts, provider, target, expected):
    provider([predicate("greater_than", "population", reference("Germany", "population"), "France")])
    result = answer("Does France have a population greater than Germany?", target)
    assert result.answer is expected


@pytest.mark.parametrize("target, expected", [("Germany", True), ("Senegal", False)])
def test_country_direction_uses_coordinates_not_country_name(audit_facts, provider, target, expected):
    provider([predicate("north_of", "name", reference("France", "name"))])
    assert answer("Is the hidden country north of France?", target).answer is expected


@pytest.mark.parametrize("target, expected", [("Germany", True), ("Japan", False)])
@pytest.mark.parametrize("question", [
    "Does the hidden country share a continent with France?",
    "Does the hidden country have any continent in common with France?",
])
def test_shared_continent_compares_lists_without_country_item_binding(audit_facts, provider, target, expected, question):
    provider([
        predicate("contains", "continent", reference("France", "continent"), "item"),
        {"operator": "any", "items": reference("target_country", "continent"), "args": [0]},
    ])
    assert answer(question, target).answer is expected


@pytest.mark.parametrize("target, expected", [("Germany", False), ("Japan", True)])
def test_player_question_keeps_explicit_boolean_grouping(audit_facts, provider, monkeypatch, target, expected):
    question = "Is it (in Europe or Asia) and an island country?"
    provider([
        predicate("contains", "continent", {"value": "Europe"}),
        predicate("contains", "continent", {"value": "Asia"}),
        {"operator": "or", "args": [0, 1]},
        predicate("equals", "is_island", {"value": True}),
        {"operator": "and", "args": [2, 3]},
    ], "Is it in Europe or Asia and an island country?")
    monkeypatch.setattr(utils.CountryRepository, "get", AsyncMock(return_value=SimpleNamespace(
        name=target, official_name=target,
    )))
    response, _ = asyncio.run(utils.analyze_and_answer_locally(
        question, SimpleNamespace(country_id=1, id=1), None, AsyncMock(), strict_errors=True,
    ))
    assert response.answer is expected
    assert "(in Europe or Asia)" in response.question


@pytest.mark.parametrize("nodes", [
    [predicate("greater_than", "population", reference("Germany", "population"), "France")],
    [predicate("north_of", "name", reference("France", "name"))],
    [predicate("contains", "continent", reference("France", "continent"))],
    [predicate("contains", "continent", {"value": "Europe"}, "item"),
     {"operator": "any", "items": reference("target_country", "continent"), "args": [0]}],
    [predicate("contains", "continent", {"value": "Europe"}, "item"),
     predicate("contains", "continent", {"value": "Europe"}),
     {"operator": "and", "args": [0, 1]},
     {"operator": "any", "items": {"value": ["Europe", "Asia"]}, "args": [2]}],
])
def test_ill_typed_or_target_free_provider_plan_cannot_claim_local_support(audit_facts, provider, nodes):
    provider(nodes)
    plan = local_planner.analyze_question_for_local_plan(
        "Could you evaluate this country's geographical and population conditions?", use_cache=False,
    )
    assert not plan.supported
    assert plan.plan is None


@pytest.mark.parametrize("target, relation, threshold", [
    ("Albania", "population", 2363314), ("Luxembourg", "area", 2586),
])
@pytest.mark.parametrize("operator", ["greater_than", "less_than"])
def test_exact_equality_explanation_does_not_assert_strict_inequality(audit_facts, target, relation, threshold, operator):
    result = local_answering.execute_local_plan(
        predicate(operator, relation, {"value": threshold}), target, "Is its value strictly beyond the threshold?",
    )
    assert result.answer is False
    # These assertions protect factual relationships, not sentence formatting.
    assert "equal to" in result.explanation
    assert not any(phrase in result.explanation for phrase in ("fewer than", "more than", "smaller than", "larger than"))


def test_named_object_references_remain_named_without_a_hidden_subject(audit_facts, provider):
    provider([predicate("greater_than", "population", reference("Germany", "population"), "France")])
    result = answer("Is the population of France greater than the population of Germany?", "Pakistan")
    assert result.answer is False


def test_model_cannot_replace_explicit_named_subject_with_constant_comparison(audit_facts, provider):
    provider([predicate("greater_than", "population", reference("Germany", "population"), "France")])
    plan = local_planner.analyze_question_for_local_plan(
        "Does France have more inhabitants than Germany?", use_cache=False,
    )
    assert not plan.supported
    assert plan.plan is None


@pytest.fixture
def border_facts(audit_facts):
    with sqlite3.connect(audit_facts) as connection:
        connection.executescript("""
            ALTER TABLE countries ADD COLUMN cca3 TEXT;
            INSERT INTO countries (id, app_country_name, official_name) VALUES
                (8, 'Panama', 'Republic of Panama'),
                (9, 'Colombia', 'Republic of Colombia'),
                (10, 'Costa Rica', 'Republic of Costa Rica');
            INSERT INTO country_continents VALUES
                (8, 'North America'), (9, 'South America'), (10, 'North America');
            CREATE TABLE country_borders (
                country_id INTEGER, border_country_name TEXT, border_cca3 TEXT
            );
            INSERT INTO country_borders (country_id, border_country_name) VALUES
                (8, 'Colombia'), (8, 'Costa Rica'), (9, 'Panama'), (10, 'Panama'),
                (2, 'France'), (3, 'Germany');
        """)


@pytest.mark.parametrize("question", [
    "does this country touch south america",
    "Does it border South America?",
    "Does the hidden country touch the continent of South America?",
    "Does France touch South America?",
])
@pytest.mark.parametrize("target, expected", [
    ("Panama", True), ("Colombia", False), ("Costa Rica", False), ("Japan", False),
])
def test_touch_continent_tests_land_neighbors_not_target_membership(
    border_facts, provider, question, target, expected,
):
    # Captured production mistake: the provider substituted continental membership.
    provider([predicate("contains", "continent", {"value": "South America"})],
             improved_question="Is the country part of South America?")
    assert answer(question, target).answer is expected


@pytest.mark.parametrize("question, target, expected", [
    ("Does it touch Europe?", "Germany", True),
    ("Does it touch Europe?", "Panama", False),
    ("Does it border Asia?", "Japan", False),
    ("Does it not touch South America?", "Panama", False),
    ("Does it not border South America?", "Colombia", True),
    ("Is it in South America?", "Panama", False),
    ("Is it in South America?", "Colombia", True),
])
def test_continent_border_preserves_continent_polarity_and_location(
    border_facts, provider, question, target, expected,
):
    provider([predicate("contains", "continent", {"value": "South America"})])
    assert answer(question, target).answer is expected


@pytest.mark.parametrize("target, expected", [
    ("Panama", True), ("Colombia", True), ("Germany", True), ("Japan", False),
])
def test_reported_americas_or_europe_uses_both_american_continents(
    border_facts, provider, target, expected,
):
    provider([
        predicate("contains", "continent", {"value": "Americas"}),
        predicate("contains", "continent", {"value": "Europe"}),
        {"operator": "or", "args": [0, 1]},
    ])
    result = answer("Is this country in the americas or europe", target)
    assert result.answer is expected


@pytest.mark.parametrize("target, expected", [
    ("Panama", False), ("Colombia", False), ("Germany", True), ("Japan", True),
])
def test_american_continent_union_preserves_nested_negation(
    border_facts, provider, target, expected,
):
    provider([
        predicate("contains", "continent", {"value": "Americas"}),
        {"operator": "not", "args": [0]},
    ])
    assert answer("Is the country not in the Americas?", target).answer is expected


@pytest.mark.parametrize("target, expected", [
    ("Panama", True), ("Germany", False),
])
def test_continental_union_preserves_neighbor_item_binding(
    border_facts, provider, target, expected,
):
    provider([
        predicate("contains", "continent", {"value": "Americas"}, "item"),
        {"operator": "any", "items": reference("target_country", "borders_country"), "args": [0]},
    ])
    assert answer("Does it have any land neighbor in the Americas?", target).answer is expected


@pytest.mark.parametrize("continent, target, expected", [
    ("North America", "Panama", True),
    ("North America", "Colombia", False),
    ("South America", "Panama", False),
    ("South America", "Colombia", True),
])
def test_continental_union_does_not_drop_north_south_qualifiers(
    border_facts, provider, continent, target, expected,
):
    provider([
        predicate("contains", "continent", {"value": continent}),
        predicate("contains", "continent", {"value": "Europe"}),
        {"operator": "or", "args": [0, 1]},
    ])
    assert answer(f"Is it in {continent} or Europe?", target).answer is expected
