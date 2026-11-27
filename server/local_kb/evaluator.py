"""AST evaluator and plan execution engine for local KB SQLite fact databases."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from powiat_names import resolve_powiat_name
from voivodeship_names import resolve_voivodeship_name

from .aliases import (
    POLISH_CITY_ALIASES,
    POLISH_HISTORICAL_PARTITION_ALIASES,
    POLISH_NEIGHBORING_COUNTRIES_ALIASES,
    POLISH_REGION_ALIASES,
    POLISH_RIVER_ALIASES,
    UK_NEIGHBORING_COUNTRIES_ALIASES,
    _canonical_us_region,
    _resolve_english_county_alias,
    fold_polish,
    is_self_reference,
    norm,
    text_value,
)
from .db import (
    _get_parent_voivodeship_relation,
    _reference_row,
    get_entity_row,
    get_relation_value,
    resolve_ref,
)
from .models import LocalAnswer, LocalModeConfig, QuestionPlan, _safe_identifier


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
        rel_name = op if op in config.list_relations else (
            "borders_county" if "county" in op
            else "borders_state" if "state" in op
            else "borders_country" if "country" in op
            else "borders_voivodeship" if "voivodeship" in op
            else "borders_powiat"
        )
        rel_items = get_relation_value(conn, config, row, rel_name)
        if not isinstance(rel_items, list) and not (
            config.mode_name == "Powiatdle" and rel_name == "borders_powiat"
        ):
            return None
        right_node = node.get("right", node.get("value"))
        right_val = resolve_ref(conn, config, row, right_node, item_value)
        if isinstance(right_val, dict):
            right_val = right_val.get("value", right_val.get("entity"))
        if rel_name.startswith("borders_") and is_self_reference(right_val, row, config):
            return False
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
        if config.mode_name == "Countydle" and rel_name == "borders_county":
            right_val = _resolve_english_county_alias(right_val)
        if rel_name.startswith("borders_") and is_self_reference(right_val, row, config):
            return False
        if isinstance(rel_items, list):
            right_norm = norm(right_val)
            if rel_name == "borders_country" and config.mode_name == "Countydle" and right_norm in UK_NEIGHBORING_COUNTRIES_ALIASES:
                target_country = UK_NEIGHBORING_COUNTRIES_ALIASES[right_norm]
                return any(norm(value) == norm(target_country) for value in rel_items)
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
            table = _safe_identifier(config.table)
            name_col = _safe_identifier(config.name_column)
            neighbors = conn.execute(
                " ".join(["SELECT * FROM", table, "WHERE", name_col, "IN (SELECT value FROM json_each(?))"]),
                (json.dumps(items),),
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
    if config.mode_name == "Countydle" and isinstance(left_node, dict) and left_node.get("relation") == "is_coastal":
        is_coast = bool(row["is_coastal"])
        if op == "exists":
            return is_coast
        if right in {True, 1, "true", "True"}:
            return is_coast
        if right in {False, 0, "false", "False"}:
            return not is_coast
    if (
        config.mode_name == "Countydle"
        and isinstance(left_node, dict)
        and left_node.get("relation") in {"borders_county", "name"}
        and op in {"contains", "contains_exact", "contains_partial", "equals"}
        and isinstance(right, str)
    ):
        right = _resolve_english_county_alias(right)
    left_row = _reference_row(conn, config, row, left_node, item_value)
    if config.mode_name in {"Wojewodztwodle", "Powiatdle"} and isinstance(left_node, dict) and left_node.get("relation") in {"water_access", "is_coastal"}:
        if config.mode_name == "Wojewodztwodle":
            is_coast = bool(row["is_coastal"])
        elif left_node.get("entity") == "target_voivodeship":
            is_coast = bool(left)
        else:
            target_row_id = left_row["id"] if left_row is not None else row["id"]
            is_coast = bool(conn.execute("SELECT 1 FROM powiat_water_access WHERE powiat_id = ? LIMIT 1", (target_row_id,)).fetchone())
        if op == "exists":
            return is_coast
        if right in {True, 1, "true", "True"} or norm(right) in {"morze", "baltyk", "morze baltyckie", "baltyckie", "sea", "baltic sea", "baltic"}:
            return is_coast
        if right in {False, 0, "false", "False"}:
            return not is_coast
    if (
        config.mode_name == "Powiatdle"
        and isinstance(left_node, dict)
        and left_node.get("relation") == "borders_powiat"
        and op in {"contains", "contains_exact", "contains_partial", "equals"}
        and not (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit()))
    ):
        if left_row is not None and is_self_reference(right, left_row, config):
            return False
        right = resolve_powiat_name(conn, right)
        if right is None:
            return None
        if left_row is not None and right == left_row[config.name_column]:
            return False
    right_is_seat = isinstance(right_node, dict) and right_node.get("relation") == "seat"
    if (
        isinstance(left_node, dict)
        and (
            left_node.get("relation") == "borders_voivodeship"
            or (config.mode_name == "Powiatdle" and left_node.get("relation") == "voivodeship")
            or (config.mode_name == "Wojewodztwodle" and left_node.get("relation") == "name")
        )
        and op in {"contains", "contains_exact", "contains_partial", "equals"}
        and not right_is_seat
        and not (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit()))
    ):
        is_border_voiv = left_node.get("relation") == "borders_voivodeship"
        if is_border_voiv and left_row is not None and is_self_reference(right, left_row, config):
            return False
        resolved_v = resolve_voivodeship_name(right)
        if resolved_v is not None:
            right = resolved_v
        if is_border_voiv and left_row is not None and right == left_row[config.name_column]:
            return False
    if left is None or (op not in {"has_space", "has_hyphen", "exists"} and right is None):
        return None

    # An entity never borders/neighbors itself.
    if op in {"contains", "contains_exact", "equals"} and isinstance(left_node, dict):
        relation = str(left_node.get("relation") or "")
        if relation.startswith("borders_") and left_row is not None and is_self_reference(right, left_row, config):
            return False
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
            if rel_name == "borders_country" and config.mode_name == "Countydle" and r_norm in UK_NEIGHBORING_COUNTRIES_ALIASES:
                target_country = UK_NEIGHBORING_COUNTRIES_ALIASES[r_norm]
                return any(norm(v) == norm(target_country) for v in left)
            if rel_name == "borders_country" and r_norm in POLISH_NEIGHBORING_COUNTRIES_ALIASES:
                target_country = POLISH_NEIGHBORING_COUNTRIES_ALIASES[r_norm]
                return any(norm(v) == norm(target_country) for v in left)
            if rel_name == "major_rivers" and r_norm in POLISH_RIVER_ALIASES:
                target_river = POLISH_RIVER_ALIASES[r_norm]
                return any(norm(v) == norm(target_river) for v in left)
            if rel_name == "historical_partitions" and r_norm in POLISH_HISTORICAL_PARTITION_ALIASES:
                target_partition = POLISH_HISTORICAL_PARTITION_ALIASES[r_norm]
                return any(norm(v) == norm(target_partition) for v in left)
            if rel_name in {"historical_regions", "landform_regions", "regional_labels"}:
                folded_r = fold_polish(right)
                target_region = POLISH_REGION_ALIASES.get(r_norm) or POLISH_REGION_ALIASES.get(folded_r)
                if target_region:
                    return any(fold_polish(v) == fold_polish(target_region) for v in left)
                if config.mode_name == "Powiatdle" and rel_name == "historical_regions" and r_norm in POLISH_HISTORICAL_PARTITION_ALIASES:
                    target_partition = POLISH_HISTORICAL_PARTITION_ALIASES[r_norm]
                    if left_row is not None:
                        partitions = get_relation_value(conn, config, left_row, "historical_partitions") or []
                        if any(norm(v) == norm(target_partition) for v in partitions):
                            return True
                return any(fold_polish(v) == folded_r for v in left)
            if rel_name in {"national_parks", "major_lakes", "lakes", "health_resorts"} and config.mode_name in {"Powiatdle", "Wojewodztwodle"}:
                folded_r = fold_polish(right)
                return any(fold_polish(v) == folded_r for v in left)
            return any(norm(v) == r_norm for v in left)
        if (
            (type(left) is bool or (isinstance(left, int) and left in (0, 1)))
            and (
                type(right) is bool
                or norm(right) in {"true", "false"}
                or (
                    isinstance(left_node, dict)
                    and str(left_node.get("relation") or "").startswith("is_")
                    and norm(right) in {"0", "1", "true", "false", "yes", "no", "tak", "nie"}
                )
            )
        ):
            right_bool = right if type(right) is bool else norm(right) in {"1", "true", "yes", "tak"}
            return bool(left) is right_bool
        n_left = norm(left)
        n_right = norm(right)
        if n_left == n_right:
            return True
        if isinstance(left_node, dict) and left_node.get("relation") == "seat":
            l_alias = POLISH_CITY_ALIASES.get(n_left) or POLISH_CITY_ALIASES.get(fold_polish(left))
            r_alias = POLISH_CITY_ALIASES.get(n_right) or POLISH_CITY_ALIASES.get(fold_polish(right))
            if fold_polish(l_alias or left) == fold_polish(r_alias or right):
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
        if rel_name in {"historical_regions", "landform_regions", "regional_labels"}:
            r_val = POLISH_REGION_ALIASES.get(norm(right)) or POLISH_REGION_ALIASES.get(fold_polish(right)) or r_val
        if isinstance(left, list):
            return any(fold_polish(v) == fold_polish(r_val) or fold_polish(r_val) in fold_polish(v) for v in left)
        return fold_polish(r_val) in fold_polish(left)
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
        if isinstance(left, list):
            return any(norm(v).startswith(n_right) for v in left)
        return n_txt.startswith(n_right)
    if op == "ends_with":
        if isinstance(left, list):
            return any(norm(v).endswith(n_right) for v in left)
        return n_txt.endswith(n_right)
    if op == "contains_text":
        if config.mode_name == "Powiatdle" and isinstance(left_node, dict) and left_node.get("relation") == "name":
            resolved_r = resolve_powiat_name(conn, right)
            if resolved_r and norm(resolved_r) == norm(left):
                return True
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
    from .clarification import build_clarification
    from .explanations import generate_mode_explanation

    relations = collect_relations(plan.plan)
    explanation = generate_mode_explanation(config, row, plan, answer, conn)
    clarification = build_clarification(config, plan, answer)
    return LocalAnswer(
        question=plan.improved_question or plan.original_question,
        answer=answer,
        explanation=explanation,
        relations=relations,
        clarification=clarification,
    )
