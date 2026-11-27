"""Human-readable factual explanation generation for evaluated Countrydle AST plans."""

from __future__ import annotations

import sqlite3

from countrydle.answering.aliases import (
    WATER_BODY_PARENT_MAP,
    _hyphenated_country_alias,
    char_count,
    expand_water_bodies,
    is_marine_water_body,
    normalize,
    normalize_hemisphere,
    word_count,
)
from countrydle.answering.clarifications import generate_plan_clarification
from countrydle.answering.db import (
    LIST_RELATION_QUERIES,
    find_country,
    resolve_entity,
    resolve_ref,
)
from countrydle.answering.evaluator import evaluate_plan_node


def generate_factual_explanation(
    conn: sqlite3.Connection,
    country: sqlite3.Row,
    plan: dict,
    answer: bool,
    *,
    item_value: str | None = None,
) -> str:
    def number(value: int | float) -> str:
        return f"{value:,}".removesuffix(".0")

    name = country["app_country_name"]
    node = plan if isinstance(plan, dict) else {}
    op = node.get("operator")
    left = node.get("left")
    right = node.get("right")
    rel = None
    target_val = None
    if isinstance(left, dict) and "relation" in left:
        rel = left["relation"]
    if isinstance(right, dict) and "value" in right:
        target_val = right["value"]
    if op == "not":
        child = node.get("condition")
        return generate_factual_explanation(
            conn, country, child, not answer, item_value=item_value
        )
    if op in {"and", "or"}:
        if op == "or" and answer is True:
            true_facts = []
            for child in node.get("conditions", []):
                if evaluate_plan_node(conn, child, country, item_value) is True:
                    detail = generate_factual_explanation(
                        conn, country, child, True, item_value=item_value
                    )
                    if detail and detail not in true_facts:
                        true_facts.append(detail)
            if true_facts:
                return " ".join(true_facts)
        facts = []
        for child in node.get("conditions", []):
            child_answer = evaluate_plan_node(conn, child, country, item_value)
            if child_answer is not None:
                detail = generate_factual_explanation(
                    conn, country, child, child_answer, item_value=item_value
                )
                if detail and detail not in facts:
                    facts.append(detail)
        if facts:
            return " ".join(facts)
        return ""
    if op in {"any", "all"}:
        items_ref = node.get("items", {})
        items = resolve_ref(conn, items_ref, country, item_value)
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return ""
        entity = items_ref.get("entity") if isinstance(items_ref, dict) else None
        subject = resolve_entity(conn, entity, country, item_value) if entity else None
        subject_name = subject["app_country_name"] if subject is not None else name
        neighbors = isinstance(items_ref, dict) and items_ref.get("relation") == "borders_country"
        facts = []
        for item in items:
            bound_value = str(item)
            child_answer = evaluate_plan_node(conn, condition, country, bound_value)
            if child_answer is answer:
                facts.append(
                    generate_factual_explanation(
                        conn, country, condition, child_answer, item_value=bound_value
                    )
                )
                if (op == "any" and answer) or (op == "all" and not answer):
                    break
        if facts:
            scope = f"Among {subject_name}'s land-border neighbors: " if neighbors else "Among the listed items: "
            return scope + " ".join(facts)
        if not items:
            return f"{subject_name} has no land-border neighbors." if neighbors else "There are no items to check."
        return ""
    target_country = country
    if isinstance(left, dict) and left.get("entity"):
        subject = resolve_entity(conn, left["entity"], target_country, item_value)
        if subject is not None:
            country = subject
            name = country["app_country_name"]

    if (
        isinstance(right, dict)
        and right.get("entity")
        and right.get("relation")
        and op not in {"north_of", "south_of", "east_of", "west_of"}
    ):
        other = resolve_entity(conn, right["entity"], target_country, item_value)
        if rel == "name" and right["relation"] == "name" and op == "equals" and other is not None:
            if country["id"] == other["id"]:
                role = "target" if country["id"] == target_country["id"] else "referenced"
                return f"{name} is the {role} country."
            return f"{name} and {other['app_country_name']} are different countries."
        value = resolve_ref(conn, right, target_country, item_value)
        if value is not None:
            detail = generate_factual_explanation(
                conn,
                target_country,
                {**node, "right": {"value": value}},
                answer,
                item_value=item_value,
            )
            other_detail = generate_factual_explanation(
                conn,
                target_country,
                {"operator": "exists", "left": right},
                bool(value),
                item_value=item_value,
            )
            return " ".join(dict.fromkeys(fact for fact in (detail, other_detail) if fact))

    if (
        rel in LIST_RELATION_QUERIES
        and op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}
        and type(target_val) is not bool
        and (isinstance(target_val, (int, float)) or isinstance(target_val, str) and target_val.isdigit())
    ):
        values = resolve_ref(conn, left, target_country, item_value)
        if isinstance(values, list):
            if rel == "borders_country":
                canonical = set()
                for value in values:
                    neighbor = find_country(conn, str(value))
                    canonical.add(neighbor["app_country_name"] if neighbor is not None else str(value))
                values = sorted(canonical)
            labels = {
                "continent": ("continent", "continents"),
                "region": ("region", "regions"),
                "subregion": ("subregion", "subregions"),
                "geographic_area": ("geographic area", "geographic areas"),
                "borders_country": ("land-border neighbor", "land-border neighbors"),
                "water_access": ("water-access entry", "water-access entries"),
                "marine_access": ("marine-access entry", "marine-access entries"),
                "currency": ("currency name or code", "currency names or codes"),
                "official_language": ("official language", "official languages"),
                "membership": ("membership", "memberships"),
                "major_rivers": ("major river", "major rivers"),
                "flag_color": ("flag color", "flag colors"),
                "flag_symbol": ("flag symbol", "flag symbols"),
                "historical_union": ("historical union", "historical unions"),
                "hemisphere": ("hemisphere", "hemispheres"),
            }
            label = labels[rel][0 if len(values) == 1 else 1]
            listing = f": {', '.join(map(str, values))}" if values else ""
            return f"{name} has {len(values)} {label} recorded{listing}."

    if rel == "borders_country":
        if target_val:
            resolved = find_country(conn, target_val)
            if resolved is not None:
                target_val = resolved["app_country_name"]
                if answer and resolved["id"] == country["id"]:
                    return f"In this game, {name} counts as bordering itself."
            borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id=?", (country["id"],))]
            if answer:
                return f"{name} shares a land border with {target_val}."
            b_str = ", ".join(sorted(set(borders))) if borders else "none"
            return f"{name} does not border {target_val}. Its land borders are: {b_str}."
        borders = resolve_ref(conn, left, target_country, item_value)
        if borders:
            return f"{name} shares land borders with {', '.join(sorted(set(borders)))}."
        return f"{name} has no land-border neighbors."

    if rel == "marine_access":
        db_waters = sorted(set(r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))))
        marine_waters = [water for water in db_waters if is_marine_water_body(water)]
        inland_waters = [water for water in db_waters if not is_marine_water_body(water)]
        if target_val:
            if answer:
                return f"{name} has coastline connected to the open sea via {target_val}."
            if not is_marine_water_body(str(target_val)):
                return f"{target_val} is an inland water body and does not connect {name}'s shoreline to the open sea."
            if inland_waters:
                return (
                    f"{name} does not have coastline connected to the open sea via {target_val}. "
                    f"It has inland shoreline on: {', '.join(inland_waters)}."
                )
            return f"{name} does not have coastline connected to the open sea via {target_val}."
        if answer:
            return f"{name} has coastline connected to the open sea via: {', '.join(marine_waters)}."
        if inland_waters:
            return (
                f"{name} has no coastline connected to the open sea. "
                f"It does have inland shoreline on: {', '.join(inland_waters)}."
            )
        return f"{name} has no coastline connected to the open sea."

    if rel == "water_access":
        db_waters = sorted(set(r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))))
        all_waters = expand_water_bodies(db_waters)
        all_waters_sorted = sorted(all_waters - {"Ocean", "Sea"})
        w_str = ", ".join(all_waters_sorted) if all_waters_sorted else ""
        if normalize(str(target_val)) == "sea":
            if answer:
                return f"{name} has direct coastline access to: {', '.join(db_waters)}."
            return f"{name} is completely landlocked with no direct coastline."

        if normalize(str(target_val)) == "ocean":
            if answer:
                return f"{name} has direct coastline access to: {', '.join(db_waters)}."
            if db_waters:
                return f"{name} does not have direct coastline access to an ocean. Its coastline access: {', '.join(db_waters)}."
            return f"{name} is completely landlocked with no direct coastline."
        if target_val:
            via_sub = [w for w in db_waters if w in WATER_BODY_PARENT_MAP and target_val in WATER_BODY_PARENT_MAP[w]]
            via_str = f" (via the {', '.join(via_sub)})"
            if answer:
                sub_note = via_str if via_sub and target_val not in db_waters else ""
                return f"{name} has direct coastline access to: {target_val}{sub_note}."
            if all_waters_sorted:
                return f"{name} does not have direct coastline access to: {target_val}. Its coastline access: {w_str}."
            return f"{name} is completely landlocked with no direct coastline to any sea or ocean (no access to: {target_val})."
        if all_waters_sorted:
            return f"{name} has direct coastline access to: {w_str}."
        return f"{name} is completely landlocked with no direct coastline."

    if rel == "hemisphere":
        db_hemis = [r[0] for r in conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id=?", (country["id"],))]
        h_str = " and the ".join(f"{hemisphere} Hemisphere" for hemisphere in sorted(db_hemis))
        if target_val:
            target_display = normalize_hemisphere(str(target_val)).capitalize()
            if answer:
                return f"{name} is located in the {target_display} Hemisphere."
            actual = f" It is located in the {h_str}." if h_str else ""
            return f"{name} is not located in the {target_display} Hemisphere.{actual}"
        return f"{name} is located in the {h_str}." if h_str else f"No hemispheres are recorded for {name}."
    if rel == "is_island":
        if country["is_island"]:
            return f"{name} is an island nation."
        return f"{name} is not an island nation."

    if rel == "continent":
        conts = [r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))]
        c_str = ", ".join(conts)
        if not conts:
            return f"No continents are recorded for {name}."
        if target_val and not answer:
            return f"{name} is not located in {target_val}; it is in {c_str}."
        return f"{name} is located in {c_str}."

    if rel in ("geographic_area", "region", "subregion"):
        subregs = [r[0] for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))]
        regs = [r[0] for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))]
        all_areas = sorted(set(subregs + regs))
        areas_str = ", ".join(all_areas)
        if target_val:
            if answer:
                return f"{name} is located in {target_val}."
            return f"{name} is not located in {target_val}. Its geographic regions are {areas_str or 'not recorded'}."
        return f"The geographic regions recorded for {name} are {areas_str}." if all_areas else f"No geographic regions are recorded for {name}."

    if rel == "currency":
        curr_rows = conn.execute("SELECT currency_name, currency_code FROM country_currencies WHERE country_id=?", (country["id"],)).fetchall()
        if not curr_rows:
            return f"No official currencies are recorded for {name}."
        currs_str = ", ".join(f"{r[0]} ({r[1]})" if r[1] else r[0] for r in curr_rows)
        label = "currency" if len(curr_rows) == 1 else "currencies"
        verb = "is" if len(curr_rows) == 1 else "are"
        actual = f"The official {label} of {name} {verb} {currs_str}."
        return actual if answer or target_val is None else f"{target_val} is not an official currency of {name}. {actual}"

    if rel == "official_language":
        langs = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id=?", (country["id"],))]
        if not langs:
            return f"No official languages are recorded for {name}."
        langs_str = ", ".join(langs)
        label = "language" if len(langs) == 1 else "languages"
        verb = "is" if len(langs) == 1 else "are"
        actual = f"The official {label} of {name} {verb} {langs_str}."
        return actual if answer or target_val is None else f"{target_val} is not an official language of {name}. {actual}"

    if rel == "major_rivers":
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id=?", (country["id"],))]
        if target_val:
            if answer:
                return f"The river {target_val} flows through {name}."
            actual = f" Major rivers include {', '.join(rivers)}." if rivers else ""
            return f"The river {target_val} does not flow through {name}.{actual}"
        return f"Major rivers in {name} include {', '.join(rivers)}." if rivers else f"No major rivers are recorded for {name}."

    if rel in ("historical_union", "membership"):
        if target_val:
            if rel == "membership":
                return f"{name} {'is' if answer else 'is not'} a member of {target_val}."
            return f"{name} {'was historically part' if answer else 'was not part'} of {target_val}."
        values = resolve_ref(conn, left, target_country, item_value)
        if values:
            listing = ", ".join(values)
            return f"{name} is a member of {listing}." if rel == "membership" else f"{name} was historically part of {listing}."
        label = "memberships" if rel == "membership" else "historical unions"
        return f"No {label} are recorded for {name}."

    if rel == "flag_color":
        colors = [r[0] for r in conn.execute("SELECT color FROM country_flag_colors WHERE country_id=?", (country["id"],))]
        if not colors:
            return f"No flag colors are recorded for {name}."
        actual = f"The flag of {name} contains {', '.join(colors)}."
        return actual if answer or target_val is None else f"The flag of {name} does not include {target_val}. {actual}"

    if rel == "flag_symbol":
        symbols = [r[0] for r in conn.execute("SELECT symbol FROM country_flag_symbols WHERE country_id=?", (country["id"],))]
        if target_val and answer:
            return f"The flag of {name} features {target_val}."
        actual = f"The flag of {name} features {', '.join(symbols)}." if symbols else f"No flag symbols are recorded for {name}."
        return actual if target_val is None else f"The flag of {name} does not feature {target_val}. {actual}"

    if rel == "driving_side":
        side_en = "left" if country["driving_side"] == "left" else "right"
        return f"Traffic in {name} drives on the {side_en} side."

    if rel == "population":
        pop = country["population"]
        if target_val is not None and op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}:
            try:
                val_num = float(target_val)
                comparison = "equal to" if pop == val_num else "more than" if pop > val_num else "fewer than"
                return f"{name} has a population of approximately {number(pop)} ({comparison} {number(val_num)})."
            except (ValueError, TypeError):
                pass
        return f"{name} has a population of approximately {number(pop)}."

    if rel in ("area_km2", "area"):
        area = country["area_km2"]
        if target_val is not None and op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}:
            try:
                val_num = float(target_val)
                comparison = "equal to" if area == val_num else "larger than" if area > val_num else "smaller than"
                return f"The area of {name} is approximately {number(area)} km², {comparison} {number(val_num)} km²."
            except (ValueError, TypeError):
                pass
        return f"The area of {name} is approximately {number(area)} km²."

    if rel == "dominant_religion":
        relig = country["dominant_religion"]
        if target_val and not answer:
            return f"The dominant religion in {name} is {relig}, not {target_val}."
        return f"The dominant religion in {name} is {relig}."

    if rel == "government_type":
        gov = country["government_type"]
        if target_val and not answer:
            return f"The government type of {name} is {gov}, not {target_val}."
        return f"The government type of {name} is {gov}."

    if op in ("north_of", "south_of", "east_of", "west_of"):
        other_entity_name = right.get("entity") if isinstance(right, dict) else None
        other_country = resolve_entity(conn, other_entity_name, target_country, item_value) if other_entity_name else None
        if other_country is not None:
            axis = "latitude" if op in ("north_of", "south_of") else "longitude"
            coordinate = country[axis]
            other_coordinate = other_country[axis]
            positive, negative = ("N", "S") if axis == "latitude" else ("E", "W")
            cardinal = positive if coordinate >= 0 else negative
            other_cardinal = positive if other_coordinate >= 0 else negative
            coordinate_text = f"{number(abs(coordinate))}°{cardinal}"
            other_text = f"{number(abs(other_coordinate))}°{other_cardinal}"
            other_name = other_country["app_country_name"]
            if coordinate == other_coordinate:
                return f"{name} and {other_name} have the same recorded {axis} ({coordinate_text})."
            directions = ("north", "south") if axis == "latitude" else ("east", "west")
            direction = directions[0 if coordinate > other_coordinate else 1]
            return (
                f"By the recorded coordinates, {name} ({coordinate_text}) is {direction} "
                f"of {other_name} ({other_text})."
            )

    if rel in {
        "coordinates.latitude", "coordinates.longitude", "latitude", "longitude",
        "min_latitude", "max_latitude", "min_longitude", "max_longitude",
    }:
        coordinate = resolve_ref(conn, left, target_country, item_value)
        if coordinate is not None:
            axis = "latitude" if "latitude" in rel else "longitude"
            positive, negative = ("N", "S") if axis == "latitude" else ("E", "W")
            cardinal = positive if coordinate >= 0 else negative
            label = rel.removeprefix("coordinates.").replace("min_", "minimum ").replace("max_", "maximum ")
            return f"The recorded {label} of {name} is {number(abs(coordinate))}°{cardinal}."

    if rel in {"name", "capital"}:
        text = name if rel == "name" else country["capital"]
        intro = "" if rel == "name" else f"The capital of {name} is {text}. "
        label = f"The name {text}" if rel == "name" else "Its name"
        if op in {"has_space", "has_hyphen"}:
            present = " " in text.strip() if op == "has_space" else any(
                char in text for char in "-\u2010\u2011"
            )
            if op == "has_hyphen" and rel == "name" and not present:
                alias = _hyphenated_country_alias(text)
                if alias is not None:
                    return f"The accepted alias “{alias}” for {name} contains a hyphen."
            mark = "a space" if op == "has_space" else "a hyphen"
            return intro + f"{label} {'contains' if present else 'does not contain'} {mark}."
        if op and op.startswith("word_count"):
            count = word_count(text)
            return intro + f"{label} consists of {count} {'words' if count != 1 else 'word'}."
        if op and op.startswith("char_count"):
            count = char_count(text)
            return intro + f"{label} has {count} characters, excluding spaces and hyphens."
        if op in {"starts_with", "ends_with", "contains_text"} and target_val is not None:
            s_val = str(target_val)
            clean_target = (
                (s_val.lstrip("-").strip() or s_val)
                if op == "ends_with"
                else ((s_val.rstrip("-").strip() or s_val) if op == "starts_with" else (s_val.strip("-").strip() or s_val))
            )
            positive, negative = {
                "starts_with": ("starts with", "does not start with"),
                "ends_with": ("ends with", "does not end with"),
                "contains_text": ("contains", "does not contain"),
            }[op]
            return intro + f"{label} {positive if answer else negative} “{clean_target}”."
        if rel == "name":
            role = "target" if country["id"] == target_country["id"] else "referenced"
            return f"{name} is the {role} country."
        return intro.strip()

    left_value = resolve_ref(conn, left, target_country, item_value)
    right_value = resolve_ref(conn, right, target_country, item_value)
    if op == "exists":
        return f"The provided value is {'nonempty' if bool(left_value) else 'empty'}."
    if isinstance(left_value, str):
        if op and op.startswith("word_count"):
            count = word_count(left_value)
            return f"The text “{left_value}” consists of {count} {'words' if count != 1 else 'word'}."
        if op and op.startswith("char_count"):
            return f"The text “{left_value}” has {char_count(left_value)} characters, excluding spaces and hyphens."
        if op in {"has_space", "has_hyphen"}:
            present = " " in left_value.strip() if op == "has_space" else any(
                char in left_value for char in "-\u2010\u2011"
            )
            mark = "a space" if op == "has_space" else "a hyphen"
            return f"The text “{left_value}” {'contains' if present else 'does not contain'} {mark}."
        if op in {"starts_with", "ends_with", "contains_text"}:
            s_val = str(right_value)
            clean_right = (
                (s_val.lstrip("-").strip() or s_val)
                if op == "ends_with"
                else ((s_val.rstrip("-").strip() or s_val) if op == "starts_with" else (s_val.strip("-").strip() or s_val))
            )
            positive, negative = {
                "starts_with": ("starts with", "does not start with"),
                "ends_with": ("ends with", "does not end with"),
                "contains_text": ("contains", "does not contain"),
            }[op]
            return f"The text “{left_value}” {positive if answer else negative} “{clean_right}”."
    if op in {"greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "north_of", "south_of", "east_of", "west_of"}:
        try:
            left_number = float(left_value)
            right_number = float(right_value)
            comparison = "equal to" if left_number == right_number else "greater than" if left_number > right_number else "less than"
            return f"{number(left_number)} is {comparison} {number(right_number)}."
        except (TypeError, ValueError):
            return ""
    if op == "equals":
        def display(value) -> str:
            if isinstance(value, str):
                return f"“{value}”"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return number(value)
            return "an empty value" if value is None else "a provided value"

        return f"{display(left_value)} is {'equal' if answer else 'not equal'} to {display(right_value)}."
    if op == "contains" and isinstance(left_value, list):
        return f"The provided list {'contains' if answer else 'does not contain'} “{right_value}”."
    return ""


__all__ = [
    "generate_factual_explanation",
    "generate_plan_clarification",
]
