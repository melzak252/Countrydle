"""SQLite fact loading, entity resolution, and provenance helpers for Countrydle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import sqlite3
import sys

from country_fact_provenance import RELATIONS as EVIDENCE_RELATIONS, read_record
from countrydle.answering.aliases import (
    COUNTRY_NAME_SYNONYMS,
    POLISH_COUNTRY_ALIASES,
    expand_geographic_areas,
    expand_water_bodies,
    is_marine_water_body,
    normalize,
    normalize_hemisphere,
    normalize_value,
)

APP_DIR = Path(__file__).resolve().parents[1]
# Local dev: <repo>/server/countrydle with data in <repo>/data.
# Docker: /usr/src/app/countrydle with data in /usr/src/app/data.
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"
_INITIAL_DEFAULT_DB_PATH = DEFAULT_DB_PATH


def get_default_db_path() -> Path:
    """Resolve the active DB path, honoring monkeypatches on the facade module."""
    for mod_name in ("countrydle.local_answering", "server.countrydle.local_answering"):
        facade = sys.modules.get(mod_name)
        if facade is not None:
            facade_path = getattr(facade, "DEFAULT_DB_PATH", None)
            if facade_path is not None and facade_path != _INITIAL_DEFAULT_DB_PATH:
                return facade_path
    return DEFAULT_DB_PATH


@dataclass(frozen=True)
class LocalAnswer:
    question: str
    answer: bool | None
    explanation: str
    relation: str
    clarification: str | None = None
    fact_provenance: list[dict] = field(default_factory=list)
    map_highlight: dict | None = None


SCALAR_RELATION_FIELDS = {
    "name": "app_country_name",
    "capital": "capital",
    "population": "population",
    "area": "area_km2",
    "area_km2": "area_km2",
    "is_island": "is_island",
    "driving_side": "driving_side",
    "government_type": "government_type",
    "dominant_religion": "dominant_religion",
    "coordinates.latitude": "latitude",
    "coordinates.longitude": "longitude",
    "latitude": "latitude",
    "longitude": "longitude",
    "min_latitude": "min_latitude",
    "max_latitude": "max_latitude",
    "min_longitude": "min_longitude",
    "max_longitude": "max_longitude",
}

LIST_RELATION_QUERIES = {
    "continent": "SELECT continent FROM country_continents WHERE country_id=?",
    "region": "SELECT region_name FROM country_regions WHERE country_id=?",
    "subregion": "SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "geographic_area": "SELECT region_name FROM country_regions WHERE country_id=? UNION SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "borders_country": "SELECT border_country_name FROM country_borders WHERE country_id=? UNION SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id=?",
    "water_access": "SELECT water_body FROM country_water_access WHERE country_id=?",
    "marine_access": "SELECT water_body FROM country_water_access WHERE country_id=?",
    "currency": "SELECT currency_name FROM country_currencies WHERE country_id=? UNION SELECT currency_code FROM country_currencies WHERE country_id=? AND currency_code IS NOT NULL",
    "official_language": "SELECT language_name FROM country_languages WHERE country_id=?",
    "membership": "SELECT organization FROM country_memberships WHERE country_id=?",
    "major_rivers": "SELECT river_name FROM country_major_rivers WHERE country_id=?",
    "flag_color": "SELECT color FROM country_flag_colors WHERE country_id=?",
    "flag_symbol": "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
    "historical_union": "SELECT union_name FROM country_historical_unions WHERE country_id=?",
    "hemisphere": "SELECT hemisphere FROM country_hemispheres WHERE country_id=?",
}

BULK_LIST_RELATION_QUERIES = {
    "continent": "SELECT country_id, continent FROM country_continents",
    "region": "SELECT country_id, region_name FROM country_regions",
    "subregion": "SELECT country_id, subregion_name FROM country_subregions",
    "geographic_area": "SELECT country_id, region_name FROM country_regions UNION SELECT country_id, subregion_name FROM country_subregions",
    "borders_country": "SELECT country_id, border_country_name FROM country_borders UNION SELECT cb.country_id, c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3",
    "water_access": "SELECT country_id, water_body FROM country_water_access",
    "marine_access": "SELECT country_id, water_body FROM country_water_access",
    "currency": "SELECT country_id, currency_name FROM country_currencies UNION SELECT country_id, currency_code FROM country_currencies WHERE currency_code IS NOT NULL",
    "official_language": "SELECT country_id, language_name FROM country_languages",
    "membership": "SELECT country_id, organization FROM country_memberships",
    "major_rivers": "SELECT country_id, river_name FROM country_major_rivers",
    "flag_color": "SELECT country_id, color FROM country_flag_colors",
    "flag_symbol": "SELECT country_id, symbol FROM country_flag_symbols",
    "historical_union": "SELECT country_id, union_name FROM country_historical_unions",
    "hemisphere": "SELECT country_id, hemisphere FROM country_hemispheres",
}


def _finalize_list_relation(relation: str, raw_values: list) -> list:
    res = [v for v in raw_values if v is not None]
    if relation == "marine_access":
        res = [water for water in res if is_marine_water_body(water)]
    if relation in {"water_access", "marine_access"}:
        expanded = expand_water_bodies(res)
        for w in list(expanded):
            w_lower = normalize_value(w)
            if "sea" in w_lower or "ocean" in w_lower or "gulf" in w_lower or "bay" in w_lower or "skagerrak" in w_lower:
                expanded.add("Sea")
        return list(expanded)
    if relation in {"geographic_area", "subregion"}:
        return list(expand_geographic_areas(res))
    return res


def preload_list_relations(
    conn: sqlite3.Connection,
    relations: set[str],
    country_ids: list[int],
) -> dict[tuple[int, str], list]:
    """Bulk-load referenced list relations in one SQL query per relation (eliminates N+1 in map highlighting)."""
    cache: dict[tuple[int, str], list] = {}
    for relation in relations:
        bulk_sql = BULK_LIST_RELATION_QUERIES.get(relation)
        if not bulk_sql:
            continue
        grouped: dict[int, list] = {cid: [] for cid in country_ids}
        for cid, val in conn.execute(bulk_sql):
            if cid in grouped and val is not None:
                grouped[cid].append(val)
        for cid, raw_values in grouped.items():
            cache[(cid, relation)] = _finalize_list_relation(relation, raw_values)
    return cache


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def _country_name_key(name: str) -> str:
    cleaned = re.sub(r"\bst\.\s*", "saint ", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<=\b[a-zA-Z])\.(?=[a-zA-Z](\.|\b))", "", cleaned).rstrip(".")
    return re.sub(r"\bst\b", "saint", normalize(cleaned.replace("&", " and ")))


def _one_edit_apart(left: str, right: str) -> bool:
    """One insertion, deletion, substitution or adjacent transposition."""
    if abs(len(left) - len(right)) > 1:
        return False
    for i, (a, b) in enumerate(zip(left, right)):
        if a == b:
            continue
        if len(left) != len(right):
            return left[i + 1:] == right[i:] if len(left) > len(right) else left[i:] == right[i + 1:]
        return left[i + 1:] == right[i + 1:] or (
            i + 1 < len(left)
            and left[i] == right[i + 1] and left[i + 1] == right[i]
            and left[i + 2:] == right[i + 2:]
        )
    return abs(len(left) - len(right)) == 1


def find_country(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    if not isinstance(name, str) or name in {"target_country", "item"}:
        return None
    direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (name,)).fetchone()
    if direct:
        return direct
    wanted = _country_name_key(name)
    alias = COUNTRY_NAME_SYNONYMS.get(wanted) or POLISH_COUNTRY_ALIASES.get(wanted)
    if alias:
        direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (alias,)).fetchone()
        if direct:
            return direct
    candidates = {}
    country_rows = {}
    for row in conn.execute("SELECT * FROM countries"):
        country = row["app_country_name"]
        country_rows[country] = row
        for label in (country, row["official_name"] or ""):
            key = _country_name_key(label)
            if key:
                candidates.setdefault(key, set()).add(country)
    for label, country in (COUNTRY_NAME_SYNONYMS | POLISH_COUNTRY_ALIASES).items():
        if country in country_rows:
            candidates.setdefault(_country_name_key(label), set()).add(country)
    matches = candidates.get(wanted)
    if matches is None:
        # Short acronyms and shared prefixes are not safe typo candidates.
        matches = set()
        if len(wanted) >= 5:
            for key, countries in candidates.items():
                if len(key) >= 5 and _one_edit_apart(wanted, key):
                    matches.update(countries)
    return country_rows[next(iter(matches))] if len(matches) == 1 else None


def resolve_entity(
    conn: sqlite3.Connection,
    entity: str,
    target_country: sqlite3.Row,
    item_value: str | None = None,
) -> sqlite3.Row | None:
    if entity == "target_country":
        return target_country
    if entity == "item":
        return find_country(conn, item_value or "")
    return find_country(conn, entity)


def resolve_ref(
    conn: sqlite3.Connection,
    ref: dict,
    target_country: sqlite3.Row,
    item_value: str | None = None,
    list_cache: dict[tuple[int, str], list] | None = None,
):
    if not isinstance(ref, dict):
        return None
    if "value" in ref:
        return ref["value"]
    entity_name = ref.get("entity")
    relation = ref.get("relation")
    if not entity_name or not relation:
        return None
    entity = resolve_entity(conn, entity_name, target_country, item_value)
    if entity is None:
        return None
    if relation in SCALAR_RELATION_FIELDS:
        return entity[SCALAR_RELATION_FIELDS[relation]]
    if relation in LIST_RELATION_QUERIES:
        if list_cache is not None:
            cached = list_cache.get((entity["id"], relation))
            if cached is not None:
                return cached
        query = LIST_RELATION_QUERIES[relation]
        params = (entity["id"],) * query.count("?")
        res = [row[0] for row in conn.execute(query, params) if row[0] is not None]
        return _finalize_list_relation(relation, res)
    return None


def is_self_country_reference(value, target_country: sqlite3.Row) -> bool:
    if value is None:
        return False
    value_norm = normalize(str(value))
    target_norm = normalize(str(target_country["app_country_name"]))
    return value_norm == target_norm or value_norm in {
        "itself",
        "it self",
        "same country",
        "same entity",
        "self",
        "samym soba",
        "samym sobą",
        "sobą",
        "soba",
    }


def collect_ref_evidence(conn, ref, target_country, item_value, evidence, *, contains_value=None):
    if evidence is None or not isinstance(ref, dict) or "value" in ref:
        return
    relation = ref.get("relation")
    if relation not in EVIDENCE_RELATIONS:
        return
    entity = resolve_entity(conn, ref.get("entity"), target_country, item_value)
    if entity is None:
        return
    value = None
    if contains_value is not None:
        actual = resolve_ref(conn, ref, target_country, item_value)
        canonical = normalize_hemisphere if relation == "hemisphere" else normalize_value
        value = next((item for item in actual if canonical(item) == canonical(contains_value)), None)
    record = read_record(conn, entity["id"], relation, value)
    if record not in evidence:
        evidence.append(record)


def merge_used_evidence(evidence, results, branches, *, decisive):
    if evidence is None:
        return
    has_decisive = any(result is decisive for result in results)
    for result, branch in zip(results, branches):
        if not has_decisive or result is decisive:
            for record in branch:
                if record not in evidence:
                    evidence.append(record)
