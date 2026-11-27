"""Modular Gemini planner and SQLite executor package for local game fact databases."""

from .aliases import (
    ENGLISH_COUNTY_ALIASES,
    POLISH_CITY_ALIASES,
    POLISH_HISTORICAL_PARTITION_ALIASES,
    POLISH_NEIGHBORING_COUNTRIES_ALIASES,
    POLISH_REGION_ALIASES,
    POLISH_RIVER_ALIASES,
    UK_NEIGHBORING_COUNTRIES_ALIASES,
    _REGIONAL_DISPLAY,
    _canonical_us_region,
    _resolve_english_county_alias,
    fold_polish,
    is_self_reference,
    norm,
    text_value,
)
from .clarification import (
    _build_local_kb_clarification,
    _clarification_subject,
    _is_false_literal,
    build_clarification,
)
from .db import (
    _get_parent_voivodeship_relation,
    _reference_row,
    get_entity_row,
    get_relation_value,
    resolve_ref,
)
from .evaluator import collect_relations, evaluate, execute_plan
from .explanations import generate_mode_explanation
from .map_highlights import GEOGRAPHIC_AUTO_COLOR_RELATIONS, compute_local_kb_map_highlight
from .models import (
    APP_DIR,
    ROOT_DIR,
    LocalAnswer,
    LocalModeConfig,
    QuestionPlan,
    _SQL_IDENTIFIER_RE,
    _VOIVODESHIP_DB_PATH,
    _VOIVODESHIP_LIST_QUERIES,
    _VOIVODESHIP_LIST_RELATIONS,
    _VOIVODESHIP_SCALAR_RELATIONS,
    _safe_identifier,
    load_dotenv,
)
from .planner import analyze_question, gemini_json

__all__ = [
    "APP_DIR",
    "ROOT_DIR",
    "LocalModeConfig",
    "QuestionPlan",
    "LocalAnswer",
    "load_dotenv",
    "gemini_json",
    "analyze_question",
    "get_entity_row",
    "get_relation_value",
    "resolve_ref",
    "evaluate",
    "collect_relations",
    "execute_plan",
    "generate_mode_explanation",
    "build_clarification",
    "norm",
    "fold_polish",
    "text_value",
    "is_self_reference",
    "POLISH_CITY_ALIASES",
    "POLISH_REGION_ALIASES",
    "POLISH_HISTORICAL_PARTITION_ALIASES",
    "POLISH_NEIGHBORING_COUNTRIES_ALIASES",
    "POLISH_RIVER_ALIASES",
    "ENGLISH_COUNTY_ALIASES",
    "UK_NEIGHBORING_COUNTRIES_ALIASES",
]
