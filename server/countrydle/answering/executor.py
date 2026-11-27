"""Top-level local plan execution pipeline for Countrydle."""

from __future__ import annotations

import re
import sqlite3

from countrydle.answering.clarifications import generate_plan_clarification
from countrydle.answering.db import LocalAnswer, find_country, get_default_db_path
from countrydle.answering.direct_answering import LocalCountryFacts
from countrydle.answering.evaluator import (
    evaluate_plan_node,
    normalize_geographic_area_plan,
    plan_relations,
)
from countrydle.answering.explanations import generate_factual_explanation
from countrydle.answering.map_highlights import compute_geographic_map_highlight


def execute_local_plan(
    plan: dict | list,
    country_name: str,
    improved_question: str,
) -> LocalAnswer | None:
    db_path = get_default_db_path()
    if not db_path.exists():
        return None
    if isinstance(plan, list):
        if not plan:
            return None
        if len(plan) == 1 and isinstance(plan[0], dict) and "args" not in plan[0]:
            plan = plan[0]
        else:
            try:
                from planner_protocol import PLANNER_OPERATORS, compile_planner_response
                from countrydle.local_planner import SUPPORTED_RELATIONS

                relations = set(SUPPORTED_RELATIONS) | {
                    "coordinates.latitude",
                    "coordinates.longitude",
                    "region",
                    "subregion",
                    "hemisphere",
                }
                operators = PLANNER_OPERATORS | {"any", "all"}
                plan = compile_planner_response(
                    {"route": "local", "plan": plan},
                    relations=relations,
                    operators=operators,
                    target_entity="target_country",
                    allow_named_entities=True,
                )
            except Exception:
                plan = plan[-1] if isinstance(plan[-1], dict) else None
    if not isinstance(plan, dict):
        return None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        country = find_country(conn, country_name)
        if country is None:
            return None
        plan = normalize_geographic_area_plan(conn, plan)
        if plan is None:
            return None
        fact_provenance = []
        answer = evaluate_plan_node(conn, plan, country, fact_provenance=fact_provenance)
        if answer is None:
            return None
        relations = sorted(plan_relations(plan)) or ["local_plan"]
        explanation = generate_factual_explanation(conn, country, plan, answer)

        clarification = generate_plan_clarification(plan, answer, conn=conn)
        if not clarification:
            try:
                direct_answer = LocalCountryFacts(db_path).try_answer(improved_question, country_name)
            except Exception:
                direct_answer = None
            if direct_answer and direct_answer.clarification:
                clarification = direct_answer.clarification
            else:
                cleaned_q = improved_question.strip().rstrip("?").strip()
                if re.match(r"^(?:was (?:the |this )?country|was it)\s+", cleaned_q, flags=re.IGNORECASE):
                    rest = re.sub(r"^(?:was (?:the |this )?country|was it)\s+", "", cleaned_q, flags=re.IGNORECASE).strip()
                    clarification = f"The country was {rest}." if answer else f"The country was not {rest}."
                elif re.match(r"^(?:is (?:the |this )?country|is it)\s+", cleaned_q, flags=re.IGNORECASE):
                    rest = re.sub(r"^(?:is (?:the |this )?country|is it)\s+", "", cleaned_q, flags=re.IGNORECASE).strip()
                    clarification = f"The country is {rest}." if answer else f"The country is not {rest}."
                else:
                    rest = re.sub(r"^(?:does (?:the |this )?country|does it|does|do|have|has)\s+", "", cleaned_q, flags=re.IGNORECASE).strip()
                    clarification = f"The country {rest}." if answer else f"The country does not {rest}."
        map_highlight = compute_geographic_map_highlight(conn, plan, answer)
        return LocalAnswer(
            question=improved_question,
            answer=answer,
            clarification=clarification,
            explanation=explanation,
            relation="+".join(relations),
            fact_provenance=fact_provenance,
            map_highlight=map_highlight,
        )
