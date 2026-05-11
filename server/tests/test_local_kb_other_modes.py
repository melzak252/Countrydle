import pathlib
from dataclasses import replace

import pytest

from local_kb_question import LocalModeConfig, QuestionPlan, execute_plan
from powiatdle.utils import LOCAL_CONFIG as POWIAT_RUNTIME_CONFIG
from us_statedle.utils import LOCAL_CONFIG as US_STATE_RUNTIME_CONFIG
from wojewodztwodle.utils import LOCAL_CONFIG as VOIVODESHIP_RUNTIME_CONFIG


DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data"
REQUIRED_DBS = [
    DATA_DIR / "us_state_facts.sqlite",
    DATA_DIR / "powiat_facts.sqlite",
    DATA_DIR / "voivodeship_facts.sqlite",
]

US_STATE_CONFIG = replace(US_STATE_RUNTIME_CONFIG, db_path=DATA_DIR / "us_state_facts.sqlite")
POWIAT_CONFIG = replace(POWIAT_RUNTIME_CONFIG, db_path=DATA_DIR / "powiat_facts.sqlite")
VOIVODESHIP_CONFIG = replace(VOIVODESHIP_RUNTIME_CONFIG, db_path=DATA_DIR / "voivodeship_facts.sqlite")


pytestmark = pytest.mark.skipif(
    not all(path.exists() for path in REQUIRED_DBS),
    reason="Local SQLite KB files for US states, powiats, and voivodeships are missing",
)


def question_plan(plan: dict) -> QuestionPlan:
    return QuestionPlan(
        original_question="Test question?",
        valid=True,
        supported=True,
        improved_question="Test question?",
        explanation="Test planner explanation.",
        plan=plan,
    )


def answer(config: LocalModeConfig, entity_name: str, plan: dict):
    return execute_plan(config, entity_name, question_plan(plan))


def left(config: LocalModeConfig, relation: str) -> dict:
    return {"entity": config.target_entity, "relation": relation}


def contains(config: LocalModeConfig, relation: str, value: str) -> dict:
    return {"operator": "contains", "left": left(config, relation), "value": value}


def equals(config: LocalModeConfig, relation: str, value) -> dict:
    return {"operator": "equals", "left": left(config, relation), "right": {"value": value}}


def scalar(config: LocalModeConfig, operator: str, relation: str, value) -> dict:
    return {"operator": operator, "left": left(config, relation), "right": value}


@pytest.mark.parametrize(
    ("state", "relation", "value"),
    [
        ("California", "region", "West"),
        ("California", "division", "Pacific"),
        ("California", "water_access", "Pacific Ocean"),
        ("California", "regional_labels", "West Coast"),
        ("California", "borders_state", "Oregon"),
        ("New York", "regional_labels", "East Coast"),
        ("New York", "water_access", "Lake Ontario"),
        ("Texas", "regional_labels", "Gulf Coast"),
        ("Texas", "borders_country", "Mexico"),
        ("Colorado", "mountain_ranges", "Rocky Mountains"),
        ("Florida", "major_highways", "I-95"),
    ],
)
def test_us_state_list_and_scalar_relations(state, relation, value):
    result = answer(US_STATE_CONFIG, state, contains(US_STATE_CONFIG, relation, value))

    assert result is not None
    assert result.answer is True
    assert relation in result.relations


def test_us_state_numeric_text_and_derived_coast_checks():
    assert answer(US_STATE_CONFIG, "California", scalar(US_STATE_CONFIG, "greater_than", "population", 30_000_000)).answer is True
    assert answer(US_STATE_CONFIG, "California", scalar(US_STATE_CONFIG, "less_than", "admission_year", 1900)).answer is True
    assert answer(US_STATE_CONFIG, "California", scalar(US_STATE_CONFIG, "contains_text", "nickname", "Golden")).answer is True
    assert answer(US_STATE_CONFIG, "California", equals(US_STATE_CONFIG, "civil_war_side", "Union")).answer is True
    assert answer(US_STATE_CONFIG, "California", contains(US_STATE_CONFIG, "region", "West Coast")).answer is True
    assert answer(US_STATE_CONFIG, "New York", contains(US_STATE_CONFIG, "region", "East Coast")).answer is True
    assert answer(US_STATE_CONFIG, "Michigan", contains(US_STATE_CONFIG, "water_access", "Great Lakes")).answer is True
    assert answer(US_STATE_CONFIG, "California", contains(US_STATE_CONFIG, "region", "East Coast")).answer is False


@pytest.mark.parametrize(
    ("powiat", "relation", "value"),
    [
        ("Kraków", "voivodeship", "małopolskie"),
        ("Kraków", "registration_plates", "KR"),
        ("Kraków", "major_rivers", "Wisła"),
        ("Kraków", "major_roads", "A4"),
        ("Powiat krakowski", "seat", "Kraków"),
        ("Powiat krakowski", "borders_powiat", "Kraków"),
        ("Powiat krakowski", "registration_plates", "KRK"),
        ("Powiat tatrzański", "seat", "Zakopane"),
        ("Powiat tatrzański", "registration_plates", "KTT"),
        ("Powiat tatrzański", "major_rivers", "Dunajec"),
    ],
)
def test_powiat_local_relations(powiat, relation, value):
    result = answer(POWIAT_CONFIG, powiat, contains(POWIAT_CONFIG, relation, value))

    assert result is not None
    assert result.answer is True
    assert relation in result.relations


def test_powiat_numeric_boolean_and_negative_cases():
    assert answer(POWIAT_CONFIG, "Kraków", equals(POWIAT_CONFIG, "is_city_county", 1)).answer is True
    assert answer(POWIAT_CONFIG, "Powiat krakowski", equals(POWIAT_CONFIG, "is_city_county", 0)).answer is True
    assert answer(POWIAT_CONFIG, "Powiat krakowski", scalar(POWIAT_CONFIG, "greater_than", "gmina_count", 10)).answer is True
    assert answer(POWIAT_CONFIG, "Powiat tatrzański", scalar(POWIAT_CONFIG, "less_than", "population", 100_000)).answer is True
    assert answer(POWIAT_CONFIG, "Powiat tatrzański", contains(POWIAT_CONFIG, "borders_powiat", "Kraków")).answer is False


@pytest.mark.parametrize(
    ("voivodeship", "relation", "value"),
    [
        ("Małopolskie", "seat", "Kraków"),
        ("Małopolskie", "macroregion", "południe"),
        ("Małopolskie", "borders_country", "Słowacja"),
        ("Małopolskie", "borders_voivodeship", "Śląskie"),
        ("Małopolskie", "mountain_ranges", "Tatry"),
        ("Małopolskie", "historical_region", "Małopolska"),
        ("Pomorskie", "water_access", "Morze Bałtyckie"),
        ("Pomorskie", "regional_labels", "nadmorska Polska"),
        ("Podlaskie", "borders_country", "Litwa"),
        ("Śląskie", "historical_region", "Górny Śląsk"),
    ],
)
def test_voivodeship_local_relations(voivodeship, relation, value):
    result = answer(VOIVODESHIP_CONFIG, voivodeship, contains(VOIVODESHIP_CONFIG, relation, value))

    assert result is not None
    assert result.answer is True
    assert relation in result.relations


def test_voivodeship_numeric_boolean_and_negative_cases():
    assert answer(VOIVODESHIP_CONFIG, "Pomorskie", equals(VOIVODESHIP_CONFIG, "is_coastal", 1)).answer is True
    assert answer(VOIVODESHIP_CONFIG, "Małopolskie", equals(VOIVODESHIP_CONFIG, "is_coastal", 0)).answer is True
    assert answer(VOIVODESHIP_CONFIG, "Mazowieckie", scalar(VOIVODESHIP_CONFIG, "greater_than", "population", 5_000_000)).answer is True
    assert answer(VOIVODESHIP_CONFIG, "Opolskie", scalar(VOIVODESHIP_CONFIG, "less_than", "area", 10_000)).answer is True
    assert answer(VOIVODESHIP_CONFIG, "Pomorskie", contains(VOIVODESHIP_CONFIG, "borders_country", "Słowacja")).answer is False


def test_generic_boolean_any_all_and_self_neighbor_semantics():
    any_border_starts_with_a = {
        "operator": "any",
        "items": left(US_STATE_CONFIG, "borders_state"),
        "condition": {"operator": "starts_with", "left": {"entity": "item"}, "value": "A"},
    }
    all_california_waters_are_oceans = {
        "operator": "all",
        "items": left(US_STATE_CONFIG, "water_access"),
        "condition": {"operator": "contains_text", "left": {"entity": "item"}, "value": "Ocean"},
    }
    self_neighbor = contains(VOIVODESHIP_CONFIG, "borders_voivodeship", "Małopolskie")

    assert answer(US_STATE_CONFIG, "California", any_border_starts_with_a).answer is True
    assert answer(US_STATE_CONFIG, "California", all_california_waters_are_oceans).answer is True
    assert answer(VOIVODESHIP_CONFIG, "Małopolskie", self_neighbor).answer is True


def test_generic_mixed_sqlite_and_unsupported_conditions_fallback_only_when_needed():
    true_sql = contains(US_STATE_CONFIG, "borders_state", "Oregon")
    false_sql = contains(US_STATE_CONFIG, "borders_state", "Florida")
    unknown = contains(US_STATE_CONFIG, "made_up_relation", "anything")

    assert answer(US_STATE_CONFIG, "California", {"operator": "and", "conditions": [true_sql, unknown]}) is None
    assert answer(US_STATE_CONFIG, "California", {"operator": "or", "conditions": [false_sql, unknown]}) is None
    assert answer(US_STATE_CONFIG, "California", {"operator": "and", "conditions": [false_sql, unknown]}).answer is False
    assert answer(US_STATE_CONFIG, "California", {"operator": "or", "conditions": [true_sql, unknown]}).answer is True


@pytest.mark.parametrize(
    "bad_plan",
    [
        {},
        {"operator": "and", "conditions": []},
        {"operator": "contains", "left": left(POWIAT_CONFIG, "registration_plates")},
        {"operator": "greater_than", "left": left(VOIVODESHIP_CONFIG, "population"), "right": "many"},
        {"operator": "made_up", "left": left(US_STATE_CONFIG, "region"), "value": "West"},
    ],
)
def test_invalid_generic_local_plans_do_not_answer(bad_plan):
    assert answer(US_STATE_CONFIG, "California", bad_plan) is None
