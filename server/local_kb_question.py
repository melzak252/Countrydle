"""Generic Gemini planner + SQLite executor for local game fact databases."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from planner_protocol import (
    PLANNER_MAX_OUTPUT_TOKENS, PLANNER_OPERATORS, PLANNER_RULES, PLANNER_THINKING_BUDGET, PLANNER_VERSION,
    compile_planner_response, planner_response_schema,
)
from powiat_names import resolve_powiat_name
from voivodeship_names import resolve_voivodeship_name


APP_DIR = Path(__file__).resolve().parent
# In local development this file lives in <repo>/server and data lives in <repo>/data.
# In Docker, docker-compose mounts ./server as /usr/src/app and ./data as /usr/src/app/data.
ROOT_DIR = APP_DIR if (APP_DIR / "data").exists() else APP_DIR.parent


@dataclass(frozen=True)
class LocalModeConfig:
    mode_name: str
    entity_label: str
    target_entity: str
    db_path: Path
    table: str
    name_column: str
    scalar_relations: dict[str, str]
    list_relations: dict[str, tuple[str, str]]
    supported_relations: list[str]
    language: str = "Polish"
    fk_column: str | None = None
    mode_notes: str | None = None
    entity_list_relations: frozenset[str] = frozenset()


@dataclass(frozen=True)
class QuestionPlan:
    original_question: str
    valid: bool
    supported: bool
    improved_question: str | None
    explanation: str | None
    plan: dict[str, Any] | None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class LocalAnswer:
    question: str
    answer: bool | None
    explanation: str
    relations: list[str]


def load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def gemini_json(
    prompt: str, max_output_tokens: int = PLANNER_MAX_OUTPUT_TOKENS, *,
    response_schema: dict[str, Any], evidence: dict | None = None,
) -> dict[str, Any]:
    from utils.ai_clients import generate_gemini_json

    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite"
    return generate_gemini_json(
        prompt, model=model, api_key=key, max_output_tokens=max_output_tokens,
        timeout=60, evidence=evidence, response_schema=response_schema,
        thinking_budget=PLANNER_THINKING_BUDGET if model.startswith("gemini-2.5-flash-lite") else None,
    )


def analyze_question(
    question: str, config: LocalModeConfig, *, use_cache: bool = True,
    strict_errors: bool = False, evidence: dict | None = None,
) -> QuestionPlan:
    from utils.plan_cache import plan_cache

    load_dotenv()
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite"
    relations = "\n".join(f"- {r}" for r in config.supported_relations)
    entity_relations = ", ".join(sorted(config.entity_list_relations)) or "(none)"
    neighbor_example = ""
    if config.entity_list_relations:
        neighbor_relation = min(config.entity_list_relations)
        neighbor_example = f"""
Example for (target population > 100000) OR (any neighbor population > 100000):
{{"route":"local","plan":[
  {{"operator":"greater_than","left":{{"entity":"{config.target_entity}","relation":"population"}},"right":{{"value":100000}}}},
  {{"operator":"greater_than","left":{{"entity":"item","relation":"population"}},"right":{{"value":100000}}}},
  {{"operator":"any","items":{{"entity":"{config.target_entity}","relation":"{neighbor_relation}"}},"args":[1]}},
  {{"operator":"or","args":[0,2]}}
]}}
Nodes 0 and 1 compare the same property and value on DIFFERENT entities; neither can replace the other.
Node 1 belongs only inside quantifier 2. The outer or combines target predicate 0 with quantifier 2,
never with the unbound item predicate 1.
""".strip()
    instruction_prompt = f"""
You are a validator and planner for a yes/no guessing game.
Game mode: {config.mode_name}
Target entity placeholder: {config.target_entity}
Entity type: {config.entity_label}

Supported SQLite relations:
{relations}

Task:
1. Decide whether the user input is a valid yes/no question about the hidden {config.entity_label}.
2. Rewrite it only if translation or clarification is needed; otherwise omit improved_question.
3. If it can be answered from the supported relations, return route="local", plan and any needed improved_question. Do not generate an explanation for a local plan: the executor explains the facts.
4. If a clear question needs external knowledge, return route="fallback", plan=null and a short fallback_reason.
5. If the question needs clarification or is unrelated/open-ended, return route="clarify", plan=null and a short explanation.

Use common names, not long official names. Normalize Polish and informal names when obvious.
When a user explicitly names an entity in the question (e.g. "Czy Kraków jest miastem na prawach powiatu?", "Czy Małopolskie graniczy ze Słowacją?"), do NOT reject it as invalid or clarify. Treat it as testing whether that property holds for the candidate or hidden target.
Do NOT answer the question. Only create the plan.

{PLANNER_RULES.replace("TARGET", config.target_entity)}

Quantified list properties:
- Same-type entity-name lists: {entity_relations}.
- For these lists, item refers to each neighboring {config.entity_label}. Its supported scalar
  and list relations can be read with {{"entity":"item","relation":"RELATION"}}.
- Other lists and literal arrays contain primitive values, not entities. Use item.name for
  their value; their other properties cannot be inspected.
- A nested any/all binds a new item only inside its predicate; its items operand may use
  the enclosing item. {config.target_entity} always refers to the original hidden target.

{neighbor_example}

Self-neighbor rule:
- If the user asks whether the hidden {config.entity_label} borders/neighbors itself
  (Polish: "sąsiaduje z samym sobą"), this is a valid supported question.
- Create a contains_exact plan on the relevant borders_* relation with right as
  the hidden entity name reference, e.g. {{"entity":"{config.target_entity}","relation":"name"}}.
- The executor treats this special self-border/self-neighbor case as true.

Allowed operators:
- contains_exact: exact list membership or complete scalar equality, never a text substring
- contains_partial: substring match, preserving the old broad contains behavior
- equals: scalar equals value
- greater_than, less_than: strict numeric comparisons >, <
- greater_than_or_equal, less_than_or_equal: inclusive numeric comparisons >=, <=
- west_of: left longitude < right longitude (further west in signed coordinates)
- east_of: left longitude > right longitude (further east in signed coordinates)
- north_of: left latitude > right latitude (further north in signed coordinates)
- south_of: left latitude < right latitude (further south in signed coordinates)
- exists: relation has any value / boolean is true
- starts_with, ends_with, has_space, has_hyphen
- contains_text: a substring inside text, including letters or punctuation inside a name
- word_count_equals, word_count_greater_than, word_count_less_than
- char_count_equals, char_count_greater_than, char_count_less_than
- and, or, not
- any, all: quantify a list with a predicate on item, preserving all requested property filters

Geographic Direction / Coordinate rules:
- Longitudes in the Americas / USA are negative decimal degrees (e.g. 74° W is -74.0, 71.5° W is -71.5).
- For questions like "further west than 74° W" or "west of 74° W":
  ALWAYS use operator "west_of" (e.g. {{"operator":"west_of","left":{{"entity":"{config.target_entity}","relation":"longitude"}},"right":{{"value":-74.0}}}}).
  NEVER use greater_than for "further west than" with negative numbers!
- For relative cardinal directions comparing position to another named entity (e.g. "na zachód od Warszawy", "west of Warsaw"):
  use operator "west_of" with left={{"entity":"{config.target_entity}","relation":"longitude"}} and right={{"entity":"Warszawa","relation":"longitude"}}.
- For "na wschód od" / "east of": use operator "east_of" comparing relation "longitude".
- For "na północ od" / "north of": use operator "north_of" comparing relation "latitude".
- For "na południe od" / "south of": use operator "south_of" comparing relation "latitude".
Reference format examples:
{{"entity":"{config.target_entity}","relation":"population"}}
{{"entity":"{config.target_entity}","relation":"name"}}

For a single predicate, put its node in a one-element plan array.
Return STRICT JSON only:
{{
  "route": "local",
  "plan": [{{...}}]
}}

Invalid format:
{{"route": "clarify", "explanation": "...", "plan": null}}

Unsupported format:
{{"route": "fallback", "improved_question": "...", "plan": null, "fallback_reason": "unsupported relation"}}
Mode-specific planning notes (apply these to positive predicates AND their negations):
{config.mode_notes or "- None"}

""".strip()
    prompt = f"{instruction_prompt}\n\nUser question: {question}"
    allowed_relations = config.scalar_relations.keys() | config.list_relations.keys() | {"name"}
    operators = (PLANNER_OPERATORS - {"contains"}) | {"contains_exact", "contains_partial", "any", "all"}
    allow_named_entities = config.mode_name in {"Countrydle", "Powiatdle", "USStatedle", "Wojewodztwodle"}
    schema = planner_response_schema(
        relations=allowed_relations, operators=operators, target_entity=config.target_entity,
        allow_named_entities=allow_named_entities,
    )
    semantic_config = {
        "prompt": instruction_prompt, "schema": schema, "table": config.table,
        "name_column": config.name_column, "fk_column": config.fk_column,
        "scalar_relations": config.scalar_relations, "list_relations": config.list_relations,
        "language": config.language, "entity_relations": sorted(config.entity_list_relations),
        "generation": {"temperature": 0, "max_output_tokens": PLANNER_MAX_OUTPUT_TOKENS,
                       "thinking_budget": PLANNER_THINKING_BUDGET if model.startswith("gemini-2.5-flash-lite") else None},
    }
    identity = hashlib.sha256(json.dumps(
        semantic_config, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    version = f"{PLANNER_VERSION}:{model}:{identity}"
    cached = plan_cache.get(config.mode_name, question, version=version) if use_cache else None
    if evidence is not None:
        evidence.update(provider="gemini", model=model, contract_version=PLANNER_VERSION,
                        semantic_identity=identity, cache_identity=version,
                        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                        cache_hit=cached is not None, cache_origin="unknown" if cached is not None else None)
    if cached is not None:
        return replace(cached, original_question=question)
    try:
        from generic_template_compiler import compile_generic_template_plan
        tpl_res = compile_generic_template_plan(question, config.mode_name)
    except Exception:
        tpl_res = None
    if tpl_res is not None:
        tpl_ast, tpl_improved = tpl_res
        plan = QuestionPlan(
            original_question=question, valid=True, supported=True,
            improved_question=tpl_improved, explanation="Deterministic template match.",
            plan=tpl_ast,
        )
        if evidence is not None:
            evidence["provider"] = "template"
        if use_cache:
            plan_cache.set(config.mode_name, question, plan, version=version)
        return plan
    data = gemini_json(prompt, response_schema=schema, evidence=evidence)
    ast = compile_planner_response(
        data, relations=allowed_relations, operators=operators, target_entity=config.target_entity,
        allow_named_entities=allow_named_entities,
    )
    if evidence is not None:
        evidence.update(
            provider="gemini",
            model=os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite",
            prompt=prompt, temperature=0, max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS, cache_hit=False,
        )
    plan = QuestionPlan(
        original_question=question,
        valid=data["route"] != "clarify",
        supported=data["route"] == "local",
        improved_question=data.get("improved_question"),
        explanation=data.get("explanation"),
        plan=ast,
        fallback_reason=data.get("fallback_reason"),
    )
    if use_cache:
        plan_cache.set(config.mode_name, question, plan, version=version)
    return plan


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def get_entity_row(conn: sqlite3.Connection, config: LocalModeConfig, entity_name: str) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        f"SELECT * FROM {config.table} WHERE {config.name_column} = ? COLLATE NOCASE",
        (entity_name,),
    ).fetchone()
    if row:
        return row
    if config.mode_name == "Wojewodztwodle":
        resolved_v = resolve_voivodeship_name(entity_name)
        if resolved_v:
            row = conn.execute(f"SELECT * FROM {config.table} WHERE {config.name_column} = ?", (resolved_v,)).fetchone()
            if row:
                return row
    target_norm = norm(entity_name)
    all_rows = conn.execute(f"SELECT * FROM {config.table}").fetchall()
    for r in all_rows:
        if norm(r[config.name_column]) == target_norm:
            return r
        if "seat" in r.keys() and r["seat"] and norm(r["seat"]) == target_norm:
            return r
    return None


def get_relation_value(conn: sqlite3.Connection, config: LocalModeConfig, row: sqlite3.Row, relation: str) -> Any:
    if relation in config.scalar_relations:
        col = config.scalar_relations[relation]
        return row[col]
    if relation in config.list_relations:
        table, column = config.list_relations[relation]
        fk_column = config.fk_column or f"{config.table[:-1]}_id"
        if config.mode_name == "Powiatdle" and relation in {"borders_powiat", "borders_voivodeship"}:
            values = conn.execute(
                f"SELECT facts.{column} FROM powiat_border_coverage AS coverage "
                f"LEFT JOIN {table} AS facts ON facts.{fk_column} = coverage.powiat_id "
                "WHERE coverage.powiat_id = ?",
                (row["id"],),
            ).fetchall()
            return [value[0] for value in values if value[0] is not None] if values else None
        return [r[0] for r in conn.execute(f"SELECT {column} FROM {table} WHERE {fk_column} = ?", (row["id"],)).fetchall()]
    return None


def _reference_row(conn: sqlite3.Connection, config: LocalModeConfig, row: sqlite3.Row, node: Any, item_value: Any) -> sqlite3.Row | None:
    if isinstance(node, dict):
        if node.get("entity") == config.target_entity:
            return row
        if node.get("entity") == "item" and isinstance(item_value, sqlite3.Row):
            return item_value
        entity_name = node.get("entity")
        if entity_name and entity_name not in {config.target_entity, "item"}:
            return get_entity_row(conn, config, entity_name)
    return None


def resolve_ref(conn: sqlite3.Connection, config: LocalModeConfig, row: sqlite3.Row, node: Any, item_value: Any = None) -> Any:
    if isinstance(node, dict) and set(node.keys()) == {"value"}:
        return node.get("value")
    entity_row = _reference_row(conn, config, row, node, item_value)
    if entity_row is not None:
        return get_relation_value(conn, config, entity_row, node.get("relation", ""))
    if isinstance(node, dict) and node.get("entity") == "item":
        return item_value if node.get("relation") == "name" else None
    return node


def text_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def is_self_reference(value: Any, row: sqlite3.Row, config: LocalModeConfig) -> bool:
    if value is None:
        return False
    value_norm = norm(value)
    target_norm = norm(row[config.name_column])
    return value_norm == target_norm or value_norm in {
        "itself",
        "it self",
        "same state",
        "same entity",
        "self",
        "samym soba",
        "samym sobą",
        "sobą",
        "soba",
    }


def _canonical_us_region(value: Any) -> Any:
    """Canonicalize a spelling alias, not a different regional category."""
    if isinstance(value, str) and re.fullmatch(r"north[\s\-\u2010-\u2015]*east", value.strip(), re.I):
        return "Northeast"
    return value


def evaluate(
    conn: sqlite3.Connection,
    config: LocalModeConfig,
    row: sqlite3.Row,
    node: dict[str, Any],
    item_value: Any = None,
) -> bool | None:
    op = node.get("operator")
    if op in {"and", "or"}:
        conditions = node.get("conditions", [])
        if not conditions:
            return None
        decisive = op == "or"
        unknown = False
        for condition in conditions:
            value = evaluate(conn, config, row, condition, item_value)
            if value is decisive:
                return decisive
            unknown = unknown or value is None
        return None if unknown else not decisive
    if op in config.list_relations or (isinstance(op, str) and op.startswith("borders_")):
        rel_name = op if op in config.list_relations else ("borders_state" if "state" in op else ("borders_country" if "country" in op else ("borders_voivodeship" if "voivodeship" in op else "borders_powiat")))
        rel_items = get_relation_value(conn, config, row, rel_name)
        if not isinstance(rel_items, list) and not (
            config.mode_name == "Powiatdle" and rel_name == "borders_powiat"
        ):
            return None
        right_node = node.get("right", node.get("value"))
        right_val = resolve_ref(conn, config, row, right_node, item_value)
        if isinstance(right_val, dict):
            right_val = right_val.get("value", right_val.get("entity"))
        if is_self_reference(right_val, row, config):
            return True
        if config.mode_name == "Powiatdle" and rel_name == "borders_powiat":
            right_val = resolve_powiat_name(conn, right_val)
        if rel_name == "borders_voivodeship" or (config.mode_name == "Powiatdle" and rel_name == "voivodeship"):
            resolved_v = resolve_voivodeship_name(right_val)
            if resolved_v is not None:
                right_val = resolved_v
        if config.mode_name == "USStatedle" and rel_name in {"region", "division", "regional_labels"}:
            right_val = _canonical_us_region(right_val)
            if isinstance(rel_items, list):
                rel_items = [_canonical_us_region(value) for value in rel_items]
        if right_val is None:
            return None
        if is_self_reference(right_val, row, config):
            return True
        if isinstance(rel_items, list):
            return any(norm(value) == norm(right_val) for value in rel_items)
        return None

    if op == "not":
        sub_node = node.get("condition") or node.get("operand") or {}
        value = evaluate(conn, config, row, sub_node, item_value)
        return None if value is None else not value
    if op in {"any", "all"}:
        items_node = node.get("items", {})
        items = resolve_ref(conn, config, row, items_node, item_value)
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return None
        item_rows = {}
        if items and isinstance(items_node, dict) and items_node.get("relation") in config.entity_list_relations:
            placeholders = ",".join("?" for _ in items)
            neighbors = conn.execute(
                f"SELECT * FROM {config.table} WHERE {config.name_column} IN ({placeholders})",
                items,
            )
            item_rows = {neighbor[config.name_column]: neighbor for neighbor in neighbors}
        decisive = op == "any"
        unknown = False
        for item in items:
            bound_item = item_rows.get(item, item) if item_rows else item
            value = evaluate(conn, config, row, condition, bound_item)
            if value is decisive:
                return decisive
            unknown = unknown or value is None
        return None if unknown else not decisive

    left_node = node.get("left")
    right_node = node.get("right", node.get("value"))

    # USStatedle convenience: users often ask about coast names, but the DB stores
    # concrete water bodies. Treat planner outputs such as region == "East Coast"
    # as derived checks against water_access so New York/California/etc. work.
    if config.mode_name == "USStatedle" and isinstance(left_node, dict):
        relation = left_node.get("relation")
        coast = norm(right_node)
        if relation in {"region", "division", "water_access"} and coast in {
            "east coast", "eastern coast", "wschodnie wybrzeze", "wschodnie wybrzeże",
            "west coast", "western coast", "zachodnie wybrzeze", "zachodnie wybrzeże",
            "gulf coast", "wybrzeze zatoki", "wybrzeże zatoki",
            "great lakes", "wielkie jeziora",
        }:
            waters = get_relation_value(conn, config, row, "water_access") or []
            if coast in {"east coast", "eastern coast", "wschodnie wybrzeze", "wschodnie wybrzeże"}:
                return any(norm(w) == "atlantic ocean" for w in waters)
            if coast in {"west coast", "western coast", "zachodnie wybrzeze", "zachodnie wybrzeże"}:
                return any(norm(w) == "pacific ocean" for w in waters)
            if coast in {"gulf coast", "wybrzeze zatoki", "wybrzeże zatoki"}:
                return any(norm(w) == "gulf of mexico" for w in waters)
            if coast in {"great lakes", "wielkie jeziora"}:
                return any(norm(w).startswith("lake ") for w in waters)
        if relation == "major_highways" and right_node is not None:
            raw_hw = resolve_ref(conn, config, row, right_node, item_value)
            if isinstance(raw_hw, str):
                hw_match = re.search(r"\b(?:interstate|i)[\s-]+(\d+)\b", raw_hw, re.I)
                if hw_match:
                    normalized_hw = f"I-{hw_match.group(1)}"
                    highways = get_relation_value(conn, config, row, "major_highways") or []
                    return any(norm(h) == norm(normalized_hw) for h in highways)

        if relation == "major_rivers" and right_node is not None:
            raw_riv = resolve_ref(conn, config, row, right_node, item_value)
            if isinstance(raw_riv, str):
                clean_riv = re.sub(r"\b(river|rzeka|rzeki)\b", "", raw_riv, flags=re.I).strip()
                rivers = get_relation_value(conn, config, row, "major_rivers") or []
                return any(norm(clean_riv) == norm(r) or norm(clean_riv) in norm(r) or norm(r) in norm(clean_riv) for r in rivers)

        if relation == "nickname" and right_node is not None:
            raw_nick = resolve_ref(conn, config, row, right_node, item_value)
            if isinstance(raw_nick, str):
                actual_nick = row["nickname"] or ""
                clean_actual = re.sub(r"^the\s+", "", norm(actual_nick)).strip()
                clean_queried = re.sub(r"^the\s+", "", norm(raw_nick)).strip()
                if op in {"contains_text", "contains_partial"}:
                    return clean_queried in clean_actual
                return clean_actual == clean_queried

    left = resolve_ref(conn, config, row, left_node, item_value)
    right = resolve_ref(conn, config, row, right_node, item_value)
    if (
        config.mode_name == "USStatedle"
        and isinstance(left_node, dict)
        and left_node.get("relation") in {"region", "division", "regional_labels"}
        and op in {"contains", "contains_exact", "equals", "exists"}
    ):
        # Apply at each predicate so existing nested/negated cached ASTs agree
        # with new deterministic plans without weakening exact membership.
        left = [_canonical_us_region(value) for value in left] if isinstance(left, list) else _canonical_us_region(left)
        right = _canonical_us_region(right)
    if config.mode_name in {"Wojewodztwodle", "Powiatdle"} and isinstance(left_node, dict) and left_node.get("relation") in {"water_access", "is_coastal"}:
        if config.mode_name == "Wojewodztwodle":
            is_coast = bool(row["is_coastal"])
        else:
            is_coast = bool(conn.execute("SELECT 1 FROM powiat_water_access WHERE powiat_id = ? LIMIT 1", (row["id"],)).fetchone())
        if op == "exists":
            return is_coast
        if right in {True, 1, "true", "True"} or norm(right) in {"morze", "baltyk", "morze baltyckie", "baltyckie", "sea", "baltic sea", "baltic"}:
            return is_coast
        if right in {False, 0, "false", "False"}:
            return not is_coast
    left_row = _reference_row(conn, config, row, left_node, item_value)
    if (
        config.mode_name == "Powiatdle"
        and isinstance(left_node, dict)
        and left_node.get("relation") == "borders_powiat"
        and op in {"contains", "contains_exact", "contains_partial", "equals"}
        and not (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit()))
    ):
        if left_row is not None and is_self_reference(right, left_row, config):
            return True
        right = resolve_powiat_name(conn, right)
        if right is None:
            return None
        if left_row is not None and right == left_row[config.name_column]:
            return True
    if (
        isinstance(left_node, dict)
        and (
            left_node.get("relation") == "borders_voivodeship"
            or (config.mode_name == "Powiatdle" and left_node.get("relation") == "voivodeship")
            or (config.mode_name == "Wojewodztwodle" and left_node.get("relation") == "name")
        )
        and op in {"contains", "contains_exact", "contains_partial", "equals"}
        and not (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit()))
    ):
        if left_row is not None and is_self_reference(right, left_row, config):
            return True
        resolved_v = resolve_voivodeship_name(right)
        if resolved_v is not None:
            right = resolved_v
        if left_row is not None and right == left_row[config.name_column]:
            return True
    if left is None or (op not in {"has_space", "has_hyphen", "exists"} and right is None):
        return None

    # Game rule inherited from the old prompts: if the user asks whether the
    # referenced entity borders/neighbors itself, answer true. We do not store
    # self-edges in SQLite border tables, so handle it explicitly for all modes.
    if op in {"contains", "contains_exact", "equals"} and isinstance(left_node, dict):
        relation = str(left_node.get("relation") or "")
        if relation.startswith("borders_") and left_row is not None and is_self_reference(right, left_row, config):
            return True
    if op == "exists":
        # If right/value is provided, the planner intended membership check (e.g. water_access contains "Gulf of Mexico")
        if right is not None:
            if isinstance(left, list):
                return any(norm(v) == norm(right) for v in left)
            return norm(left) == norm(right)
        if isinstance(left, list):
            return len(left) > 0
        return bool(left)
    if op in {"contains", "contains_exact", "equals"}:
        if isinstance(left, list):
            if type(right) is not bool and (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit())):
                return float(len(left)) == float(right)
            return any(norm(v) == norm(right) for v in left)
        if isinstance(left, (bool, int, float)) and isinstance(right, (bool, int, float)):
            return left == right
        n_left = norm(left)
        n_right = norm(right)
        if n_left == n_right:
            return True
        if config.mode_name == "Powiatdle" and isinstance(left_node, dict) and left_node.get("relation") == "name":
            resolved_r = resolve_powiat_name(conn, right)
            if resolved_r and norm(resolved_r) == n_left:
                return True
            resolved_l = resolve_powiat_name(conn, left)
            if resolved_l and resolved_r and resolved_l == resolved_r:
                return True
            clean_left = re.sub(r"\s*\([^)]*\)", "", n_left).replace("powiat ", "").strip()
            clean_right = re.sub(r"\s*\([^)]*\)", "", n_right).replace("powiat ", "").strip()
            return clean_left == clean_right
        return False
    if op == "contains_partial":
        if isinstance(left, list):
            return any(norm(v) == norm(right) or norm(right) in norm(v) for v in left)
        return norm(right) in norm(left)
    if op in {"greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "west_of", "east_of", "north_of", "south_of"}:
        if isinstance(left, list) and type(right) is not bool and (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit())):
            lnum, rnum = float(len(left)), float(right)
        else:
            try:
                lnum, rnum = float(left), float(right)
            except (TypeError, ValueError):
                return None
        if op == "greater_than_or_equal":
            return lnum >= rnum
        if op == "less_than_or_equal":
            return lnum <= rnum

        if op in {"greater_than", "east_of", "north_of"}:
            return lnum > rnum
        return lnum < rnum
    txt = text_value(left)
    n_txt = norm(txt)
    n_right = norm(right)
    if op == "starts_with":
        return n_txt.startswith(n_right)
    if op == "ends_with":
        return n_txt.endswith(n_right)
    if op == "contains_text":
        return n_right in n_txt
    if op == "has_space":
        return " " in txt.strip()
    if op == "has_hyphen":
        return any(char in txt for char in "-\u2010\u2011")
    words = [w for w in re.split(r"\s+", txt.strip()) if w]
    chars = len(re.sub(r"\s+", "", txt))
    try:
        num = int(right)
    except (TypeError, ValueError):
        return None
    if op in {"word_count_equals", "word_count_greater_than", "word_count_less_than"}:
        count = len(left) if isinstance(left, list) else len(words)
        try:
            num = int(right)
        except (TypeError, ValueError):
            return None
        if op == "word_count_equals":
            return count == num
        if op == "word_count_greater_than":
            return count > num
        if op == "word_count_less_than":
            return count < num
    if op == "char_count_equals":
        if isinstance(left, list):
            return any(len(str(item).strip()) == num for item in left)
        return chars == num
    if op == "char_count_greater_than":
        if isinstance(left, list):
            return any(len(str(item).strip()) > num for item in left)
        return chars > num
    if op == "char_count_less_than":
        if isinstance(left, list):
            return any(len(str(item).strip()) < num for item in left)
        return chars < num
    return None


def collect_relations(node: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        if "relation" in node:
            found.add(str(node["relation"]))
        for value in node.values():
            found.update(collect_relations(value))
    elif isinstance(node, list):
        for value in node:
            found.update(collect_relations(value))
    return sorted(found)

def generate_mode_explanation(
    config: LocalModeConfig,
    row: sqlite3.Row,
    plan: QuestionPlan,
    answer: bool | None,
    conn: sqlite3.Connection,
    *,
    item_value: Any = None,
) -> str:
    target_row = row
    polish = config.language == "Polish"
    verdict = ("Tak" if answer else "Nie") if polish else ("Yes" if answer else "No")
    if answer is None:
        verdict = "Brak danych" if polish else "Unknown"
    node = plan.plan or {}
    op = node.get("operator") if isinstance(node, dict) else None
    left = node.get("left", {}) if isinstance(node, dict) else {}
    rel = left.get("relation") if isinstance(left, dict) else None
    if not rel and isinstance(op, str) and (op in config.list_relations or op.startswith("borders_")):
        rel = op if op in config.list_relations else (
            "borders_state" if "state" in op else "borders_country" if "country" in op
            else "borders_voivodeship" if "voivodeship" in op else "borders_powiat"
        )
        left = {"entity": config.target_entity, "relation": rel}
    right_node = node.get("right", node.get("value")) if isinstance(node, dict) else None
    val = resolve_ref(conn, config, target_row, right_node, item_value)
    subject_row = _reference_row(conn, config, target_row, left, item_value)
    row = subject_row if subject_row is not None else target_row
    name = row[config.name_column]

    def value_text(value: Any) -> str:
        if value is None or isinstance(value, dict):
            return "brak danych" if polish else "unknown"
        if isinstance(value, list):
            return ", ".join(value_text(item) for item in value) if value else ("brak" if polish else "none")
        if isinstance(value, bool):
            return ("tak" if value else "nie") if polish else ("yes" if value else "no")
        if isinstance(value, (int, float)):
            return f"{value:,}".removesuffix(".0").replace(",", " " if polish else ",")
        return str(value)

    def reference_fact(reference: Any) -> str:
        value = resolve_ref(conn, config, target_row, reference, item_value)
        relation = reference.get("relation") if isinstance(reference, dict) else None
        referenced_row = _reference_row(conn, config, target_row, reference, item_value)
        subject = referenced_row[config.name_column] if referenced_row is not None else None
        if isinstance(reference, dict) and reference.get("entity") == "item" and subject is None:
            subject = item_value if not isinstance(item_value, (dict, sqlite3.Row)) else None
        labels = {
            "name": "nazwa", "population": "populacja", "area": "powierzchnia",
            "population_density": "gęstość zaludnienia", "urbanization": "urbanizacja",
            "latitude": "szerokość geograficzna", "longitude": "długość geograficzna",
            "seat": "siedziba", "macroregion": "makroregion", "voivodeship": "województwo",
            "is_coastal": "dostęp do morza", "is_city_county": "miasto na prawach powiatu",
            "borders_state": "sąsiednie stany", "borders_country": "sąsiednie państwa",
            "borders_voivodeship": "sąsiednie województwa", "borders_powiat": "sąsiednie powiaty",
            "water_access": "dostęp do wód", "major_rivers": "główne rzeki",
            "major_roads": "główne drogi", "major_highways": "główne autostrady",
            "mountain_ranges": "pasma górskie", "national_parks": "parki narodowe",
            "major_lakes": "duże jeziora", "lakes": "jeziora", "unesco_sites": "obiekty UNESCO",
            "health_resorts": "uzdrowiska", "registration_plates": "wyróżniki tablic",
            "historical_region": "regiony historyczne", "historical_regions": "regiony historyczne",
            "historical_partitions": "zabory", "landform_regions": "regiony geograficzne",
            "regional_labels": "określenia regionalne", "region": "region", "division": "podregion",
            "nickname": "przydomek", "civil_war_side": "strona wojny secesyjnej",
            "admission_year": "rok przyjęcia do Unii", "admission_order": "kolejność przyjęcia do Unii",
            "gmina_count": "liczba gmin", "urban_gmina_count": "liczba gmin miejskich",
            "rural_gmina_count": "liczba gmin wiejskich", "urban_rural_gmina_count": "liczba gmin miejsko-wiejskich",
            "powiat_count": "liczba powiatów", "city_count": "liczba miast",
            "city_count_with_powiat_rights": "liczba miast na prawach powiatu",
        }
        label = labels.get(relation, str(relation or "").replace("_", " ")) if polish else str(relation or "").replace("_", " ")
        text = value_text(value)
        if relation in {"latitude", "longitude"} and isinstance(value, (int, float)):
            positive, negative = ("E", "W") if relation == "longitude" else ("N", "S")
            text = f"{value_text(abs(value))}° {negative if value < 0 else positive}"
        elif relation == "area" and isinstance(value, (int, float)):
            text += " mi²" if "sq_mi" in config.scalar_relations.get("area", "") else " km²"
        elif relation == "population_density" and isinstance(value, (int, float)):
            text += " / km²"
        elif relation == "urbanization" and isinstance(value, (int, float)):
            text += "%"
        if isinstance(value, list):
            label += f" ({len(value)})"
        prefix = f"{subject} — " if subject is not None else ""
        return f"{prefix}{label}: {text}" if label else text

    def factual_fallback() -> str:
        facts = [reference_fact(left)]
        if isinstance(right_node, dict) and "entity" in right_node:
            right_fact = reference_fact(right_node)
            if right_fact not in facts:
                facts.append(right_fact)
        left_value = resolve_ref(conn, config, target_row, left, item_value)
        if isinstance(op, str) and op.startswith("word_count_") and isinstance(left_value, str):
            label = "liczba słów" if polish else "word count"
            facts.append(f"{label}: {len(left_value.split())}")
        if isinstance(op, str) and op.startswith("char_count_"):
            label = "liczba znaków" if polish else "character count"
            if isinstance(left_value, list):
                facts.append(f"{label}: " + ", ".join(f"{value_text(item)} ({len(str(item).strip())})" for item in left_value))
            elif isinstance(left_value, str):
                characters = len(re.sub(r"\s+", "", left_value))
                facts.append(f"{label}: {characters}")
        return f"{verdict} - {'; '.join(facts)}."

    def child_facts(
        child: dict[str, Any], child_answer: bool | None, bound_item: Any = item_value,
    ) -> str:
        explanation = generate_mode_explanation(
            config, target_row, replace(plan, plan=child), child_answer, conn, item_value=bound_item,
        )
        for prefix in ("Tak - ", "Nie - ", "Yes - ", "No - ", "Brak danych - ", "Unknown - "):
            if explanation.startswith(prefix):
                explanation = explanation[len(prefix):]
                break
        return explanation.rstrip(".")

    if op == "not":
        child = node.get("condition") or node.get("operand") or {}
        child_answer = None if answer is None else not answer
        return f"{verdict} - {child_facts(child, child_answer)}."
    if op in {"and", "or"}:
        facts = []
        decisive = op == "or"
        for child in node.get("conditions", []):
            child_answer = evaluate(conn, config, target_row, child, item_value)
            facts.append(child_facts(child, child_answer))
            if child_answer is decisive:
                break
        return f"{verdict} - {'; '.join(facts)}."
    if op in {"any", "all"}:
        items_node = node.get("items", {})
        items = resolve_ref(conn, config, target_row, items_node, item_value)
        facts = [reference_fact(items_node)]
        if isinstance(items, list):
            item_rows = {}
            if items and isinstance(items_node, dict) and items_node.get("relation") in config.entity_list_relations:
                placeholders = ",".join("?" for _ in items)
                neighbors = conn.execute(
                    f"SELECT * FROM {config.table} WHERE {config.name_column} IN ({placeholders})", items,
                )
                item_rows = {neighbor[config.name_column]: neighbor for neighbor in neighbors}
            condition = node.get("condition") or {}
            decisive = op == "any"
            for item in items:
                bound_item = item_rows.get(item, item) if item_rows else item
                child_answer = evaluate(conn, config, target_row, condition, bound_item)
                facts.append(child_facts(condition, child_answer, bound_item))
                if child_answer is decisive:
                    break
        return f"{verdict} - {'; '.join(facts)}."

    membership_ops = {"contains", "contains_exact", "contains_partial", "equals", "exists", rel}
    numeric_value = type(val) is not bool and (isinstance(val, (int, float)) or (isinstance(val, str) and val.isdigit()))
    if answer is None or (
        rel in config.list_relations and (
            op not in membership_ops or (op == "exists" and val is not None) or type(val) is bool
            or (numeric_value and rel not in {"borders_state", "borders_voivodeship", "borders_powiat"})
            or (val is not None and (val == "" or isinstance(val, (list, dict))))
        )
    ) or (
        isinstance(right_node, dict) and "entity" in right_node
        and right_node.get("relation") != "name" and rel not in {"longitude", "latitude"}
    ) or (isinstance(left, dict) and left.get("entity") == "item" and subject_row is None):
        return factual_fallback()

    if rel in {"longitude", "latitude"} and op in {
        "greater_than", "less_than", "west_of", "east_of", "north_of", "south_of", "equals",
        "greater_than_or_equal", "less_than_or_equal",
    }:
        left_value = resolve_ref(conn, config, target_row, left, item_value)
        try:
            coord, threshold = float(left_value), float(val)
        except (TypeError, ValueError):
            pass
        else:
            positive, negative = ("E", "W") if rel == "longitude" else ("N", "S")
            coord_text = f"{abs(coord)}° {negative if coord < 0 else positive}"
            threshold_text = f"{abs(threshold)}° {negative if threshold < 0 else positive}"
            if op == "greater_than_or_equal":
                comparison = ">="
            elif op == "less_than_or_equal":
                comparison = "<="
            else:
                comparison = "=" if op == "equals" else (">" if op in {"greater_than", "east_of", "north_of"} else "<")
            if config.language == "Polish":
                axis = "długości geograficznej" if rel == "longitude" else "szerokości geograficznej"
                if coord == threshold:
                    position = f"na tej samej {axis} co"
                elif rel == "longitude":
                    position = "na wschód od" if coord > threshold else "na zachód od"
                else:
                    position = "na północ od" if coord > threshold else "na południe od"
                verdict = "Tak" if answer else "Nie"
                condition = "prawdziwy" if answer else "fałszywy"
                reference_name = _reference_row(conn, config, target_row, right_node, item_value)
                reference_text = f" ({reference_name[config.name_column]})" if reference_name is not None else ""
                return f"{verdict} - {name} leży na {axis} {coord_text} ({position} {threshold_text}{reference_text}; warunek {coord} {comparison} {threshold} jest {condition})."
            if coord == threshold:
                position = f"at the same {rel} as"
            elif rel == "longitude":
                position = "east of" if coord > threshold else "west of"
            else:
                position = "north of" if coord > threshold else "south of"
            reference_name = _reference_row(conn, config, target_row, right_node, item_value)
            reference_text = f" ({reference_name[config.name_column]})" if reference_name is not None else ""
            return f"{verdict} - {name} is located at {rel} {coord_text} ({position} {threshold_text}{reference_text}; the condition {coord} {comparison} {threshold} is {'true' if answer else 'false'})."

    if config.language == "Polish":
        if rel in {"is_coastal", "water_access"}:
            label = "Powiat" if config.mode_name == "Powiatdle" else "Województwo"
            coastal = bool(row["is_coastal"]) if config.mode_name == "Wojewodztwodle" else bool(get_relation_value(conn, config, row, "water_access"))
            return f"{label} {name} ma bezpośredni dostęp do Morza Bałtyckiego." if coastal else f"{label} {name} nie ma dostępu do morza (jest jednostką śródlądową)."
        if rel == "national_parks" and (op == "exists" or not val):
            parks = [r[0] for r in conn.execute("SELECT park_name FROM powiat_national_parks WHERE powiat_id=?", (row["id"],))]
            return f"Na terenie {name} znajduje się park narodowy: {', '.join(parks)}." if answer else f"Na terenie {name} nie ma parku narodowego."
        if rel == "national_parks" and val:
            return f"Na terenie {name} znajduje się: {val}." if answer else f"Na terenie {name} nie leży {val}."
        if rel in {"major_lakes", "lakes"} and (op == "exists" or not val):
            lakes = [r[0] for r in conn.execute("SELECT lake_name FROM powiat_lakes WHERE powiat_id=?", (row["id"],))]
            return f"W {name} znajduje się jezioro / zbiornik wodny: {', '.join(lakes)}." if answer else f"W {name} nie ma dużego jeziora ani zbiornika."
        if rel in {"major_lakes", "lakes"} and val:
            return f"W {name} znajduje się: {val}." if answer else f"W {name} nie leży {val}."
        if rel == "unesco_sites" and (op == "exists" or not val):
            sites = [r[0] for r in conn.execute("SELECT site_name FROM powiat_unesco_sites WHERE powiat_id=?", (row["id"],))]
            return f"Na terenie {name} znajduje się obiekt z listy UNESCO: {', '.join(sites)}." if answer else f"Na terenie {name} nie ma obiektu z listy UNESCO."
        if rel == "unesco_sites" and val:
            return f"Na terenie {name} znajduje się obiekt UNESCO: {val}." if answer else f"Na terenie {name} nie leży obiekt UNESCO: {val}."
        if rel == "health_resorts":
            spas = [r[0] for r in conn.execute("SELECT resort_name FROM powiat_health_resorts WHERE powiat_id=?", (row["id"],))]
            return f"Na terenie {name} znajduje się uzdrowisko: {', '.join(spas)}." if spas else f"Na terenie {name} nie ma statutowego uzdrowiska."
        if rel == "borders_voivodeship" and val:
            borders = get_relation_value(conn, config, row, rel) or []
            entity_name = f"Województwo {name}" if config.target_entity == "target_voivodeship" else name
            if isinstance(val, (int, float)) or (isinstance(val, str) and str(val).isdigit()):
                b_str = f" ({', '.join(borders)})" if borders else ""
                return f"{entity_name} graniczy z {len(borders)} sąsiednimi województwami{b_str}."
            display_val = resolve_voivodeship_name(val) or val
            if answer:
                return f"{entity_name} graniczy z: {display_val}."
            neighbors = f" Graniczy z: {', '.join(borders)}." if borders else ""
            return f"{entity_name} nie graniczy z {display_val}.{neighbors}"
        if rel == "borders_powiat" and val:
            borders = get_relation_value(conn, config, row, rel) or []
            if isinstance(val, (int, float)) or (isinstance(val, str) and str(val).isdigit()):
                b_str = f" ({', '.join(borders)})" if borders else ""
                name_display = name if name.startswith("Powiat") else f"Powiat {name}"
                return f"{name_display} graniczy z {len(borders)} sąsiednimi powiatami{b_str}."
        if rel == "borders_country" and val:
            country_instr = {
                "Niemcy": "Niemcami", "Czechy": "Czechami", "Słowacja": "Słowacją",
                "Ukraina": "Ukrainą", "Białoruś": "Białorusią", "Litwa": "Litwą", "Rosja": "Rosją",
            }
            val_instr = country_instr.get(val, val)
            prep = "ze" if val in {"Słowacja", "Słowacją"} else "z"
            return f"{name} graniczy {prep} {val_instr}." if answer else f"{name} nie graniczy {prep} {val_instr}."
        if rel == "seat":
            return f"Siedzibą {name} jest {row['seat']}."
        if rel == "major_roads" and val:
            label = "Województwo" if config.mode_name == "Wojewodztwodle" else "Powiat"
            return f"Przez {label} {name} przebiega {val}." if answer else f"Przez {label} {name} nie przebiega {val}."
        if rel == "major_rivers" and val:
            label = "Województwo" if config.mode_name == "Wojewodztwodle" else "Powiat"
            return f"Przez {label} {name} przepływa {val}." if answer else f"Przez {label} {name} nie przepływa {val}."
        if rel == "macroregion":
            return f"{name} leży w makroregionie: {row['macroregion']}."
        if rel == "registration_plates" and val:
            plates = [r[0] for r in conn.execute("SELECT plate_code FROM powiat_registration_plates WHERE powiat_id=?", (row["id"],))]
            if isinstance(val, (int, float)) or (isinstance(val, str) and str(val).isdigit()):
                return f"Wyróżnik tablic powiatu {name} ma {val} znaki ({', '.join(plates)})." if answer else f"Wyróżnik tablic powiatu {name} nie ma {val} znaków ({', '.join(plates)})."
            return f"Wyróżnik tablic powiatu {name} to: {val}. Wszystkie kody: {', '.join(plates)}." if answer else f"Powiat {name} nie ma wyróżnika {val}. Tablice to: {', '.join(plates)}."
        if rel == "voivodeship":
            voiv_locative = {
                "dolnośląskie": "dolnośląskim", "kujawsko-pomorskie": "kujawsko-pomorskim", "lubelskie": "lubelskim",
                "lubuskie": "lubuskim", "łódzkie": "łódzkim", "małopolskie": "małopolskim", "mazowieckie": "mazowieckim",
                "opolskie": "opolskim", "podkarpackie": "podkarpackim", "podlaskie": "podlaskim", "pomorskie": "pomorskim",
                "śląskie": "śląskim", "świętokrzyskie": "świętokrzyskim", "warmińsko-mazurskie": "warmińsko-mazurskim",
                "wielkopolskie": "wielkopolskim", "zachodniopomorskie": "zachodniopomorskim",
            }
            loc_woj = voiv_locative.get(str(row['voivodeship']).lower(), row['voivodeship'])
            name_display = name if name.startswith("Powiat") else f"Powiat {name}"
            return f"{name_display} leży w województwie {loc_woj}."
        if rel == "is_city_county":
            return f"{name} jest miastem na prawach powiatu." if row[config.scalar_relations[rel]] else f"{name} jest powiatem ziemskim."
        if rel == "mountain_ranges":
            ranges = [r[0] for r in conn.execute("SELECT range_name FROM voivodeship_mountain_ranges WHERE voivodeship_id=?", (row["id"],))] if "voivodeship" in config.table else []
            r_str = ", ".join(ranges)
            if ranges:
                if val:
                    return f"{name} leży w paśmie: {val}. Pasma w województwie: {r_str}." if answer else f"{name} nie leży w paśmie: {val}. Pasma w województwie: {r_str}."
                return f"{name} leży w pasmach górskich: {r_str}."
            return f"{name} nie leży w górach (brak pasm górskich)."
        return factual_fallback()
    else:
        if rel == "is_coastal":
            return f"{name} is a coastal state with ocean/gulf coastline." if row[config.scalar_relations[rel]] else f"{name} is an inland state with no ocean coastline."
        if rel == "borders_state" and val:
            borders = [r[0] for r in conn.execute("SELECT border_state_name FROM us_state_borders_states WHERE state_id=?", (row["id"],))]
            if isinstance(val, (int, float)) or (isinstance(val, str) and str(val).isdigit()):
                b_str = f" ({', '.join(borders)})" if borders else ""
                return f"{name} borders {len(borders)} neighboring states{b_str}."
            return f"{name} borders {val}." if answer else f"{name} does not border {val}. Bordering states: {', '.join(borders)}."
        if rel in ("region", "division"):
            return f"{name} is located in the {row['region']} region ({row['division']} division)."
        if rel == "admission_year":
            return f"{name} was admitted to the Union in {row['admission_year']} (state #{row['admission_order']})."
        return factual_fallback()


def execute_plan(config: LocalModeConfig, entity_name: str, plan: QuestionPlan) -> LocalAnswer | None:
    if not plan.valid or not plan.supported or not plan.plan:
        return None
    with sqlite3.connect(config.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = get_entity_row(conn, config, entity_name)
        if row is None:
            return None
        answer = evaluate(conn, config, row, plan.plan)
    if answer is None:
        return None
    relations = collect_relations(plan.plan)
    explanation = generate_mode_explanation(config, row, plan, answer, conn)
    return LocalAnswer(
        question=plan.improved_question or plan.original_question,
        answer=answer,
        explanation=explanation,
        relations=relations,
    )
