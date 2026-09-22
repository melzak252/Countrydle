"""Generic Gemini planner + SQLite executor for local game fact databases."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


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


def gemini_json(prompt: str, max_output_tokens: int = 1024, *, evidence: dict | None = None) -> dict[str, Any]:
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_output_tokens, "responseMimeType": "application/json"},
    }
    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")[:1000]) from exc
    if evidence is not None:
        evidence.update(model_version=data.get("modelVersion"), response_id=data.get("responseId"))
    raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return json.loads(raw)


def validate_planner_response(data: Any) -> None:
    """Reject provider protocol failures rather than classifying them as invalid questions."""
    if not isinstance(data, dict) or type(data.get("valid")) is not bool or type(data.get("supported")) is not bool:
        raise RuntimeError("Planner returned an invalid response schema")
    if data["valid"] and data["supported"] and not isinstance(data.get("plan"), dict):
        raise RuntimeError("Planner returned no executable plan")
    if data.get("explanation") is not None and not isinstance(data["explanation"], str):
        raise RuntimeError("Planner returned a malformed explanation")
    for key in ("improved_question", "fallback_reason"):
        if data.get(key) is not None and not isinstance(data[key], str):
            raise RuntimeError("Planner returned an invalid response schema")


def analyze_question(
    question: str, config: LocalModeConfig, *, use_cache: bool = True,
    strict_errors: bool = False, evidence: dict | None = None,
) -> QuestionPlan:
    from utils.plan_cache import plan_cache

    cached = plan_cache.get(config.mode_name, question) if use_cache else None
    if cached is not None:
        return cached

    relations = "\n".join(f"- {r}" for r in config.supported_relations)
    prompt = f"""
You are a validator and planner for a yes/no guessing game.
Game mode: {config.mode_name}
Target entity placeholder: {config.target_entity}
Entity type: {config.entity_label}

Supported SQLite relations:
{relations}

Mode-specific planning notes:
{config.mode_notes or "- None"}

Task:
1. Decide whether the user input is a valid yes/no question about the hidden {config.entity_label}.
2. Rewrite/improve it into a clear atomic question.
3. Explain what the user wants to check.
4. If it can be answered from the supported relations, return a safe JSON execution plan.
5. If it needs unsupported/open-ended knowledge, set supported=false and provide fallback_reason.

Use common names, not long official names. Normalize Polish and informal names when obvious.
Do NOT answer the question. Only create the plan.

Self-neighbor rule:
- If the user asks whether the hidden {config.entity_label} borders/neighbors itself
  (Polish: "sąsiaduje z samym sobą"), this is a valid supported question.
- Create a contains_exact plan on the relevant borders_* relation with the right/value as
  the hidden entity name reference, e.g. {{"entity":"{config.target_entity}","relation":"name"}}.
- The executor treats this special self-border/self-neighbor case as true.

Allowed operators:
- contains / contains_exact: exact list membership or exact scalar match
- contains_partial: substring match, preserving the old broad contains behavior
- equals: scalar equals value
- greater_than, less_than: numeric comparison
- west_of: left longitude < right longitude (further west in signed coordinates)
- east_of: left longitude > right longitude (further east in signed coordinates)
- north_of: left latitude > right latitude (further north in signed coordinates)
- south_of: left latitude < right latitude (further south in signed coordinates)
- exists: relation has any value / boolean is true
- starts_with, ends_with, contains_text, has_space
- word_count_equals, word_count_greater_than, word_count_less_than
- char_count_equals, char_count_greater_than, char_count_less_than
- and, or, not

Geographic Direction / Coordinate rules:
- Longitudes in the Americas / USA are negative decimal degrees (e.g. 74° W is -74.0, 71.5° W is -71.5).
- For questions like "further west than 74° W" or "west of 74° W":
  ALWAYS use operator "west_of" (e.g. {{"operator":"west_of","left":{{"entity":"target_state","relation":"longitude"}},"right":-74.0}}).
  NEVER use greater_than for "further west than" with negative numbers!
- For questions like "further east than" or "east of", use operator "east_of".
- For "further north than" or "north of", use operator "north_of".
- For "further south than" or "south of", use operator "south_of".

Reference format examples:
{{"entity":"{config.target_entity}","relation":"population"}}
{{"entity":"{config.target_entity}","relation":"name"}}

Plan examples:
{{"operator":"contains_exact","left":{{"entity":"target_state","relation":"borders_state"}},"value":"Utah"}}
{{"operator":"contains_exact","left":{{"entity":"target_voivodeship","relation":"borders_voivodeship"}},"value":"małopolskie"}}
{{"operator":"contains_exact","left":{{"entity":"target_powiat","relation":"borders_country"}},"value":"Czechy"}}
{{"operator":"greater_than","left":{{"entity":"target_country","relation":"population"}},"right":100000}}
{{"operator":"starts_with","left":{{"entity":"target_country","relation":"name"}},"value":"K"}}
Return STRICT JSON only:
{{
  "valid": true,
  "supported": true,
  "improved_question": "...",
  "explanation": "...",
  "plan": {{...}},
  "fallback_reason": null
}}

Invalid format:
{{"valid": false, "supported": false, "improved_question": null, "explanation": "...", "plan": null, "fallback_reason": "not a yes/no question"}}

Unsupported format:
{{"valid": true, "supported": false, "improved_question": "...", "explanation": "...", "plan": null, "fallback_reason": "unsupported relation"}}

User question: {question}
""".strip()
    data = gemini_json(prompt, evidence=evidence) if evidence is not None else gemini_json(prompt)
    if strict_errors:
        validate_planner_response(data)
    if evidence is not None:
        evidence.update(
            provider="gemini",
            model=os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite",
            prompt=prompt, temperature=0, max_output_tokens=1024, cache_hit=False,
        )
    plan = QuestionPlan(
        original_question=question,
        valid=bool(data.get("valid")),
        supported=bool(data.get("supported")),
        improved_question=data.get("improved_question"),
        explanation=data.get("explanation"),
        plan=data.get("plan"),
        fallback_reason=data.get("fallback_reason"),
    )
    if use_cache:
        plan_cache.set(config.mode_name, question, plan)
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
        return [r[0] for r in conn.execute(f"SELECT {column} FROM {table} WHERE {fk_column} = ?", (row["id"],)).fetchall()]
    return None


def resolve_ref(conn: sqlite3.Connection, config: LocalModeConfig, row: sqlite3.Row, node: Any, item_value: str | None = None) -> Any:
    if isinstance(node, dict) and set(node.keys()) == {"value"}:
        return node.get("value")
    if isinstance(node, dict) and node.get("entity") == "item":
        return item_value
    if isinstance(node, dict) and node.get("entity") == config.target_entity:
        return get_relation_value(conn, config, row, node.get("relation", ""))
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
    item_value: str | None = None,
) -> bool | None:
    op = node.get("operator")
    if op in {"and", "or"}:
        values = [evaluate(conn, config, row, c, item_value) for c in node.get("conditions", [])]
        if not values:
            return None
        if op == "or":
            if any(v is True for v in values):
                return True
            if any(v is None for v in values):
                return None
            return False
        if any(v is False for v in values):
            return False
        if any(v is None for v in values):
            return None
        return True
    if op in config.list_relations or (isinstance(op, str) and op.startswith("borders_")):
        rel_name = op if op in config.list_relations else ("borders_state" if "state" in op else ("borders_country" if "country" in op else ("borders_voivodeship" if "voivodeship" in op else "borders_powiat")))
        rel_items = get_relation_value(conn, config, row, rel_name)
        if isinstance(rel_items, list):
            right_node = node.get("right", node.get("value"))
            right_val = norm(right_node if not isinstance(right_node, dict) else (right_node.get("value") or right_node.get("entity")))
            if is_self_reference(right_val, row, config):
                return True
            return any(norm(v) == right_val for v in rel_items)

    if op == "not":
        value = evaluate(conn, config, row, node.get("condition", {}), item_value)
        return None if value is None else not value
    if op in {"any", "all"}:
        items = resolve_ref(conn, config, row, node.get("items", {}))
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return None
        values = [evaluate(conn, config, row, condition, str(item)) for item in items]
        if op == "any":
            if any(v is True for v in values):
                return True
            if any(v is None for v in values):
                return None
            return False
        if any(v is False for v in values):
            return False
        if any(v is None for v in values):
            return None
        return True

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
    if left is None or (op not in {"has_space", "exists"} and right is None):
        return None

    # Game rule inherited from the old prompts: if the user asks whether the
    # hidden entity borders/neighbors itself, answer true. We do not store
    # self-edges in SQLite border tables, so handle it explicitly for all modes.
    if op in {"contains", "contains_exact", "equals"} and isinstance(left_node, dict):
        relation = str(left_node.get("relation") or "")
        if relation.startswith("borders_") and is_self_reference(right, row, config):
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
    if op in {"contains", "contains_exact"}:
        if isinstance(left, list):
            return any(norm(v) == norm(right) for v in left)
        return norm(left) == norm(right)
    if op == "contains_partial":
        if isinstance(left, list):
            return any(norm(v) == norm(right) or norm(right) in norm(v) for v in left)
        return norm(right) in norm(left)
    if op == "equals":
        return norm(left) == norm(right)
    if op in {"greater_than", "less_than", "west_of", "east_of", "north_of", "south_of"}:
        try:
            lnum, rnum = float(left), float(right)
        except (TypeError, ValueError):
            return None

        # Guard against LLM cardinal direction inversion on negative longitudes:
        left_dict = node.get("left") if isinstance(node.get("left"), dict) else {}
        if op == "greater_than" and left_dict.get("relation") == "longitude" and rnum < 0:
            q_lower = (plan.original_question or "").lower() + " " + (plan.improved_question or "").lower()
            if any(w in q_lower for w in ["west", "further west", "zachod", "zachód", "zachodniej", "zachodnim"]):
                op = "west_of"

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
    val = node.get("value") or node.get("right") if isinstance(node, dict) else None

    if config.language == "Polish":
        if rel == "is_coastal":
            return f"Województwo {name} ma bezpośredni dostęp do Morza Bałtyckiego." if answer else f"Województwo {name} nie ma dostępu do morza (jest województwem śródlądowym)."
        if rel == "borders_voivodeship" and val:
            borders = [r[0] for r in conn.execute("SELECT border_voivodeship_name FROM voivodeship_borders_voivodeships WHERE voivodeship_id=?", (row["id"],))]
            return f"Województwo {name} graniczy z: {val}." if answer else f"Województwo {name} nie graniczy z {val}. Graniczy z: {', '.join(borders)}."
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
            return f"{name} jest miastem na prawach powiatu." if answer else f"{name} jest powiatem ziemskim."
        return f"Odpowiedź {'TAK' if answer else 'NIE'} wynika ze sprawdzonych faktów o: {name}."
    else:
        if rel == "is_coastal":
            return f"{name} is a coastal state with ocean/gulf coastline." if answer else f"{name} is an inland state with no ocean coastline."
        if rel == "borders_state" and val:
            borders = [r[0] for r in conn.execute("SELECT border_state_name FROM us_state_borders_states WHERE state_id=?", (row["id"],))]
            return f"{name} borders {val}." if answer else f"{name} does not border {val}. Bordering states: {', '.join(borders)}."
        if rel in ("region", "division"):
            return f"{name} is located in the {row['region']} region ({row['division']} division)."
        if rel == "admission_year":
            return f"{name} was admitted to the Union in {row['admission_year']} (state #{row['admission_order']})."
        if rel == "longitude" and val is not None:
            coord = abs(float(row["longitude"]))
            dir_card = "W" if float(row["longitude"]) < 0 else "E"
            val_num = float(val) if val is not None else 0
            val_abs = abs(val_num)
            val_dir = "W" if val_num < 0 else "E"
            if answer:
                return f"{name} is located at longitude {coord:.1f}° {dir_card} (further west than {val_abs:.1f}° {val_dir})."
            else:
                return f"{name} is located at longitude {coord:.1f}° {dir_card} (east of {val_abs:.1f}° {val_dir}, not further west)."
        if rel == "latitude" and val is not None:
            coord = abs(float(row["latitude"]))
            dir_card = "N" if float(row["latitude"]) >= 0 else "S"
            val_num = float(val) if val is not None else 0
            val_abs = abs(val_num)
            val_dir = "N" if val_num >= 0 else "S"
            if answer:
                return f"{name} is located at latitude {coord:.1f}° {dir_card} (further north than {val_abs:.1f}° {val_dir})."
            else:
                return f"{name} is located at latitude {coord:.1f}° {dir_card} (south of {val_abs:.1f}° {val_dir}, not further north)."
        return f"The answer is {'YES' if answer else 'NO'} based on verified facts about {name}."


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
