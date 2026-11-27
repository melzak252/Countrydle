"""Symbol catalog loading, powiat/entity lookup, normalization, and target selection."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

from powiat_names import resolve_powiat_name
from powiatdle import flag_catalog
from powiatdle.heraldry_pkg.schemas import facade_attr
from powiatdle.utils import LOCAL_CONFIG
from regional_symbols import catalog as regional_catalog
from utils.geo import calculate_bearing, calculate_distance_km

HERB_CACHE_DIR = LOCAL_CONFIG.db_path.parent / "powiat_herb_cache"

PL_ALPHABET = "aąbcćdeęfghijklłmnńoóprsśtuwyzźż"
PL_ORDER = {ch: idx for idx, ch in enumerate(PL_ALPHABET)}

_HERALDRY_MAP_CACHE: Optional[dict[str, str]] = None


def get_db_path() -> Path:
    db_path = getattr(LOCAL_CONFIG, "db_path", None)
    if db_path and Path(db_path).exists():
        return Path(db_path)
    here = Path(__file__).resolve()
    for candidate in [
        Path("data/powiat_facts.sqlite"),
        Path("server/data/powiat_facts.sqlite"),
        here.parents[2] / "data" / "powiat_facts.sqlite",
        here.parents[3] / "data" / "powiat_facts.sqlite",
    ]:
        if candidate.exists():
            return candidate
    return Path(db_path) if db_path else Path("data/powiat_facts.sqlite")


def get_herb_cache_dir() -> Path:
    db_p = facade_attr("get_db_path", get_db_path)()
    cache_dir = db_p.parent / "powiat_herb_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_heraldry_filename(powiat_id: int) -> Optional[str]:
    global _HERALDRY_MAP_CACHE
    if _HERALDRY_MAP_CACHE is None:
        map_path = facade_attr("get_db_path", get_db_path)().parent / "powiat_heraldry_map.json"
        if not map_path.exists():
            map_path = Path(__file__).resolve().parent.parent / "heraldry_map.json"
        if map_path.exists():
            try:
                _HERALDRY_MAP_CACHE = json.loads(map_path.read_text(encoding="utf-8"))
            except Exception:
                _HERALDRY_MAP_CACHE = {}
        else:
            _HERALDRY_MAP_CACHE = {}
    return _HERALDRY_MAP_CACHE.get(str(powiat_id))


def heraldry_cache_path(cache_dir: Path, powiat_id: int) -> Path:
    # Legacy SVGs may have lost their original dimensions.
    return cache_dir / f"{powiat_id}.v2.json"


def polish_sort_key(s: str) -> list[int]:
    return [PL_ORDER.get(ch, 1000 + ord(ch)) for ch in s.lower()]


def clean_html(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    clean = re.sub(r"<[^>]+>", "", text).strip()
    return clean or None


def _row_to_county(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "name": str(row["name"]),
        "voivodeship": str(row["voivodeship"]),
        "is_city_county": bool(row["is_city_county"]),
        "latitude": float(row["latitude"]) if row["latitude"] is not None else 0.0,
        "longitude": float(row["longitude"]) if row["longitude"] is not None else 0.0,
    }


def get_all_counties(db_path: Optional[Path] = None) -> list[dict]:
    p = db_path or facade_attr("get_db_path", get_db_path)()
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
            "FROM powiats ORDER BY id ASC"
        )
        return [_row_to_county(row) for row in cur.fetchall()]


def get_county_by_id(county_id: int, db_path: Optional[Path] = None) -> Optional[dict]:
    p = db_path or facade_attr("get_db_path", get_db_path)()
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
            "FROM powiats WHERE id = ? LIMIT 1",
            (county_id,),
        )
        row = cur.fetchone()
        return _row_to_county(row) if row else None


def get_registration_plates(county_id: int, db_path: Optional[Path] = None) -> list[str]:
    p = db_path or facade_attr("get_db_path", get_db_path)()
    with sqlite3.connect(p) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT plate_code FROM powiat_registration_plates WHERE powiat_id = ? ORDER BY plate_code ASC",
            (county_id,),
        )
        return [r[0] for r in cur.fetchall()]


def resolve_guessed_county(
    guess: str, powiat_id: Optional[int] = None, db_path: Optional[Path] = None
) -> Optional[dict]:
    p = db_path or facade_attr("get_db_path", get_db_path)()
    if powiat_id is not None:
        c = get_county_by_id(powiat_id, db_path=p)
        if c:
            return c

    clean_guess = guess.strip()
    if not clean_guess:
        return None

    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
            "FROM powiats WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (clean_guess,),
        )
        row = cur.fetchone()
        if row:
            return _row_to_county(row)

        try:
            canonical_name = resolve_powiat_name(conn, clean_guess)
            if canonical_name:
                cur.execute(
                    "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
                    "FROM powiats WHERE LOWER(name) = LOWER(?) LIMIT 1",
                    (canonical_name,),
                )
                row = cur.fetchone()
                if row:
                    return _row_to_county(row)
        except Exception:
            pass

    return None


def symbol_mode(request: Request) -> str:
    return request.path_params.get("mode") or ("flag" if "/flags/" in request.url.path else "coat")


def entity_scope(request: Request) -> str:
    scope = request.path_params.get("scope", "county")
    if scope != "county" and scope not in regional_catalog.SCOPES:
        raise HTTPException(status_code=404, detail="Unknown geography.")
    if scope == "county" and "scope" in request.path_params:
        raise HTTPException(status_code=404, detail="Unknown geography.")
    return scope


def entities_for(scope: str) -> list[dict]:
    if scope == "county":
        return facade_attr("get_all_counties", get_all_counties)()
    return [
        dict(entity, voivodeship="", is_city_county=False)
        for entity in regional_catalog.load_entities(scope).values()
    ]


def entity_by_id(scope: str, entity_id: int) -> Optional[dict]:
    if scope == "county":
        return facade_attr("get_county_by_id", get_county_by_id)(entity_id)
    entity = regional_catalog.load_entities(scope).get(entity_id)
    return dict(entity, voivodeship="", is_city_county=False) if entity else None


def resolve_entity(scope: str, guess: str, entity_id: Optional[int]) -> Optional[dict]:
    if scope == "county":
        return facade_attr("resolve_guessed_county", resolve_guessed_county)(guess, entity_id)
    if entity_id is not None:
        return entity_by_id(scope, entity_id)
    key = regional_catalog.normalize(guess)
    for entity in entities_for(scope):
        if key and key in {
            regional_catalog.normalize(form) for form in [entity["name"], *entity["aliases"]]
        }:
            return entity
    return None


def regional_target(scope: str, mode: str, seed: str) -> dict:
    records = regional_catalog.load_catalog(scope, mode)
    ids = regional_catalog.load_daily_ids(scope, mode) if seed.startswith("daily-") else sorted(records)
    value = int(hashlib.sha256(f"regional-symbols:{scope}:{mode}:{seed}".encode()).hexdigest(), 16)
    return entity_by_id(scope, ids[value % len(ids)])


def distance_between(scope: str, source: dict, target: dict) -> float:
    if scope == "county":
        return calculate_distance_km(
            source["latitude"], source["longitude"], target["latitude"], target["longitude"]
        )
    lat1, lat2 = math.radians(source["latitude"]), math.radians(target["latitude"])
    dlat = lat2 - lat1
    dlon = math.radians(target["longitude"] - source["longitude"])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(12742 * math.asin(min(1, math.sqrt(a))), 2)


def bearing_between(scope: str, source: dict, target: dict):
    if (
        scope != "county"
        and source["latitude"] == target["latitude"]
        and source["longitude"] == target["longitude"]
    ):
        return None, None, None
    return calculate_bearing(
        source["latitude"], source["longitude"], target["latitude"], target["longitude"]
    )


def require_token_scope(payload: dict, scope: str) -> None:
    if payload.get("entity_scope", "county") != scope:
        raise HTTPException(status_code=403, detail="Token belongs to another geography.")


def require_token_mode(payload: dict, mode: str) -> None:
    if payload.get("symbol_mode", "coat") != mode:
        raise HTTPException(status_code=403, detail="Token belongs to another symbol mode.")


def select_target(counties: list[dict], seed: str, symbol_mode: str = "coat") -> dict:
    if symbol_mode == "flag":
        catalog = flag_catalog.load_catalog()
        if seed.startswith("daily-"):
            ids = flag_catalog.load_daily_ids()
            by_id = {county["id"]: county for county in counties}
            if any(county_id not in catalog or county_id not in by_id for county_id in ids):
                raise HTTPException(status_code=503, detail="Flag daily pool unavailable.")
            counties = [by_id[county_id] for county_id in ids]
        else:
            counties = [county for county in counties if county["id"] in catalog]
    if not counties:
        raise HTTPException(status_code=503, detail="No counties catalog available.")
    namespace = "powiat-flags" if symbol_mode == "flag" else "powiat-heraldry"
    value = int(hashlib.sha256(f"{namespace}:{seed}".encode("utf-8")).hexdigest(), 16)
    return counties[value % len(counties)]
