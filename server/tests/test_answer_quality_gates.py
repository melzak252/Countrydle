"""H10 key-free semantic/report regressions, not live-model accuracy tests.

The existing benchmark is the subject under test. Supplied plans deliberately
isolate evaluation/report behavior; they never certify provider interpretation.
The parent owns RED capture and all execution for this tests-first assignment.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import subprocess
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


TEST_DIR = Path(__file__).parent
CORPUS = json.loads((TEST_DIR / "answer_quality_corpus.json").read_text(encoding="utf-8"))
CASES = CORPUS["cases"]
LOCAL_CASES = [case for case in CASES if case["route"] == "local"]


@pytest.fixture
def benchmark():
    path = TEST_DIR.parent / "scripts" / "benchmark_country_planner.py"
    spec = importlib.util.spec_from_file_location("answer_quality_benchmark", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fact_snapshot(tmp_path):
    """Reuse the existing frozen snapshot, never the mutable application KB."""
    facts = json.loads((TEST_DIR / CORPUS["facts_fixture"]).read_text(encoding="utf-8"))
    database = tmp_path / "quality-facts.sqlite"
    with sqlite3.connect(database) as connection:
        for table in facts["tables"]:
            columns = ", ".join(f'"{name}" {datatype}' for name, datatype in table["columns"])
            connection.execute(f'CREATE TABLE "{table["name"]}" ({columns})')
            placeholders = ", ".join("?" for _ in table["columns"])
            connection.executemany(f'INSERT INTO "{table["name"]}" VALUES ({placeholders})', table["rows"])
    return database


@pytest.fixture
def country_executor(fact_snapshot, monkeypatch):
    from countrydle import local_answering

    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", fact_snapshot)
    return local_answering


def supplied_planner(executor, plan, *, valid=True, supported=True):
    """Fault injection at the interpretation boundary, not a provider replay."""
    return SimpleNamespace(
        local_answering=executor,
        analyze_question_for_local_plan=lambda question, **kwargs: SimpleNamespace(
            original_question=question, valid=valid, supported=supported,
            improved_question=question, explanation=None, fallback_reason=None, plan=plan,
        ),
    )


@pytest.mark.parametrize("case", LOCAL_CASES, ids=lambda case: case["id"])
def test_reviewed_gold_executes_complete_proposition_on_multiple_targets(case, country_executor):
    for target, expected in case["expected_answers"].items():
        result = country_executor.execute_local_plan(case["gold_plan"], target, case["question"])
        assert result is not None, (case["id"], target)
        assert result.answer is expected, (case["id"], target)


@pytest.mark.parametrize("case", LOCAL_CASES, ids=lambda case: case["id"])
def test_every_accepted_template_preserves_reviewed_answer(case, country_executor):
    from countrydle.template_compiler import compile_template_plan

    compiled = compile_template_plan(case["question"])
    if compiled is None:
        return  # Safe decline is permitted, and is not scored as a correct answer.
    for target, expected in case["expected_answers"].items():
        result = country_executor.execute_local_plan(compiled[0], target, case["question"])
        assert result is not None, (case["id"], target)
        assert result.answer is expected, (case["id"], target)


@pytest.mark.parametrize("case", [case for case in CASES if case["route"] != "local"], ids=lambda case: case["id"])
def test_templates_do_not_replace_temporal_unsupported_or_ambiguous_questions(case):
    from countrydle.template_compiler import compile_template_plan

    assert compile_template_plan(case["question"]) is None


def test_dropped_upper_bound_is_an_interpretation_failure_not_a_success(
    benchmark, country_executor, fact_snapshot,
):
    case = next(case for case in CASES if case["id"] == "dev-population-bounds")
    wrong_plan = case["gold_plan"]["conditions"][0]
    record = benchmark.run_one(
        supplied_planner(country_executor, wrong_plan), "offline-supplied-plan", case,
        1, fact_snapshot, list(case["expected_answers"]),
    )
    assert record["route_matches"] is True
    assert record["execution_ok"] is True
    assert record["semantic_correct"] is False
    assert {row["country"] for row in record["denotation_comparison"]["mismatches"]} == {"Poland", "Sweden"}


def test_shared_incorrect_fact_cannot_make_actual_and_gold_agreement_correct(
    benchmark, country_executor, fact_snapshot,
):
    case = next(case for case in CASES if case["id"] == "dev-europe-en")
    # Deliberate isolated corruption: both actual and gold plans now see the
    # same incorrect fact. Independent reviewed answers must catch this.
    with sqlite3.connect(fact_snapshot) as connection:
        connection.execute(
            "UPDATE country_continents SET continent = 'Asia' "
            "WHERE country_id = (SELECT id FROM countries WHERE app_country_name = 'Poland')"
        )
    record = benchmark.run_one(
        supplied_planner(country_executor, case["gold_plan"]), "offline-supplied-plan", case,
        1, fact_snapshot, list(case["expected_answers"]),
    )
    assert record["actual_denotation"]["Poland"] is False
    assert record["denotation_comparison"]["mismatch_count"] == 0
    assert record["semantic_correct"] is False


def test_fallback_routing_without_answer_generation_is_not_answer_success(
    benchmark, country_executor, fact_snapshot,
):
    case = next(case for case in CASES if case["id"] == "hold-nato-period-en")
    record = benchmark.run_one(
        supplied_planner(country_executor, None, supported=False), "offline-routing-only", case,
        1, fact_snapshot, list(case["expected_answers"]),
    )
    assert record["actual_route"] == "fallback"
    assert record["route_matches"] is True
    assert record["execution_ok"] is None
    assert record["semantic_correct"] is None


def test_false_answer_and_abstention_are_distinct(benchmark):
    comparison = benchmark._compare_denotations({"Poland": None}, {"Poland": False})
    assert comparison["mismatch_count"] == 1
    assert comparison["mismatches"] == [{"country": "Poland", "gold": False, "actual": None}]


def test_missing_target_result_is_not_a_correct_abstention(benchmark):
    comparison = benchmark._compare_denotations({}, {"Poland": None})
    assert comparison["mismatch_count"] == 1


def test_executor_exceptions_are_not_silently_successful_abstentions(
    benchmark, country_executor, fact_snapshot, monkeypatch,
):
    def failed_execution(*args, **kwargs):
        raise sqlite3.OperationalError("isolated unavailable fact table")

    monkeypatch.setattr(country_executor, "execute_local_plan", failed_execution)
    case = next(case for case in CASES if case["id"] == "dev-europe-en")
    record = benchmark.run_one(
        supplied_planner(country_executor, case["gold_plan"]), "offline-executor-failure", case,
        1, fact_snapshot, list(case["expected_answers"]),
    )
    assert record["execution_exceptions"] == 2
    assert record["execution_ok"] is False
    assert record["semantic_correct"] is False


@pytest.mark.parametrize("identity_change", [
    "model", "protocol_version", "mode_notes", "shared_rules",
    "generation_settings", "entity_bindings", "relation_bindings",
])
def test_generic_planner_cache_invalidates_semantic_identity_changes(
    identity_change, tmp_path, monkeypatch,
):
    import local_kb_question as generic

    database = tmp_path / "generic-facts.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT, population INTEGER, revised_population INTEGER)")
        connection.execute("INSERT INTO entities VALUES (1, 'Example', 5000000, 5000000)")
    config = generic.LocalModeConfig(
        mode_name="QualityFixture", entity_label="entity", target_entity="target_entity",
        db_path=database, table="entities", name_column="name",
        scalar_relations={"population": "population"}, list_relations={},
        supported_relations=["population"], language="English",
        mode_notes="Use the fixture cutoff of 1000000 people.",
    )
    entries = {}
    cache_module = ModuleType("utils.plan_cache")
    cache_module.plan_cache = SimpleNamespace(
        get=lambda mode, question, *, version: entries.get((mode, question, version)),
        set=lambda mode, question, plan, *, version: entries.__setitem__((mode, question, version), plan),
    )
    monkeypatch.setitem(sys.modules, "utils.plan_cache", cache_module)
    monkeypatch.setattr(generic, "load_dotenv", lambda: None)
    monkeypatch.setenv("LOCAL_QUESTION_MODEL", "offline-model-a")
    invocations = []

    def planned_response(prompt, **kwargs):
        invocations.append(prompt)
        cutoff = 1000000 if len(invocations) == 1 else 10000000
        return {"route": "local", "plan": [{
            "operator": "greater_than",
            "left": {"entity": config.target_entity, "relation": "population"},
            "right": {"value": cutoff},
        }]}

    monkeypatch.setattr(generic, "gemini_json", planned_response)
    question = "Does it satisfy the configured population cutoff?"
    first = generic.analyze_question(question, config)
    assert generic.execute_plan(config, "Example", first).answer is True
    # Prove an unchanged identity reuses the plan, without a provider boundary call.
    cached = generic.analyze_question(question, config)
    assert generic.execute_plan(config, "Example", cached).answer is True
    assert len(invocations) == 1

    if identity_change == "model":
        monkeypatch.setenv("LOCAL_QUESTION_MODEL", "offline-model-b")
    elif identity_change == "protocol_version":
        monkeypatch.setattr(generic, "PLANNER_VERSION", "offline-changed-contract")
    elif identity_change == "mode_notes":
        config = replace(config, mode_notes="Use the fixture cutoff of 10000000 people.")
    elif identity_change == "shared_rules":
        monkeypatch.setattr(generic, "PLANNER_RULES", generic.PLANNER_RULES + "\nUse the fixture cutoff of 10000000 people.")
    elif identity_change == "generation_settings":
        monkeypatch.setattr(generic, "PLANNER_MAX_OUTPUT_TOKENS", generic.PLANNER_MAX_OUTPUT_TOKENS + 64)
    elif identity_change == "entity_bindings":
        config = replace(config, target_entity="changed_target")
    else:
        config = replace(config, scalar_relations={"population": "revised_population"})

    changed = generic.analyze_question(question, config)
    assert generic.execute_plan(config, "Example", changed).answer is False
    assert len(invocations) == 2


def test_unreviewed_null_and_failed_generation_are_not_correct_abstentions(benchmark):
    case = next(case for case in CASES if case["id"] == "hold-flag-measurement")
    rows = benchmark.assess_targets(case, {"Poland": None, "Japan": None}, executed=True, route="fallback")
    outcomes = {row["target"]: row["outcome"] for row in rows}
    assert outcomes == {"Poland": "avoidable_abstention", "Japan": "needs_adjudication"}
    failed = benchmark.assess_targets(case, {}, executed=True, route="fallback", provider_error="provider unavailable")
    assert all(row["outcome"] == "provider_error" for row in failed)


def test_causal_evidence_must_match_observed_answer_artifact(benchmark):
    case = dict(next(case for case in CASES if case["id"] == "dev-europe-en"))
    case["causal_reviews"] = {"Poland": {
        "reviewed": True, "observed_artifact_sha256": "old-interpretation",
        "causes": ["incorrect_fact"], "grounding": "supported", "evidence": ["reviewed source"],
    }}
    rows = benchmark.assess_targets(
        case, {"Poland": False, "Japan": False}, executed=True, route="local",
        artifacts={"Poland": "new-interpretation"},
    )
    poland = next(row for row in rows if row["target"] == "Poland")
    assert poland["outcome"] == "wrong_answer"
    assert poland["causal_evidence"] == []
    assert poland["grounding"] == "unassessed"


def test_offline_cli_evaluates_reviewed_answers_without_network_or_fact_writes(fact_snapshot, tmp_path):
    script = TEST_DIR.parent / "scripts" / "benchmark_country_planner.py"
    output = tmp_path / "offline-quality.json"
    original = fact_snapshot.read_bytes()
    bootstrap = """
import os, runpy, socket, sys
def forbidden_network(*args, **kwargs):
    os._exit(87)
socket.socket.connect = forbidden_network
sys.argv.pop(0)
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    environment = {
        **os.environ, "PYTHON_DOTENV_DISABLED": "1", "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "", "QDRANT_HOST": "127.0.0.1", "QDRANT_PORT": "1",
    }
    result = subprocess.run(
        [sys.executable, "-c", bootstrap, str(script), "--offline", "--variant", "current",
         "--corpus", str(TEST_DIR / "answer_quality_corpus.json"), "--database", str(fact_snapshot),
         "--output", str(output)],
        env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 3, result.stderr
    report = json.loads(output.read_text())
    local = next(row for row in report["records"] if row["case_id"] == "dev-europe-en"
                 and row["path"] == "model_planned_local")
    assert local["actual_denotation"] == {"Poland": True, "Japan": False}
    assert {row["outcome"] for row in local["target_assessments"]} == {"correct_answer"}
    assert report["release_status"] == "insufficient"
    assert fact_snapshot.read_bytes() == original
