"""QA evaluator/template regressions; live interpretation is explicitly opt-in.

Captured plans test executor/report behavior only, not present provider accuracy.
Every executor uses an owned temporary database, never ignored application data.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).parent
CAPTURED_FIXTURE = json.loads((TEST_DIR / "qa_playground_captured_plans.json").read_text(encoding="utf-8"))
CAPTURED_CASES = CAPTURED_FIXTURE["cases"]
live_planner_eval = pytest.mark.skipif(
    os.getenv("COUNTRYDLE_RUN_LIVE_PLANNER_EVAL") != "1",
    reason="Set COUNTRYDLE_RUN_LIVE_PLANNER_EVAL=1 for current provider interpretation checks",
)


@pytest.fixture
def playground(monkeypatch, tmp_path):
    import dotenv
    import local_kb_question
    from countrydle import local_answering, local_planner

    # Importing the CLI must not load a developer's .env or leak default settings.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_kb_question, "load_dotenv", lambda: None)
    monkeypatch.setattr(local_planner, "load_dotenv_if_present", lambda: None)
    for key, value in {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "LOCAL_QUESTION_MODEL": "gemini-2.5-flash-lite",
        "GEMINI_QUESTION_MODEL": "gemini-2.5-flash-lite",
        "EMAIL_USERNAME": "test@example.com", "NOREPLY_EMAIL": "test@example.com",
        "EMAIL_PASSWORD": "test-password", "ALGORITHM": "HS256",
        "SECRET_KEY": "test-secret-key-1234567890123456",
    }.items():
        monkeypatch.setenv(key, os.environ.get(key, value))
    module = importlib.import_module("scripts.qa_playground")

    country_db = tmp_path / "countries.sqlite"
    facts = json.loads((TEST_DIR / "countrydle_english_facts.json").read_text(encoding="utf-8"))
    with sqlite3.connect(country_db) as connection:
        for table in facts["tables"]:
            columns = ", ".join(f'"{name}" {datatype}' for name, datatype in table["columns"])
            connection.execute(f'CREATE TABLE "{table["name"]}" ({columns})')
            placeholders = ", ".join("?" for _ in table["columns"])
            connection.executemany(f'INSERT INTO "{table["name"]}" VALUES ({placeholders})', table["rows"])
        # Historical captured operands fill only relations absent from the snapshot.
        additions = CAPTURED_FIXTURE["fact_additions"]
        religion = additions["religion"]
        connection.execute("ALTER TABLE countries ADD COLUMN dominant_religion TEXT")
        connection.execute(
            "UPDATE countries SET dominant_religion = ? WHERE app_country_name = ?",
            (religion["value"], religion["country"]),
        )
        currency = additions["currency"]
        connection.execute("CREATE TABLE country_currencies (country_id INTEGER, currency_code TEXT, currency_name TEXT)")
        connection.execute(
            "INSERT INTO country_currencies SELECT id, ?, ? FROM countries WHERE app_country_name = ?",
            (currency["code"], currency["name"], currency["country"]),
        )
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", country_db)

    # Controlled regional operands exercise the real template and SQLite executor.
    regional_db = tmp_path / "regional.sqlite"
    with sqlite3.connect(regional_db) as connection:
        connection.executescript("""
            CREATE TABLE voivodeships (id INTEGER PRIMARY KEY, name TEXT, is_coastal INTEGER);
            INSERT INTO voivodeships VALUES (1, 'Śląskie', 0), (2, 'Pomorskie', 1), (3, 'Małopolskie', 0);
            CREATE TABLE voivodeship_borders_voivodeships (voivodeship_id INTEGER, border_voivodeship_name TEXT);
            INSERT INTO voivodeship_borders_voivodeships VALUES (1, 'Łódzkie');
            CREATE TABLE voivodeship_borders_countries (voivodeship_id INTEGER, country_name TEXT);
            INSERT INTO voivodeship_borders_countries VALUES (3, 'Słowacja');
            CREATE TABLE voivodeship_water_access (voivodeship_id INTEGER, water_body TEXT);
            INSERT INTO voivodeship_water_access VALUES (2, 'Morze Bałtyckie');
            CREATE TABLE powiats (id INTEGER PRIMARY KEY, name TEXT, voivodeship TEXT, is_city_county INTEGER);
            INSERT INTO powiats VALUES (1, 'Kraków', 'Małopolskie', 1), (2, 'Powiat krakowski', 'Małopolskie', 0);
            CREATE TABLE powiat_name_aliases (alias TEXT, powiat_id INTEGER);
            CREATE TABLE us_states (id INTEGER PRIMARY KEY, name TEXT, is_coastal INTEGER);
            INSERT INTO us_states VALUES (1, 'New Mexico', 0), (2, 'California', 1), (3, 'Texas', 1);
            CREATE TABLE us_state_borders_states (state_id INTEGER, border_state_name TEXT);
            INSERT INTO us_state_borders_states VALUES (1, 'Texas');
        """)
    for mode, config in module.MODES.items():
        if config is not None:
            monkeypatch.setitem(module.MODES, mode, replace(config, db_path=regional_db))
    cache_module = importlib.import_module("utils.plan_cache")
    monkeypatch.setattr(cache_module, "plan_cache", cache_module.PlanCache(db_path=tmp_path / "cache.sqlite"))
    return module


@pytest.mark.parametrize("mode, question, target, expected", [
    ("countrydle", "Is it in Europe?", "Poland", True),
    ("countrydle", "Is it in the Northern Hemisphere?", "Kiribati", True),
    ("countrydle", "Is it in the Southern Hemisphere?", "Kiribati", True),
    ("countrydle", "Does it have access to the sea?", "Poland", True),
    ("countrydle", "Is it landlocked?", "Czech Republic", True),
    ("countrydle", "Is it an island country?", "Dominican Republic", True),
    ("wojewodztwodle", "Czy to województwo graniczy z województwem łódzkim?", "Śląskie", True),
    ("wojewodztwodle", "Czy ma dostęp do morza?", "Pomorskie", True),
    ("wojewodztwodle", "Czy to województwo graniczy ze Słowacją?", "Małopolskie", True),
    ("powiatdle", "Czy to miasto na prawach powiatu?", "Kraków", True),
    ("powiatdle", "Czy to powiat ziemski?", "Powiat krakowski", True),
    ("us_statedle", "Is it coastal?", "California", True),
])
def test_qa_playground_actual_templates_evaluate_offline(playground, monkeypatch, mode, question, target, expected):
    import local_kb_question
    from utils import ai_clients

    def unexpected_provider(*args, **kwargs):
        pytest.fail("An offline template regression must not request a provider interpretation")

    monkeypatch.setattr(local_kb_question, "gemini_json", unexpected_provider)
    monkeypatch.setattr(ai_clients, "generate_gemini_json", unexpected_provider)
    rec = playground.evaluate_case(mode, question, target, expected, category="offline_template_regression")
    assert rec["verdict"] == "PASS", rec
    assert rec["actual_answer"] is expected


@live_planner_eval
@pytest.mark.parametrize("mode, question, target, expected", [
    ("countrydle", "Is it entirely in the Northern Hemisphere?", "Kiribati", False),
    ("countrydle", "Is it entirely in the Northern Hemisphere?", "Poland", True),
    ("us_statedle", "Does it border Texas?", "New Mexico", True),
    ("countrydle", "Is Catholicism the dominant religion?", "Poland", True),
    ("countrydle", "Is it neither in Europe nor in Asia?", "Brazil", True),
    ("countrydle", "Does the country have territory in both Africa and Asia?", "Egypt", True),
    ("countrydle", "Does any of the country territory lie in Europe?", "Kazakhstan", True),
    ("countrydle", "Does the country have territory in all four hemispheres?", "Kiribati", True),
    ("countrydle", "Is the US dollar an official currency in El Salvador?", "El Salvador", True),
])
def test_qa_playground_current_provider_interpretation(playground, mode, question, target, expected):
    rec = playground.evaluate_case(mode, question, target, expected, category="live_provider_interpretation")
    assert rec["verdict"] == "PASS", rec
    assert rec["actual_answer"] is expected


@pytest.mark.parametrize("case", CAPTURED_CASES, ids=lambda case: case["question"])
def test_qa_playground_captured_plan_executor_and_verdict(playground, monkeypatch, case):
    from countrydle.local_planner import QuestionPlan

    planned = QuestionPlan(
        original_question=case["question"], valid=True, supported=True,
        improved_question=None, explanation=None, plan=case["plan"],
    )
    monkeypatch.setattr(playground, "analyze_question_for_local_plan", lambda *args, **kwargs: planned)
    rec = playground.evaluate_case("countrydle", case["question"], case["target"], case["expected"], category="captured_executor_regression")
    assert rec["verdict"] == "PASS", rec
    assert rec["actual_answer"] is case["expected"]


@pytest.mark.parametrize("state, target, expected, verdict", [
    ("local", "Poland", True, "PASS"),
    ("local", "Japan", True, "FAIL_LOGIC"),
    ("local", "Unknown fixture entity", True, "FAIL_UNRESOLVED"),
    ("clarify", "Poland", True, "FAIL_INVALID"),
    ("fallback", "Poland", True, "FAIL_FALLTHROUGH"),
    ("crash", "Poland", True, "FAIL_CRASH"),
    ("local", "Poland", None, "EXPLORATORY"),
])
def test_qa_playground_classifies_real_executor_results_without_false_passes(playground, monkeypatch, state, target, expected, verdict):
    from countrydle.local_planner import QuestionPlan

    def interpretation(question, **kwargs):
        if state == "crash":
            raise RuntimeError("Provider interpretation unavailable")
        return QuestionPlan(
            original_question=question, valid=state != "clarify", supported=state == "local",
            improved_question=None, explanation=None,
            plan={"operator": "contains", "left": {"entity": "target_country", "relation": "continent"}, "right": {"value": "Europe"}} if state == "local" else None,
            fallback_reason="Relation unavailable" if state == "fallback" else None,
        )

    monkeypatch.setattr(playground, "analyze_question_for_local_plan", interpretation)
    rec = playground.evaluate_case("countrydle", "Is it in Europe?", target, expected)
    assert rec["verdict"] == verdict, rec
    if state == "local" and target in {"Poland", "Japan"}:
        assert rec["actual_answer"] is (target == "Poland")
    elif state != "crash":
        assert rec["actual_answer"] is None


def test_cli_import_preserves_explicit_environment_without_loading_developer_dotenv(monkeypatch):
    import dotenv

    def forbidden_developer_config(*args, **kwargs):
        raise AssertionError("QA import must not read an unrequested developer dotenv file")

    explicit = {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "GEMINI_API_KEY": "explicit-provider-test-value-never-used",
        "SECRET_KEY": "explicit-isolated-qa-signing-test-value",
    }
    for key, value in explicit.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(dotenv, "load_dotenv", forbidden_developer_config)
    spec = importlib.util.spec_from_file_location(
        "_qa_environment_contract", TEST_DIR.parent / "scripts" / "qa_playground.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {key: os.environ[key] for key in explicit} == explicit
