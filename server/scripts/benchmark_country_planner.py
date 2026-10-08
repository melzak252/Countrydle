#!/usr/bin/env python3
"""Opt-in live comparison harness for Countrydle local planner prompts.

Gemini Flash-Lite cost estimates use fixed USD rates: $0.10 / 1M uncached
input tokens, $0.01 / 1M cached input tokens, and $0.40 / 1M output tokens.
Provider-reported thought tokens are priced as output tokens and added to
candidatesTokenCount. Rates are intentionally fixed for reproducibility;
update them explicitly when pricing changes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sqlite3
import statistics
import sys
import tempfile
import time
import threading
import types
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata
from pathlib import Path
from typing import Any


@contextmanager
def private_database_snapshot(source: Path):
    """Yield a chmod-read-only private SQLite backup and the source-file checksum."""
    source = source.resolve()
    digest = hashlib.sha256()
    with source.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    handle = tempfile.NamedTemporaryFile(prefix="country-planner-", suffix=".sqlite", delete=False)
    snapshot = Path(handle.name)
    handle.close()
    source_conn = None
    snapshot_conn = None
    try:
        source_conn = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        snapshot_conn = sqlite3.connect(snapshot)
        source_conn.backup(snapshot_conn)
        snapshot_conn.close()
        snapshot_conn = None
        source_conn.close()
        source_conn = None
        snapshot.chmod(0o444)
        yield snapshot, digest.hexdigest()
    finally:
        if snapshot_conn is not None:
            snapshot_conn.close()
        if source_conn is not None:
            source_conn.close()
        if snapshot.exists():
            snapshot.chmod(0o600)
            snapshot.unlink()


def validate_output_path(output: Path, protected_paths: list[Path]) -> None:
    resolved_output = output.expanduser().resolve()
    output_exists = resolved_output.exists()
    collisions = []
    for path in protected_paths:
        protected = path.expanduser().resolve()
        if resolved_output == protected or (
            output_exists and protected.exists() and resolved_output.samefile(protected)
        ):
            collisions.append(str(path))
    if collisions:
        raise ValueError(f"Output path collides with protected input: {', '.join(collisions)}")


def connect_readonly(path: Path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT_DIR / "server"
DEFAULT_CORPUS = SERVER_DIR / "tests" / "country_planner_benchmark.json"
DEFAULT_DB = SERVER_DIR / "data" / "country_facts.sqlite"
INPUT_RATE = 0.10
CACHED_INPUT_RATE = 0.01
OUTPUT_RATE = 0.40
RATE_UNIT = 1_000_000


def prepare_environment(env_file: Path | None) -> None:
    if env_file is not None:
        if not env_file.is_file():
            raise FileNotFoundError(f"Environment file does not exist: {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
    # Prevent application imports from silently loading repo-local credentials.
    os.environ.setdefault("GEMINI_API_KEY", "")
    # Force safe application configuration after credentials have been loaded.
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    for key, value in {
        "EMAIL_USERNAME": "benchmark@example.com", "NOREPLY_EMAIL": "benchmark@example.com",
        "EMAIL_PASSWORD": "benchmark-only-password", "SECRET_KEY": "benchmark-only-secret-key-1234567890",
        "ALGORITHM": "HS256",
    }.items():
        os.environ[key] = value
    if str(SERVER_DIR) not in sys.path:
        sys.path.insert(0, str(SERVER_DIR))


def isolate_plan_cache() -> None:
    """Prevent the planner's lazy cache import from initializing app storage."""
    class DisabledPlanCache:
        def get(self, *args, **kwargs):
            raise AssertionError("Planner cache access is forbidden; use_cache=False is required")

        def set(self, *args, **kwargs):
            raise AssertionError("Planner cache writes are forbidden; use_cache=False is required")

    cache_module = types.ModuleType("utils.plan_cache")
    cache_module.plan_cache = DisabledPlanCache()
    sys.modules["utils.plan_cache"] = cache_module


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load planner module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_corpus(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(corpus, dict) or not isinstance(corpus.get("description"), str) or not isinstance(corpus.get("cases"), list):
        raise ValueError("Corpus must be an object with a string description and cases array")
    seen: set[str] = set()
    for index, case in enumerate(corpus["cases"]):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] must be an object")
        required = {"id", "split", "category", "question", "route", "gold_plan", "required_atoms", "notes"}
        missing = required - case.keys()
        if missing:
            raise ValueError(f"cases[{index}] missing fields: {', '.join(sorted(missing))}")
        if not isinstance(case["id"], str) or not case["id"] or case["id"] in seen:
            raise ValueError(f"cases[{index}] has an empty or duplicate id")
        seen.add(case["id"])
        if not all(isinstance(case[field], str) for field in ("category", "question", "notes")):
            raise ValueError(f"Case {case['id']}: category, question, and notes must be strings")
        if case["split"] not in {"development", "held_out"}:
            raise ValueError(f"Case {case['id']}: invalid split")
        if case["route"] not in {"local", "fallback", "clarify"}:
            raise ValueError(f"Case {case['id']}: invalid route")
        if (case["route"] == "local") != (case["gold_plan"] is not None):
            raise ValueError(f"Case {case['id']}: local requires gold_plan and other routes require null")
        if case["route"] == "local" and not isinstance(case["gold_plan"], dict):
            raise ValueError(f"Case {case['id']}: gold_plan must be an executor AST object")
        if not isinstance(case["required_atoms"], list):
            raise ValueError(f"Case {case['id']}: required_atoms must be a list")
        for atom in case["required_atoms"]:
            if not isinstance(atom, dict) or not isinstance(atom.get("operator"), str) or not isinstance(atom.get("relation"), str):
                raise ValueError(f"Case {case['id']}: each required atom needs operator and relation")
            if "value" in atom and not (atom["value"] is None or type(atom["value"]) in (bool, int, float, str)):
                raise ValueError(f"Case {case['id']}: required atom value must be a scalar")
    return corpus, corpus["cases"]


def _node_atoms(node: Any, negated: bool = False):
    if isinstance(node, list):
        for child in node:
            yield from _node_atoms(child, negated)
        return
    if not isinstance(node, dict):
        return
    operator = node.get("operator")
    if not isinstance(operator, str):
        return
    if operator == "not":
        children = list(_node_atoms(node.get("condition"), not negated))
        for child in children:
            yield {"operator": "not", "relation": child["relation"]}
            yield child
        return
    children = []
    for key in ("conditions", "condition"):
        if key in node:
            children.extend(_node_atoms(node[key], negated))
    if operator in {"and", "or"}:
        for relation in sorted({atom["relation"] for atom in children}):
            yield {"operator": operator, "relation": relation}
        yield from children
        return
    if operator in {"any", "all"}:
        items = node.get("items")
        if isinstance(items, dict) and isinstance(items.get("relation"), str):
            yield {"operator": operator, "relation": items["relation"]}
        yield from children
        return
    left = node.get("left")
    for operand in (left, node.get("right")):
        if isinstance(operand, dict) and isinstance(operand.get("relation"), str):
            atom = {"operator": operator, "relation": operand["relation"]}
            right = node.get("right")
            if isinstance(right, dict) and "value" in right:
                atom["value"] = right["value"]
            if negated:
                atom["operator"] = {
                    "less_than": "greater_than_or_equal",
                    "greater_than": "less_than_or_equal",
                    "less_than_or_equal": "greater_than",
                    "greater_than_or_equal": "less_than",
                }.get(operator, operator)
            yield atom
    for key in ("left", "right", "items"):
        child = node.get(key)
        if isinstance(child, list) or (isinstance(child, dict) and isinstance(child.get("operator"), str)):
            yield from _node_atoms(child, negated)


def _normalized_atom(atom: dict[str, Any], module, conn) -> tuple:
    relation = atom.get("relation")
    value = atom.get("value")
    if isinstance(value, str):
        value = " ".join(unicodedata.normalize("NFKD", value).casefold().split())
        value = "".join(char for char in value if not unicodedata.combining(char))
        aliases = {
            "currency": {"euro": "eur", "€": "eur"},
            "membership": {"european union": "eu"},
            "flag_symbol": {"stars": "star"},
        }.get(relation, {})
        value = aliases.get(value, value)
        if relation in {"name", "borders_country"}:
            country = module.local_answering.find_country(conn, atom["value"])
            if country is not None:
                value = " ".join(country["app_country_name"].casefold().split())
    return (atom.get("operator"), relation, value if "value" in atom else None, "value" in atom)


def atoms_missing(plan: Any, required: list[dict[str, Any]], module, conn) -> list[dict[str, Any]]:
    actual = [_normalized_atom(atom, module, conn) for atom in _node_atoms(plan)]
    missing = []
    for wanted in required:
        if _normalized_atom(wanted, module, conn) not in actual:
            missing.append(wanted)
    return missing


def _check_plan_shape(plan: Any, module, conn, path: str = "gold_plan") -> list[dict[str, str]]:
    """Validate gold AST shape; scope errors use ``unbound_item``/``missing_bound_item`` codes."""
    errors: list[dict[str, str]] = []
    relations = set(module.SUPPORTED_RELATIONS) | {"region", "subregion", "coordinates.latitude", "coordinates.longitude"}
    operators = set(module.PLANNER_OPERATORS) | {"any", "all"}
    unary = {"exists", "has_space", "has_hyphen"}
    logical = {"and", "or"}
    next_binding = 0

    def operand(value, at, bindings):
        if not isinstance(value, dict):
            errors.append({"path": at, "error": "operand must be an object"})
            return set()
        if set(value) == {"value"}:
            if value["value"] is not None and type(value["value"]) not in (bool, int, float, str):
                errors.append({"path": at, "error": "literal must be scalar"})
            return set()
        if set(value) != {"entity", "relation"}:
            errors.append({"path": at, "error": "operand must contain exactly value or entity/relation"})
            return set()
        entity = value["entity"]
        used_bindings = set()
        if not isinstance(entity, str):
            errors.append({"path": at, "error": "entity must be a string"})
        elif entity == "item":
            if not bindings:
                errors.append({"path": at, "code": "unbound_item", "error": "item operand is outside a quantifier binding"})
            else:
                used_bindings.add(bindings[-1])
        elif entity not in {"target_country", "TARGET"}:
            if entity.startswith("target_") or module.local_answering.find_country(conn, entity) is None:
                errors.append({"path": at, "error": f"unsupported or unresolved named-country entity {entity!r}"})
        if not isinstance(value["relation"], str) or value["relation"] not in relations:
            errors.append({"path": at, "error": f"unsupported relation {value['relation']!r}"})
        return used_bindings

    def visit(node, at, bindings=()):
        nonlocal next_binding
        if not isinstance(node, dict) or not isinstance(node.get("operator"), str):
            errors.append({"path": at, "error": "node must be an object with operator"})
            return set()
        op = node["operator"]
        if op not in operators:
            errors.append({"path": at, "error": f"unsupported operator {op!r}"})
            return set()
        expected_fields = (
            {"operator", "left"} if op in unary else
            {"operator", "conditions"} if op in logical else
            {"operator", "condition"} if op == "not" else
            {"operator", "items", "condition"} if op in {"any", "all"} else
            {"operator", "left", "right"}
        )
        if set(node) != expected_fields:
            errors.append({"path": at, "error": f"{op} node fields must be {sorted(expected_fields)}"})
        if op in unary:
            return operand(node.get("left"), at + ".left", bindings)
        if op in logical:
            conditions = node.get("conditions")
            if not isinstance(conditions, list) or not conditions:
                errors.append({"path": at + ".conditions", "error": f"{op} requires one or more conditions"})
                return set()
            used = set()
            for index, child in enumerate(conditions):
                used.update(visit(child, f"{at}.conditions[{index}]", bindings))
            return used
        if op == "not":
            return visit(node.get("condition"), at + ".condition", bindings)
        if op in {"any", "all"}:
            items = node.get("items")
            used = operand(items, at + ".items", bindings)
            if isinstance(items, dict) and items.get("relation") not in module.local_answering.LIST_RELATION_QUERIES:
                errors.append({"path": at + ".items", "error": "quantifier items must reference a list-valued relation"})
            binding = next_binding
            next_binding += 1
            condition_used = visit(node.get("condition"), at + ".condition", (*bindings, binding))
            if binding not in condition_used:
                errors.append({"path": at + ".condition", "code": "missing_bound_item", "error": "quantified predicate must reference its bound item"})
            used.update(condition_used - {binding})
            return used

        left = node.get("left")
        right = node.get("right")
        used = operand(left, at + ".left", bindings)
        used.update(operand(right, at + ".right", bindings))
        relation = left.get("relation") if isinstance(left, dict) else None
        list_relations = set(module.local_answering.LIST_RELATION_QUERIES)
        right_value = right.get("value") if isinstance(right, dict) and set(right) == {"value"} else None
        numeric_count = (
            op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}
            and (type(right_value) in (int, float) or isinstance(right_value, str) and right_value.isdigit())
        )
        currency_alias_match = op == "equals" and relation == "currency" and isinstance(right_value, str)
        if op == "contains" and relation not in list_relations:
            errors.append({"path": at + ".left", "error": f"contains requires list-valued relation, got {relation!r}"})
        elif relation in list_relations and op != "contains" and not numeric_count and not currency_alias_match:
            errors.append({"path": at, "error": f"{op} cannot compare list-valued relation {relation!r} as a scalar"})
        return used

    visit(plan, path)
    return errors


def _country_reference_literals(plan: Any):
    if isinstance(plan, list):
        for child in plan:
            yield from _country_reference_literals(child)
    elif isinstance(plan, dict):
        op = plan.get("operator")
        left, right = plan.get("left"), plan.get("right")
        if op == "equals" and isinstance(left, dict) and left.get("relation") == "name" and isinstance(right, dict) and "value" in right:
            yield right["value"]
        if op == "equals" and isinstance(right, dict) and right.get("relation") == "name" and isinstance(left, dict) and "value" in left:
            yield left["value"]
        for operand, literal in ((left, right), (right, left)):
            if isinstance(operand, dict) and operand.get("relation") == "borders_country" and isinstance(literal, dict) and "value" in literal:
                yield literal["value"]
        for child in plan.values():
            yield from _country_reference_literals(child)


def validate_gold(cases: list[dict[str, Any]], module, db_path: Path) -> dict[str, Any]:
    errors = []
    guard_reviews = []
    module.local_answering.DEFAULT_DB_PATH = db_path
    relations = set(module.SUPPORTED_RELATIONS) | {"region", "subregion", "coordinates.latitude", "coordinates.longitude"}
    operators = set(module.PLANNER_OPERATORS) | {"any", "all", "not"}
    with connect_readonly(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for case in cases:
            if case["route"] != "local":
                continue
            plan = case["gold_plan"]
            shape_errors = _check_plan_shape(plan, module, conn)
            errors.extend({"id": case["id"], **problem} for problem in shape_errors)
            for atom in case["required_atoms"]:
                if atom["operator"] not in operators or atom["relation"] not in relations:
                    errors.append({"id": case["id"], "path": "required_atoms", "error": f"impossible guard atom {atom!r}"})
            try:
                for name in _country_reference_literals(plan):
                    if not isinstance(name, str) or module.local_answering.find_country(conn, name) is None:
                        errors.append({"id": case["id"], "path": "gold_plan", "error": f"unresolved country reference {name!r}"})
            except Exception as exc:
                errors.append({"id": case["id"], "path": "gold_plan", "error": f"country literal inspection failed: {type(exc).__name__}"})
            if not shape_errors:
                missing = atoms_missing(plan, case["required_atoms"], module, conn)
                if missing:
                    guard_reviews.append({"id": case["id"], "status": "needs_adjudication", "unmatched_required_atoms": missing})
    return {"valid": not errors, "case_count": len(cases), "errors": errors, "required_atom_guard_reviews": guard_reviews}


def get_countries(db_path: Path) -> list[str]:
    with connect_readonly(db_path) as conn:
        return [row[0] for row in conn.execute("SELECT app_country_name FROM countries ORDER BY app_country_name")]


def _safe_exception(exc: BaseException) -> str:
    # Avoid leaking request headers or credential-bearing URLs in provider exceptions.
    text = f"{type(exc).__name__}: {exc}"
    for secret in (os.getenv("GEMINI_API_KEY"), os.getenv("OPENAI_API_KEY")):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:1200]


def _denotation(module, plan: Any, countries: list[str], question: str) -> tuple[dict[str, bool | None], int]:
    answers: dict[str, bool | None] = {}
    failures = 0
    if not isinstance(plan, (dict, list)):
        return answers, failures
    for country in countries:
        try:
            result = module.local_answering.execute_local_plan(plan, country, question)
            answers[country] = result.answer if result is not None else None
        except Exception:
            failures += 1
            answers[country] = None
    return answers, failures


def _compare_denotations(actual: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for country in gold:
        if actual.get(country) != gold[country]:
            mismatches.append({"country": country, "gold": gold[country], "actual": actual.get(country)})
    return {"compared_entities": len(gold), "mismatch_count": len(mismatches), "mismatches": mismatches}


def _cost(usage: dict[str, Any] | None) -> float | None:
    if not usage:
        return None
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    thoughts = usage.get("thought_tokens")
    if type(inp) is not int or type(out) is not int or type(thoughts) is not int:
        return None
    cached = usage.get("cached_input_tokens")
    if type(cached) is not int or cached < 0 or cached > inp:
        return None
    return ((inp - cached) * INPUT_RATE + cached * CACHED_INPUT_RATE + (out + thoughts) * OUTPUT_RATE) / RATE_UNIT

def _cost_uncached_upper_bound(usage: dict[str, Any] | None) -> float | None:
    if not usage:
        return None
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    thoughts = usage.get("thought_tokens")
    if type(inp) is not int or type(out) is not int or type(thoughts) is not int:
        return None
    return (inp * INPUT_RATE + (out + thoughts) * OUTPUT_RATE) / RATE_UNIT


def _percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


_provider_patch_lock = threading.Lock()
_provider_original = None
_provider_original_http_getter = None
_provider_evidence_local = threading.local()


def install_provider_capture() -> None:
    """Capture parsed output and visible candidate text without retaining thoughts or credentials."""
    global _provider_original, _provider_original_http_getter
    from utils import ai_clients
    with _provider_patch_lock:
        if _provider_original is not None:
            return
        _provider_original = ai_clients.generate_gemini_json
        _provider_original_http_getter = ai_clients.get_http_client

        class CapturedResponse:
            def __init__(self, response):
                self._response = response

            def __getattr__(self, name):
                return getattr(self._response, name)

            def json(self, *args, **kwargs):
                data = self._response.json(*args, **kwargs)
                evidence = getattr(_provider_evidence_local, "evidence", None)
                if isinstance(evidence, dict) and isinstance(data, dict):
                    candidates = data.get("candidates") or []
                    if candidates:
                        candidate = candidates[0]
                        parts = candidate.get("content", {}).get("parts", [])
                        evidence["raw_output_text"] = "".join(
                            part["text"] for part in parts
                            if isinstance(part.get("text"), str) and not part.get("thought")
                        )
                        evidence["raw_finish_reason"] = candidate.get("finishReason")
                return data

        class CapturedHttpClient:
            def post(self, *args, **kwargs):
                response = _provider_original_http_getter().post(*args, **kwargs)
                return CapturedResponse(response)

        client = CapturedHttpClient()
        ai_clients.get_http_client = lambda: client

        def capture(*args, **kwargs):
            evidence = kwargs.get("evidence")
            if isinstance(evidence, dict):
                evidence["provider_call_attempted"] = True
            _provider_evidence_local.evidence = evidence
            try:
                parsed = _provider_original(*args, **kwargs)
                if isinstance(evidence, dict):
                    evidence["raw_output"] = parsed
                return parsed
            finally:
                _provider_evidence_local.evidence = None

        ai_clients.generate_gemini_json = capture


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    good_usage = [row["usage"] for row in records if isinstance(row.get("usage"), dict)]
    costs = [row["actual_cost_usd"] for row in records if row.get("actual_cost_usd") is not None]
    upper_bounds = [row["uncached_input_cost_upper_bound_usd"] for row in records if row.get("uncached_input_cost_upper_bound_usd") is not None]
    provider_calls = sum(row.get("provider_call") is True for row in records)
    full_coverage = len(costs) == provider_calls
    bound_coverage = len(upper_bounds) == provider_calls
    def token_stats(key: str):
        values = [u[key] for u in good_usage if type(u.get(key)) is int]
        return {"observed_count": len(values), "mean": _mean(values), "p95": _percentile95(values), "sum": sum(values) if values else None}
    attempted = len(records)
    resolved = sum(row.get("actual_route") == "local" and row.get("execution_ok") is True for row in records)
    total_cost = sum(costs) if full_coverage else None
    total_upper_bound = sum(upper_bounds) if bound_coverage else None
    return {
        "attempted": attempted, "resolved": resolved,
        "provider_calls": provider_calls,
        "route_mismatches": sum(row.get("route_matches") is False for row in records),
        "plan_latency_ms": {"mean": _mean([r["plan_ms"] for r in records if r.get("plan_ms") is not None]), "p95": _percentile95([r["plan_ms"] for r in records if r.get("plan_ms") is not None])},
        "execution_latency_ms": {"mean": _mean([r["execution_ms"] for r in records if r.get("execution_ms") is not None]), "p95": _percentile95([r["execution_ms"] for r in records if r.get("execution_ms") is not None])},
        "tokens": {key: token_stats(key) for key in ("input_tokens", "cached_input_tokens", "output_tokens", "thought_tokens")},
        "fully_observed_provider_cost_usd": total_cost,
        "fully_observed_cost_calls": len(costs),
        "cost_per_1000_attempted_usd": total_cost * 1000 / attempted if total_cost is not None and attempted else None,
        "cost_per_1000_resolved_usd": total_cost * 1000 / resolved if total_cost is not None and resolved else None,
        "uncached_input_cost_upper_bound_usd": total_upper_bound,
        "upper_bound_cost_calls": len(upper_bounds),
        "uncached_upper_bound_per_1000_attempted_usd": total_upper_bound * 1000 / attempted if total_upper_bound is not None and attempted else None,
        "uncached_upper_bound_per_1000_resolved_usd": total_upper_bound * 1000 / resolved if total_upper_bound is not None and resolved else None,
        "cost_coverage": {"provider_calls": provider_calls, "fully_observed": len(costs), "uncached_upper_bound": len(upper_bounds)},
        "malformed_or_route_errors": sum(bool(r.get("route_error")) for r in records),
        "execution_failures": sum(row.get("execution_ok") is False for row in records),
        "semantic_failures": sum(row.get("semantic_correct") is False for row in records),
        "semantic_needs_adjudication": sum(row.get("semantic_status") == "needs_adjudication" for row in records),
        "provider_cache_observed": {str(value).lower(): sum(r.get("provider_cache_observed") is value for r in records if r.get("provider_cache_observed") is not None) for value in (True, False)},
        "planner_cache_hits": sum(r.get("cache_hit") is True for r in records),
    }


def run_one(module, variant: str, case: dict[str, Any], repeat: int, db_path: Path, countries: list[str]) -> dict[str, Any]:
    # The executor points only at the copied facts DB selected by the harness.
    module.local_answering.DEFAULT_DB_PATH = db_path
    evidence: dict[str, Any] = {}
    record: dict[str, Any] = {"variant": variant, "case_id": case["id"], "split": case["split"], "category": case["category"], "question": case["question"], "repeat": repeat, "provider_call": False, "usage": None, "actual_cost_usd": None}
    started = time.perf_counter()
    plan_result = None
    try:
        plan_result = module.analyze_question_for_local_plan(case["question"], use_cache=False, strict_errors=True, evidence=evidence)
        record["plan_ms"] = (time.perf_counter() - started) * 1000
        record.update({"valid": getattr(plan_result, "valid", None), "supported": getattr(plan_result, "supported", None), "actual_route": "local" if getattr(plan_result, "supported", False) else ("clarify" if not getattr(plan_result, "valid", True) else "fallback"), "improved_question": getattr(plan_result, "improved_question", None), "explanation": getattr(plan_result, "explanation", None), "fallback_reason": getattr(plan_result, "fallback_reason", None), "compiled_plan": getattr(plan_result, "plan", None)})
    except Exception as exc:
        record["plan_ms"] = (time.perf_counter() - started) * 1000
        record["route_error"] = _safe_exception(exc)
        record["actual_route"] = "error"
        record["compiled_plan"] = None
    record["provider"] = evidence.get("provider")
    record["model"] = evidence.get("model")
    record["contract_version"] = evidence.get("contract_version")
    record["cache_hit"] = evidence.get("cache_hit")
    record["provider_call"] = evidence.get("provider_call_attempted") is True
    record["provider_response_id"] = evidence.get("response_id")
    record["provider_model_version"] = evidence.get("model_version")
    record["usage"] = evidence.get("usage")
    cached_tokens = record["usage"].get("cached_input_tokens") if isinstance(record["usage"], dict) else None
    record["provider_cache_observed"] = None if type(cached_tokens) is not int else cached_tokens > 0
    record["actual_cost_usd"] = _cost(record["usage"]) if record["provider_call"] else None
    record["uncached_input_cost_upper_bound_usd"] = _cost_uncached_upper_bound(record["usage"]) if record["provider_call"] else None
    record["prompt"] = evidence.get("prompt")
    record["raw_provider_output"] = evidence.get("raw_output")
    record["raw_provider_text"] = evidence.get("raw_output_text")
    record["raw_finish_reason"] = evidence.get("raw_finish_reason")
    if isinstance(record.get("fallback_reason"), str) and record["fallback_reason"].startswith("Plan compilation failed:"):
        record["route_error"] = "Malformed planner response: " + record["fallback_reason"]
    record["execution_ms"] = None
    record["execution_ok"] = None
    record["semantic_correct"] = None
    record["gold_route"] = case["route"]
    if case["route"] == record.get("actual_route"):
        record["route_matches"] = True
    else:
        record["route_matches"] = False
    actual_plan = record.get("compiled_plan")
    if isinstance(actual_plan, (dict, list)) and record["actual_route"] == "local" and case["route"] == "local":
        t_exec = time.perf_counter()
        try:
            answers, execution_exceptions = _denotation(module, actual_plan, countries, case["question"])
            record["execution_ms"] = (time.perf_counter() - t_exec) * 1000
            record["execution_exceptions"] = execution_exceptions
            record["execution_ok"] = len(answers) == len(countries) and execution_exceptions == 0 and any(value is not None for value in answers.values())
            gold_answers, gold_exceptions = _denotation(module, case["gold_plan"], countries, case["question"])
            record["gold_execution_exceptions"] = gold_exceptions
            record["denotation_comparison"] = _compare_denotations(answers, gold_answers)
            with connect_readonly(db_path) as conn:
                conn.row_factory = sqlite3.Row
                required_missing = atoms_missing(actual_plan, case["required_atoms"], module, conn)
            record["required_atoms_missing"] = required_missing
            record["actual_denotation"] = answers
            if execution_exceptions or gold_exceptions or record["denotation_comparison"]["mismatch_count"]:
                record["semantic_correct"] = False
                record["semantic_status"] = "incorrect"
            elif required_missing:
                record["semantic_correct"] = None
                record["semantic_status"] = "needs_adjudication"
            else:
                record["semantic_correct"] = True
                record["semantic_status"] = "correct"
        except Exception as exc:
            record["execution_ms"] = (time.perf_counter() - t_exec) * 1000
            record["execution_ok"] = False
            record["semantic_correct"] = False
            record["semantic_status"] = "incorrect"
            record["execution_error"] = _safe_exception(exc)
    elif record["actual_route"] == case["route"] and case["route"] != "local":
        record["execution_ok"] = True
        record["semantic_correct"] = True
        record["semantic_status"] = "correct"
    else:
        record["execution_ok"] = False if record["actual_route"] == "local" else None
        record["semantic_correct"] = False
        record["semantic_status"] = "incorrect"
    record["raw_plan_result"] = None if plan_result is None else {"original_question": getattr(plan_result, "original_question", None), "valid": getattr(plan_result, "valid", None), "supported": getattr(plan_result, "supported", None), "improved_question": getattr(plan_result, "improved_question", None), "explanation": getattr(plan_result, "explanation", None), "fallback_reason": getattr(plan_result, "fallback_reason", None), "plan": getattr(plan_result, "plan", None)}
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Optional dotenv credentials file; values are never printed")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB, help="Copied country facts SQLite database (read-only)")
    parser.add_argument("--baseline-planner", type=Path, help="Path to saved baseline local_planner.py")
    parser.add_argument("--variant", choices=("baseline", "current", "both"), default="both")
    parser.add_argument("--split", choices=("development", "held_out", "all"), default="all")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=SERVER_DIR / "test_reports" / "country_planner_benchmark.json", help="JSON evidence output path")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--thinking-budget", type=int, help="Experiment-only planner thinking budget override")
    parser.add_argument("--validate-only", "--validate-gold-only", dest="validate_only", action="store_true", help="Validate gold AST shape, relations, country literals, and guard atoms without provider calls")
    args = parser.parse_args(argv)
    if args.workers < 1 or args.repeat < 1 or (args.limit is not None and args.limit < 1) or (args.thinking_budget is not None and args.thinking_budget < 0):
        parser.error("workers/repeat/limit must be positive and thinking-budget non-negative")
    database_path = args.database.resolve()
    protected = [args.corpus, database_path, Path(__file__), SERVER_DIR / "countrydle" / "local_planner.py"]
    protected.extend(Path(f"{database_path}{suffix}") for suffix in ("-wal", "-shm", "-journal"))
    if args.baseline_planner is not None:
        protected.append(args.baseline_planner)
    if args.env_file is not None:
        protected.append(args.env_file)
    try:
        validate_output_path(args.output, protected)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.database.is_file():
        parser.error(f"Copied facts database not found: {args.database}")
    prepare_environment(args.env_file)
    corpus, cases = load_corpus(args.corpus)
    with private_database_snapshot(args.database) as (database_path, database_checksum):
        isolate_plan_cache()
        current = load_module(SERVER_DIR / "countrydle" / "local_planner.py", "countrydle_current_planner")
        current.local_answering.DEFAULT_DB_PATH = database_path
        gold_validation = validate_gold(cases, current, database_path)
        if args.validate_only:
            print(json.dumps({
                "database_source_path": str(args.database.resolve()),
                "database_source_sha256": database_checksum,
                "gold_validation": gold_validation,
            }, ensure_ascii=False, indent=2))
            return 0 if gold_validation["valid"] else 2
        if not gold_validation["valid"]:
            parser.error("Gold corpus validation failed; run --validate-only for details")
        if args.split != "all":
            cases = [case for case in cases if case["split"] == args.split]
        if args.limit is not None:
            cases = cases[:args.limit]
        if args.variant in ("baseline", "both") and args.baseline_planner is None:
            parser.error("--baseline-planner is required for baseline/both variants")
        variants: list[tuple[str, Any]] = []
        if args.variant in ("baseline", "both"):
            baseline = load_module(args.baseline_planner, "countrydle_baseline_planner")
            variants.append(("baseline", baseline))
        if args.variant in ("current", "both"):
            variants.append(("current", current))
        if args.thinking_budget is not None:
            for _, module in variants:
                module.PLANNER_THINKING_BUDGET = args.thinking_budget
        countries = get_countries(database_path)
        records: list[dict[str, Any]] = []
        jobs = []
        install_provider_capture()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for name, module in variants:
                for case in cases:
                    for repeat in range(1, args.repeat + 1):
                        jobs.append(pool.submit(run_one, module, name, case, repeat, database_path, countries))
            for future in as_completed(jobs):
                records.append(future.result())
        records.sort(key=lambda r: (r["variant"], r["case_id"], r["repeat"]))
        by_variant = {}
        for name, _ in variants:
            by_variant[name] = {}
            for split in ("development", "held_out"):
                by_variant[name][split] = _summary([row for row in records if row["variant"] == name and row["split"] == split])
            by_variant[name]["all"] = _summary([row for row in records if row["variant"] == name])
            by_variant[name]["cache_observed_cohorts_by_split"] = {}
            for split in ("development", "held_out", "all"):
                split_rows = [row for row in records if row["variant"] == name and (split == "all" or row["split"] == split)]
                cohorts = {}
                for observed in (True, False, None):
                    label = "unknown" if observed is None else str(observed).lower()
                    cohorts[label] = _summary([row for row in split_rows if row.get("provider_cache_observed") is observed])
                by_variant[name]["cache_observed_cohorts_by_split"][split] = cohorts
        report = {
            "description": corpus.get("description"), "corpus_path": str(args.corpus.resolve()),
            "database_source_path": str(args.database.resolve()), "database_source_sha256": database_checksum,
            "split": args.split, "limit": args.limit, "repeat": args.repeat, "workers": args.workers,
            "variants": [name for name, _ in variants], "planner_version": {name: getattr(module, "PLANNER_VERSION", None) for name, module in variants},
            "thinking_budget_override": args.thinking_budget,
            "planner_settings": {
                name: {
                    "model": os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or getattr(module, "DEFAULT_MODEL", None),
                    "thinking_budget": module.PLANNER_THINKING_BUDGET,
                    "max_output_tokens": getattr(module, "PLANNER_MAX_OUTPUT_TOKENS", None),
                }
                for name, module in variants
            },
            "pricing": {
                "input_usd_per_million": INPUT_RATE,
                "cached_input_usd_per_million": CACHED_INPUT_RATE,
                "output_usd_per_million": OUTPUT_RATE,
                "formula": "(input_tokens-cached_input_tokens)*0.10 + cached_input_tokens*0.01 + (candidate_output_tokens+thought_tokens)*0.40, divided by 1,000,000",
                "incomplete_usage": "Actual cost is withheld unless input, cached-input, candidate-output, and thought token counts are all observed. An uncached-input cost upper bound is reported only when input, output, and thought counts are observed; absent cache metadata is treated as all input uncached for this bound.",
            },
            "gold_validation": gold_validation, "summary": by_variant,
            "cache_note": "Cache observations are reported as observed; planner calls use_cache=False. No claim of a cold provider cache is made.",
            "records": records,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "records": len(records), "summary": by_variant}, ensure_ascii=False, indent=2))
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
