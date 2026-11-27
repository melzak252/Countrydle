"""Geographic bot auto-coloring computation for regional local KB modes."""

from __future__ import annotations

import sqlite3
from typing import Any

from .db import get_entity_row
from .evaluator import collect_relations, evaluate
from .models import LocalModeConfig, _safe_identifier

GEOGRAPHIC_AUTO_COLOR_RELATIONS = frozenset({
    # Borders & adjacency
    "borders_state",
    "borders_voivodeship",
    "borders_powiat",
    "borders_county",
    "borders_country",
    # Regions & administrative areas
    "region",
    "division",
    "macroregion",
    "voivodeship",
    "regional_labels",
    "historical_region",
    "historical_regions",
    "landform_regions",
    "historical_partitions",
    # Water & coastline
    "water_access",
    "is_coastal",
    "is_island",
    # Coordinates & cardinal directions
    "latitude",
    "longitude",
    "min_latitude",
    "max_latitude",
    "min_longitude",
    "max_longitude",
    # Reliable objective local KB facts (excluding fuzzy fields like nickname, health_resorts)
    "population",
    "area",
    "population_density",
    "urbanization",
    "major_rivers",
    "mountain_ranges",
    "major_roads",
    "major_highways",
    "registration_plates",
    "national_parks",
    "major_lakes",
    "lakes",
    "unesco_sites",
    "is_city_county",
    "is_metropolitan",
    "gmina_count",
    "urban_gmina_count",
    "rural_gmina_count",
    "urban_rural_gmina_count",
    "powiat_count",
    "city_count",
    "city_count_with_powiat_rights",
    "admission_year",
    "admission_order",
    "civil_war_side",
    "seat",
    "county_town",
    "major_cities",
})


def _collect_effective_relations(node: Any, config: LocalModeConfig) -> set[str]:
    """Collect relations referenced in an AST plan, including shorthand list operators."""
    found = set(collect_relations(node))
    if isinstance(node, dict):
        op = node.get("operator")
        if isinstance(op, str):
            if op in config.list_relations:
                found.add(op)
            elif op.startswith("borders_"):
                if "county" in op:
                    found.add("borders_county")
                elif "state" in op:
                    found.add("borders_state")
                elif "country" in op:
                    found.add("borders_country")
                elif "voivodeship" in op:
                    found.add("borders_voivodeship")
                elif "powiat" in op:
                    found.add("borders_powiat")
        for value in node.values():
            found.update(_collect_effective_relations(value, config))
    elif isinstance(node, list):
        for item in node:
            found.update(_collect_effective_relations(item, config))
    return found


def _extract_direct_name_targets(plan: Any) -> list[str] | None:
    if not isinstance(plan, dict):
        return None
    op = plan.get("operator")
    if op in ("equals", "contains_exact"):
        left = plan.get("left") or {}
        right = plan.get("right", plan.get("value"))
        if isinstance(left, dict) and left.get("relation") == "name":
            if isinstance(right, dict) and right.get("value"):
                return [str(right["value"])]
            if isinstance(right, str) and right.strip():
                return [right.strip()]
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


def compute_local_kb_map_highlight(
    conn: sqlite3.Connection,
    config: LocalModeConfig,
    plan: dict[str, Any],
    answer: bool,
) -> dict[str, Any] | None:
    """Evaluate a geographic AST plan across all entities in a regional SQLite KB.

    Only runs when every relation referenced by the plan is geographic/spatial (or a direct
    "Is it X?" entity-name check that answered False) so non-geographic trivia is never auto-colored.
    """
    direct_names = _extract_direct_name_targets(plan)
    if direct_names is not None:
        if answer is not False:
            return None
        eliminated_direct: list[str] = []
        for candidate in direct_names:
            found = get_entity_row(conn, config, candidate)
            if found is not None:
                canonical = found[config.name_column]
                if canonical and canonical not in eliminated_direct:
                    eliminated_direct.append(canonical)
        if not eliminated_direct:
            return None
        return {
            "supported": True,
            "matched": [],
            "eliminated": eliminated_direct,
            "note": None,
        }

    relations = _collect_effective_relations(plan, config)
    if not relations or not relations.issubset(GEOGRAPHIC_AUTO_COLOR_RELATIONS):
        return None

    table = _safe_identifier(config.table)
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    matched: list[str] = []
    eliminated: list[str] = []
    for row in rows:
        name = row[config.name_column]
        if not name:
            continue
        try:
            row_ans = evaluate(conn, config, row, plan)
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
