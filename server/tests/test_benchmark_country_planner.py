from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "server" / "scripts" / "benchmark_country_planner.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("benchmark_country_planner_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shape_module():
    return SimpleNamespace(
        SUPPORTED_RELATIONS={"name", "official_languages", "borders_country"},
        PLANNER_OPERATORS={"equals", "contains"},
        local_answering=SimpleNamespace(
            LIST_RELATION_QUERIES={"official_languages", "borders_country"},
            find_country=lambda conn, name: None,
        ),
    )


@pytest.mark.parametrize("hardlink", [False, True])
def test_output_collision_preserves_database_and_stops_cli_before_provider(tmp_path, hardlink):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps({
            "description": "collision regression",
            "cases": [{
                "id": "clarify-only", "split": "development", "category": "clarify",
                "question": "Unclear question", "route": "clarify", "gold_plan": None,
                "required_atoms": [], "notes": "",
            }],
        }),
        encoding="utf-8",
    )
    database = tmp_path / "facts.sqlite"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE countries (app_country_name TEXT)")
        conn.execute("INSERT INTO countries VALUES ('Exampleland')")
    original = database.read_bytes()
    output = tmp_path / "report.json" if hardlink else database
    if hardlink:
        os.link(database, output)
    env = os.environ.copy()
    # Keep dotenv from restoring live credentials if the collision guard regresses.
    env["GEMINI_API_KEY"] = ""
    env["OPENAI_API_KEY"] = "benchmark-disabled"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(corpus),
            "--database",
            str(database),
            "--output",
            str(output),
            "--variant",
            "current",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 2
    assert database.read_bytes() == original


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
@pytest.mark.parametrize("alias", ["direct", "hardlink", "symlink"])
def test_output_collision_preserves_sqlite_sidecars(tmp_path, monkeypatch, suffix, alias):
    database = tmp_path / "facts.sqlite"
    with sqlite3.connect(database) as conn:
        if suffix != "-journal":
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE countries (app_country_name TEXT)")
        conn.execute("INSERT INTO countries VALUES ('Exampleland')")
        conn.commit()
        if suffix == "-journal":
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO countries VALUES ('Uncommitted')")
        sidecar = Path(f"{database}{suffix}")
        original = sidecar.read_bytes()
        output = sidecar
        if alias == "hardlink":
            output = tmp_path / "report.json"
            os.link(sidecar, output)
        elif alias == "symlink":
            output = tmp_path / "report.json"
            output.symlink_to(sidecar)
        harness = _load_harness()

        def forbid_environment_setup(*args):
            pytest.fail("A destructive output path reached provider environment setup")

        monkeypatch.setattr(harness, "prepare_environment", forbid_environment_setup)
        with pytest.raises(SystemExit) as rejected:
            harness.main(["--database", str(database), "--output", str(output)])
        assert rejected.value.code == 2
        assert sidecar.read_bytes() == original


def test_gold_item_operand_requires_its_quantifier_scope():
    harness = _load_harness()
    module = _shape_module()
    free_item = {
        "operator": "equals",
        "left": {"entity": "item", "relation": "name"},
        "right": {"value": "English"},
    }
    predicate_without_bound_item = {
        "operator": "any",
        "items": {"entity": "target_country", "relation": "official_languages"},
        "condition": {
            "operator": "equals",
            "left": {"entity": "target_country", "relation": "name"},
            "right": {"value": "Germany"},
        },
    }

    free_item_errors = harness._check_plan_shape(free_item, module, None)
    predicate_errors = harness._check_plan_shape(predicate_without_bound_item, module, None)

    assert any(issue.get("code") == "unbound_item" for issue in free_item_errors)
    assert any(issue.get("code") == "missing_bound_item" for issue in predicate_errors)


def test_nested_quantifier_item_uses_the_nearest_binding():
    harness = _load_harness()
    nested = {
        "operator": "any",
        "items": {"entity": "target_country", "relation": "borders_country"},
        "condition": {
            "operator": "any",
            "items": {"entity": "item", "relation": "official_languages"},
            "condition": {
                "operator": "equals",
                "left": {"entity": "item", "relation": "name"},
                "right": {"value": "English"},
            },
        },
    }

    assert harness._check_plan_shape(nested, _shape_module(), None) == []


def _approved_pricing():
    return {"approved": True, "currency": "USD", "as_of": "2026-10-06", "models": {
        "priced-model": {"input_usd_per_million": 0.1, "cached_input_usd_per_million": 0.01,
                         "output_usd_per_million": 0.4, "max_input_tokens": 8192},
    }}


def _bounded_request():
    return {"contents": [{"parts": [{"text": "A short fixture question"}]}],
            "generationConfig": {"maxOutputTokens": 2048, "thinkingConfig": {"thinkingBudget": 1024}}}


def test_live_budget_includes_repeats_and_stops_before_next_call():
    harness = _load_harness()
    budget = harness.LiveBudget(_approved_pricing(), 2, 1.0)
    budget.reserve("priced-model", _bounded_request())
    budget.reserve("priced-model", _bounded_request())
    with pytest.raises(RuntimeError, match="exhausted before"):
        budget.reserve("priced-model", _bounded_request())
    assert budget.reserved_cost_usd == pytest.approx(2 * (8192 * 0.1 + 3072 * 0.4) / 1_000_000)


def test_live_budget_reserves_full_uncached_ceiling_before_cost_cap():
    harness = _load_harness()
    budget = harness.LiveBudget(_approved_pricing(), 100, 0.001)
    with pytest.raises(RuntimeError, match="exhausted before"):
        budget.reserve("priced-model", _bounded_request())
    assert budget.reserved_cost_usd == 0


@pytest.mark.parametrize("mutation", ["unknown_model", "unbounded_thinking", "oversized_input"])
def test_live_budget_rejects_unknown_cost_or_token_bounds(mutation):
    harness = _load_harness()
    budget = harness.LiveBudget(_approved_pricing(), 100, 1.0)
    body = _bounded_request()
    model = "priced-model"
    if mutation == "unknown_model":
        model = "unpriced-model"
    elif mutation == "unbounded_thinking":
        body["generationConfig"]["thinkingConfig"]["thinkingBudget"] = -1
    else:
        body["contents"][0]["parts"][0]["text"] = "ą" * 8192
    with pytest.raises(ValueError):
        budget.reserve(model, body)
    assert budget.reserved_cost_usd == 0


def test_multistage_cost_does_not_hide_unknown_fallback_usage():
    harness = _load_harness()
    pricing = _approved_pricing()
    usage = {"input_tokens": 1000, "cached_input_tokens": 200, "output_tokens": 50, "thought_tokens": 100}
    planner = harness.finalize_stage({
        "model": "priced-model", "reservations": [{}], "attempts": [{"usage": usage}],
    }, pricing)
    fallback = harness.finalize_stage({
        "model": "priced-model", "reservations": [{}], "attempts": [{"failed": True, "usage": {}}],
    }, pricing)
    summary = harness._summary([{"stages": [planner, fallback]}])
    assert planner["actual_cost_usd"] == pytest.approx((800 * 0.1 + 200 * 0.01 + 150 * 0.4) / 1_000_000)
    assert summary["provider_calls"] == 2
    assert summary["fully_observed_provider_cost_usd"] is None
    assert summary["uncached_input_cost_upper_bound_usd"] is None


def test_perfect_supplied_answers_and_unexecuted_fallback_cannot_approve_release():
    harness = _load_harness()
    corpus = json.loads((SCRIPT.parent.parent / "tests" / "answer_quality_corpus.json").read_text())
    local_case = next(case for case in corpus["cases"] if case["route"] == "local")
    fallback_case = next(case for case in corpus["cases"] if case["route"] == "fallback")
    rows = [
        {"path": "model_planned_local", "interpretation_path": "model_planned_local", "case_id": local_case["id"],
         "split": "held_out", "language": "en", "repeat": 1, "route_matches": True,
         "evidence_origin": "offline_supplied_gold_not_provider_accuracy",
         "target_assessments": harness.assess_targets(local_case, local_case["expected_answers"], executed=True, route="local")},
        {"path": "fallback", "interpretation_path": "model_planned_local", "case_id": fallback_case["id"],
         "split": "held_out", "language": "en", "repeat": 1, "route_matches": True,
         "target_assessments": harness.assess_targets(fallback_case, {}, executed=False, route="fallback")},
    ]
    offline = harness.path_quality(rows, corpus, live=False)
    assert offline["model_planned_local"]["release_status"] == "insufficient"
    assert offline["fallback"]["release_status"] == "insufficient"
    assert offline["fallback"]["correct_answer_rate"] is None
    live_claim = harness.path_quality(rows, corpus, live=True)["model_planned_local"]
    assert live_claim["release_status"] == "insufficient"
    assert "supplied_or_unverified_outputs_are_not_live_accuracy" in live_claim["insufficiency_reasons"]


def test_live_gateway_rejects_cost_cap_before_http_client_is_called(monkeypatch):
    from types import ModuleType

    harness = _load_harness()
    package = ModuleType("utils")
    provider = ModuleType("utils.ai_clients")
    calls = []

    def forbidden_http(*args, **kwargs):
        calls.append("unexpected paid call")
        raise AssertionError("Budget must be reserved before sending HTTP")

    def unused_generator(*args, **kwargs):
        raise AssertionError("This regression exercises the HTTP budget boundary directly")

    provider.get_http_client = lambda: SimpleNamespace(post=forbidden_http)
    provider.generate_gemini_json = unused_generator
    package.ai_clients = provider
    monkeypatch.setitem(sys.modules, "utils", package)
    monkeypatch.setitem(sys.modules, "utils.ai_clients", provider)
    harness._live_budget = harness.LiveBudget(_approved_pricing(), 100, 0.001)
    harness.install_provider_capture()
    with pytest.raises(RuntimeError, match="exhausted before"):
        provider.get_http_client().post(
            "https://generativelanguage.googleapis.com/v1beta/models/priced-model:generateContent",
            json=_bounded_request(),
        )
    assert calls == []
