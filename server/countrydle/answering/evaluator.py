"""AST evaluation, relation extraction, and geographic plan normalization."""

from __future__ import annotations

import sqlite3

from countrydle.answering.aliases import (
    CURRENCY_ALIASES,
    GEOGRAPHIC_AREA_ALIASES,
    RELIGION_ALIASES,
    _hyphenated_country_alias,
    canonical_country_name,
    char_count,
    normalize,
    normalize_hemisphere,
    normalize_value,
    text_value,
    word_count,
)
from countrydle.answering.db import (
    collect_ref_evidence,
    find_country,
    is_self_country_reference,
    merge_used_evidence,
    resolve_entity,
    resolve_ref,
)


def evaluate_plan_node(
    conn: sqlite3.Connection,
    node: dict,
    target_country: sqlite3.Row,
    item_value: str | None = None,
    fact_provenance: list[dict] | None = None,
    list_cache: dict[tuple[int, str], list] | None = None,
) -> bool | None:
    if not isinstance(node, dict):
        return None
    operator = node.get("operator")

    if operator == "not":
        result = evaluate_plan_node(conn, node.get("condition"), target_country, item_value, fact_provenance, list_cache=list_cache)
        return None if result is None else not result

    if operator in {"and", "or"}:
        conditions = node.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            return None
        branches = [[] for _ in conditions] if fact_provenance is not None else [None] * len(conditions)
        results = [
            evaluate_plan_node(conn, condition, target_country, item_value, branch, list_cache=list_cache)
            for condition, branch in zip(conditions, branches)
        ]
        merge_used_evidence(fact_provenance, results, branches, decisive=operator == "or")
        if operator == "or":
            if any(result is True for result in results):
                return True
            if any(result is None for result in results):
                return None
            return False
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True

    if operator == "exists":
        value = resolve_ref(conn, node.get("left", {}), target_country, item_value, list_cache=list_cache)
        if value is None:
            return None
        collect_ref_evidence(conn, node.get("left", {}), target_country, item_value, fact_provenance)
        if isinstance(value, list):
            return bool(value)
        return bool(value)

    if operator in {
        "contains",
        "equals",
        "greater_than",
        "less_than",
        "greater_than_or_equal",
        "less_than_or_equal",
        "west_of",
        "east_of",
        "north_of",
        "south_of",
        "starts_with",
        "ends_with",
        "contains_text",
        "has_space",
        "has_hyphen",
        "word_count_equals",
        "word_count_greater_than",
        "word_count_less_than",
        "char_count_equals",
        "char_count_greater_than",
        "char_count_less_than",
    }:
        left = resolve_ref(conn, node.get("left", {}), target_country, item_value, list_cache=list_cache)
        right = resolve_ref(conn, node.get("right", {}), target_country, item_value, list_cache=list_cache)
        if left is None or (operator not in {"has_space", "has_hyphen"} and right is None):
            return None
        collect_ref_evidence(
            conn,
            node.get("left", {}),
            target_country,
            item_value,
            fact_provenance,
            contains_value=right if operator == "contains" else None,
        )
        collect_ref_evidence(conn, node.get("right", {}), target_country, item_value, fact_provenance)
        left_ref = node.get("left", {})
        relation = str(left_ref.get("relation") or "") if isinstance(left_ref, dict) else ""
        if operator == "equals" and relation == "currency" and isinstance(left, list):
            c_canon = CURRENCY_ALIASES.get(normalize_value(right), normalize_value(right))
            return any(CURRENCY_ALIASES.get(normalize_value(v), normalize_value(v)) == c_canon for v in left)
        if operator != "contains" and (isinstance(left, list) or isinstance(right, list)):
            if (
                operator in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}
                and isinstance(left, list)
                and type(right) is not bool
                and (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit()))
            ):
                if relation == "borders_country":
                    canonical = set()
                    for item in left:
                        c_row = find_country(conn, str(item))
                        canonical.add(c_row["app_country_name"] if c_row is not None else str(item))
                    left_num = float(len(canonical))
                else:
                    left_num = float(len(left))
                right_num = float(right)
                if operator == "equals":
                    return left_num == right_num
                if operator == "greater_than_or_equal":
                    return left_num >= right_num
                if operator == "less_than_or_equal":
                    return left_num <= right_num
                if operator == "greater_than":
                    return left_num > right_num
                if operator == "less_than":
                    return left_num < right_num
            return None
        left_ref = node.get("left", {})
        if (
            operator in {"contains", "equals"}
            and isinstance(left_ref, dict)
            and str(left_ref.get("relation") or "").startswith("borders_")
            and is_self_country_reference(right, target_country)
        ):
            return False
        relation = str(left_ref.get("relation") or "") if isinstance(left_ref, dict) else ""
        if operator == "contains":
            if not isinstance(left, list) or isinstance(right, (list, dict, bool)):
                return None
            right_norm = normalize_value(right)
            if relation == "historical_union" and not conn.execute(
                "SELECT 1 FROM country_historical_unions WHERE union_name = ? COLLATE NOCASE LIMIT 1",
                (right,),
            ).fetchone():
                return None
            if relation == "borders_country":
                resolved = find_country(conn, right)
                if resolved is None:
                    return None
                subject = resolve_entity(conn, left_ref["entity"], target_country, item_value)
                if subject is not None and resolved["id"] == subject["id"]:
                    return False
                r_canon = canonical_country_name(resolved["app_country_name"])
                return any(canonical_country_name(value) == r_canon for value in left)
            if relation == "currency":
                c_canon = CURRENCY_ALIASES.get(right_norm, right_norm)
                return any(CURRENCY_ALIASES.get(normalize_value(value), normalize_value(value)) == c_canon for value in left)
            if relation == "hemisphere":
                h_canon = normalize_hemisphere(right_norm)
                return any(normalize_hemisphere(normalize_value(value)) == h_canon for value in left)
            if relation == "water_access":
                if right_norm == "sea":
                    return "Sea" in left or bool(left)
                if right_norm == "ocean":
                    return "Ocean" in left or any("ocean" in normalize_value(w) for w in left)
                return any(normalize_value(value) == right_norm for value in left)
            return any(normalize_value(value) == right_norm for value in left)
        if operator == "equals":
            refs = (left_ref, node.get("right", {}))
            if (
                any(ref.get("relation") == "name" for ref in refs)
                and all("value" in ref or ref.get("relation") == "name" for ref in refs)
            ):
                left_country = find_country(conn, left)
                right_country = find_country(conn, right)
                if left_country is None or right_country is None:
                    return None
                return left_country["id"] == right_country["id"]
            if relation == "dominant_religion":
                c_left = RELIGION_ALIASES.get(normalize_value(left).lower(), normalize_value(left))
                c_right = RELIGION_ALIASES.get(normalize_value(right).lower(), normalize_value(right))
                return normalize_value(c_left) == normalize_value(c_right)
            if relation == "driving_side":
                c_left = "left" if "left" in str(left).lower() else ("right" if "right" in str(left).lower() else str(left))
                c_right = "left" if "right" not in str(right).lower() and "left" in str(right).lower() else ("right" if "right" in str(right).lower() else str(right))
                return c_left.lower() == c_right.lower()
            return normalize_value(left) == normalize_value(right)
        if operator == "has_space":
            return " " in (text_value(left) or "").strip()
        if operator == "has_hyphen":
            left_text = text_value(left) or ""
            if any(char in left_text for char in "-\u2010\u2011"):
                return True
            return relation == "name" and _hyphenated_country_alias(left_text) is not None
        if operator in {"starts_with", "ends_with", "contains_text"}:
            left_text = normalize(text_value(left) or "", preserve_separators=True)
            right_text = normalize(text_value(right) or "", preserve_separators=True)
            if operator == "starts_with":
                stripped = right_text.rstrip("-").strip()
                if stripped:
                    right_text = stripped
                return left_text.startswith(right_text)
            if operator == "ends_with":
                stripped = right_text.lstrip("-").strip()
                if stripped:
                    right_text = stripped
                return left_text.endswith(right_text)
            if operator == "contains_text":
                stripped = right_text.strip("-").strip()
                if stripped:
                    right_text = stripped
                return right_text in left_text
        if operator.startswith("word_count_"):
            left_num = word_count(text_value(left) or "")
            try:
                right_num = int(right)
            except (TypeError, ValueError):
                return None
            if operator == "word_count_equals":
                return left_num == right_num
            if operator == "word_count_greater_than":
                return left_num > right_num
            if operator == "word_count_less_than":
                return left_num < right_num
        if operator.startswith("char_count_"):
            left_num = char_count(text_value(left) or "")
            try:
                right_num = int(right)
            except (TypeError, ValueError):
                return None
            if operator == "char_count_equals":
                return left_num == right_num
            if operator == "char_count_greater_than":
                return left_num > right_num
            if operator == "char_count_less_than":
                return left_num < right_num
        try:
            left_num = float(left)
            right_num = float(right)
        except (TypeError, ValueError):
            return None
        if operator == "greater_than_or_equal":
            return left_num >= right_num
        if operator == "less_than_or_equal":
            return left_num <= right_num
        if operator in {"north_of", "south_of", "west_of", "east_of"}:
            right_entity = node.get("right", {}).get("entity") if isinstance(node.get("right"), dict) else None
            if (
                right_entity in {"target_country", target_country["app_country_name"], target_country["official_name"]}
                or is_self_country_reference(right_entity, target_country)
            ):
                return None
        if operator in {"greater_than", "east_of", "north_of"}:
            return left_num > right_num
        if operator in {"less_than", "west_of", "south_of"}:
            return left_num < right_num

    if operator in {"any", "all"}:
        items = resolve_ref(conn, node.get("items", {}), target_country, item_value)
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return None
        collect_ref_evidence(conn, node.get("items", {}), target_country, item_value, fact_provenance)
        branches = [[] for _ in items] if fact_provenance is not None else [None] * len(items)
        results = [
            evaluate_plan_node(conn, condition, target_country, str(item), branch)
            for item, branch in zip(items, branches)
        ]
        merge_used_evidence(fact_provenance, results, branches, decisive=operator == "any")
        if operator == "any":
            if any(result is True for result in results):
                return True
            if any(result is None for result in results):
                return None
            return False
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True

    return None


def plan_relations(node: dict | None) -> set[str]:
    found: set[str] = set()
    if not isinstance(node, dict):
        return found
    for key in ("left", "right", "items"):
        ref = node.get(key)
        if isinstance(ref, dict) and isinstance(ref.get("relation"), str):
            found.add(ref["relation"].split(".")[0])
    found |= plan_relations(node.get("condition"))
    for condition in node.get("conditions", []) if isinstance(node.get("conditions"), list) else []:
        found |= plan_relations(condition)
    return found


_CONTINENT_UNIONS = {
    "america": ("North America", "South America"),
    "americas": ("North America", "South America"),
    "eurasia": ("Europe", "Asia"),
}


def normalize_continent_unions(node: dict | None) -> dict | None:
    """Expand physical continent unions without changing bindings or the input AST."""
    if not isinstance(node, dict):
        return node
    normalized = dict(node)
    if isinstance(normalized.get("condition"), dict):
        normalized["condition"] = normalize_continent_unions(normalized["condition"])
    if isinstance(normalized.get("conditions"), list):
        normalized["conditions"] = [
            normalize_continent_unions(condition) for condition in normalized["conditions"]
        ]
    left = normalized.get("left")
    right = normalized.get("right")
    if (
        normalized.get("operator") == "contains"
        and isinstance(left, dict)
        and left.get("relation") == "continent"
        and isinstance(right, dict)
        and isinstance(right.get("value"), str)
    ):
        continents = _CONTINENT_UNIONS.get(normalize(right["value"]))
        if continents is not None:
            return {
                "operator": "or",
                "conditions": [
                    {
                        **normalized,
                        "left": dict(left),
                        "right": {**right, "value": continent},
                    }
                    for continent in continents
                ],
            }
    return normalized


def normalize_geographic_area_plan(conn: sqlite3.Connection, node: dict | None) -> dict | None:
    """Canonicalize physical continent unions and the stored geographic-area layer."""
    return _normalize_geographic_area_plan(conn, normalize_continent_unions(node))


def _normalize_geographic_area_plan(conn: sqlite3.Connection, node: dict | None) -> dict | None:
    """Treat region and subregion planner output as one geographic-area layer."""
    if not isinstance(node, dict):
        return node

    normalized = dict(node)

    for key in ("left", "right", "items"):
        ref = normalized.get(key)
        if isinstance(ref, dict):
            normalized[key] = dict(ref)
            if ref.get("relation") in {"region", "subregion"}:
                normalized[key]["relation"] = "geographic_area"

    left = normalized.get("left")
    right = normalized.get("right")
    if (
        isinstance(left, dict)
        and left.get("relation") == "geographic_area"
        and isinstance(right, dict)
        and isinstance(right.get("value"), str)
    ):
        value = normalize(right["value"])
        if value in {"north america", "south america"}:
            left["relation"] = "continent"
            canonical_area = value.title()
        else:
            canonical_area = GEOGRAPHIC_AREA_ALIASES.get(value)
            if canonical_area is None:
                canonical_area = next(
                    (
                        row[0]
                        for row in conn.execute(
                            "SELECT region_name FROM country_regions "
                            "UNION SELECT subregion_name FROM country_subregions"
                        )
                        if normalize(row[0]) == value
                    ),
                    None,
                )
        if canonical_area is None:
            return None
        right["value"] = canonical_area
    if isinstance(normalized.get("condition"), dict):
        normalized["condition"] = _normalize_geographic_area_plan(conn, normalized["condition"])
    if isinstance(normalized.get("conditions"), list):
        normalized["conditions"] = [
            _normalize_geographic_area_plan(conn, condition)
            if isinstance(condition, dict)
            else condition
            for condition in normalized["conditions"]
        ]
    return normalized
