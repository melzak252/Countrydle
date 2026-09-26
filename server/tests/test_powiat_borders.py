import sqlite3
from dataclasses import replace

import pytest

from local_kb_question import QuestionPlan, execute_plan
from powiatdle.utils import LOCAL_CONFIG
from powiat_names import build_powiat_aliases
from planner_protocol import compile_planner_response


@pytest.fixture
def county_border_config(tmp_path):
    path = tmp_path / "county_borders.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE powiats (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                voivodeship TEXT NOT NULL, is_city_county INTEGER NOT NULL
            );
            CREATE TABLE powiat_borders_powiats (
                powiat_id INTEGER NOT NULL, border_powiat_name TEXT NOT NULL
            );
            CREATE TABLE powiat_borders_voivodeships (
                powiat_id INTEGER NOT NULL, voivodeship TEXT NOT NULL
            );
            CREATE TABLE powiat_border_coverage (powiat_id INTEGER PRIMARY KEY);
            CREATE TABLE powiat_name_aliases (
                alias TEXT NOT NULL, powiat_id INTEGER NOT NULL,
                PRIMARY KEY (alias, powiat_id)
            );
            INSERT INTO powiats VALUES
                (1, 'Tychy', 'śląskie', 1),
                (2, 'Powiat pszczyński', 'śląskie', 0),
                (3, 'Powiat częstochowski', 'śląskie', 0),
                (4, 'Powiat kłobucki', 'śląskie', 0);
            INSERT INTO powiat_borders_powiats VALUES
                (1, 'Powiat pszczyński'), (2, 'Tychy'),
                (3, 'Powiat kłobucki'), (4, 'Powiat częstochowski');
            INSERT INTO powiat_border_coverage VALUES (1), (2), (3), (4);
            """
        )
        conn.row_factory = sqlite3.Row
        aliases = build_powiat_aliases(dict(row) for row in conn.execute("SELECT * FROM powiats"))
        conn.executemany(
            "INSERT INTO powiat_name_aliases VALUES (?, ?)",
            [(alias, identifier) for alias, identifiers in aliases.items() for identifier in identifiers],
        )
    return replace(LOCAL_CONFIG, db_path=path)


def border_plan(value, *, negate=False):
    condition = {
        "operator": "contains_exact",
        "left": {"entity": "target_powiat", "relation": "borders_powiat"},
        "right": {"value": value},
    }
    return QuestionPlan(
        original_question="Czy graniczy z tym powiatem?",
        valid=True,
        supported=True,
        improved_question=None,
        explanation=None,
        plan={"operator": "not", "condition": condition} if negate else condition,
    )


def test_county_border_inflection_preserves_true_and_false_answers(county_border_config):
    assert execute_plan(county_border_config, "Tychy", border_plan("pszczyńskim")).answer is True
    assert execute_plan(county_border_config, "Tychy", border_plan("częstochowskim")).answer is False
    assert execute_plan(county_border_config, "Powiat kłobucki", border_plan("częstochowskim")).answer is True


def test_unknown_county_reference_is_unknown_even_under_negation(county_border_config):
    assert execute_plan(county_border_config, "Tychy", border_plan("nieistniejący")) is None
    assert execute_plan(county_border_config, "Tychy", border_plan("nieistniejący", negate=True)) is None


def test_incomplete_county_borders_do_not_prove_a_negative(county_border_config):
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("DELETE FROM powiat_border_coverage WHERE powiat_id = 1")
        conn.execute("DELETE FROM powiat_borders_powiats WHERE powiat_id = 1")
    assert execute_plan(county_border_config, "Tychy", border_plan("pszczyński")) is None
    assert execute_plan(county_border_config, "Tychy", border_plan("pszczyński", negate=True)) is None


def test_complete_interior_county_can_have_no_other_voivodeship_border(county_border_config):
    plan = QuestionPlan(
        original_question="Czy graniczy z innym województwem?",
        valid=True,
        supported=True,
        improved_question=None,
        explanation=None,
        plan={"operator": "exists", "left": {"entity": "target_powiat", "relation": "borders_voivodeship"}},
    )
    assert execute_plan(county_border_config, "Tychy", plan).answer is False
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("DELETE FROM powiat_border_coverage WHERE powiat_id = 1")
    assert execute_plan(county_border_config, "Tychy", plan) is None


def test_county_self_reference_keeps_the_game_rule_without_self_edges(county_border_config):
    assert execute_plan(county_border_config, "Tychy", border_plan("Tychy")).answer is True
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("DELETE FROM powiat_border_coverage WHERE powiat_id = 1")
    assert execute_plan(county_border_config, "Tychy", border_plan("Tychy")).answer is True


def scoped_plan(condition):
    return QuestionPlan(
        original_question="Czy podany warunek dotyczący powiatu i jego sąsiadów jest prawdziwy?",
        valid=True,
        supported=True,
        improved_question=None,
        explanation=None,
        plan=condition,
    )


def city_neighbor_condition():
    return {
        "operator": "any",
        "items": {"entity": "target_powiat", "relation": "borders_powiat"},
        "condition": {
            "operator": "equals",
            "left": {"entity": "item", "relation": "is_city_county"},
            "right": {"value": 1},
        },
    }


def test_compiled_city_or_city_neighbor_distinguishes_all_three_cases(county_border_config):
    wire = {
        "route": "local",
        "plan": [
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 1}},
            {"operator": "equals", "left": {"entity": "item", "relation": "is_city_county"}, "right": {"value": 1}},
            {"operator": "any", "items": {"entity": "target_powiat", "relation": "borders_powiat"}, "args": [1]},
            {"operator": "or", "args": [0, 2]},
        ],
    }
    condition = compile_planner_response(
        wire,
        relations=county_border_config.supported_relations,
        operators={"equals", "any", "or"},
        target_entity="target_powiat",
    )
    plan = scoped_plan(condition)
    assert execute_plan(county_border_config, "Tychy", plan).answer is True
    assert execute_plan(county_border_config, "Powiat pszczyński", plan).answer is True
    assert execute_plan(county_border_config, "Powiat kłobucki", plan).answer is False


def test_nested_neighbor_quantifiers_keep_hidden_target_and_outer_item_scope(county_border_config):
    same_as_target = {
        "operator": "equals",
        "left": {"entity": "item", "relation": "name"},
        "right": {"entity": "target_powiat", "relation": "name"},
    }
    condition = {
        "operator": "all",
        "items": {"entity": "target_powiat", "relation": "borders_powiat"},
        "condition": {
            "operator": "and",
            "conditions": [
                {
                    "operator": "any",
                    "items": {"entity": "item", "relation": "borders_powiat"},
                    "condition": same_as_target,
                },
                {"operator": "not", "condition": same_as_target},
            ],
        },
    }
    assert execute_plan(county_border_config, "Tychy", scoped_plan(condition)).answer is True


def test_unresolved_neighbor_properties_remain_unknown_unless_a_witness_proves_true(county_border_config):
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("INSERT INTO powiat_borders_powiats VALUES (4, 'Nieznany powiat')")
        conn.execute("DELETE FROM powiat_borders_powiats WHERE powiat_id = 2")
        conn.executemany(
            "INSERT INTO powiat_borders_powiats VALUES (2, ?)",
            [("Nieznany powiat",), ("Tychy",)],
        )
    condition = city_neighbor_condition()
    assert execute_plan(county_border_config, "Powiat kłobucki", scoped_plan(condition)) is None
    assert execute_plan(
        county_border_config, "Powiat kłobucki",
        scoped_plan({"operator": "not", "condition": condition}),
    ) is None
    assert execute_plan(county_border_config, "Powiat pszczyński", scoped_plan(condition)).answer is True


def test_literal_list_values_do_not_become_entities_by_matching_a_county_name(county_border_config):
    condition = {
        "operator": "any",
        "items": {"value": ["Tychy"]},
        "condition": {
            "operator": "equals",
            "left": {"entity": "item", "relation": "is_city_county"},
            "right": {"value": 1},
        },
    }
    assert execute_plan(county_border_config, "Tychy", scoped_plan(condition)) is None
    condition["condition"] = {
        "operator": "contains_text",
        "left": {"entity": "item", "relation": "name"},
        "right": {"value": "ych"},
    }
    assert execute_plan(county_border_config, "Tychy", scoped_plan(condition)).answer is True


def test_neighbor_self_rule_uses_neighbor_not_the_hidden_target(county_border_config):
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("DELETE FROM powiat_border_coverage WHERE powiat_id = 2")
    condition = {
        "operator": "any",
        "items": {"entity": "target_powiat", "relation": "borders_powiat"},
        "condition": {
            "operator": "contains_exact",
            "left": {"entity": "item", "relation": "borders_powiat"},
            "right": {"entity": "target_powiat", "relation": "name"},
        },
    }
    assert execute_plan(county_border_config, "Tychy", scoped_plan(condition)) is None
    condition["condition"]["right"] = {"entity": "item", "relation": "name"}
    assert execute_plan(county_border_config, "Tychy", scoped_plan(condition)).answer is True


def test_quantifiers_distinguish_verified_empty_neighbors_from_missing_coverage(county_border_config):
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("DELETE FROM powiat_borders_powiats WHERE powiat_id = 4")
    condition = city_neighbor_condition()
    all_condition = {**condition, "operator": "all"}
    assert execute_plan(county_border_config, "Powiat kłobucki", scoped_plan(condition)).answer is False
    assert execute_plan(county_border_config, "Powiat kłobucki", scoped_plan(all_condition)).answer is True
    with sqlite3.connect(county_border_config.db_path) as conn:
        conn.execute("DELETE FROM powiat_border_coverage WHERE powiat_id = 4")
    assert execute_plan(county_border_config, "Powiat kłobucki", scoped_plan(condition)) is None
    assert execute_plan(county_border_config, "Powiat kłobucki", scoped_plan(all_condition)) is None
