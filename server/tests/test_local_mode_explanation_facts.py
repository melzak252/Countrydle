"""Explanations must retain the facts and bindings used to answer a question."""

from dataclasses import replace
import sqlite3
from pathlib import Path

import pytest

from local_kb_question import (
    LocalModeConfig, QuestionPlan, evaluate, generate_mode_explanation, get_relation_value,
)


@pytest.fixture
def facts():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE entities (id INTEGER, name TEXT, population INTEGER,
                                   is_coastal INTEGER, seat TEXT);
            INSERT INTO entities VALUES (1, 'Amber', 12345, 1, 'Amber Seat');
            INSERT INTO entities VALUES (2, 'Birch', 67890, 0, 'Birch Seat');
            CREATE TABLE neighbors (entity_id INTEGER, name TEXT);
            INSERT INTO neighbors VALUES (1, 'Birch');
            CREATE TABLE rivers (entity_id INTEGER, name TEXT);
            INSERT INTO rivers VALUES (1, 'Silver River');
            INSERT INTO rivers VALUES (1, 'Copper River');
        """)
        yield conn, conn.execute("SELECT * FROM entities WHERE id = 1").fetchone()


def config(language="English"):
    return LocalModeConfig(
        mode_name="Wojewodztwodle" if language == "Polish" else "USStatedle",
        entity_label="entity", target_entity="target", db_path=Path(":memory:"),
        table="entities", name_column="name", fk_column="entity_id",
        scalar_relations={"name": "name", "population": "population",
                          "is_coastal": "is_coastal", "seat": "seat"},
        list_relations={"neighbors": ("neighbors", "name"), "major_rivers": ("rivers", "name")},
        supported_relations=["name", "population", "is_coastal", "seat", "neighbors", "major_rivers"],
        entity_list_relations=frozenset({"neighbors"}), language=language,
    )


def explain(facts, mode, node):
    conn, row = facts
    answer = evaluate(conn, mode, row, node)
    assert answer is not None
    plan = QuestionPlan("Question?", True, True, "Question?", "Planner note", node)
    return answer, generate_mode_explanation(mode, row, plan, answer, conn)


def test_false_coastal_comparison_does_not_claim_coastal_entity_is_inland(facts):
    answer, explanation = explain(facts, config("Polish"), {
        "operator": "equals", "left": {"entity": "target", "relation": "is_coastal"},
        "right": {"value": False},
    })
    assert answer is False
    assert "Amber" in explanation
    assert "nie ma dostępu" not in explanation
    assert "śródląd" not in explanation


def test_named_seat_reference_explains_referenced_entity_not_target(facts):
    answer, explanation = explain(facts, config("Polish"), {
        "operator": "equals", "left": {"entity": "Birch", "relation": "seat"},
        "right": {"value": "Birch Seat"},
    })
    assert answer is True
    assert "Birch Seat" in explanation
    assert "Amber Seat" not in explanation


@pytest.mark.parametrize("language", ["English", "Polish"])
@pytest.mark.parametrize("operator", ["not", "and", "or"])
def test_logical_explanation_preserves_actual_population(facts, language, operator):
    predicate = {
        "operator": "greater_than", "left": {"entity": "target", "relation": "population"},
        "right": {"value": 20000},
    }
    node = ({"operator": "not", "condition": predicate} if operator == "not" else
            {"operator": operator, "conditions": [predicate, {
                "operator": "equals", "left": {"entity": "target", "relation": "name"},
                "right": {"value": "Amber"},
            }]})
    _, explanation = explain(facts, config(language), node)
    assert "Amber" in explanation
    assert "12345" in explanation.replace(" ", "").replace(",", "").replace("\u00a0", "")


@pytest.mark.parametrize("operator", ["any", "all"])
def test_quantified_explanation_uses_neighbor_population_not_target(facts, operator):
    answer, explanation = explain(facts, config(), {
        "operator": operator, "items": {"entity": "target", "relation": "neighbors"},
        "condition": {
            "operator": "greater_than", "left": {"entity": "item", "relation": "population"},
            "right": {"value": 50000},
        },
    })
    assert answer is True
    assert "Birch" in explanation
    assert "67890" in explanation.replace(" ", "").replace(",", "").replace("\u00a0", "")
    assert "12345" not in explanation.replace(" ", "").replace(",", "")


def test_list_count_explanation_preserves_real_rivers_instead_of_inventing_numeric_river(facts):
    answer, explanation = explain(facts, config("Polish"), {
        "operator": "word_count_greater_than",
        "left": {"entity": "target", "relation": "major_rivers"},
        "right": {"value": 1},
    })
    assert answer is True
    assert "Silver River" in explanation
    assert "Copper River" in explanation


def test_named_comparison_preserves_both_population_facts(facts):
    answer, explanation = explain(facts, config(), {
        "operator": "less_than",
        "left": {"entity": "target", "relation": "population"},
        "right": {"entity": "Birch", "relation": "population"},
    })
    assert answer is True
    assert "Amber" in explanation
    assert "Birch" in explanation
    numbers = explanation.replace(" ", "").replace(",", "").replace("\u00a0", "")
    assert "12345" in numbers
    assert "67890" in numbers


@pytest.mark.parametrize("operator", ["or", "and", "any", "all"])
def test_explanation_preserves_decisive_answer_without_visiting_skipped_predicates(
    facts, operator
):
    conn, row = facts
    conn.executescript("""
        CREATE TABLE waters (entity_id INTEGER, name TEXT);
        INSERT INTO waters VALUES (1, 'Demo Sea');
        INSERT INTO neighbors VALUES (1, 'Amber');
    """)
    mode = config("Polish")
    mode = replace(
        mode,
        list_relations={**mode.list_relations, "water_access": ("waters", "name")},
        supported_relations=[*mode.supported_relations, "water_access"],
    )
    skipped = {
        "operator": "equals",
        "left": {"entity": "target", "relation": "water_access"},
        "right": {"entity": "Amber", "relation": "water_access"},
    }
    expected = operator in {"or", "any"}
    if operator in {"and", "or"}:
        node = {
            "operator": operator,
            "conditions": [{
                "operator": "equals",
                "left": {"entity": "target", "relation": "is_coastal"},
                "right": {"value": expected},
            }, skipped],
        }
    else:
        neighbors = get_relation_value(conn, mode, row, "neighbors")
        selected = neighbors[0] if expected else neighbors[-1]
        node = {
            "operator": operator,
            "items": {"entity": "target", "relation": "neighbors"},
            "condition": {
                "operator": "or" if expected else "and",
                "conditions": [{
                    "operator": "equals",
                    "left": {"entity": "item", "relation": "name"},
                    "right": {"value": selected},
                }, skipped],
            },
        }
    assert evaluate(conn, mode, row, node) is expected
    plan = QuestionPlan("Question?", True, True, "Question?", "Planner note", node)
    explanation = generate_mode_explanation(mode, row, plan, expected, conn)
    assert "Amber" in explanation
    assert explanation.startswith("Tak" if expected else "Nie")
