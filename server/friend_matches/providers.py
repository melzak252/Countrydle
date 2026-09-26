"""Explicit-target adapter to the normal games' planners, evaluators and fallback.

No daily rows are loaded or written. Blocking SQLite, canonical markdown and
Gemini work runs in threads; guidance does not use vector retrieval or embeddings.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import importlib
import json
import platform
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import local_kb_question as local
from country_eligibility import is_country_eligible


@dataclass(frozen=True)
class _Engine:
    mode: str
    module: ModuleType
    db_path: Path
    table: str
    name_column: str
    key_column: str
    code_column: str | None
    target_entity: str
    config: local.LocalModeConfig | None = None


CONTINENTAL_MODES = {
    "europe": ["Europe"],
    "asia": ["Asia"],
    "africa": ["Africa"],
    "americas": ["North America", "South America"],
}

@lru_cache(maxsize=16)
def _engine(mode: str) -> _Engine:
    if mode not in {"countrydle", "us_statedle", "wojewodztwodle", "powiatdle", *CONTINENTAL_MODES}:
        raise ValueError("Unsupported friend match mode")
    if mode in CONTINENTAL_MODES or mode == "countrydle":
        module = importlib.import_module("countrydle.utils")
        from countrydle.local_answering import DEFAULT_DB_PATH
        return _Engine(mode, module, DEFAULT_DB_PATH, "countries", "app_country_name", "cca3", "cca2", "target_country")
    module = importlib.import_module(f"{mode}.utils")
    config = module.LOCAL_CONFIG
    key, code = {
        "us_statedle": ("name", None),
        "wojewodztwodle": ("teryt", "teryt"),
        "powiatdle": ("terc", "terc"),
    }[mode]
    return _Engine(mode, module, config.db_path, config.table, config.name_column, key, code, config.target_entity, config)

def _connect(path: Path) -> sqlite3.Connection:
    # mode=ro also makes a missing facts database an error, never an empty file.
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _stamp(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def _entity(engine: _Engine, row: sqlite3.Row) -> dict:
    return {
        "id": str(row[engine.key_column]),
        "name": row[engine.name_column],
        "code": str(row[engine.code_column]) if engine.code_column and row[engine.code_column] is not None else None,
    }


@lru_cache(maxsize=32)
def _entity_pool(mode: str, stamp: tuple[int, int]) -> tuple[dict, ...]:
    engine = _engine(mode)
    with closing(_connect(engine.db_path)) as conn:
        if mode in CONTINENTAL_MODES:
            continents = CONTINENTAL_MODES[mode]
            ph = ",".join("?" for _ in continents)
            query = (
                f"SELECT DISTINCT c.* FROM {engine.table} c "
                f"JOIN country_continents cc ON c.id = cc.country_id "
                f"WHERE cc.continent IN ({ph}) "
                f"ORDER BY c.{engine.name_column}, c.{engine.key_column}"
            )
            entities = tuple(_entity(engine, row) for row in conn.execute(query, continents))
        else:
            entities = tuple(_entity(engine, row) for row in conn.execute(
                f"SELECT * FROM {engine.table} ORDER BY {engine.name_column}, {engine.key_column}"
            ))
    if mode == "countrydle" or mode in CONTINENTAL_MODES:
        entities = tuple(item for item in entities if is_country_eligible(item["name"], mode))
    if not entities or len({item["id"] for item in entities}) != len(entities):
        raise RuntimeError("Canonical entity pool is empty or has duplicate identifiers")
    return entities


def list_entities(mode: str) -> list[dict]:
    """Return eligible canonical entities. Async callers must offload the first read."""
    engine = _engine(mode)
    return [dict(item) for item in _entity_pool(mode, _stamp(engine.db_path))]


@lru_cache(maxsize=64)
def _file_hash(path: Path, stamp: tuple[int, int]) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _digest(path: Path) -> str:
    return _file_hash(path, _stamp(path))


def _facts(engine: _Engine, conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    values = dict(row)
    if engine.config is not None:
        relations = {name: local.get_relation_value(conn, engine.config, row, name) for name in engine.config.list_relations}
    else:
        from countrydle.local_answering import LIST_RELATION_QUERIES

        relations = {
            name: [item[0] for item in conn.execute(sql, (row["id"],) * sql.count("?"))]
            for name, sql in LIST_RELATION_QUERIES.items()
        }
    schema = [tuple(item) for item in conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name")]
    wal = Path(str(engine.db_path) + "-wal")
    return {
        "file": engine.db_path.name,
        "sha256": _digest(engine.db_path),
        "wal_sha256": _digest(wal) if wal.exists() else None,
        "schema_sha256": hashlib.sha256(json.dumps(schema).encode()).hexdigest(),
        "target_row": values,
        "target_relations": relations,
    }


def _server_metadata(engine: _Engine) -> dict:
    from version import SERVER_VERSION

    server = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), Path(local.__file__), Path(engine.module.__file__)]
    if engine.mode not in ("countrydle", *CONTINENTAL_MODES):
        sources.append(server / "countrydle" / "utils.py")
    if engine.mode in ("countrydle", *CONTINENTAL_MODES):
        sources += [server / "countrydle" / "local_planner.py", server / "countrydle" / "local_answering.py"]
    return {
        "version": SERVER_VERSION,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "sources_sha256": {str(path.relative_to(server)): _digest(path) for path in sources},
    }


def _plan(engine: _Engine, question: str, evidence: dict):
    # Legacy cached plans do not record their model/prompt provenance. A fresh
    if engine.mode in ("countrydle", *CONTINENTAL_MODES):
        from countrydle.local_planner import analyze_question_for_local_plan

        return analyze_question_for_local_plan(question, use_cache=False, strict_errors=True, evidence=evidence)
    return local.analyze_question(question, engine.config, use_cache=False, strict_errors=True, evidence=evidence)


def _normalize_answer(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    if value is None:
        return "INVALID"
    raise RuntimeError("Answer provider returned a non-boolean answer")


def _result(answer: Any, explanation: str | None, source: str, plan, evidence: dict) -> dict:
    if explanation is not None and not isinstance(explanation, str):
        raise RuntimeError("Answer provider returned a malformed explanation")
    missing_explanation = explanation is None or not explanation.strip()
    evidence["explanation_missing"] = missing_explanation
    return {
        "answer": _normalize_answer(answer),
        "explanation": "" if missing_explanation else explanation,
        "source": source,
        "interpretation": plan.improved_question,
        "evidence": evidence,
    }


@dataclass(frozen=True)
class _Fallback:
    engine: _Engine
    target: dict
    question: Any
    plan: Any
    evidence: dict


def _evaluate(mode: str, entity: dict, question: str) -> dict | _Fallback:
    engine = _engine(mode)
    entity_id = entity.get("id")
    if not isinstance(entity_id, str):
        raise ValueError("Entity identifier must be a canonical string")
    with closing(_connect(engine.db_path)) as conn:
        row = conn.execute(
            f"SELECT * FROM {engine.table} WHERE {engine.key_column} = ?", (entity_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown entity for this mode")
        target = _entity(engine, row)
        evidence = {
            "version": 2,
            "mode": mode,
            "target": target,
            "original_question": question,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "server": _server_metadata(engine),
            "planner": {},
        }
        # No database transaction, connection or match lock crosses a model call.
    plan = _plan(engine, question, evidence["planner"])
    evidence["planner"]["output"] = asdict(plan)
    if not plan.valid:
        return _result(None, plan.explanation, "local_planner:invalid", plan, evidence)

    with closing(_connect(engine.db_path)) as conn:
        row = conn.execute(
            f"SELECT * FROM {engine.table} WHERE {engine.key_column} = ?", (entity_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("Canonical target disappeared during guidance evaluation")
        evidence["facts"] = _facts(engine, conn, row)
        if plan.supported and plan.plan:
            if mode in ("countrydle", *CONTINENTAL_MODES):
                from countrydle import local_answering as country

                executed_plan = country.normalize_geographic_area_plan(conn, plan.plan)
                answer = country.evaluate_plan_node(conn, executed_plan, row)
                relations = sorted(country.plan_relations(executed_plan))
                explanation = country.generate_factual_explanation(
                    conn, row, executed_plan, answer
                ) if answer is not None else None
            else:
                executed_plan = plan.plan
                answer = local.evaluate(conn, engine.config, row, executed_plan)
                relations = local.collect_relations(executed_plan)
                explanation = local.generate_mode_explanation(engine.config, row, plan, answer, conn) if answer is not None else None
            evidence["execution"] = {"plan": executed_plan, "relations": relations, "answer": answer, "explanation": explanation}
            if answer is not None:
                return _result(answer, explanation, "local_kb", plan, evidence)
    enhanced = engine.module.question_enhanced_from_plan(question, plan)
    return _Fallback(engine, target, enhanced, plan, evidence)


def _fallback_context(request: _Fallback) -> tuple[str, dict]:
    facts = request.evidence["facts"]
    provenance = {"source": "canonical_facts_and_markdown"}
    if request.engine.mode in ("countrydle", *CONTINENTAL_MODES):
        # Countries' SQLite schema has no markdown column. Use the same index
        # as the normal country data population scripts, keyed by canonical name.
        index_path = local.ROOT_DIR / "data" / "countries.csv"
        with index_path.open(newline="", encoding="utf-8") as stream:
            markdown_file = next(
                (row["md_file"] for row in csv.DictReader(stream) if row["name"] == request.target["name"]),
                None,
            )
        provenance["index"] = {"file": str(index_path.relative_to(local.ROOT_DIR)), "sha256": _digest(index_path)}
    else:
        markdown_file = facts["target_row"].get("md_file")
    if not markdown_file:
        raise RuntimeError("Canonical target has no markdown source")
    path = local.ROOT_DIR / markdown_file.replace("\\", "/")
    markdown_bytes = path.read_bytes()
    markdown = markdown_bytes.decode("utf-8")
    if not markdown.strip():
        raise RuntimeError("Canonical target markdown is empty")
    context = (
        "Canonical target facts:\n"
        + json.dumps(facts["target_row"], ensure_ascii=False)
        + "\nCanonical target relations:\n"
        + json.dumps(facts["target_relations"], ensure_ascii=False)
        + "\nCanonical target article:\n"
        + markdown
    )
    provenance["markdown"] = {
        "file": str(path.relative_to(local.ROOT_DIR)),
        "sha256": hashlib.sha256(markdown_bytes).hexdigest(),
    }
    provenance["sha256"] = hashlib.sha256(context.encode("utf-8")).hexdigest()
    return context, provenance


def _answer_fallback(request: _Fallback) -> dict:
    from countrydle.utils import gemini_json

    evidence = request.evidence
    context, evidence["context"] = _fallback_context(request)
    evidence["fallback"] = {"request_timeout_seconds": 30, "max_attempts": 1}
    system_prompt, question_prompt = request.engine.module.answer_prompts(
        request.question, request.target["name"], context,
    )
    result = gemini_json(
        system_prompt, question_prompt, max_output_tokens=768,
        evidence=evidence["fallback"], request_timeout=30, max_attempts=1,
    )
    if not isinstance(result, dict) or "answer" not in result:
        raise RuntimeError("Answer provider returned an invalid response schema")
    # Retain only the public answer and explanation, not arbitrary model fields
    # (which might include unsupported reasoning/chain-of-thought fields).
    evidence["fallback"]["output"] = {"answer": result["answer"], "explanation": result.get("explanation")}
    return _result(result["answer"], result.get("explanation"), "normal_fallback", request.plan, evidence)


async def evaluate_question(mode: str, entity: dict, question: str) -> dict:
    """Answer for the explicit canonical secret. Operational failures propagate."""
    result = await asyncio.to_thread(_evaluate, mode, entity, question)
    if isinstance(result, _Fallback):
        return await asyncio.to_thread(_answer_fallback, result)
    return result
