"""Mode-specific factual explanation generation for local KB answers."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import replace
from typing import Any

from powiat_names import resolve_powiat_name
from voivodeship_names import resolve_voivodeship_name

from .aliases import (
    POLISH_NEIGHBORING_COUNTRIES_ALIASES,
    POLISH_RIVER_ALIASES,
    UK_NEIGHBORING_COUNTRIES_ALIASES,
    _REGIONAL_DISPLAY,
    _resolve_english_county_alias,
    norm,
)
from .clarification import _build_local_kb_clarification, build_clarification
from .db import _get_parent_voivodeship_relation, _reference_row, resolve_ref
from .evaluator import evaluate
from .models import (
    LocalModeConfig,
    QuestionPlan,
    _VOIVODESHIP_LIST_RELATIONS,
    _safe_identifier,
)


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
            "borders_county" if "county" in op
            else "borders_state" if "state" in op
            else "borders_country" if "country" in op
            else "borders_voivodeship" if "voivodeship" in op
            else "borders_powiat"
        )
        left = {"entity": config.target_entity, "relation": rel}
    right_node = node.get("right", node.get("value")) if isinstance(node, dict) else None
    val = resolve_ref(conn, config, target_row, right_node, item_value)
    subject_row = _reference_row(conn, config, target_row, left, item_value)
    row = subject_row if subject_row is not None else target_row
    name = row[config.name_column]
    from utils.water_hierarchy import get_distinct_oceans, is_multi_ocean_question

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
        prefix = f"{subject}: " if subject is not None else ""
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
                table = _safe_identifier(config.table)
                name_col = _safe_identifier(config.name_column)
                neighbors = conn.execute(
                    " ".join(["SELECT * FROM", table, "WHERE", name_col, "IN (SELECT value FROM json_each(?))"]),
                    (json.dumps(items),),
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
            or (numeric_value and rel not in {"borders_state", "borders_voivodeship", "borders_powiat", "borders_county"})
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
                raw_table, raw_column = config.list_relations[rel]
                table = _safe_identifier(raw_table)
                column = _safe_identifier(raw_column)
                fk_column = _safe_identifier(config.fk_column or "".join([config.table[:-1], "_id"]))
                values = [r[0] for r in conn.execute(
                    " ".join(["SELECT", column, "FROM", table, "WHERE", fk_column, "= ?"]), (row["id"],)
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
    elif config.mode_name == "Countydle":
        if rel == "name" and op in {"equals", "contains_exact", "contains"} and val:
            display_val = _resolve_english_county_alias(val)
            return f"{verdict} - The county is {display_val}." if answer else f"{verdict} - The county is not {display_val}."
        if rel == "is_coastal":
            return f"{verdict} - {name} is a coastal county." if row["is_coastal"] else f"{verdict} - {name} is a landlocked county."
        if rel == "is_metropolitan":
            return f"{verdict} - {name} is a metropolitan county." if row["is_metropolitan"] else f"{verdict} - {name} is a non-metropolitan ceremonial county."
        if rel == "county_town":
            return f"{verdict} - {name}'s county town is {row['county_town']}."
        if rel == "region":
            return f"{verdict} - {name} is located in the {row['region']} region of England."
        if rel == "borders_county":
            borders = [r[0] for r in conn.execute("SELECT border_county_name FROM english_county_borders_counties WHERE county_id = ?", (row["id"],))]
            if numeric_value:
                b_str = f" ({', '.join(borders)})" if borders else ""
                return f"{verdict} - {name} borders {len(borders)} English ceremonial counties{b_str}."
            display_val = _resolve_english_county_alias(val) if val else ""
            if display_val:
                if answer:
                    return f"{verdict} - {name} borders {display_val}."
                return f"{verdict} - {name} does not border {display_val}. Bordering counties: {', '.join(borders) if borders else 'none'}."
            return f"{verdict} - {name}'s bordering counties ({len(borders)}): {', '.join(borders) if borders else 'none'}."
        if rel == "borders_country":
            borders = [r[0] for r in conn.execute("SELECT country_name FROM english_county_borders_countries WHERE county_id = ?", (row["id"],))]
            if val:
                display_val = UK_NEIGHBORING_COUNTRIES_ALIASES.get(norm(val), val)
                if answer:
                    return f"{verdict} - {name} borders {display_val}."
                return f"{verdict} - {name} does not border {display_val}. Bordering countries: {', '.join(borders) if borders else 'none'}."
            return f"{verdict} - {name}'s bordering countries: {', '.join(borders) if borders else 'none'}."
        if rel == "water_access":
            waters = [r[0] for r in conn.execute("SELECT water_body FROM english_county_water_access WHERE county_id = ?", (row["id"],))]
            if val:
                if answer:
                    return f"{verdict} - {name} has coastline access to {val}."
                return f"{verdict} - {name} does not have access to {val}. Recorded water bodies: {', '.join(waters) if waters else 'none'}."
            return f"{verdict} - {name}'s coastline water bodies: {', '.join(waters) if waters else 'none'}."
        if rel == "regional_labels":
            labels_list = [r[0] for r in conn.execute("SELECT label FROM english_county_regional_labels WHERE county_id = ?", (row["id"],))]
            return f"{verdict} - {name}'s regional labels: {', '.join(labels_list) if labels_list else 'none'}."
        return factual_fallback()
    else:
        if rel == "name" and op in {"equals", "contains_exact", "contains"} and val:
            return f"{verdict} - The state is {val}." if answer else f"{verdict} - The state is not {val}."
        if rel == "is_coastal":
            return f"{name} is a coastal state with ocean/gulf coastline." if row[config.scalar_relations[rel]] else f"{name} is an inland state with no ocean coastline."
        if rel == "water_access":
            from utils.water_hierarchy import WATER_BODY_PARENT_MAP, get_distinct_oceans, is_multi_ocean_question

            direct_waters = [r[0] for r in conn.execute("SELECT water_body FROM us_state_water_access WHERE state_id=?", (row["id"],))]
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


__all__ = [
    "build_clarification",
    "_build_local_kb_clarification",
    "generate_mode_explanation",
]
