"""Generic Gemini planner + SQLite executor for local game fact databases."""

from __future__ import annotations

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

_REGIONAL_DISPLAY = {
    "centrum": "central", "południe": "south", "północ": "north",
    "wschód": "east", "zachód": "west",
    "południowe centrum": "south central", "północne centrum": "north central",
    "zachodnie centrum": "west central", "południowy wschód": "southeast",
    "południowy zachód": "southwest", "północny wschód": "northeast",
    "północny zachód": "northwest",
    "polska centralna": "central Poland", "centralna polska": "central Poland",
    "polska wschodnia": "eastern Poland", "wschodnia polska": "eastern Poland",
    "polska zachodnia": "western Poland", "zachodnia polska": "western Poland",
    "południowa polska": "southern Poland", "północna polska": "northern Poland",
    "południowo-centralna polska": "south-central Poland",
    "południowo-wschodnia polska": "southeastern Poland",
    "południowo-zachodnia polska": "southwestern Poland",
    "północno-centralna polska": "north-central Poland",
    "północno-wschodnia polska": "northeastern Poland",
    "północno-zachodnia polska": "northwestern Poland",
    "zachodnio-centralna polska": "west-central Poland",
    "nadmorska polska": "coastal Poland", "wybrzeże bałtyku": "Baltic coast",
    "zabór austriacki": "Austrian partition", "zabór pruski": "Prussian partition",
    "zabór rosyjski": "Russian partition", "ziemie odzyskane": "Recovered Territories",
    "morze bałtyckie": "Baltic Sea",
}


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
    version = f"{PLANNER_VERSION}:english-output-v1:{model}"
    cached = plan_cache.get(config.mode_name, question, version=version) if use_cache else None
    if evidence is not None:
        evidence.update(provider="gemini", model=model, contract_version=f"{PLANNER_VERSION}:english-output-v1", cache_hit=cached is not None)
    if cached is not None:
        return replace(cached, original_question=question)
    from utils.water_hierarchy import is_multi_ocean_question, build_multi_ocean_plan
    if is_multi_ocean_question(question):
        entity = {"USStatedle": "state", "Powiatdle": "county", "Wojewodztwodle": "voivodeship"}.get(
            config.mode_name, "location",
        )
        improved = f"Does the {entity} have access to two or more oceans?"
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=True,
            improved_question=improved,
            explanation="Deterministic multi-ocean query resolution.",
            plan=build_multi_ocean_plan(config.target_entity),
        )

    try:
        from generic_template_compiler import compile_generic_template_plan
        tpl_res = compile_generic_template_plan(question, config.mode_name)
        if tpl_res is not None:
            tpl_ast, tpl_improved = tpl_res
            plan = QuestionPlan(
                original_question=question,
                valid=True,
                supported=True,
                improved_question=tpl_improved,
                explanation="Deterministic template match.",
                plan=tpl_ast,
            )
            if use_cache:
                plan_cache.set(config.mode_name, question, plan, version=version)
            return plan
    except Exception:
        pass
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
    prompt = f"""
You are a validator and planner for a yes/no guessing game.
Game mode: {config.mode_name}
Target entity placeholder: {config.target_entity}
Entity type: {config.entity_label}

Supported SQLite relations:
{relations}

Task:
1. Decide whether the user input is a valid yes/no question about the hidden {config.entity_label}.
2. Rewrite Polish questions in English, preserving their meaning; otherwise rewrite only if clarification is needed.
3. If it can be answered from the supported relations, return route="local", plan and any needed improved_question. Do not generate an explanation for a local plan: the executor explains the facts.
4. If a clear question needs external knowledge, return route="fallback", plan=null and a short fallback_reason.
5. If the question needs clarification or is unrelated/open-ended, return route="clarify", plan=null and a short explanation.
Write every improved_question, clarification explanation, and fallback_reason in English, regardless of the input language. Preserve native geographic names and interpret Polish and English questions equivalently.

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


User question: {question}
""".strip()
    allowed_relations = config.scalar_relations.keys() | config.list_relations.keys() | {"name"}
    operators = (PLANNER_OPERATORS - {"contains"}) | {"contains_exact", "contains_partial", "any", "all"}
    allow_named_entities = config.mode_name in {"Countrydle", "Powiatdle", "USStatedle", "Wojewodztwodle"}
    schema = planner_response_schema(
        relations=allowed_relations, operators=operators, target_entity=config.target_entity,
        allow_named_entities=allow_named_entities,
    )
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


POLISH_NEIGHBORING_COUNTRIES_ALIASES: dict[str, str] = {
    "slovakia": "Słowacja",
    "slowacja": "Słowacja",
    "słowacja": "Słowacja",
    "czech republic": "Czechy",
    "czechia": "Czechy",
    "czechy": "Czechy",
    "germany": "Niemcy",
    "niemcy": "Niemcy",
    "ukraine": "Ukraina",
    "ukraina": "Ukraina",
    "belarus": "Białoruś",
    "bialorus": "Białoruś",
    "białoruś": "Białoruś",
    "lithuania": "Litwa",
    "litwa": "Litwa",
    "russia": "Rosja",
    "rosja": "Rosja",
}

POLISH_RIVER_ALIASES: dict[str, str] = {
    "vistula": "Wisła",
    "vistula river": "Wisła",
    "river vistula": "Wisła",
    "wisla": "Wisła",
    "wisly": "Wisła",
    "wisle": "Wisła",
    "wisłę": "Wisła",
    "wisły": "Wisła",
    "wiśle": "Wisła",
    "wisłą": "Wisła",
    "oder": "Odra",
    "oder river": "Odra",
    "river oder": "Odra",
    "odra": "Odra",
    "odry": "Odra",
    "odrze": "Odra",
    "odrę": "Odra",
    "odrą": "Odra",
}

_VOIVODESHIP_DB_PATH = ROOT_DIR / "data" / "voivodeship_facts.sqlite"
_VOIVODESHIP_LIST_RELATIONS: dict[str, tuple[str, str]] = {
    "borders_voivodeship": ("voivodeship_borders_voivodeships", "border_voivodeship_name"),
    "borders_country": ("voivodeship_borders_countries", "country_name"),
    "water_access": ("voivodeship_water_access", "water_body"),
    "major_rivers": ("voivodeship_major_rivers", "river_name"),
    "major_roads": ("voivodeship_major_roads", "road_name"),
    "mountain_ranges": ("voivodeship_mountain_ranges", "range_name"),
    "historical_region": ("voivodeship_historical_regions", "region_name"),
    "landform_regions": ("voivodeship_landform_regions", "region_name"),
    "regional_labels": ("voivodeship_regional_labels", "label"),
}
_VOIVODESHIP_SCALAR_RELATIONS: dict[str, str] = {
    "name": "name",
    "seat": "seat",
    "macroregion": "macroregion",
    "is_coastal": "is_coastal",
    "population": "population",
    "area": "area_km2",
    "latitude": "latitude",
    "longitude": "longitude",
    "urbanization": "urbanization_percent",
    "powiat_count": "powiat_count",
    "city_count": "city_count",
    "city_count_with_powiat_rights": "city_count_with_powiat_rights",
}


def _get_parent_voivodeship_relation(row: sqlite3.Row, relation: str) -> Any:
    if "voivodeship" not in row.keys() or not row["voivodeship"] or not _VOIVODESHIP_DB_PATH.is_file():
        return None
    voiv_name = str(row["voivodeship"])
    with sqlite3.connect(_VOIVODESHIP_DB_PATH) as v_conn:
        v_conn.row_factory = sqlite3.Row
        v_row = v_conn.execute(
            "SELECT * FROM voivodeships WHERE name = ? COLLATE NOCASE",
            (voiv_name,),
        ).fetchone()
        if v_row is None:
            return None
        if relation in _VOIVODESHIP_SCALAR_RELATIONS:
            return v_row[_VOIVODESHIP_SCALAR_RELATIONS[relation]]
        if relation in _VOIVODESHIP_LIST_RELATIONS:
            table, column = _VOIVODESHIP_LIST_RELATIONS[relation]
            return [
                r[0]
                for r in v_conn.execute(
                    f"SELECT {column} FROM {table} WHERE voivodeship_id = ?",
                    (v_row["id"],),
                ).fetchall()
            ]
    return None
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
        waters = [r[0] for r in conn.execute(f"SELECT {column} FROM {table} WHERE {fk_column} = ?", (row["id"],)).fetchall()]
        if relation == "water_access":
            from utils.water_hierarchy import expand_water_bodies
            return list(expand_water_bodies(waters))
        return waters


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
    if (
        config.mode_name == "Powiatdle"
        and isinstance(node, dict)
        and node.get("entity") in {"target_voivodeship", "voivodeship", "wojewodztwo"}
    ):
        return _get_parent_voivodeship_relation(row, str(node.get("relation") or ""))
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
            right_norm = norm(right_val)
            if rel_name == "borders_country" and right_norm in POLISH_NEIGHBORING_COUNTRIES_ALIASES:
                target_country = POLISH_NEIGHBORING_COUNTRIES_ALIASES[right_norm]
                return any(norm(value) == norm(target_country) for value in rel_items)
            return any(norm(value) == right_norm for value in rel_items)
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
            rel_name = left_node.get("relation") if isinstance(left_node, dict) else ""
            r_norm = norm(right)
            if rel_name == "borders_country" and r_norm in POLISH_NEIGHBORING_COUNTRIES_ALIASES:
                target_country = POLISH_NEIGHBORING_COUNTRIES_ALIASES[r_norm]
                return any(norm(v) == norm(target_country) for v in left)
            if rel_name == "major_rivers" and r_norm in POLISH_RIVER_ALIASES:
                target_river = POLISH_RIVER_ALIASES[r_norm]
                return any(norm(v) == norm(target_river) for v in left)
            return any(norm(v) == r_norm for v in left)
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
            clean_left = re.sub(r"\b(?:powiat|powiatu|powiatem|powiecie|county)\b", "", re.sub(r"\s*\([^)]*\)", "", n_left)).strip()
            clean_right = re.sub(r"\b(?:powiat|powiatu|powiatem|powiecie|county)\b", "", re.sub(r"\s*\([^)]*\)", "", n_right)).strip()
            return bool(clean_left) and clean_left == clean_right
        return False
    if op == "contains_partial":
        rel_name = left_node.get("relation") if isinstance(left_node, dict) else ""
        r_val = POLISH_RIVER_ALIASES.get(norm(right), right) if rel_name == "major_rivers" else right
        if isinstance(left, list):
            return any(norm(v) == norm(r_val) or norm(r_val) in norm(v) for v in left)
        return norm(r_val) in norm(left)
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
    rel_name = left_node.get("relation") if isinstance(left_node, dict) else ""
    r_effective = POLISH_RIVER_ALIASES.get(norm(right), right) if rel_name == "major_rivers" else right
    n_right = norm(r_effective)
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
    verdict = "Unknown" if answer is None else ("Yes" if answer else "No")
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
    from utils.water_hierarchy import is_multi_ocean_question, get_distinct_oceans
    if config.mode_name == "USStatedle" and is_multi_ocean_question(plan.original_question):
        direct_waters = [r[0] for r in conn.execute("SELECT water_body FROM us_state_water_access WHERE state_id=?", (row["id"],))]
        oceans = sorted(get_distinct_oceans(direct_waters))
        count = len(oceans)
        if count >= 2:
            return f"{verdict} - {name} has coastline access to {count} oceans: {', '.join(oceans)}."
        elif count == 1:
            return f"{verdict} - {name} has coastline access to only 1 ocean: {oceans[0]}."
        else:
            return f"{verdict} - {name} is an inland state with no ocean coastline."

    def value_text(value: Any) -> str:
        if value is None or isinstance(value, dict):
            return "unknown"
        if isinstance(value, list):
            return ", ".join(value_text(item) for item in value) if value else "none"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (int, float)):
            return f"{value:,}".removesuffix(".0")
        return str(value)

    def reference_fact(reference: Any) -> str:
        value = resolve_ref(conn, config, target_row, reference, item_value)
        relation = reference.get("relation") if isinstance(reference, dict) else None
        referenced_row = _reference_row(conn, config, target_row, reference, item_value)
        subject = referenced_row[config.name_column] if referenced_row is not None else None
        if isinstance(reference, dict) and reference.get("entity") == "item" and subject is None:
            subject = item_value if not isinstance(item_value, (dict, sqlite3.Row)) else None
        label = str(relation or "").replace("_", " ")
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
            label = "word count"
            facts.append(f"{label}: {len(left_value.split())}")
        if isinstance(op, str) and op.startswith("char_count_"):
            label = "character count"
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
            if coord == threshold:
                position = f"at the same {rel} as"
            elif rel == "longitude":
                position = "east of" if coord > threshold else "west of"
            else:
                position = "north of" if coord > threshold else "south of"
            reference_name = _reference_row(conn, config, target_row, right_node, item_value)
            reference_text = f" ({reference_name[config.name_column]})" if reference_name is not None else ""
            return f"{verdict} - {name} is located at {rel} {coord_text} ({position} {threshold_text}{reference_text}; the condition {coord} {comparison} {threshold} is {'true' if answer else 'false'})."

    if config.mode_name in {"Powiatdle", "Wojewodztwodle"}:
        if rel == "name" and op in {"equals", "contains_exact", "contains"} and val:
            if config.mode_name == "Powiatdle":
                display_val = resolve_powiat_name(conn, val) or str(val)
            else:
                display_val = resolve_voivodeship_name(val) or str(val)
            return f"{verdict} - This is{' not' if not answer else ''} {display_val}."

        parent = (
            config.mode_name == "Powiatdle" and isinstance(left, dict)
            and left.get("entity") in {"target_voivodeship", "voivodeship", "wojewodztwo"}
        )
        if parent:
            parent_name = _get_parent_voivodeship_relation(target_row, "name") or target_row["voivodeship"]
            subject = f"{parent_name} voivodeship"
            context = f"{name} is in {subject}. "
        else:
            subject = name
            context = ""

        if rel == "is_city_county" and rel in config.scalar_relations:
            city_county = row[config.scalar_relations[rel]]
            if city_county is None:
                return factual_fallback()
            kind = "a city with county rights" if city_county else "a land county"
            return f"{verdict} - {name} is {kind}."
        if rel == "is_coastal":
            coastal = resolve_ref(conn, config, target_row, left, item_value)
            if coastal is None:
                return factual_fallback()
            return f"{verdict} - {context}{subject} {'has' if coastal else 'does not have'} direct access to the Baltic Sea."
        if rel in {"seat", "macroregion", "voivodeship"}:
            actual = resolve_ref(conn, config, target_row, left, item_value)
            label = {"seat": "administrative seat", "macroregion": "macroregion", "voivodeship": "voivodeship"}[rel]
            text = _REGIONAL_DISPLAY.get(str(actual).casefold(), value_text(actual)) if rel == "macroregion" else value_text(actual)
            return f"{verdict} - {context}{subject}'s {label}: {text}."

        if rel in config.list_relations or (parent and rel in _VOIVODESHIP_LIST_RELATIONS):
            if rel == "water_access" and parent:
                values = _get_parent_voivodeship_relation(target_row, rel)
            elif rel == "water_access":
                table, column = config.list_relations[rel]
                fk_column = config.fk_column or f"{config.table[:-1]}_id"
                values = [r[0] for r in conn.execute(
                    f"SELECT {column} FROM {table} WHERE {fk_column} = ?", (row["id"],)
                )]
            else:
                values = resolve_ref(conn, config, target_row, left, item_value)
            if values is None or isinstance(values, dict):
                return factual_fallback()
            if not isinstance(values, list):
                return factual_fallback()
            labels = {
                "water_access": "water bodies", "national_parks": "national parks",
                "major_lakes": "major lakes", "lakes": "lakes",
                "unesco_sites": "UNESCO sites", "health_resorts": "health resorts",
                "borders_voivodeship": "neighboring voivodeships",
                "borders_powiat": "neighboring counties", "borders_country": "neighboring countries",
                "major_roads": "major roads", "major_rivers": "major rivers",
                "registration_plates": "registration plate codes", "mountain_ranges": "mountain ranges",
            }
            label = labels.get(rel, rel.replace("_", " "))
            countries = {
                "Niemcy": "Germany", "Czechy": "Czechia", "Słowacja": "Slovakia",
                "Ukraina": "Ukraine", "Białoruś": "Belarus", "Litwa": "Lithuania", "Rosja": "Russia",
            }
            def display(value: Any) -> str:
                if rel == "borders_country":
                    canonical = POLISH_NEIGHBORING_COUNTRIES_ALIASES.get(norm(value), value)
                    return countries.get(canonical, str(canonical))
                if rel == "major_rivers":
                    return str(POLISH_RIVER_ALIASES.get(norm(value), value))
                if rel == "borders_voivodeship":
                    return str(resolve_voivodeship_name(value) or value)
                if rel in {"regional_labels", "historical_partitions", "water_access"}:
                    return _REGIONAL_DISPLAY.get(str(value).casefold(), str(value))
                return str(value)

            recorded = ", ".join(display(value) for value in values) if values else "none"
            fact = f"{context}{subject}'s {label} ({len(values)}): {recorded}"
            if val is not None and not numeric_value and op != "exists":
                fact += f"; the condition involving {display(val)} is {'true' if answer else 'false'}"
            return f"{verdict} - {fact}."
        return factual_fallback()
    else:
        if rel == "name" and op in {"equals", "contains_exact", "contains"} and val:
            return f"{verdict} - The state is {val}." if answer else f"{verdict} - The state is not {val}."
        if rel == "is_coastal":
            return f"{name} is a coastal state with ocean/gulf coastline." if row[config.scalar_relations[rel]] else f"{name} is an inland state with no ocean coastline."
        if rel == "water_access":
            from utils.water_hierarchy import WATER_BODY_PARENT_MAP, is_multi_ocean_question, get_distinct_oceans
            direct_waters = [r[0] for r in conn.execute(f"SELECT water_body FROM us_state_water_access WHERE state_id=?", (row["id"],))]
            if is_multi_ocean_question(plan.original_question):
                oceans = sorted(get_distinct_oceans(direct_waters))
                count = len(oceans)
                if count >= 2:
                    return f"{name} has coastline access to {count} oceans: {', '.join(oceans)}."
                elif count == 1:
                    return f"{name} has coastline access to only 1 ocean: {oceans[0]}."
                else:
                    return f"{name} is an inland state with no ocean coastline."
            if val:
                via_sub = [w for w in direct_waters if w in WATER_BODY_PARENT_MAP and val in WATER_BODY_PARENT_MAP[w]]
                via_str = f" (via the {', '.join(via_sub)})" if via_sub and val not in direct_waters else ""
                if answer:
                    return f"{name} has coastline access to: {val}{via_str}."
                return f"{name} does not have access to {val}. Recorded water bodies: {', '.join(direct_waters) if direct_waters else 'none'}."
            return f"{name} has coastline access to: {', '.join(direct_waters)}." if answer else f"{name} has no coastline access."
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
