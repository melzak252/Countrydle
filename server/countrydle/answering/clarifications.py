"""Spoiler-free player clarifications generated directly from AST plans."""

from __future__ import annotations

import sqlite3

from countrydle.answering.db import find_country


def generate_plan_clarification(
    plan: dict,
    answer: bool,
    conn: sqlite3.Connection | None = None,
) -> str | None:
    """Generate a clean, grammatical English clarification directly from AST plan node."""
    if not isinstance(plan, dict):
        return None

    op = plan.get("operator")
    left = plan.get("left") or {}
    right = plan.get("right") or {}
    rel = left.get("relation") if isinstance(left, dict) else None
    val = right.get("value") if isinstance(right, dict) else None
    entity = right.get("entity") if isinstance(right, dict) else None

    # Handle negation wrapper
    if op == "not":
        child = plan.get("condition") or (plan.get("args") and isinstance(plan.get("args")[0], dict) and plan.get("args")[0])
        if child:
            return generate_plan_clarification(child, not answer, conn=conn)
        if rel in ("marine_access", "water_access"):
            return "The country is landlocked." if answer else "The country has access to the sea/ocean."

    # Handle compound boolean nodes (or/any/and/all)
    if op in ("or", "any", "and", "all"):
        args = [a for a in (plan.get("conditions") or plan.get("args") or []) if isinstance(a, dict)]
        if args:
            arg_rels = {a.get("left", {}).get("relation") for a in args if isinstance(a.get("left"), dict)}
            arg_vals = [
                str(a.get("right", {}).get("value") or a.get("right", {}).get("entity") or "")
                for a in args
                if isinstance(a.get("right"), dict) and (a.get("right", {}).get("value") or a.get("right", {}).get("entity"))
            ]
            conj = " and " if op in ("and", "all") else " or "
            if arg_rels and arg_rels.issubset({"continent", "geographic_area", "region", "subregion"}) and arg_vals:
                val_set = set(arg_vals)
                if op in ("or", "any") and val_set == {"Europe", "Asia"}:
                    target = "Eurasia"
                elif op in ("or", "any") and val_set == {"North America", "South America"}:
                    target = "the Americas"
                else:
                    target = conj.join(arg_vals)
                return f"The country is located in {target}." if answer else f"The country is not located in {target}."
            if arg_rels and arg_rels.issubset({"water_access", "marine_access"}) and arg_vals:
                target = conj.join(arg_vals)
                return f"The country has access to {target}." if answer else f"The country does not have access to {target}."
            if arg_rels == {"borders_country"} and arg_vals:
                target = conj.join(arg_vals)
                return f"The country borders {target}." if answer else f"The country does not border {target}."
            if arg_rels == {"membership"} and arg_vals:
                target = conj.join(arg_vals)
                return f"The country is a member of {target}." if answer else f"The country is not a member of {target}."
            if arg_rels == {"hemisphere"} and arg_vals:
                if op in ("and", "all") and set(arg_vals) == {"Northern", "Southern"}:
                    return "The country crosses the equator." if answer else "The country does not cross the equator."
                target = conj.join(f"the {v} Hemisphere" for v in arg_vals)
                return f"The country is in {target}." if answer else f"The country is not in {target}."

    # Direct Country Name / Identity
    if rel == "name":
        if op == "equals" and val:
            return f"The country is {val}." if answer else f"The country is not {val}."
        if op == "ends_with" and val:
            clean_val = str(val).lstrip("-").strip() or str(val)
            return f"The country name ends with “{clean_val}”." if answer else f"The country name does not end with “{clean_val}”."
        if op == "starts_with" and val:
            clean_val = str(val).rstrip("-").strip() or str(val)
            return f"The country name starts with “{clean_val}”." if answer else f"The country name does not start with “{clean_val}”."
        if op == "contains_text" and val:
            clean_val = str(val).strip("-").strip() or str(val)
            return f"The country name contains “{clean_val}”." if answer else f"The country name does not contain “{clean_val}”."

    # Geography: Continents & Regions
    if rel in ("continent", "geographic_area", "region", "subregion"):
        target = val or "this region"
        return f"The country is located in {target}." if answer else f"The country is not located in {target}."

    # Borders
    if rel == "borders_country":
        if op in ("equals", "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal") and isinstance(val, (int, float)):
            n = int(val) if float(val).is_integer() else val
            unit = "country" if n == 1 else "countries"
            if op == "equals":
                return f"The country borders exactly {n} {unit}." if answer else f"The country does not border exactly {n} {unit}."
            if op == "greater_than":
                return f"The country borders more than {n} {unit}." if answer else f"The country does not border more than {n} {unit}."
            if op == "greater_than_or_equal":
                return f"The country borders at least {n} {unit}." if answer else f"The country borders fewer than {n} {unit}."
            if op == "less_than":
                return f"The country borders fewer than {n} {unit}." if answer else f"The country does not border fewer than {n} {unit}."
            if op == "less_than_or_equal":
                return f"The country borders at most {n} {unit}." if answer else f"The country borders more than {n} {unit}."
        target = val or entity or "that country"
        return f"The country borders {target}." if answer else f"The country does not border {target}."

    # Water & Sea Access
    if rel in ("water_access", "marine_access"):
        if op == "exists":
            return "The country has direct coastline access to the sea." if answer else "The country is landlocked."
        if val == "Ocean":
            return "The country has direct coastline access to an ocean." if answer else "The country does not have direct coastline access to an ocean."
        if val == "Sea":
            return "The country has direct coastline access to the sea." if answer else "The country does not have direct access to the sea."
        if val:
            return f"The country has access to {val}." if answer else f"The country does not have access to {val}."
        return "The country has direct coastline access to the sea." if answer else "The country is landlocked."

    # Islands
    if rel == "is_island":
        return "The country is an island / archipelago." if answer else "The country is not an island country."

    # Coordinates & Hemispheres & Directions
    if rel == "hemisphere":
        if val in ("Northern", "Southern", "Eastern", "Western"):
            return f"The country is in the {val} Hemisphere." if answer else f"The country is not in the {val} Hemisphere."

    if op in ("north_of", "south_of", "east_of", "west_of"):
        axis = "latitude" if op in ("north_of", "south_of") else "longitude"
        ref_coord = None
        if entity and conn is not None:
            other_country = find_country(conn, entity)
            if other_country is not None:
                ref_coord = other_country[axis]
        elif isinstance(val, (int, float)):
            ref_coord = float(val)

        if ref_coord is not None:
            positive, negative = ("N", "S") if axis == "latitude" else ("E", "W")
            cardinal = positive if ref_coord >= 0 else negative
            coord_text = f"{round(abs(ref_coord))}°{cardinal}"
            phrases = {
                "south_of": (
                    f"The country is below {coord_text} (anywhere below this line).",
                    f"The country is not below {coord_text} (at or above this line).",
                ),
                "north_of": (
                    f"The country is above {coord_text} (anywhere above this line).",
                    f"The country is not above {coord_text} (at or below this line).",
                ),
                "west_of": (
                    f"The country is west of {coord_text} (anywhere left of this line).",
                    f"The country is not west of {coord_text} (at or right of this line).",
                ),
                "east_of": (
                    f"The country is east of {coord_text} (anywhere right of this line).",
                    f"The country is not east of {coord_text} (at or left of this line).",
                ),
            }
            return phrases[op][0 if answer else 1]

        target = entity or val or "that country"
        fallback_phrases = {
            "south_of": (
                f"The country is south of {target} (anywhere below its latitude line).",
                f"The country is not south of {target} (at or above its latitude line).",
            ),
            "north_of": (
                f"The country is north of {target} (anywhere above its latitude line).",
                f"The country is not north of {target} (at or below its latitude line).",
            ),
            "west_of": (
                f"The country is west of {target} (anywhere left of its longitude line).",
                f"The country is not west of {target} (at or right of its longitude line).",
            ),
            "east_of": (
                f"The country is east of {target} (anywhere right of its longitude line).",
                f"The country is not east of {target} (at or left of its longitude line).",
            ),
        }
        return fallback_phrases[op][0 if answer else 1]

    # Capital
    if rel == "capital":
        target = val or "that capital"
        return f"The capital is {target}." if answer else f"The capital is not {target}."

    # Currency
    if rel == "currency":
        display = "US dollars / dollars" if val == "United States dollar" else (val or "that currency")
        return f"The country uses {display}." if answer else f"The country does not use {display}."

    # Government
    if rel == "government_type":
        target = val or "that government type"
        return f"The government type is {target}." if answer else f"The government type is not {target}."

    # Memberships / Alliances
    if rel == "membership":
        target = val or "that organization"
        return f"The country is a member of {target}." if answer else f"The country is not a member of {target}."

    # Historical Union / Empire / Colony
    if rel in ("historical_union", "historical_empire"):
        target = val or "that empire"
        return f"The country was part of {target}." if answer else f"The country was not part of {target}."

    # Languages
    if rel == "languages":
        target = val or "that language"
        return f"{target} is an official/co-official language of the country." if answer else f"{target} is not an official language of the country."

    # Religion
    if rel == "dominant_religion":
        target = val or "that religion"
        return f"The dominant religion is {target}." if answer else f"The dominant religion is not {target}."

    # Driving Side
    if rel == "driving_side":
        side = val or "that side"
        return f"Traffic drives on the {side} side." if answer else f"Traffic does not drive on the {side} side."

    # Population & Area Comparisons (both numeric values and entity comparisons)
    if rel in ("population", "area"):
        is_more = op in ("greater_than", "greater_than_or_equal", "more_than", "larger_than")
        if entity:
            metric = "a larger area" if rel == "area" else "a larger population"
            if is_more:
                return f"The country has {metric} than {entity}." if answer else f"The country does not have {metric} than {entity}."
            metric_less = "a smaller area" if rel == "area" else "a smaller population"
            return f"The country has {metric_less} than {entity}." if answer else f"The country does not have {metric_less} than {entity}."
        if val is not None:
            comp = {
                "greater_than": "more than",
                "greater_than_or_equal": "at least",
                "less_than": "less than",
                "less_than_or_equal": "at most",
                "equals": "exactly",
            }.get(op, "more than" if is_more else "less than")
            unit = " km²" if rel == "area" else ""
            formatted_val = f"{val:,}{unit}" if isinstance(val, (int, float)) else str(val)
            return (
                f"The country has {comp} {formatted_val} {rel}."
                if answer
                else f"The country does not have {comp} {formatted_val} {rel}."
            )
    return None
