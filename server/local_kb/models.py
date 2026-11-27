"""Data models, path constants, and SQLite metadata for local KB question answering."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# This module lives in <repo>/server/local_kb/models.py (or /usr/src/app/local_kb/models.py in Docker).
APP_DIR = Path(__file__).resolve().parents[1]
# In local development APP_DIR is <repo>/server and data lives in <repo>/data (or <repo>/server/data).
# In Docker, docker-compose mounts ./server as /usr/src/app and ./data as /usr/src/app/data.
ROOT_DIR = APP_DIR if (APP_DIR / "data").exists() else APP_DIR.parent

_VOIVODESHIP_DB_PATH = ROOT_DIR / "data" / "voivodeship_facts.sqlite"

_VOIVODESHIP_LIST_RELATIONS: dict[str, tuple[str, str]] = {
    "borders_voivodeship": ("voivodeship_borders_voivodeships", "border_voivodeship_name"),
    "borders_country": ("voivodeship_borders_countries", "country_name"),
    "water_access": ("voivodeship_water_access", "water_body"),
    "major_rivers": ("voivodeship_major_rivers", "river_name"),
    "major_roads": ("voivodeship_major_roads", "road_name"),
    "mountain_ranges": ("voivodeship_mountain_ranges", "range_name"),
    "historical_region": ("voivodeship_historical_regions", "region_name"),
    "historical_regions": ("voivodeship_historical_regions", "region_name"),
    "landform_regions": ("voivodeship_landform_regions", "region_name"),
    "regional_labels": ("voivodeship_regional_labels", "label"),
}

_VOIVODESHIP_LIST_QUERIES: dict[str, str] = {
    "borders_voivodeship": "SELECT border_voivodeship_name FROM voivodeship_borders_voivodeships WHERE voivodeship_id = ?",
    "borders_country": "SELECT country_name FROM voivodeship_borders_countries WHERE voivodeship_id = ?",
    "water_access": "SELECT water_body FROM voivodeship_water_access WHERE voivodeship_id = ?",
    "major_rivers": "SELECT river_name FROM voivodeship_major_rivers WHERE voivodeship_id = ?",
    "major_roads": "SELECT road_name FROM voivodeship_major_roads WHERE voivodeship_id = ?",
    "mountain_ranges": "SELECT range_name FROM voivodeship_mountain_ranges WHERE voivodeship_id = ?",
    "historical_region": "SELECT region_name FROM voivodeship_historical_regions WHERE voivodeship_id = ?",
    "landform_regions": "SELECT region_name FROM voivodeship_landform_regions WHERE voivodeship_id = ?",
    "regional_labels": "SELECT label FROM voivodeship_regional_labels WHERE voivodeship_id = ?",
}

_VOIVODESHIP_SCALAR_RELATIONS: dict[str, str] = {
    "name": "name",
    "seat": "seat",
    "macroregion": "macroregion",
    "is_coastal": "is_coastal",
    "population": "population",
    "area": "area_km2",
    "latitude": "latitude",
    "longitude": "longitude",
    "urbanization": "urbanization_percent",
    "powiat_count": "powiat_count",
    "city_count": "city_count",
    "city_count_with_powiat_rights": "city_count_with_powiat_rights",
}

_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(name: str) -> str:
    if not _SQL_IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


@dataclass(frozen=True)
class LocalModeConfig:
    mode_name: str
    entity_label: str
    target_entity: str
    db_path: Path
    table: str
    name_column: str
    scalar_relations: dict[str, str]
    list_relations: dict[str, tuple[str, str]]
    supported_relations: list[str]
    language: str = "Polish"
    fk_column: str | None = None
    mode_notes: str | None = None
    entity_list_relations: frozenset[str] = frozenset()


@dataclass(frozen=True)
class QuestionPlan:
    original_question: str
    valid: bool
    supported: bool
    improved_question: str | None
    explanation: str | None
    plan: dict[str, Any] | None
    fallback_reason: str | None = None


# Preserve plan_cache serialization/deserialization module identity ("local_kb_question").
QuestionPlan.__module__ = "local_kb_question"


@dataclass(frozen=True)
class LocalAnswer:
    question: str
    answer: bool | None
    explanation: str
    relations: list[str]
    clarification: str | None = None
    map_highlight: dict[str, Any] | None = None


def load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
