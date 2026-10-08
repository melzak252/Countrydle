#!/usr/bin/env python3
"""Isolated Countrydle quality gate: offline semantics or explicitly bounded live stages.

Supplied gold plans never establish current provider accuracy. Live execution requires
model-specific approved prices and reserves worst-case cost before every HTTP call.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import threading
import types
from contextlib import contextmanager
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
DEFAULT_CORPUS = SERVER_DIR / "tests" / "answer_quality_corpus.json"
DEFAULT_DB = SERVER_DIR / "data" / "country_facts.sqlite"
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
    """Load real pure submodules without application package startup or cache access."""
    for package_name in ("countrydle", "utils"):
        package = types.ModuleType(package_name)
        package.__path__ = [str(SERVER_DIR / package_name)]
        sys.modules[package_name] = package

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
        if "expected_answers" in case:
            answers = case["expected_answers"]
            if not isinstance(answers, dict) or any(
                not isinstance(target, str) or not target or (answer is not None and type(answer) is not bool)
                for target, answer in answers.items()
            ):
                raise ValueError(f"Case {case['id']}: reviewed answers require named targets and bool/null")
            if any(target not in answers for target in case.get("unreviewed_targets", [])):
                raise ValueError(f"Case {case['id']}: unreviewed targets must be explicitly represented")
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
            if result is not None:
                answers[country] = result.answer
        except Exception:
            failures += 1
    return answers, failures


def _compare_denotations(actual: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for country in gold:
        if country not in actual or actual[country] is not gold[country]:
            mismatch = {"country": country, "gold": gold[country], "actual": actual.get(country)}
            if country not in actual:
                mismatch["missing"] = True
            mismatches.append(mismatch)
    return {"compared_entities": len(gold), "mismatch_count": len(mismatches), "mismatches": mismatches}


PATHS = ("template", "model_planned_local", "fallback")
POLICY_ID = "h10-pre-score-20261006-v1"
_live_budget = None


def json_identity(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def load_pricing(path: Path) -> dict[str, Any]:
    pricing = json.loads(path.read_text(encoding="utf-8"))
    if pricing.get("currency") != "USD" or not pricing.get("as_of") or pricing.get("approved") is not True:
        raise ValueError("Pricing requires approved=true, currency=USD, and as_of date")
    models = pricing.get("models")
    if not isinstance(models, dict) or not models:
        raise ValueError("Pricing requires model-specific entries")
    for model, rates in models.items():
        if not isinstance(model, str) or not isinstance(rates, dict):
            raise ValueError("Invalid model pricing entry")
        for key in ("input_usd_per_million", "cached_input_usd_per_million", "output_usd_per_million"):
            value = rates.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{model}: missing/invalid {key}")
        if rates["cached_input_usd_per_million"] > rates["input_usd_per_million"]:
            raise ValueError(f"{model}: cached rate exceeds uncached reservation rate")
        if type(rates.get("max_input_tokens")) is not int or rates["max_input_tokens"] < 1:
            raise ValueError(f"{model}: positive approved max_input_tokens required")
    return pricing


def stage_cost(usage: dict | None, rates: dict | None, *, uncached=False) -> float | None:
    if not isinstance(usage, dict) or rates is None:
        return None
    if any(type(usage.get(key)) is not int or usage[key] < 0
           for key in ("input_tokens", "output_tokens", "thought_tokens")):
        return None
    cached = 0 if uncached else usage.get("cached_input_tokens")
    if type(cached) is not int or not 0 <= cached <= usage["input_tokens"]:
        return None
    return ((usage["input_tokens"] - cached) * rates["input_usd_per_million"]
            + cached * rates["cached_input_usd_per_million"]
            + (usage["output_tokens"] + usage["thought_tokens"]) * rates["output_usd_per_million"]) / RATE_UNIT


class LiveBudget:
    """Reservations never reclaimed, including failures; every retry reserves."""

    def __init__(self, pricing: dict, max_calls: int, max_cost_usd: float):
        if type(max_calls) is not int or not 1 <= max_calls <= 100:
            raise ValueError("Live provider cap must be between 1 and 100 calls")
        if not math.isfinite(max_cost_usd) or not 0 < max_cost_usd <= 1:
            raise ValueError("Live cost cap must be positive and at most USD 1")
        self.pricing = pricing
        self.max_calls = max_calls
        self.max_cost_usd = max_cost_usd
        self.reservations: list[dict] = []

    def reserve(self, model: str, body: dict) -> dict:
        rates = self.pricing["models"].get(model)
        if rates is None:
            raise ValueError(f"No approved pricing for model {model}")
        generation = body.get("generationConfig", {})
        output = generation.get("maxOutputTokens")
        thinking = generation.get("thinkingConfig", {}).get("thinkingBudget")
        if type(output) is not int or output < 1 or type(thinking) is not int or thinking < 0:
            raise ValueError("Live calls require finite explicit output AND thinking token bounds")
        # UTF-8 bytes conservatively bound text/schema tokens. Reserve the full
        # approved ceiling, including fixed request-envelope headroom.
        request_bytes = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        if request_bytes + 4096 > rates["max_input_tokens"]:
            raise ValueError("Request exceeds approved conservative input-token bound")
        reserved = (rates["max_input_tokens"] * rates["input_usd_per_million"]
                    + (output + thinking) * rates["output_usd_per_million"]) / RATE_UNIT
        if len(self.reservations) >= self.max_calls or self.reserved_cost_usd + reserved > self.max_cost_usd:
            raise RuntimeError("Live budget exhausted before provider call")
        entry = {"call": len(self.reservations) + 1, "model": model,
                 "reserved_cost_usd": reserved, "max_input_tokens": rates["max_input_tokens"],
                 "max_output_tokens": output, "max_thought_tokens": thinking}
        self.reservations.append(entry)
        return entry

    @property
    def reserved_cost_usd(self) -> float:
        return sum(item["reserved_cost_usd"] for item in self.reservations)


def load_fallback_prompt_builder():
    """Load the actual pure prompt builder without importing gameplay/DB/Qdrant."""
    from countrydle.template_compiler import _bind_named_country_subject
    source = SERVER_DIR / "countrydle" / "utils.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "answer_prompts")
    namespace = {"QuestionEnhanced": Any, "_bind_named_country_subject": _bind_named_country_subject}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["answer_prompts"]


class IsolatedFallback:
    """Actual answer stage, conditional on immutable pre-retrieved context.

    No live embedding/vector search, gameplay imports, caches or history writes.
    This is not a measurement of live retrieval accuracy or answer reuse.
    """

    def __init__(self, snapshot_path: Path, model: str):
        snapshot_bytes = snapshot_path.read_bytes()
        snapshot = json.loads(snapshot_bytes)
        if snapshot.get("schema_version") != 1 or not isinstance(snapshot.get("contexts"), dict):
            raise ValueError("Retrieval snapshot requires schema_version=1 and contexts map")
        self.contexts = snapshot["contexts"]
        self.snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
        self.model = model
        self.prompt_builder = load_fallback_prompt_builder()

    def answer(self, case: dict, target: str) -> tuple[Any, dict]:
        from utils.fallback_answers import get_answer
        context = self.contexts.get(case["id"], {}).get(target)
        if not isinstance(context, dict) or not isinstance(context.get("text"), str):
            raise ValueError(f"Missing frozen retrieval context: {case['id']}/{target}")
        question = types.SimpleNamespace(original_question=case["question"], question=case["question"])
        started = time.perf_counter()
        system, user = self.prompt_builder(question, target, context["text"])
        evidence = {"stage": "fallback", "model": self.model, "retrieval": context,
                    "retrieval_snapshot_sha256": self.snapshot_sha256,
                    "retrieval_mode": "immutable_pre_retrieved_context",
                    "embedding_provider_calls": 0, "retrieval_provider_calls": 0,
                    "prompt_sha256": hashlib.sha256(f"{system.strip()}\n\n{user.strip()}".encode("utf-8")).hexdigest()}
        try:
            result = get_answer(system, user, model=self.model, evidence=evidence, request_timeout=30)
            evidence.update(answer=result["answer"], explanation=result["explanation"])
        except Exception as exc:
            evidence["error"] = _safe_exception(exc)
            evidence["error_kind"] = "provider_error" if evidence.get("provider_call_attempted") else "pre_call_blocked"
            result = None
        evidence["duration_ms"] = (time.perf_counter() - started) * 1000
        return result, evidence


def assess_targets(case: dict, answers: dict, *, executed: bool, route: str,
                   errors: dict | None = None, provider_error: str | None = None,
                   artifacts: dict | None = None) -> list[dict]:
    reviewed = case.get("expected_answers", {})
    assessments = []
    for target in dict.fromkeys([*reviewed, *case.get("unreviewed_targets", [])]):
        expected = reviewed.get(target)
        row = {"target": target, "expected": expected, "actual": answers.get(target),
               "answerable": expected is not None, "route_correct": route == case["route"],
               "interpretation_correct": None, "factual_correct": None,
               "evaluator_correct": None, "grounding": "unassessed", "causal_evidence": []}
        error = (errors or {}).get(target)
        if provider_error or error:
            row["outcome"] = "provider_error" if provider_error else (
                error.get("kind", "execution_error") if isinstance(error, dict) else "execution_error")
            row["error"] = provider_error or (error.get("message") if isinstance(error, dict) else error)
        elif target in case.get("unreviewed_targets", []) or target not in reviewed:
            row["outcome"] = "needs_adjudication"
        elif not executed:
            row["outcome"] = "unassessed"
        elif target not in answers:
            row["outcome"] = "missing_result"
        elif answers[target] is None:
            row["outcome"] = "correct_abstention" if expected is None else "avoidable_abstention"
        elif expected is None:
            row["outcome"] = "wrong_answer"
            row["unknown_to_boolean"] = True
        else:
            row["outcome"] = "correct_answer" if answers[target] is expected else "wrong_answer"
            row["factual_correct"] = answers[target] is expected
        artifact = (artifacts or {}).get(target)
        row["assessment_artifact_sha256"] = artifact
        adjudication = case.get("causal_reviews", {}).get(target, {})
        if (adjudication.get("reviewed") is True and artifact is not None
                and adjudication.get("observed_artifact_sha256") == artifact
                and adjudication.get("evidence")):
            row["causal_evidence"] = list(adjudication["evidence"])
            row["causes"] = list(adjudication.get("causes", []))
            row["grounding"] = adjudication.get("grounding", "unassessed")
        assessments.append(row)
    return assessments


def finish_assessment(record: dict, case: dict, *, executed: bool, errors: dict | None = None) -> None:
    errors = dict(errors or {})
    if record.get("route_error") and not record.get("provider_call"):
        errors.update({target: {"kind": "pre_call_blocked", "message": record["route_error"]}
                       for target in case.get("expected_answers", {})})
    explanations = {stage["target"]: stage.get("explanation") for stage in record.get("stages", []) if stage.get("target")}
    artifacts = {target: json_identity({"answer": answer, "plan": record.get("compiled_plan"),
                                       "explanation": explanations.get(target), "route": record["actual_route"]})
                 for target, answer in record.get("actual_denotation", {}).items()}
    assessments = assess_targets(case, record.get("actual_denotation", {}), executed=executed,
                                 route=record["actual_route"], errors=errors, artifacts=artifacts,
                                 provider_error=record.get("route_error") if record.get("provider_call") else None)
    record["target_assessments"] = assessments
    record["reviewed_answer_comparison"] = _compare_denotations(
        record.get("actual_denotation", {}),
        {target: value for target, value in case.get("expected_answers", {}).items()
         if target not in case.get("unreviewed_targets", [])},
    ) if executed else None
    if any(row["outcome"] in {"wrong_answer", "avoidable_abstention", "missing_result",
                             "provider_error", "execution_error", "pre_call_blocked"} for row in assessments):
        record.update(semantic_correct=False, semantic_status="incorrect")
    elif not executed or not assessments or any(row["outcome"] in {"needs_adjudication", "unassessed"} for row in assessments):
        record.update(semantic_correct=None, semantic_status="needs_adjudication" if executed else "unassessed")
    elif record.get("required_atoms_missing"):
        record.update(semantic_correct=None, semantic_status="needs_adjudication")
    else:
        record["semantic_correct"] = record["route_matches"] is True
        record["semantic_status"] = "correct" if record["semantic_correct"] else "incorrect"
    for row in assessments:
        if record.get("required_atoms_missing"):
            row["causal_evidence"].append({"kind": "required_predicates_guard",
                                          "predicates": record["required_atoms_missing"],
                                          "status": "advisory_not_equivalence_proof"})
            if (row["outcome"] == "wrong_answer" and row["target"] in record.get("gold_denotation", {})
                    and record["gold_denotation"][row["target"]] is row["expected"]):
                row["interpretation_correct"] = False
                row.setdefault("causes", []).append("interpretation_error")
                row["causal_evidence"].append({"kind": "missing_predicate_and_reviewed_gold_correct_actual_wrong"})
        if row["target"] in record.get("gold_denotation", {}) and record["gold_denotation"][row["target"]] is not row["expected"]:
            if row["factual_correct"] is False:
                row["fact_or_evaluator_disagreement"] = True
                row["causal_evidence"].append({"kind": "gold_executor_disagrees_with_reviewed_answer",
                                              "cause": "unadjudicated_fact_or_evaluator"})


def path_quality(records: list[dict], corpus: dict, *, live: bool) -> dict:
    """Frozen before scoring: template zero errors, local 95%, fallback 90%."""
    output = {}
    for path in PATHS:
        rows = [row for row in records if row.get("path") == path]
        targets = [item for row in rows for item in row.get("target_assessments", [])]
        outcomes = {}
        for item in targets:
            outcomes[item["outcome"]] = outcomes.get(item["outcome"], 0) + 1
        answerable = [item for item in targets if item["answerable"] and item["outcome"] not in {"unassessed", "needs_adjudication"}]
        correct = sum(item["outcome"] == "correct_answer" for item in answerable)
        held = [row for row in rows if row["split"] == "held_out"]
        held_targets = {(row["case_id"], item["target"]) for row in held
                        for item in row.get("target_assessments", [])}
        languages = {lang: len({row["case_id"] for row in held if row.get("language") == lang})
                     for lang in ("en", "pl")}
        fatal_outcomes = ("provider_error", "execution_error", "pre_call_blocked", "missing_result")
        fatal_failures = sum(outcomes.get(key, 0) for key in fatal_outcomes)
        unknown_to_false = sum(item.get("unknown_to_boolean") is True and item["actual"] is False for item in targets)
        interpretation_errors = sum(item.get("interpretation_correct") is False for item in targets)
        causes = {cause: sum(cause in item.get("causes", []) for item in targets)
                  for cause in ("interpretation_error", "stale_fact", "incorrect_fact", "unsupported_route")}
        route_rows = [row for row in records if row.get("route_matches") is not None
                      and (row.get("interpretation_path") == "model_planned_local" if path == "model_planned_local"
                           else row.get("path") == path)]
        route_rate = sum(row["route_matches"] is True for row in route_rows) / len(route_rows) if route_rows else None
        rate = correct / len(answerable) if answerable else None
        held_answerable = [item for row in held for item in row.get("target_assessments", [])
                           if item["answerable"] and item["outcome"] not in {"unassessed", "needs_adjudication"}]
        held_rate = sum(item["outcome"] == "correct_answer" for item in held_answerable) / len(held_answerable) if held_answerable else None
        held_routes = [row for row in route_rows if row["split"] == "held_out"]
        held_route_rate = sum(row["route_matches"] is True for row in held_routes) / len(held_routes) if held_routes else None
        reasons, insufficient = [], []
        development_regressions = any(item["outcome"] in {"wrong_answer", "avoidable_abstention"}
                                      for row in rows if row["split"] == "development"
                                      for item in row.get("target_assessments", []))
        template_errors = path == "template" and any(outcomes.get(key, 0) for key in ("wrong_answer", "avoidable_abstention"))
        unresolved_fact_disputes = sum(item.get("fact_or_evaluator_disagreement") is True for item in targets)
        if (fatal_failures or interpretation_errors or any(causes.values()) or unknown_to_false
                or development_regressions or template_errors or unresolved_fact_disputes):
            reasons.append("observed_quality_failure")
        if path != "template" and held_rate is not None and held_rate < (0.95 if path == "model_planned_local" else 0.90):
            reasons.append("below_frozen_answer_threshold")
        if path == "model_planned_local" and held_route_rate is not None and held_route_rate < 0.95:
            reasons.append("below_frozen_route_threshold")
        if not live:
            insufficient.append("offline_deterministic_evidence_is_not_live_accuracy")
        if corpus.get("release_policy", {}).get("policy_id") != POLICY_ID:
            insufficient.append("missing_frozen_release_policy")
        if any(row.get("path") not in PATHS for row in records):
            insufficient.append("unknown_answering_path")
        if live and any(row.get("evidence_origin") != "live_provider_or_template" for row in rows if not row.get("declined")):
            insufficient.append("supplied_or_unverified_outputs_are_not_live_accuracy")
        if any(row.get("experimental_generation_override") for row in rows):
            insufficient.append("generation_override_outside_frozen_release_settings")
        if len(held_targets) < 20 or any(count < 5 for count in languages.values()):
            insufficient.append("insufficient_held_out_targets_or_languages")
        if not held or any(len({row["repeat"] for row in held if row["case_id"] == case_id}) < 3
                           for case_id in {row["case_id"] for row in held}):
            insufficient.append("insufficient_live_repeats")
        if any(outcomes.get(key, 0) for key in ("unassessed", "needs_adjudication")) or not targets:
            insufficient.append("unassessed_or_unreviewed_results")
        if any(row.get("semantic_status") == "needs_adjudication" for row in rows):
            insufficient.append("interpretation_adjudication_pending")
        if corpus.get("review", {}).get("independent_external_fact_review") is not True:
            insufficient.append("independent_factual_review_missing")
        if corpus.get("release_policy", {}).get("current_corpus_is_release_sufficient") is False:
            insufficient.append("corpus_declared_release_insufficient")
        stages = [stage for row in rows for stage in row.get("stages", []) if stage.get("provider_call_attempted")]
        if any(stage.get("actual_cost_usd") is None or not stage.get("model_version")
               or not stage.get("request_semantic_identity") for stage in stages):
            insufficient.append("incomplete_provider_cost_or_revision")
        if path == "fallback" and any(item["grounding"] == "unassessed" for item in targets):
            insufficient.append("fallback_grounding_unreviewed")
        if path == "fallback" and any(stage.get("retrieval_mode") == "immutable_pre_retrieved_context"
                                      for row in rows for stage in row.get("stages", [])):
            insufficient.append("live_retrieval_not_assessed_conditional_answer_stage_only")
        if any(item["grounding"] == "unsupported" for item in targets):
            reasons.append("unsupported_grounding_claim")
        output[path] = {"records": len(rows), "declines": sum(row.get("declined") is True for row in rows),
                        "outcomes": outcomes, "reviewed_causes": causes, "interpretation_errors": interpretation_errors,
                        "route_mismatches": sum(row.get("route_matches") is False for row in route_rows),
                        "unsupported_routes": sum(row.get("route_assessment", {}).get("outcome") == "unsupported_route" for row in rows),
                        "unknown_to_false_conversions": unknown_to_false, "unresolved_fact_disputes": unresolved_fact_disputes,
                        "held_out_answerable_attempts": len(held_answerable), "held_out_correct_answer_rate": held_rate,
                        "held_out_route_accuracy": held_route_rate,
                        "template_coverage": sum(not row.get("declined") for row in rows) / len(rows) if rows and path == "template" else None,
                        "answerable_attempts": len(answerable), "correct_answer_rate": rate, "route_accuracy": route_rate,
                        "held_out_unique_targets": len(held_targets), "held_out_cases_by_language": languages,
                        "release_status": "fail" if reasons else ("insufficient" if insufficient else "pass"),
                        "failure_reasons": reasons, "insufficiency_reasons": insufficient}
    return output




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
                evidence = getattr(_provider_evidence_local, "evidence", None)
                if _live_budget is None:
                    raise RuntimeError("Provider calls require an explicit approved live budget")
                url = args[0] if args else kwargs.get("url", "")
                model = str(url).split("/models/", 1)[-1].split(":generateContent", 1)[0]
                reservation = _live_budget.reserve(model, kwargs.get("json", {}))
                if isinstance(evidence, dict):
                    evidence["provider_call_attempted"] = True
                    evidence["request_semantic_identity"] = json_identity({"model": model, "request": kwargs.get("json", {})})
                    evidence.setdefault("reservations", []).append(reservation)
                response = _provider_original_http_getter().post(*args, **kwargs)
                return CapturedResponse(response)

        client = CapturedHttpClient()
        ai_clients.get_http_client = lambda: client

        def capture(*args, **kwargs):
            evidence = kwargs.get("evidence")
            if isinstance(evidence, dict):
                evidence["prompt"] = args[0] if args else kwargs.get("prompt")
                evidence["model"] = kwargs.get("model", evidence.get("model"))
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
    stages = [stage for row in records for stage in row.get("stages", [])]
    attempts = [attempt for stage in stages for attempt in stage.get("attempts", [])]
    good_usage = [attempt["usage"] for attempt in attempts if isinstance(attempt.get("usage"), dict)]
    costs = [cost for stage in stages for cost in stage.get("attempt_costs_usd", []) if cost is not None]
    upper_bounds = [cost for stage in stages for cost in stage.get("attempt_uncached_upper_bounds_usd", []) if cost is not None]
    provider_calls = sum(stage.get("provider_calls", 0) for stage in stages)
    full_coverage = len(costs) == provider_calls
    bound_coverage = len(upper_bounds) == provider_calls
    def token_stats(key: str):
        values = [u[key] for u in good_usage if type(u.get(key)) is int]
        return {"observed_count": len(values), "mean": _mean(values), "p95": _percentile95(values), "sum": sum(values) if values else None}
    attempted = sum(not row.get("declined") for row in records)
    resolved = sum(row.get("execution_ok") is True and any(
        item.get("actual") is not None for item in row.get("target_assessments", [])) for row in records)
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


def finalize_stage(evidence: dict, pricing: dict | None) -> dict:
    stage = dict(evidence)
    rates = pricing.get("models", {}).get(stage.get("model")) if pricing else None
    attempts = [attempt for attempt in stage.get("attempts", []) if "http_status" in attempt or attempt.get("usage")]
    # Network exceptions have no HTTP status/usage, but still consumed a call.
    count = len(stage.get("reservations", []))
    stage["provider_calls"] = count
    stage["attempt_costs_usd"] = [stage_cost(attempt.get("usage"), rates) for attempt in attempts]
    stage["attempt_uncached_upper_bounds_usd"] = [stage_cost(attempt.get("usage"), rates, uncached=True) for attempt in attempts]
    costs = stage["attempt_costs_usd"]
    bounds = stage["attempt_uncached_upper_bounds_usd"]
    stage["actual_cost_usd"] = sum(costs) if count and len(costs) == count and all(cost is not None for cost in costs) else None
    stage["uncached_input_cost_upper_bound_usd"] = sum(bounds) if count and len(bounds) == count and all(cost is not None for cost in bounds) else None
    if stage.get("prompt"):
        stage["prompt_sha256"] = hashlib.sha256(stage["prompt"].encode("utf-8")).hexdigest()
    return stage


def run_one(module, variant: str, case: dict[str, Any], repeat: int, db_path: Path,
            countries: list[str], *, fallback=None, pricing=None, origin="supplied_or_unverified") -> dict[str, Any]:
    module.local_answering.DEFAULT_DB_PATH = db_path
    targets = list(case.get("expected_answers", {})) or countries
    evidence: dict[str, Any] = {"stage": "interpretation"}
    record: dict[str, Any] = {
        "variant": variant, "case_id": case["id"], "split": case["split"],
        "category": case["category"], "language": case.get("language"),
        "family": case.get("family"), "question": case["question"], "repeat": repeat,
        "evidence_origin": origin, "provider_call": False, "usage": None,
        "actual_cost_usd": None, "execution_ms": None, "execution_ok": None,
        "semantic_correct": None, "actual_denotation": {}, "gold_route": case["route"],
        "application_cache_bypassed": True, "history_writes": False,
    }
    started = time.perf_counter()
    plan_result = None
    try:
        plan_result = module.analyze_question_for_local_plan(
            case["question"], use_cache=False, strict_errors=True, evidence=evidence,
        )
        record.update({
            "valid": getattr(plan_result, "valid", None), "supported": getattr(plan_result, "supported", None),
            "actual_route": "local" if getattr(plan_result, "supported", False) else
                            ("clarify" if not getattr(plan_result, "valid", True) else "fallback"),
            "improved_question": getattr(plan_result, "improved_question", None),
            "explanation": getattr(plan_result, "explanation", None),
            "fallback_reason": getattr(plan_result, "fallback_reason", None),
            "compiled_plan": getattr(plan_result, "plan", None),
        })
    except Exception as exc:
        record.update(route_error=_safe_exception(exc), actual_route="error", compiled_plan=None)
    record["plan_ms"] = (time.perf_counter() - started) * 1000
    evidence["duration_ms"] = record["plan_ms"]
    for key in ("provider", "model", "contract_version", "cache_hit", "usage", "prompt"):
        record[key] = evidence.get(key)
    record["provider_call"] = evidence.get("provider_call_attempted") is True
    record["provider_response_id"] = evidence.get("response_id")
    record["provider_model_version"] = evidence.get("model_version")
    record["raw_provider_output"] = evidence.get("raw_output")
    record["raw_provider_text"] = evidence.get("raw_output_text")
    record["raw_finish_reason"] = evidence.get("raw_finish_reason")
    cached_tokens = record["usage"].get("cached_input_tokens") if isinstance(record["usage"], dict) else None
    record["provider_cache_observed"] = None if type(cached_tokens) is not int else cached_tokens > 0
    record["interpretation_path"] = "template" if record["provider"] == "template" else "model_planned_local"
    record["path"] = "fallback" if record["actual_route"] == "fallback" else record["interpretation_path"]
    if record["cache_hit"]:
        record["path"] = "unknown_cached_origin"
    record["route_matches"] = record["actual_route"] == case["route"]
    record["route_assessment"] = {
        "expected": case["route"], "actual": record["actual_route"],
        "outcome": "correct_route" if record["route_matches"] else
                   ("provider_error" if record["actual_route"] == "error" and record["provider_call"] else
                    ("pre_call_blocked" if record["actual_route"] == "error" else "unsupported_route")),
    }
    record["experimental_generation_override"] = getattr(module, "_benchmark_generation_override", False)
    stages = [finalize_stage(evidence, pricing)]
    errors = {}
    executed = False
    execution_started = time.perf_counter()
    if record["actual_route"] == "local" and isinstance(record["compiled_plan"], (dict, list)):
        executed = True
        answers, exceptions = _denotation(module, record["compiled_plan"], targets, case["question"])
        record.update(actual_denotation=answers, execution_exceptions=exceptions,
                      execution_ok=not exceptions and len(answers) == len(targets))
        if exceptions:
            errors = {target: "Local executor exception (not an abstention)" for target in targets if target not in answers}
        if case["gold_plan"] is not None:
            gold, gold_exceptions = _denotation(module, case["gold_plan"], targets, case["question"])
            record.update(gold_denotation=gold, gold_execution_exceptions=gold_exceptions,
                          denotation_comparison=_compare_denotations(answers, gold))
            with connect_readonly(db_path) as conn:
                conn.row_factory = sqlite3.Row
                record["required_atoms_missing"] = atoms_missing(record["compiled_plan"], case["required_atoms"], module, conn)
    elif record["actual_route"] == "clarify":
        executed = True
        record.update(actual_denotation={target: None for target in targets}, execution_ok=True)
    elif record["actual_route"] == "fallback" and fallback is not None:
        executed = True
        for target in targets:
            try:
                result, stage = fallback.answer(case, target)
                stage["target"] = target
                stages.append(finalize_stage(stage, pricing))
                if result is not None:
                    record["actual_denotation"][target] = result["answer"]
                else:
                    errors[target] = {"kind": stage.get("error_kind", "missing_result"),
                                      "message": stage.get("error", "Missing fallback result")}
            except Exception as exc:
                errors[target] = {"kind": "pre_call_blocked", "message": _safe_exception(exc)}
        record["execution_ok"] = not errors and len(record["actual_denotation"]) == len(targets)
    record["execution_ms"] = (time.perf_counter() - execution_started) * 1000 if executed else None
    record["stages"] = stages
    record["actual_cost_usd"] = sum(stage["actual_cost_usd"] for stage in stages if stage["provider_calls"]) if all(
        stage["actual_cost_usd"] is not None for stage in stages if stage["provider_calls"]) and any(
        stage["provider_calls"] for stage in stages) else None
    record["uncached_input_cost_upper_bound_usd"] = sum(
        stage["uncached_input_cost_upper_bound_usd"] for stage in stages if stage["provider_calls"]
    ) if all(stage["uncached_input_cost_upper_bound_usd"] is not None for stage in stages if stage["provider_calls"]) and any(
        stage["provider_calls"] for stage in stages) else None
    finish_assessment(record, case, executed=executed, errors=errors)
    if record.get("execution_exceptions"):
        record.update(semantic_correct=False, semantic_status="incorrect")
    record["raw_plan_result"] = None if plan_result is None else {
        key: getattr(plan_result, key, None) for key in
        ("original_question", "valid", "supported", "improved_question", "explanation", "fallback_reason", "plan")
    }
    return record


def offline_planner(module, case: dict, *, template: bool):
    if template:
        # Probe current fast-path eligibility, then exercise the real planner.
        # A decline never runs Gemini in offline mode.
        entity = module.compile_entity_question(case["question"])
        compiled = module.compile_template_plan(case["question"], english_only=True) if entity is None else None
        if entity is None and compiled is None:
            return None
        return module
    def analyze(question, **kwargs):
        kwargs["evidence"].update(provider="supplied_gold", contract_version=POLICY_ID)
        return types.SimpleNamespace(valid=case["route"] != "clarify", supported=case["route"] == "local",
                                     plan=case["gold_plan"], improved_question=None)
    return types.SimpleNamespace(local_answering=module.local_answering, analyze_question_for_local_plan=analyze)


def main(argv: list[str] | None = None) -> int:
    global _live_budget
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Live credentials only; values never printed")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB, help="Private country facts SQLite snapshot")
    parser.add_argument("--baseline-planner", type=Path)
    parser.add_argument("--variant", choices=("baseline", "current", "both"), default="current")
    parser.add_argument("--split", choices=("development", "held_out", "all"), default="all")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path, default=SERVER_DIR / "test_reports" / "country_planner_benchmark.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--thinking-budget", type=int, help="Existing experiment-only override; never release approval")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--live", action="store_true", help="Opt in to bounded real provider execution")
    execution.add_argument("--offline", action="store_true", help="Key-free templates and supplied-plan semantics (default)")
    parser.add_argument("--pricing", type=Path, help="Approved model-specific USD pricing/context bounds JSON")
    parser.add_argument("--max-provider-calls", type=int)
    parser.add_argument("--max-cost-usd", type=float)
    parser.add_argument("--execute-fallback", action="store_true", help="Run actual isolated fallback answer stage")
    parser.add_argument("--retrieval-snapshot", type=Path, help="Frozen pre-retrieved contexts; no live vector service")
    parser.add_argument("--fallback-model", help="Explicit real fallback model, with approved pricing")
    parser.add_argument("--validate-only", "--validate-gold-only", dest="validate_only", action="store_true")
    args = parser.parse_args(argv)
    if args.workers != 1 or args.repeat < 1 or (args.limit is not None and args.limit < 1):
        parser.error("Exactly one worker required; repeat/limit must be positive")
    if args.thinking_budget is not None and args.thinking_budget < 0:
        parser.error("thinking-budget must be non-negative")
    protected = [args.corpus, args.database, Path(__file__), SERVER_DIR / "countrydle" / "local_planner.py"]
    protected.extend((
        SERVER_DIR / "planner_protocol.py", SERVER_DIR / "countrydle" / "local_answering.py",
        SERVER_DIR / "countrydle" / "template_compiler.py", SERVER_DIR / "countrydle" / "utils.py",
        SERVER_DIR / "utils" / "ai_clients.py", SERVER_DIR / "utils" / "fallback_answers.py",
    ))
    protected.extend(Path(f"{args.database}{suffix}") for suffix in ("-wal", "-shm", "-journal"))
    protected.extend(path for path in (args.baseline_planner, args.env_file, args.pricing, args.retrieval_snapshot) if path is not None)
    try:
        validate_output_path(args.output, protected)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.database.is_file():
        parser.error(f"Copied facts database not found: {args.database}")
    if args.execute_fallback and (not args.live or not args.retrieval_snapshot or not args.fallback_model):
        parser.error("--execute-fallback requires --live, --retrieval-snapshot and --fallback-model")
    if not args.live and args.env_file is not None:
        parser.error("Offline evaluation must not load live credentials")
    if args.live and (args.pricing is None or args.max_provider_calls is None or args.max_cost_usd is None):
        parser.error("--live requires --pricing, --max-provider-calls and --max-cost-usd")
    prepare_environment(args.env_file if args.live else None)
    isolate_plan_cache()
    if not args.live:
        os.environ["GEMINI_API_KEY"] = ""
    pricing = None
    _live_budget = None
    if args.live:
        try:
            pricing = load_pricing(args.pricing)
            _live_budget = LiveBudget(pricing, args.max_provider_calls, args.max_cost_usd)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        planner_model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite"
        os.environ["LOCAL_QUESTION_MODEL"] = planner_model
        if not planner_model.startswith("gemini-2.5-flash-lite"):
            parser.error("Planner model has no finite explicit thinking bound in the current adapter")
        models = [planner_model] + ([args.fallback_model] if args.execute_fallback else [])
        if any(model not in pricing["models"] for model in models):
            parser.error("Every executing model requires exact approved pricing")
        if args.execute_fallback and not args.fallback_model.startswith("gemini-2.5"):
            parser.error("Fallback model has no finite explicit thinking bound in the current adapter")
        if not os.environ.get("GEMINI_API_KEY") and not args.validate_only:
            parser.error("Live execution requires GEMINI_API_KEY")
        install_provider_capture()
    corpus_bytes = args.corpus.read_bytes()
    corpus, cases = load_corpus(args.corpus)
    # Freeze the identity/policy before any interpretation or answer call.
    frozen_policy = {"policy_id": POLICY_ID, "template_max_errors": 0,
                     "model_planned_local_min_answer_rate": 0.95, "model_planned_local_min_route_rate": 0.95,
                     "fallback_min_answer_rate": 0.90, "minimum_held_out_targets_per_path": 20,
                     "minimum_cases_per_language_per_path": 5, "minimum_live_repeats": 3,
                     "unreviewed_missing_unknown_cost_or_grounding": "insufficient"}
    with private_database_snapshot(args.database) as (database_path, database_checksum):
        current = load_module(SERVER_DIR / "countrydle" / "local_planner.py", "countrydle_current_planner")
        current.local_answering.DEFAULT_DB_PATH = database_path
        gold_validation = validate_gold(cases, current, database_path)
        if args.validate_only:
            print(json.dumps({"database_source_sha256": database_checksum, "gold_validation": gold_validation}, indent=2))
            return 0 if gold_validation["valid"] else 2
        if not gold_validation["valid"]:
            parser.error("Gold corpus validation failed; run --validate-only for details")
        if args.split != "all":
            cases = [case for case in cases if case["split"] == args.split]
        if args.limit is not None:
            cases = cases[:args.limit]
        if args.variant in ("baseline", "both") and args.baseline_planner is None:
            parser.error("--baseline-planner is required for baseline/both variants")
        variants = []
        if args.variant in ("baseline", "both"):
            variants.append(("baseline", load_module(args.baseline_planner, "countrydle_baseline_planner")))
        if args.variant in ("current", "both"):
            variants.append(("current", current))
        if args.thinking_budget is not None:
            for _, module in variants:
                module.PLANNER_THINKING_BUDGET = args.thinking_budget
                module._benchmark_generation_override = True
        fallback = IsolatedFallback(args.retrieval_snapshot, args.fallback_model) if args.execute_fallback else None
        if fallback:
            # Reject missing evidence snapshots before any paid planning.
            for case in cases:
                for target in case.get("expected_answers", {}):
                    context = fallback.contexts.get(case["id"], {}).get(target)
                    if not isinstance(context, dict) or not isinstance(context.get("text"), str):
                        parser.error(f"Missing frozen retrieval context: {case['id']}/{target}")
        countries = get_countries(database_path)
        records = []
        for name, module in variants:
            for case in cases:
                for repeat in range(1, args.repeat + 1):
                    if args.live:
                        record = run_one(module, name, case, repeat, database_path, countries,
                                         fallback=fallback, pricing=pricing, origin="live_provider_or_template")
                        records.append(record)
                        if name == "current" and record["interpretation_path"] != "template":
                            records.append({"variant": name, "case_id": case["id"], "split": case["split"],
                                            "language": case.get("language"), "repeat": repeat, "path": "template",
                                            "declined": True, "route_matches": None, "target_assessments": [],
                                            "evidence_origin": "live_provider_or_template", "stages": []})
                    else:
                        template = offline_planner(current, case, template=True)
                        if template is not None:
                            records.append(run_one(template, name, case, repeat, database_path, countries,
                                                   origin="offline_actual_template"))
                        else:
                            records.append({"variant": name, "case_id": case["id"], "split": case["split"],
                                            "language": case.get("language"), "repeat": repeat, "path": "template",
                                            "declined": True, "route_matches": None, "target_assessments": [],
                                            "evidence_origin": "offline_actual_template", "stages": []})
                        supplied = offline_planner(module, case, template=False)
                        records.append(run_one(supplied, name, case, repeat, database_path, countries,
                                               origin="offline_supplied_gold_not_provider_accuracy"))
        records.sort(key=lambda row: (row["variant"], row["case_id"], row["repeat"], row["path"]))
        summaries = {}
        for name, _ in variants:
            summaries[name] = {}
            for split in ("development", "held_out", "all"):
                cohort = [row for row in records if row["variant"] == name and (split == "all" or row["split"] == split)]
                summaries[name][split] = {"quality_by_path": path_quality(cohort, corpus, live=args.live),
                                         "cost_latency": _summary(cohort)}
        quality = path_quality(records, corpus, live=args.live)
        status = "fail" if any(row["release_status"] == "fail" for row in quality.values()) else (
            "pass" if all(row["release_status"] == "pass" for row in quality.values()) else "insufficient")
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=False)
        report = {
            "description": corpus["description"], "mode": "live" if args.live else "offline",
            "accuracy_claim": "Corpus-scoped live path assessment" if args.live else "Deterministic semantics only; no current provider accuracy claim",
            "application_revision": revision.stdout.strip() if revision.returncode == 0 else None,
            "application_source_sha256": {
                str(path.relative_to(SERVER_DIR)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (SERVER_DIR / "planner_protocol.py", SERVER_DIR / "countrydle" / "local_answering.py",
                             SERVER_DIR / "countrydle" / "template_compiler.py", SERVER_DIR / "countrydle" / "utils.py",
                             SERVER_DIR / "utils" / "ai_clients.py", SERVER_DIR / "utils" / "fallback_answers.py")
            },
            "corpus_path": str(args.corpus.resolve()), "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
            "database_source_path": str(args.database.resolve()), "database_source_sha256": database_checksum,
            "fact_snapshot_sha256": hashlib.sha256(database_path.read_bytes()).hexdigest(),
            "retrieval_snapshot_sha256": fallback.snapshot_sha256 if fallback else None,
            "split_exposure": corpus.get("split_policy"), "fact_review": corpus.get("review"),
            "split": args.split, "limit": args.limit, "repeat": args.repeat, "workers": args.workers,
            "frozen_release_policy": frozen_policy, "release_policy_sha256": json_identity(frozen_policy),
            "release_status": status, "quality_by_path": quality,
            "planner_settings": {name: {"model": os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or module.DEFAULT_MODEL,
                                       "version": module.PLANNER_VERSION, "thinking_budget": module.PLANNER_THINKING_BUDGET,
                                       "max_output_tokens": module.PLANNER_MAX_OUTPUT_TOKENS,
                                       "source_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
                                 for name, module in variants},
            "pricing": pricing,
            "live_budget": {"max_provider_calls": _live_budget.max_calls, "max_cost_usd": _live_budget.max_cost_usd,
                            "reserved_cost_usd": _live_budget.reserved_cost_usd, "reservations": _live_budget.reservations} if _live_budget else None,
            "gold_validation": gold_validation, "summary": summaries,
            "isolation": "Private read-only fact backup; immutable pre-retrieved contexts; no gameplay imports, history or application cache calls.",
            "fallback_scope": "Real answer stage conditional on frozen retrieval; embedding/vector retrieval not executed or assessed.",
            "cache_note": "Application caches bypassed; provider cache observations are not claims of cold-cache control.",
            "records": records,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "records": len(records), "release_status": status,
                          "quality_by_path": quality}, ensure_ascii=False, indent=2))
        return 0 if status == "pass" else (1 if status == "fail" else 3)

if __name__ == "__main__":
    raise SystemExit(main())
