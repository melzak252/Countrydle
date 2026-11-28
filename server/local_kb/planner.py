"""Gemini question planner, prompt construction, and schema compilation."""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from typing import Any

from planner_protocol import (
    PLANNER_MAX_OUTPUT_TOKENS,
    PLANNER_OPERATORS,
    PLANNER_RULES,
    PLANNER_THINKING_BUDGET,
    PLANNER_VERSION,
    compile_planner_response,
    planner_response_schema,
)

from .models import LocalModeConfig, QuestionPlan, load_dotenv


def gemini_json(
    prompt: str,
    max_output_tokens: int = PLANNER_MAX_OUTPUT_TOKENS,
    *,
    response_schema: dict[str, Any],
    evidence: dict | None = None,
) -> dict[str, Any]:
    from utils.ai_clients import generate_gemini_json

    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite"
    return generate_gemini_json(
        prompt,
        model=model,
        api_key=key,
        max_output_tokens=max_output_tokens,
        timeout=60,
        evidence=evidence,
        response_schema=response_schema,
        thinking_budget=PLANNER_THINKING_BUDGET if model.startswith("gemini-2.5-flash-lite") else None,
    )


_DEFAULT_GEMINI_JSON = gemini_json


def _resolve_gemini_json():
    """Respect monkeypatches applied either to local_kb.planner or the local_kb_question facade."""
    if gemini_json is not _DEFAULT_GEMINI_JSON:
        return gemini_json
    facade = sys.modules.get("local_kb_question")
    if facade is not None:
        facade_fn = getattr(facade, "gemini_json", None)
        if callable(facade_fn) and facade_fn is not _DEFAULT_GEMINI_JSON:
            return facade_fn
    return gemini_json


def analyze_question(
    question: str,
    config: LocalModeConfig,
    *,
    use_cache: bool = True,
    strict_errors: bool = False,
    evidence: dict | None = None,
) -> QuestionPlan:
    from countrydle.template_compiler import check_open_ended_question
    open_ended = check_open_ended_question(question)
    if open_ended is not None:
        return QuestionPlan(
            original_question=question,
            valid=False,
            supported=False,
            improved_question=None,
            explanation=open_ended,
            plan=None,
            fallback_reason="open_ended",
        )

    from utils.plan_cache import plan_cache

    load_dotenv()
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite"
    version = f"{PLANNER_VERSION}:english-output-v1:{model}"
    cached = plan_cache.get(config.mode_name, question, version=version) if use_cache else None
    if evidence is not None:
        evidence.update(
            provider="gemini",
            model=model,
            contract_version=f"{PLANNER_VERSION}:english-output-v1",
            cache_hit=cached is not None,
        )
    if cached is not None:
        return replace(cached, original_question=question)

    from utils.water_hierarchy import build_multi_ocean_plan, is_multi_ocean_question

    if is_multi_ocean_question(question):
        entity = {
            "USStatedle": "state",
            "Powiatdle": "county",
            "Wojewodztwodle": "voivodeship",
            "Countydle": "county",
        }.get(config.mode_name, "location")
        improved = f"Does the {entity} have access to two or more oceans?"
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=True,
            improved_question=improved,
            explanation="Deterministic multi-ocean query resolution.",
            plan=build_multi_ocean_plan(config.target_entity),
        )

    try:
        from generic_template_compiler import compile_generic_template_plan

        tpl_res = compile_generic_template_plan(question, config.mode_name)
        if tpl_res is not None:
            tpl_ast, tpl_improved = tpl_res
            plan = QuestionPlan(
                original_question=question,
                valid=True,
                supported=True,
                improved_question=tpl_improved,
                explanation="Deterministic template match.",
                plan=tpl_ast,
            )
            if use_cache:
                plan_cache.set(config.mode_name, question, plan, version=version)
            return plan
    except Exception:
        pass

    relations = "\n".join(f"- {r}" for r in config.supported_relations)
    entity_relations = ", ".join(sorted(config.entity_list_relations)) or "(none)"
    neighbor_example = ""
    if config.entity_list_relations:
        neighbor_relation = min(config.entity_list_relations)
        neighbor_example = f"""
Example for (target population > 100000) OR (any neighbor population > 100000):
{{"route":"local","plan":[
  {{"operator":"greater_than","left":{{"entity":"{config.target_entity}","relation":"population"}},"right":{{"value":100000}}}},
  {{"operator":"greater_than","left":{{"entity":"item","relation":"population"}},"right":{{"value":100000}}}},
  {{"operator":"any","items":{{"entity":"{config.target_entity}","relation":"{neighbor_relation}"}},"args":[1]}},
  {{"operator":"or","args":[0,2]}}
]}}
Nodes 0 and 1 compare the same property and value on DIFFERENT entities; neither can replace the other.
Node 1 belongs only inside quantifier 2. The outer or combines target predicate 0 with quantifier 2,
never with the unbound item predicate 1.
""".strip()

    prompt = f"""
You are a validator and planner for a yes/no guessing game.
Game mode: {config.mode_name}
Target entity placeholder: {config.target_entity}
Entity type: {config.entity_label}

Supported SQLite relations:
{relations}

Task:
1. Decide whether the user input is a valid yes/no question about the hidden {config.entity_label}.
2. Rewrite Polish questions in English, preserving their meaning; otherwise rewrite only if clarification is needed.
3. If it can be answered from the supported relations, return route="local", plan and any needed improved_question. Do not generate an explanation for a local plan: the executor explains the facts.
4. If a clear question needs external knowledge, return route="fallback", plan=null and a short fallback_reason.
5. If the question needs clarification or is unrelated/open-ended, return route="clarify", plan=null and a short explanation.
Write every improved_question, clarification explanation, and fallback_reason in English, regardless of the input language. Preserve native geographic names and interpret Polish and English questions equivalently.

Use common names, not long official names. Normalize Polish and informal names when obvious.
When a user explicitly names an entity in the question (e.g. "Czy Kraków jest miastem na prawach powiatu?", "Czy Małopolskie graniczy ze Słowacją?"), do NOT reject it as invalid or clarify. Treat it as testing whether that property holds for the candidate or hidden target.
Do NOT answer the question. Only create the plan.

{PLANNER_RULES.replace("TARGET", config.target_entity)}

Quantified list properties:
- Same-type entity-name lists: {entity_relations}.
- For these lists, item refers to each neighboring {config.entity_label}. Its supported scalar
  and list relations can be read with {{"entity":"item","relation":"RELATION"}}.
- Other lists and literal arrays contain primitive values, not entities. Use item.name for
  their value; their other properties cannot be inspected.
- A nested any/all binds a new item only inside its predicate; its items operand may use
  the enclosing item. {config.target_entity} always refers to the original hidden target.

{neighbor_example}

Self-neighbor rule:
- If the user asks whether the hidden {config.entity_label} borders/neighbors itself
  (Polish: "sąsiaduje z samym sobą"), this is a valid supported question.
- Create a contains_exact plan on the relevant borders_* relation with right as
  the hidden entity name reference, e.g. {{"entity":"{config.target_entity}","relation":"name"}}.
- The executor treats this self-border/self-neighbor case as false (an entity does not border itself).

Allowed operators:
- contains_exact: exact list membership or complete scalar equality, never a text substring
- contains_partial: substring match, preserving the old broad contains behavior
- equals: scalar equals value
- greater_than, less_than: strict numeric comparisons >, <
- greater_than_or_equal, less_than_or_equal: inclusive numeric comparisons >=, <=
- west_of: left longitude < right longitude (further west in signed coordinates)
- east_of: left longitude > right longitude (further east in signed coordinates)
- north_of: left latitude > right latitude (further north in signed coordinates)
- south_of: left latitude < right latitude (further south in signed coordinates)
- exists: relation has any value / boolean is true
- starts_with, ends_with, has_space, has_hyphen
- contains_text: a substring inside text, including letters or punctuation inside a name
- word_count_equals, word_count_greater_than, word_count_less_than
- char_count_equals, char_count_greater_than, char_count_less_than
- and, or, not
- any, all: quantify a list with a predicate on item, preserving all requested property filters

Geographic Direction / Coordinate rules:
- Longitudes in the Americas / USA are negative decimal degrees (e.g. 74° W is -74.0, 71.5° W is -71.5).
- For questions like "further west than 74° W" or "west of 74° W":
  ALWAYS use operator "west_of" (e.g. {{"operator":"west_of","left":{{"entity":"{config.target_entity}","relation":"longitude"}},"right":{{"value":-74.0}}}}).
  NEVER use greater_than for "further west than" with negative numbers!
- For relative cardinal directions comparing position to another named entity (e.g. "na zachód od Warszawy", "west of Warsaw"):
  use operator "west_of" with left={{"entity":"{config.target_entity}","relation":"longitude"}} and right={{"entity":"Warszawa","relation":"longitude"}}.
- For "na wschód od" / "east of": use operator "east_of" comparing relation "longitude".
- For "na północ od" / "north of": use operator "north_of" comparing relation "latitude".
- For "na południe od" / "south of": use operator "south_of" comparing relation "latitude".
Reference format examples:
{{"entity":"{config.target_entity}","relation":"population"}}
{{"entity":"{config.target_entity}","relation":"name"}}

For a single predicate, put its node in a one-element plan array.
Return STRICT JSON only:
{{
  "route": "local",
  "plan": [{{...}}]
}}

Invalid format:
{{"route": "clarify", "explanation": "...", "plan": null}}

Unsupported format:
{{"route": "fallback", "improved_question": "...", "plan": null, "fallback_reason": "unsupported relation"}}
Mode-specific planning notes (apply these to positive predicates AND their negations):
{config.mode_notes or "- None"}


User question: {question}
""".strip()

    allowed_relations = config.scalar_relations.keys() | config.list_relations.keys() | {"name"}
    if config.mode_name == "Powiatdle":
        allowed_relations = allowed_relations | {"is_coastal", "mountain_ranges"}
    operators = (PLANNER_OPERATORS - {"contains"}) | {"contains_exact", "contains_partial", "any", "all"}
    allow_named_entities = config.mode_name in {"Countrydle", "Powiatdle", "USStatedle", "Wojewodztwodle", "Countydle"}
    schema = planner_response_schema(
        relations=allowed_relations,
        operators=operators,
        target_entity=config.target_entity,
        allow_named_entities=allow_named_entities,
    )
    provider = _resolve_gemini_json()
    data = provider(prompt, response_schema=schema, evidence=evidence)
    ast = compile_planner_response(
        data,
        relations=allowed_relations,
        operators=operators,
        target_entity=config.target_entity,
        allow_named_entities=allow_named_entities,
    )
    if evidence is not None:
        evidence.update(
            provider="gemini",
            model=os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or "gemini-2.5-flash-lite",
            prompt=prompt,
            temperature=0,
            max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS,
            cache_hit=False,
        )
    plan = QuestionPlan(
        original_question=question,
        valid=data["route"] != "clarify",
        supported=data["route"] == "local",
        improved_question=data.get("improved_question"),
        explanation=data.get("explanation"),
        plan=ast,
        fallback_reason=data.get("fallback_reason"),
    )
    if use_cache:
        plan_cache.set(config.mode_name, question, plan, version=version)
    return plan
