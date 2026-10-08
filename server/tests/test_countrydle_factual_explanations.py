import re
import sqlite3

import pytest

from countrydle.local_answering import evaluate_plan_node, generate_factual_explanation


@pytest.fixture
def country_facts():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE countries (
                id INTEGER PRIMARY KEY, app_country_name TEXT, official_name TEXT,
                capital TEXT, latitude REAL, longitude REAL
            );
            INSERT INTO countries VALUES (1, 'Alpha', 'Alpha', 'Alpha City', 12, 24);
            INSERT INTO countries VALUES (2, 'Beta', 'Beta', 'Beta City', 12, 24);
            CREATE TABLE country_languages (country_id INTEGER, language_name TEXT);
            INSERT INTO country_languages VALUES (1, 'First');
            INSERT INTO country_languages VALUES (1, 'Second');
            """
        )
        target = conn.execute("SELECT * FROM countries WHERE id=1").fetchone()
        yield conn, target


@pytest.mark.parametrize(
    "operator,relation,axis,wrong_direction",
    [
        ("north_of", "coordinates.latitude", "latitude", "south"),
        ("south_of", "coordinates.latitude", "latitude", "south"),
        ("east_of", "coordinates.longitude", "longitude", "west"),
        ("west_of", "coordinates.longitude", "longitude", "west"),
    ],
)
def test_equal_coordinates_explain_equality_not_an_opposite_direction(
    country_facts, operator, relation, axis, wrong_direction
):
    conn, target = country_facts
    plan = {
        "operator": operator,
        "left": {"entity": "target_country", "relation": relation},
        "right": {"entity": "Beta", "relation": relation},
    }
    assert evaluate_plan_node(conn, plan, target) is False
    explanation = generate_factual_explanation(conn, target, plan, False).lower()
    assert "alpha" in explanation and "beta" in explanation
    assert axis in explanation and any(word in explanation for word in ("same", "equal"))
    assert f"{wrong_direction} of" not in explanation


def test_quantified_direction_explains_the_bound_right_country(country_facts):
    conn, target = country_facts
    conn.execute("UPDATE countries SET latitude=5 WHERE id=2")
    plan = {
        "operator": "any",
        "items": {"value": ["Beta"]},
        "condition": {
            "operator": "north_of",
            "left": {"entity": "target_country", "relation": "coordinates.latitude"},
            "right": {"entity": "item", "relation": "coordinates.latitude"},
        },
    }
    assert evaluate_plan_node(conn, plan, target) is True
    explanation = generate_factual_explanation(conn, target, plan, True)
    assert "Alpha" in explanation and "Beta" in explanation
    assert "north" in explanation.lower()
    assert "12" in explanation and "5" in explanation


def test_language_count_explains_languages_not_a_numeric_language(country_facts):
    conn, target = country_facts
    plan = {
        "operator": "equals",
        "left": {"entity": "target_country", "relation": "official_language"},
        "right": {"value": 2},
    }
    assert evaluate_plan_node(conn, plan, target) is True
    explanation = generate_factual_explanation(conn, target, plan, True).lower()
    assert "first" in explanation and "second" in explanation
    assert re.search(r"\b2\b.*\blanguages\b|\blanguages\b.*\b2\b", explanation)


@pytest.mark.parametrize("literal_operand", [False, True])
def test_country_alias_hyphen_does_not_become_a_fact_about_capital_text(
    country_facts, literal_operand
):
    conn, _ = country_facts
    conn.execute(
        "UPDATE countries SET app_country_name='East Timor', "
        "official_name='Timor-Leste', capital='Dili' WHERE id=1"
    )
    target = conn.execute("SELECT * FROM countries WHERE id=1").fetchone()
    plan = {
        "operator": "has_hyphen",
        "left": {"value": "Dili"} if literal_operand else {
            "entity": "target_country", "relation": "capital"
        },
    }
    answer = evaluate_plan_node(conn, plan, target)
    assert answer is False
    explanation = generate_factual_explanation(conn, target, plan, answer)
    assert "Dili" in explanation
    assert re.search(r"does not contain.*hyphen", explanation)


@pytest.mark.parametrize("literal_operand", [False, True])
def test_punctuated_capital_count_is_described_as_characters_not_letters(
    country_facts, literal_operand
):
    conn, _ = country_facts
    conn.execute(
        "UPDATE countries SET app_country_name='Chad', official_name='Chad', "
        "capital=? WHERE id=1",
        ("N'Djamena",),
    )
    target = conn.execute("SELECT * FROM countries WHERE id=1").fetchone()
    plan = {
        "operator": "char_count_equals",
        "left": {"value": "N'Djamena"} if literal_operand else {
            "entity": "target_country", "relation": "capital"
        },
        "right": {"value": 9},
    }
    assert evaluate_plan_node(conn, plan, target) is True
    explanation = generate_factual_explanation(conn, target, plan, True)
    assert "N'Djamena" in explanation
    assert re.search(r"\b9\b.*\bcharacters\b", explanation)
    assert not re.search(r"\b9\b.*\bletters\b", explanation)


@pytest.mark.parametrize("relation,expected", [("capital", False), ("name", True)])
def test_named_reference_is_not_described_as_the_target(country_facts, relation, expected):
    conn, target = country_facts
    plan = {
        "operator": "equals",
        "left": {
            "entity": "target_country" if relation == "capital" else "Beta",
            "relation": relation,
        },
        "right": {"entity": "Beta", "relation": "name"},
    }
    assert evaluate_plan_node(conn, plan, target) is expected
    explanation = generate_factual_explanation(conn, target, plan, expected).lower()
    assert re.search(r"referenc.*\bbeta\b|\bbeta\b.*referenc", explanation)
    if relation == "capital":
        assert "alpha city" in explanation


@pytest.mark.parametrize("negated", [False, True])
def test_country_name_hyphen_explains_the_accepted_alias(country_facts, negated):
    conn, _ = country_facts
    conn.execute("UPDATE countries SET app_country_name='East Timor' WHERE id=1")
    target = conn.execute("SELECT * FROM countries WHERE id=1").fetchone()
    predicate = {
        "operator": "has_hyphen",
        "left": {"entity": "target_country", "relation": "name"},
    }
    plan = {"operator": "not", "condition": predicate} if negated else predicate
    answer = evaluate_plan_node(conn, plan, target)
    assert answer is not negated
    explanation = generate_factual_explanation(conn, target, plan, answer).lower()
    assert "east timor" in explanation and "timor-leste" in explanation
    assert re.search(r"contain.*hyphen", explanation)


def test_country_alias_hyphen_uses_the_named_operand_not_the_target(country_facts):
    conn, target = country_facts
    conn.execute("UPDATE countries SET app_country_name='East Timor' WHERE id=2")
    plan = {
        "operator": "has_hyphen",
        "left": {"entity": "East Timor", "relation": "name"},
    }
    assert evaluate_plan_node(conn, plan, target) is True
    explanation = generate_factual_explanation(conn, target, plan, True).lower()
    assert "east timor" in explanation and "timor-leste" in explanation
