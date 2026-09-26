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
    version = f"{PLANNER_VERSION}:{model}"
    cached = plan_cache.get(config.mode_name, question, version=version) if use_cache else None
    if evidence is not None:
        evidence.update(provider="gemini", model=model, contract_version=PLANNER_VERSION, cache_hit=cached is not None)
    if cached is not None:
        return replace(cached, original_question=question)

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
2. Rewrite it only if translation or clarification is needed; otherwise omit improved_question.
3. If it can be answered from the supported relations, return route="local", plan and any needed improved_question. Do not generate an explanation for a local plan: the executor explains the facts.
4. If a clear question needs external knowledge, return route="fallback", plan=null and a short fallback_reason.
5. If the question needs clarification or is unrelated/open-ended, return route="clarify", plan=null and a short explanation.

Use common names, not long official names. Normalize Polish and informal names when obvious.
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
- For questions like "further east than" or "east of", use operator "east_of".
- For "further north than" or "north of", use operator "north_of".
- For "further south than" or "south of", use operator "south_of".

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
    schema = planner_response_schema(
        relations=allowed_relations, operators=operators, target_entity=config.target_entity,
    )
    data = gemini_json(prompt, response_schema=schema, evidence=evidence)
    ast = compile_planner_response(
        data, relations=allowed_relations, operators=operators, target_entity=config.target_entity,
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
    return conn.execute(
        f"SELECT * FROM {config.table} WHERE {config.name_column} = ? COLLATE NOCASE",
        (entity_name,),
    ).fetchone()


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


def _reference_row(config: LocalModeConfig, row: sqlite3.Row, node: Any, item_value: Any) -> sqlite3.Row | None:
    if isinstance(node, dict):
        if node.get("entity") == config.target_entity:
            return row
        if node.get("entity") == "item" and isinstance(item_value, sqlite3.Row):
            return item_value
    return None


def resolve_ref(conn: sqlite3.Connection, config: LocalModeConfig, row: sqlite3.Row, node: Any, item_value: Any = None) -> Any:
    if isinstance(node, dict) and set(node.keys()) == {"value"}:
        return node.get("value")
    entity_row = _reference_row(config, row, node, item_value)
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

    left = resolve_ref(conn, config, row, left_node, item_value)
    right = resolve_ref(conn, config, row, right_node, item_value)
    left_row = _reference_row(config, row, left_node, item_value)
    if (
        config.mode_name == "Powiatdle"
        and isinstance(left_node, dict)
        and left_node.get("relation") == "borders_powiat"
        and op in {"contains", "contains_exact", "contains_partial", "equals"}
    ):
        if left_row is not None and is_self_reference(right, left_row, config):
            return True
        right = resolve_powiat_name(conn, right)
        if right is None:
            return None
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
        if op != "equals" and isinstance(left, list):
            return any(norm(v) == norm(right) for v in left)
        if isinstance(left, (bool, int, float)) and isinstance(right, (bool, int, float)):
            return left == right
        return norm(left) == norm(right)
    if op == "contains_partial":
        if isinstance(left, list):
            return any(norm(v) == norm(right) or norm(right) in norm(v) for v in left)
        return norm(right) in norm(left)
    if op in {"greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "west_of", "east_of", "north_of", "south_of"}:
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
    if op == "word_count_equals":
        return len(words) == num
    if op == "word_count_greater_than":
        return len(words) > num
    if op == "word_count_less_than":
        return len(words) < num
    if op == "char_count_equals":
        return chars == num
    if op == "char_count_greater_than":
        return chars > num
    if op == "char_count_less_than":
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
    answer: bool,
    conn: sqlite3.Connection,
) -> str:
    name = row[config.name_column]
    node = plan.plan or {}
    op = node.get("operator") if isinstance(node, dict) else None
    left = node.get("left", {}) if isinstance(node, dict) else {}
    rel = left.get("relation") if isinstance(left, dict) else None
    if not rel and isinstance(op, str) and (op in config.list_relations or op.startswith("borders_")):
        rel = op
    right_node = node.get("right", node.get("value")) if isinstance(node, dict) else None
    val = resolve_ref(conn, config, row, right_node)

    if rel in {"longitude", "latitude"} and op in {
        "greater_than", "less_than", "west_of", "east_of", "north_of", "south_of", "equals",
        "greater_than_or_equal", "less_than_or_equal",
    }:
        left_value = resolve_ref(conn, config, row, left)
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
                return f"{verdict} - {name} leży na {axis} {coord_text} ({position} {threshold_text}; warunek {left_value!r} {comparison} {val!r} jest {condition})."
            if coord == threshold:
                position = f"at the same {rel} as"
            elif rel == "longitude":
                position = "east of" if coord > threshold else "west of"
            else:
                position = "north of" if coord > threshold else "south of"
            return f"{'Yes' if answer else 'No'} - {name} is located at {rel} {coord_text} ({position} {threshold_text}; the condition {left_value!r} {comparison} {val!r} is {'true' if answer else 'false'})."

    if config.language == "Polish":
        if rel == "is_coastal":
            return f"Województwo {name} ma bezpośredni dostęp do Morza Bałtyckiego." if row[config.scalar_relations[rel]] else f"Województwo {name} nie ma dostępu do morza (jest województwem śródlądowym)."
        if rel == "borders_voivodeship" and val:
            entity_name = f"Województwo {name}" if config.target_entity == "target_voivodeship" else name
            if answer:
                return f"{entity_name} graniczy z: {val}."
            borders = get_relation_value(conn, config, row, rel)
            neighbors = f" Graniczy z: {', '.join(borders)}." if borders else ""
            return f"{entity_name} nie graniczy z {val}.{neighbors}"
        if rel == "borders_country" and val:
            borders = [r[0] for r in conn.execute("SELECT country_name FROM voivodeship_borders_countries WHERE voivodeship_id=?", (row["id"],))] if "voivodeship" in config.table else []
            return f"{name} graniczy z obcym państwem: {val}." if answer else f"{name} nie graniczy z {val}."
        if rel == "seat":
            return f"Siedzibą {name} jest {row['seat']}."
        if rel == "macroregion":
            return f"{name} leży w makroregionie: {row['macroregion']}."
        if rel == "registration_plates" and val:
            plates = [r[0] for r in conn.execute("SELECT plate_code FROM powiat_registration_plates WHERE powiat_id=?", (row["id"],))]
            return f"Wyróżnik tablic powiatu {name} to: {val}. Wszystkie kody: {', '.join(plates)}." if answer else f"Powiat {name} nie ma wyróżnika {val}. Tablice to: {', '.join(plates)}."
        if rel == "voivodeship":
            return f"Powiat {name} leży w województwie {row['voivodeship']}."
        if rel == "is_city_county":
            return f"{name} jest miastem na prawach powiatu." if row[config.scalar_relations[rel]] else f"{name} jest powiatem ziemskim."
        return f"{'Tak' if answer else 'Nie'} - {plan.explanation.rstrip('.')} dla {name}." if plan.explanation else f"{'Tak' if answer else 'Nie'} dla: {name}."
    else:
        if rel == "is_coastal":
            return f"{name} is a coastal state with ocean/gulf coastline." if row[config.scalar_relations[rel]] else f"{name} is an inland state with no ocean coastline."
        if rel == "borders_state" and val:
            borders = [r[0] for r in conn.execute("SELECT border_state_name FROM us_state_borders_states WHERE state_id=?", (row["id"],))]
            return f"{name} borders {val}." if answer else f"{name} does not border {val}. Bordering states: {', '.join(borders)}."
        if rel in ("region", "division"):
            return f"{name} is located in the {row['region']} region ({row['division']} division)."
        if rel == "admission_year":
            return f"{name} was admitted to the Union in {row['admission_year']} (state #{row['admission_order']})."
        return f"{'Yes' if answer else 'No'} - {plan.explanation.rstrip('.')} for {name}." if plan.explanation else f"{'Yes' if answer else 'No'} for {name}."


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
