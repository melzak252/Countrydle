from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
import re
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

UNMASK_ORDER = [0, 6, 11, 5, 3, 8, 1, 10, 2, 9, 4, 7]


def get_sqlite_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or FACTS_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_sqlite_country_id(
    cur: sqlite3.Cursor, country_id: int | None = None, name: str | None = None
) -> int | None:
    if name:
        clean = name.strip()
        row = cur.execute(
            "SELECT id FROM countries WHERE LOWER(app_country_name) = LOWER(?) OR LOWER(official_name) = LOWER(?)",
            (clean, clean),
        ).fetchone()
        if row:
            return row[0]
    if country_id is not None and country_id > 0:
        row = cur.execute("SELECT id FROM countries WHERE id = ?", (country_id,)).fetchone()
        if row:
            return row[0]
    return None


def evaluate_flag_clues(
    target_country_id: int | None = None,
    guessed_country_id: int | None = None,
    target_country_name: str | None = None,
    guessed_country_name: str | None = None,
    db_path: Optional[Path] = None,
    all_matched_colors_so_far: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Compares colors, symbols, and coordinates between target and guessed countries."""
    conn = get_sqlite_connection(db_path)
    cur = conn.cursor()

    try:
        t_id = get_sqlite_country_id(cur, target_country_id, target_country_name)
        g_id = get_sqlite_country_id(cur, guessed_country_id, guessed_country_name)
        # 1. Colors
        cur.execute(
            "SELECT color FROM country_flag_colors WHERE country_id=?",
            (t_id,),
        )
        target_colors = {r[0] for r in cur.fetchall()} if t_id else set()

        cur.execute(
            "SELECT color FROM country_flag_colors WHERE country_id=?",
            (g_id,),
        )
        guessed_colors = {r[0] for r in cur.fetchall()} if g_id else set()

        matched_colors = sorted(list(target_colors.intersection(guessed_colors)))
        missed_colors = sorted(list(guessed_colors.difference(target_colors)))

        discovered = set(matched_colors)
        if all_matched_colors_so_far:
            discovered = discovered.union(all_matched_colors_so_far)

        remaining_colors_count = max(0, len(target_colors.difference(discovered)))

        # 2. Symbols
        cur.execute(
            "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
            (t_id,),
        )
        target_symbols = {r[0] for r in cur.fetchall()} if t_id else set()

        cur.execute(
            "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
            (g_id,),
        )
        guessed_symbols = {r[0] for r in cur.fetchall()} if g_id else set()

        matched_symbols = sorted(list(target_symbols.intersection(guessed_symbols)))

        # 3. Coordinates & Geo
        cur.execute(
            "SELECT latitude, longitude FROM countries WHERE id=?",
            (t_id,),
        )
        target_coords = cur.fetchone() if t_id else None

        cur.execute(
            "SELECT latitude, longitude FROM countries WHERE id=?",
            (g_id,),
        )
        guessed_coords = cur.fetchone() if g_id else None

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


def normalize_svg_for_grid(svg_bytes: bytes, iso2: str = "") -> bytes:
    """Normalize SVG for 3:2 grid rendering edge-to-edge.

    Removes any preserveAspectRatio attribute and sets preserveAspectRatio="none"
    on the opening <svg> tag. For Nepal (iso2=="np"), injects an opaque background
    rect right after the opening <svg> tag.
    """
    svg_text = svg_bytes.decode("utf-8", errors="replace")
    match = re.search(r"<svg\b([^>]*)>", svg_text, flags=re.IGNORECASE)
    if not match:
        return svg_bytes

    orig_attrs = match.group(1)
    # Remove existing preserveAspectRatio="..." or '...'
    clean_attrs = re.sub(
        r'\s*preserveAspectRatio\s*=\s*(["\']).*?\1',
        "",
        orig_attrs,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    if clean_attrs:
        new_tag = f'<svg preserveAspectRatio="none" {clean_attrs}>'
    else:
        new_tag = '<svg preserveAspectRatio="none">'

    # For Nepal, inject opaque backdrop rect
    backdrop = ""
    if iso2.strip().lower() == "np":
        vb_match = re.search(
            r'viewBox\s*=\s*["\']\s*([-\d.]+)[,\s]+([-\d.]+)[,\s]+([-\d.]+)[,\s]+([-\d.]+)\s*["\']',
            orig_attrs,
            flags=re.IGNORECASE,
        )
        if vb_match:
            min_x, min_y = vb_match.group(1), vb_match.group(2)
            backdrop = f'<rect x="{min_x}" y="{min_y}" width="100%" height="100%" fill="#1e293b"/>'
        else:
            backdrop = '<rect width="100%" height="100%" fill="#1e293b"/>'

    start_idx, end_idx = match.span()
    result_text = svg_text[:start_idx] + new_tag + backdrop + svg_text[end_idx:]
    return result_text.encode("utf-8")


def generate_shades_token(seed: str, country_id: int) -> str:
    """Generates a tamper-proof base64url token encoding seed, country_id, and HMAC signature."""
    sig = hmac.new(
        SECRET_KEY.encode(),
        f"flag-shades:{seed}:{country_id}".encode(),
        hashlib.sha256,
     ).hexdigest()[:16]
    payload = f"{seed}:{country_id}:{sig}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def verify_shades_token(token: str) -> Optional[Tuple[str, int]]:
    """Verifies base64url shades token and extracts (seed, country_id). Returns None if invalid."""
    if not token or not isinstance(token, str):
        return None
    try:
        token_padded = token + "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(token_padded.encode("ascii")).decode("utf-8")
        parts = payload.rsplit(":", 2)
        if len(parts) != 3:
            return None
        seed, country_id_str, sig = parts
        country_id = int(country_id_str)
        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            f"flag-shades:{seed}:{country_id}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return seed, country_id
    except Exception:
        return None
