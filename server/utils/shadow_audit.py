"""Asynchronous shadow audit engine comparing fast template matches with Gemini.

Samples a percentage of deterministic template matches in the background, queries
Gemini for an independent AST plan, and records divergences in the database for
admin review. Never blocks or delays player question evaluation.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any

from db import AsyncSessionLocal
from db.models.template_divergence import TemplateDivergence

logger = logging.getLogger("countrydle.shadow_audit")

_counter_lock = threading.Lock()
_sample_counter = 0


def get_audit_sample_rate() -> int:
    """Return the audit interval (default: every 5th match = 20%). 0 disables auditing."""
    try:
        return int(os.getenv("TEMPLATE_AUDIT_SAMPLE_RATE", "5"))
    except (ValueError, TypeError):
        return 5


def should_audit_template() -> bool:
    """Check whether this template match should trigger a background shadow audit."""
    sample_rate = get_audit_sample_rate()
    if sample_rate <= 0:
        return False
    global _sample_counter
    with _counter_lock:
        _sample_counter += 1
        return (_sample_counter % sample_rate) == 0


def _extract_primary_tuple(plan: Any) -> tuple[str | None, str | None, Any]:
    """Extract (operator, relation, value) from the first condition node of an AST plan."""
    if not plan:
        return None, None, None
    node = plan[0] if isinstance(plan, list) and plan else plan
    if not isinstance(node, dict):
        return None, None, None
    op = node.get("operator")
    left = node.get("left")
    rel = left.get("relation") if isinstance(left, dict) else None
    right = node.get("right")
    val = right.get("value") if isinstance(right, dict) else right
    return op, rel, val


def compare_plans(
    template_plan: Any,
    gemini_plan: Any,
    gemini_supported: bool,
    gemini_valid: bool,
) -> tuple[bool, str, dict[str, Any]]:
    """Compare a template-generated AST plan with an independent Gemini-generated plan.

    Returns:
        (is_divergent, divergence_type, details_dict)
    """
    if not gemini_valid:
        return True, "gemini_invalid", {"reason": "Gemini rejected the question as invalid/off-topic"}

    if not gemini_supported or not gemini_plan:
        return True, "gemini_unsupported", {"reason": "Gemini considers question outside supported local facts"}

    t_op, t_rel, t_val = _extract_primary_tuple(template_plan)
    g_op, g_rel, g_val = _extract_primary_tuple(gemini_plan)

    # Normalize relations that represent the same concept across engines
    area_relations = {"geographic_area", "region", "subregion", "continent"}
    if t_rel in area_relations and g_rel in area_relations:
        # Both refer to regional/continental areas - compare the extracted values
        norm_t_val = str(t_val or "").strip().lower()
        norm_g_val = str(g_val or "").strip().lower()
        if norm_t_val != norm_g_val:
            return True, "value_mismatch", {
                "template_relation": t_rel, "gemini_relation": g_rel,
                "template_value": t_val, "gemini_value": g_val,
            }
        return False, "match", {}

    if t_rel != g_rel:
        return True, "relation_mismatch", {
            "template_relation": t_rel, "gemini_relation": g_rel,
            "template_operator": t_op, "gemini_operator": g_op,
            "template_value": t_val, "gemini_value": g_val,
        }

    if t_op != g_op:
        # Allow exact vs contains equivalence for list relations
        equivalent_ops = {("contains", "contains_exact"), ("contains_exact", "contains")}
        if (t_op, g_op) not in equivalent_ops:
            return True, "operator_mismatch", {
                "relation": t_rel,
                "template_operator": t_op, "gemini_operator": g_op,
                "template_value": t_val, "gemini_value": g_val,
            }

    norm_t_val = str(t_val or "").strip().lower()
    norm_g_val = str(g_val or "").strip().lower()
    if norm_t_val != norm_g_val:
        return True, "value_mismatch", {
            "relation": t_rel, "operator": t_op,
            "template_value": t_val, "gemini_value": g_val,
        }

    return False, "match", {}


async def _run_shadow_audit(
    mode: str,
    question: str,
    template_plan: Any,
    improved_question: str | None = None,
) -> None:
    """Execute Gemini in background thread, compare ASTs, and record any divergence."""
    try:
        norm_mode = mode.lower().replace("_", "").replace("-", "")
        if norm_mode in ("countrydle", "country", "continental"):
            from countrydle.local_planner import analyze_question_for_local_plan
            planned = await asyncio.to_thread(analyze_question_for_local_plan, question, use_cache=False)
        elif norm_mode in ("powiatdle", "powiat", "powiaty"):
            from local_kb_question import analyze_question
            from powiatdle.utils import LOCAL_CONFIG
            planned = await asyncio.to_thread(analyze_question, question, LOCAL_CONFIG, use_cache=False)
        elif norm_mode in ("usstatedle", "usstate", "usstates"):
            from local_kb_question import analyze_question
            from us_statedle.utils import LOCAL_CONFIG
            planned = await asyncio.to_thread(analyze_question, question, LOCAL_CONFIG, use_cache=False)
        elif norm_mode in ("wojewodztwodle", "wojewodztwo", "wojewodztwa"):
            from local_kb_question import analyze_question
            from wojewodztwodle.utils import LOCAL_CONFIG
            planned = await asyncio.to_thread(analyze_question, question, LOCAL_CONFIG, use_cache=False)
        else:
            return

        divergent, div_type, details = compare_plans(
            template_plan=template_plan,
            gemini_plan=planned.plan,
            gemini_supported=planned.supported,
            gemini_valid=planned.valid,
        )

        if not divergent:
            return

        # Record divergence for admin inspection
        async with AsyncSessionLocal() as session:
            record = TemplateDivergence(
                mode=mode,
                question=question,
                template_plan=template_plan if isinstance(template_plan, (list, dict)) else [template_plan],
                gemini_plan=planned.plan if isinstance(planned.plan, (list, dict)) else ([planned.plan] if planned.plan else None),
                divergence_type=div_type,
                details={
                    **details,
                    "template_improved_question": improved_question,
                    "gemini_improved_question": planned.improved_question,
                    "gemini_explanation": planned.explanation,
                },
            )
            session.add(record)
            await session.commit()
            logger.info("Recorded template divergence [%s] for mode=%s: %s", div_type, mode, question[:60])
    except Exception as exc:
        logger.debug("Background shadow audit skipped: %s", exc)


def schedule_shadow_audit(
    mode: str,
    question: str,
    template_plan: Any,
    improved_question: str | None = None,
    *,
    force: bool = False,
) -> None:
    """Schedule a non-blocking background audit if sampling condition is met."""
    if not force and not should_audit_template():
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run_shadow_audit(mode, question, template_plan, improved_question))
    except RuntimeError:
        pass
