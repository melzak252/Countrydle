from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.country_codes import COUNTRY_CCA2_MAP
from utils.geo import calculate_bearing, calculate_distance_km

_APP_DIR = Path(__file__).resolve().parent
_DATA_DIR = (
    _APP_DIR.parent / "data"
    if (_APP_DIR.parent / "data").exists()
    else _APP_DIR.parents[1] / "data"
)
FACTS_DB_PATH = _DATA_DIR / "country_facts.sqlite"
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_countrydle_secret")

UNMASK_ORDER = [0, 4, 2, 5, 1, 3]


def get_sqlite_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or FACTS_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def evaluate_flag_clues(
    target_country_id: int,
    guessed_country_id: int,
    db_path: Optional[Path] = None,
    all_matched_colors_so_far: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Compares colors, symbols, and coordinates between target and guessed countries."""
    conn = get_sqlite_connection(db_path)
    cur = conn.cursor()

    try:
        # 1. Colors
        cur.execute(
            "SELECT color FROM country_flag_colors WHERE country_id=?",
            (target_country_id,),
        )
        target_colors = {r[0] for r in cur.fetchall()}

        cur.execute(
            "SELECT color FROM country_flag_colors WHERE country_id=?",
            (guessed_country_id,),
        )
        guessed_colors = {r[0] for r in cur.fetchall()}

        matched_colors = sorted(list(target_colors.intersection(guessed_colors)))
        missed_colors = sorted(list(guessed_colors.difference(target_colors)))

        discovered = set(matched_colors)
        if all_matched_colors_so_far:
            discovered = discovered.union(all_matched_colors_so_far)

        remaining_colors_count = max(0, len(target_colors.difference(discovered)))

        # 2. Symbols
        cur.execute(
            "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
            (target_country_id,),
        )
        target_symbols = {r[0] for r in cur.fetchall()}

        cur.execute(
            "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
            (guessed_country_id,),
        )
        guessed_symbols = {r[0] for r in cur.fetchall()}

        matched_symbols = sorted(list(target_symbols.intersection(guessed_symbols)))

        # 3. Coordinates & Geo
        cur.execute(
            "SELECT latitude, longitude FROM countries WHERE id=?",
            (target_country_id,),
        )
        target_coords = cur.fetchone()

        cur.execute(
            "SELECT latitude, longitude FROM countries WHERE id=?",
            (guessed_country_id,),
        )
        guessed_coords = cur.fetchone()

        dist_km: Optional[int] = None
        bearing_deg: Optional[int] = None
        compass: Optional[str] = None
        arrow: Optional[str] = None

        if target_coords and guessed_coords:
            lat1, lon1 = float(guessed_coords["latitude"]), float(guessed_coords["longitude"])
            lat2, lon2 = float(target_coords["latitude"]), float(target_coords["longitude"])
            dist_km = calculate_distance_km(lat1, lon1, lat2, lon2)
            bearing_deg, compass, arrow = calculate_bearing(lat1, lon1, lat2, lon2)

        return {
            "matched_colors": matched_colors,
            "missed_colors": missed_colors,
            "remaining_colors_count": remaining_colors_count,
            "matched_symbols": matched_symbols,
            "distance_km": dist_km,
            "bearing_degrees": bearing_deg,
            "bearing_direction": compass,
            "bearing_arrow": arrow,
        }
    finally:
        conn.close()


def generate_asset_token(day_id: int) -> str:
    """Generates short HMAC token to verify flag asset requests."""
    return hmac.new(
        SECRET_KEY.encode(),
        f"flagdle:{day_id}".encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


def verify_asset_token(day_id: int, token: str) -> bool:
    """Validates short HMAC token."""
    expected = generate_asset_token(day_id)
    return hmac.compare_digest(expected, token)


def get_country_iso2(country_name: str) -> str:
    """Resolves country name to lowercase ISO2 cca2 code."""
    return COUNTRY_CCA2_MAP.get(country_name, "").lower()
