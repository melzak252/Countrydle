"""Spoiler-free interpretation clarifications for local KB answers."""

from __future__ import annotations

from typing import Any

from .aliases import norm
from .models import LocalModeConfig, QuestionPlan


def _clarification_subject(config: LocalModeConfig, entity: Any) -> str:
    if entity == "target_voivodeship":
        return "The voivodeship"
    return {
        "Powiatdle": "The county",
        "Wojewodztwodle": "The voivodeship",
        "USStatedle": "The US state",
        "Countydle": "The county",
    }.get(config.mode_name, f"The {config.entity_label}")


def _is_false_literal(val: Any) -> bool:
    return val is False or (isinstance(val, int) and type(val) is int and val == 0) or norm(val) in {"0", "false", "no", "nie"}


def build_clarification(config: LocalModeConfig, plan: QuestionPlan, answer: bool) -> str | None:
    """Return a short, spoiler-free confirmation of how a local KB question was interpreted."""
    root_plan = plan.plan
    node = root_plan[-1] if isinstance(root_plan, list) and root_plan else root_plan
    if not isinstance(node, dict):
        return None
    op = str(node.get("operator") or "")
    while op == "not":
        inner = node.get("condition") or node.get("operand")
        if isinstance(inner, int) and isinstance(root_plan, list) and 0 <= inner < len(root_plan):
            inner = root_plan[inner]
        if not isinstance(inner, dict):
            return None
        node = inner
        op = str(node.get("operator") or "")
        answer = not answer

    if op == "any":
        items = node.get("items")
        args = node.get("args")
        pred = node.get("condition") or (args[0] if isinstance(args, list) and args else None)
        if isinstance(items, dict) and items.get("relation") == "borders_powiat" and pred is not None:
            if isinstance(pred, int) and isinstance(root_plan, list) and 0 <= pred < len(root_plan):
                pred = root_plan[pred]
            if isinstance(pred, dict) and isinstance(pred.get("left"), dict) and pred["left"].get("relation") == "is_city_county":
                pred_val = pred.get("right", pred.get("value"))
                if isinstance(pred_val, dict):
                    pred_val = pred_val.get("value")
                is_city = not _is_false_literal(pred_val)
                subject = _clarification_subject(config, items.get("entity"))
                kind = "a city with county rights" if is_city else "a land county"
                return f"{subject} borders {kind}." if answer else f"{subject} does not border {kind}."
        return None

    left = node.get("left")
    right = node.get("right", node.get("value"))
    val = right.get("value") if isinstance(right, dict) else right

    if isinstance(left, dict):
        rel = str(left.get("relation") or "")
        subject = _clarification_subject(config, left.get("entity"))
    elif op in config.list_relations or op.startswith("borders_"):
        rel = op
        subject = _clarification_subject(config, None)
    else:
        return None

    if rel == "is_coastal":
        eff = (not answer) if _is_false_literal(val) else answer
        if config.mode_name in {"USStatedle", "Countydle"}:
            return f"{subject} has coastal access." if eff else f"{subject} is landlocked."
        return f"{subject} has Baltic Sea coastline." if eff else f"{subject} does not have Baltic Sea coastline."
    if rel == "is_metropolitan":
        eff = (not answer) if _is_false_literal(val) else answer
        return f"{subject} is a metropolitan county." if eff else f"{subject} is not a metropolitan county."
    if rel == "is_city_county":
        eff = (not answer) if _is_false_literal(val) else answer
        return f"{subject} is a city with county rights." if eff else f"{subject} is a land county."
    if rel == "water_access":
        eff = (not answer) if _is_false_literal(val) else answer
        if isinstance(val, str) and val.strip() and norm(val) not in {"true", "false", "1", "0"}:
            return f"{subject} has access to {val}." if eff else f"{subject} does not have access to {val}."
        return f"{subject} has coastline/water access." if eff else f"{subject} has no coastline/water access."

    if rel == "name":
        if op in {"equals", "contains_exact", "contains"} and isinstance(val, str) and val.strip():
            return f"{subject} is {val}." if answer else f"{subject} is not {val}."
        if op in {"contains_text", "contains_partial"} and isinstance(val, str) and val.strip():
            return f"{subject}'s name contains \"{val}\"." if answer else f"{subject}'s name does not contain \"{val}\"."
        if op in {"starts_with", "ends_with"} and isinstance(val, str) and val.strip():
            verb = "starts" if op == "starts_with" else "ends"
            neg = "start" if op == "starts_with" else "end"
            return f"{subject}'s name {verb} with \"{val}\"." if answer else f"{subject}'s name does not {neg} with \"{val}\"."
        if op == "has_space":
            return f"{subject}'s name has more than one word." if answer else f"{subject}'s name is a single word."
        if op == "has_hyphen":
            return f"{subject}'s name contains a hyphen." if answer else f"{subject}'s name does not contain a hyphen."
        if op in {"word_count_equals", "word_count_greater_than", "word_count_less_than", "char_count_equals", "char_count_greater_than", "char_count_less_than"} and val is not None:
            unit = "words" if op.startswith("word_count") else "letters"
            cmp_map = {"equals": "", "greater_than": "more than ", "less_than": "fewer than "}
            cmp_key = op.split("count_", 1)[1]
            phrase = f"{cmp_map.get(cmp_key, '')}{val} {unit}"
            return f"{subject}'s name has {phrase}." if answer else f"{subject}'s name does not have {phrase}."

    if rel == "seat" and isinstance(val, str) and val.strip():
        return f"{subject}'s seat is {val}." if answer else f"{subject}'s seat is not {val}."
    if rel == "county_town" and isinstance(val, str) and val.strip():
        return f"{subject}'s county town is {val}." if answer else f"{subject}'s county town is not {val}."
    if rel in {"voivodeship", "region", "division", "macroregion", "historical_regions", "landform_regions", "regional_labels"} and isinstance(val, str) and val.strip():
        return f"{subject} is in {val}." if answer else f"{subject} is not in {val}."
    if rel == "historical_partitions" and isinstance(val, str) and val.strip():
        return f"{subject} was part of {val}." if answer else f"{subject} was not part of {val}."
    if rel.startswith("borders_"):
        if op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"} and (isinstance(val, (int, float)) or (isinstance(val, str) and val.isdigit())):
            unit = {"borders_country": "countries", "borders_state": "states", "borders_voivodeship": "voivodeships", "borders_powiat": "counties", "borders_county": "counties"}.get(rel, "neighbors")
            cmp_phrase = {"equals": "", "greater_than": "more than ", "less_than": "fewer than ", "greater_than_or_equal": "at least ", "less_than_or_equal": "at most "}[op]
            return f"{subject} borders {cmp_phrase}{val} {unit}." if answer else f"{subject} does not border {cmp_phrase}{val} {unit}."
        if isinstance(val, str) and val.strip():
            return f"{subject} borders {val}." if answer else f"{subject} does not border {val}."
    if rel == "registration_plates":
        if op in {"char_count_equals", "char_count_greater_than", "char_count_less_than"} and val is not None:
            cmp_phrase = {"char_count_equals": "", "char_count_greater_than": "more than ", "char_count_less_than": "fewer than "}[op]
            return f"{subject}'s license plates have {cmp_phrase}{val} characters." if answer else f"{subject}'s license plates do not have {cmp_phrase}{val} characters."
        if op in {"starts_with", "ends_with"} and isinstance(val, str) and val.strip():
            verb = "start" if op == "starts_with" else "end"
            return f"{subject}'s license plates {verb} with \"{val}\"." if answer else f"{subject}'s license plates do not {verb} with \"{val}\"."
        if isinstance(val, str) and val.strip():
            return f"{subject} uses plate code {val}." if answer else f"{subject} does not use plate code {val}."
    if rel in {"major_rivers", "major_roads", "major_cities", "national_parks", "lakes", "major_lakes", "unesco_sites", "health_resorts", "mountain_ranges"}:
        if op == "exists":
            label = rel.replace("_", " ")
            return f"{subject} has {label}." if answer else f"{subject} does not have {label}."
        if isinstance(val, str) and val.strip():
            return f"{subject} has {val}." if answer else f"{subject} does not have {val}."
    if rel in {"latitude", "longitude"} and op in {"north_of", "south_of", "east_of", "west_of"}:
        dir_label = op.replace("_", " ")
        ref_name = right.get("entity") if isinstance(right, dict) and right.get("entity") else val
        if isinstance(ref_name, str) and (ref_name.startswith("target_") or ref_name == "item"):
            ref_name = None
        if ref_name is not None:
            return f"{subject} is {dir_label} {ref_name}." if answer else f"{subject} is not {dir_label} {ref_name}."
    if op in {"greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "equals"} and val is not None:
        label = rel.replace("_", " ")
        cmp_phrase = {"greater_than": "greater than", "less_than": "less than", "greater_than_or_equal": "at least", "less_than_or_equal": "at most", "equals": "equal to"}[op]
        return f"{subject}'s {label} is {cmp_phrase} {val}." if answer else f"{subject}'s {label} is not {cmp_phrase} {val}."
    if op == "exists":
        label = rel.replace("_", " ")
        return f"{subject} has {label}." if answer else f"{subject} does not have {label}."
    return None


_build_local_kb_clarification = build_clarification
