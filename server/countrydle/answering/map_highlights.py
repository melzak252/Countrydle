"""Geographic bot auto-coloring computation for Countrydle map highlights."""

from __future__ import annotations

import sqlite3

from countrydle.answering.db import find_country, preload_list_relations
from countrydle.answering.evaluator import evaluate_plan_node, plan_relations

_MAX_AUTO_COLOR_NODES = 8
_MAX_AUTO_COLOR_DEPTH = 4


def _is_simple_auto_color_plan(plan: dict) -> bool:
    """Keep auto-coloring fast and predictable by skipping quantified or deeply nested ASTs."""
    node_count = 0

    def walk(node: object, depth: int) -> bool:
        nonlocal node_count
        if not isinstance(node, dict):
            return True
        node_count += 1
        if node_count > _MAX_AUTO_COLOR_NODES or depth > _MAX_AUTO_COLOR_DEPTH:
            return False
        op = node.get("operator")
        if op in {"any", "all"}:
            return False
        if isinstance(node.get("condition"), dict):
            if not walk(node["condition"], depth + 1):
                return False
        conditions = node.get("conditions")
        if isinstance(conditions, list):
            for child in conditions:
                if not walk(child, depth + 1):
                    return False
        return True

    return walk(plan, 1)

GEOGRAPHIC_AUTO_COLOR_RELATIONS = frozenset({
    # Geographic & spatial
    "continent",
    "geographic_area",
    "region",
    "subregion",
    "hemisphere",
    "borders_country",
    "water_access",
    "marine_access",
    "is_island",
    "coordinates",
    "coordinates.latitude",
    "coordinates.longitude",
    "latitude",
    "longitude",
    "min_latitude",
    "max_latitude",
    "min_longitude",
    "max_longitude",
    # Reliable objective local KB facts (excluding fuzzy/subjective fields like government_type, dominant_religion)
    "population",
    "area",
    "currency",
    "official_language",
    "membership",
    "major_rivers",
    "driving_side",
    "flag_color",
    "flag_symbol",
    "historical_union",
    "capital",
})


def _extract_direct_name_targets(plan: dict) -> list[str] | None:
    if not isinstance(plan, dict):
        return None
    op = plan.get("operator")
    if op == "equals":
        left = plan.get("left") or {}
        right = plan.get("right") or {}
        if isinstance(left, dict) and left.get("relation") == "name" and isinstance(right, dict) and right.get("value"):
            return [str(right["value"])]
        return None
    if op in ("or", "any"):
        args = plan.get("conditions") or plan.get("args") or []
        if not args or not isinstance(args, list):
            return None
        names: list[str] = []
        for child in args:
            child_names = _extract_direct_name_targets(child)
            if not child_names:
                return None
            names.extend(child_names)
        return names
    return None


def compute_geographic_map_highlight(
    conn: sqlite3.Connection,
    plan: dict,
    answer: bool,
) -> dict | None:
    """Evaluate a geographic AST plan across all countries to return matched/eliminated sets.

    Only runs when every relation referenced by the plan is geographic/spatial (or a direct
    "Is it X?" country-name check that answered False) so non-geographic trivia is never auto-solved.
    """
    direct_names = _extract_direct_name_targets(plan)
    if direct_names is not None:
        if answer is not False:
            return None
        eliminated_direct: list[str] = []
        for candidate in direct_names:
            found = find_country(conn, candidate)
            if found is not None and found["app_country_name"] not in eliminated_direct:
                eliminated_direct.append(found["app_country_name"])
        if not eliminated_direct:
            return None
        return {
            "supported": True,
            "matched": [],
            "eliminated": eliminated_direct,
            "note": None,
        }

    if not _is_simple_auto_color_plan(plan):
        return None
    relations = plan_relations(plan)
    if not relations or not relations.issubset(GEOGRAPHIC_AUTO_COLOR_RELATIONS):
        return None
    country_rows = conn.execute("SELECT * FROM countries").fetchall()
    country_ids = [row["id"] for row in country_rows if row["id"] is not None]
    list_cache = preload_list_relations(conn, relations, country_ids)
    matched: list[str] = []
    eliminated: list[str] = []
    for row in country_rows:
        name = row["app_country_name"]
        if not name:
            continue
        try:
            row_ans = evaluate_plan_node(conn, plan, row, list_cache=list_cache)
        except Exception:
            continue
        if row_ans is None:
            continue
        if bool(row_ans) is bool(answer):
            matched.append(name)
        else:
            eliminated.append(name)
    if not matched and not eliminated:
        return None
    return {
        "supported": True,
        "matched": matched,
        "eliminated": eliminated,
        "note": None,
    }
