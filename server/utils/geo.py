from __future__ import annotations

import math
from pathlib import Path
import sqlite3
from typing import Any

_APP_DIR = Path(__file__).resolve().parent
_DATA_DIR = (
    _APP_DIR.parent / "data"
    if (_APP_DIR.parent / "data").exists()
    else _APP_DIR.parents[1] / "data"
)

# 8-point compass directions with unicode arrows
COMPASS_DIRECTIONS: list[tuple[float, float, str, str]] = [
    (337.5, 360.0, "N", "↑"),
    (0.0, 22.5, "N", "↑"),
    (22.5, 67.5, "NE", "↗"),
    (67.5, 112.5, "E", "→"),
    (112.5, 157.5, "SE", "↘"),
    (157.5, 202.5, "S", "↓"),
    (202.5, 247.5, "SW", "↙"),
    (247.5, 292.5, "W", "←"),
    (292.5, 337.5, "NW", "↖"),
]

MODE_TABLE_MAP: dict[str, tuple[str, str, str]] = {
    "countrydle": ("country_facts.sqlite", "countries", "app_country_name"),
    "country": ("country_facts.sqlite", "countries", "app_country_name"),
    "us_statedle": ("us_state_facts.sqlite", "us_states", "name"),
    "us_states": ("us_state_facts.sqlite", "us_states", "name"),
    "wojewodztwodle": ("voivodeship_facts.sqlite", "voivodeships", "name"),
    "wojewodztwa": ("voivodeship_facts.sqlite", "voivodeships", "name"),
    "powiatdle": ("powiat_facts.sqlite", "powiats", "name"),
    "powiaty": ("powiat_facts.sqlite", "powiats", "name"),
    "continental": ("country_facts.sqlite", "countries", "app_country_name"),
    "europe": ("country_facts.sqlite", "countries", "app_country_name"),
    "asia": ("country_facts.sqlite", "countries", "app_country_name"),
    "africa": ("country_facts.sqlite", "countries", "app_country_name"),
    "americas": ("country_facts.sqlite", "countries", "app_country_name"),
}


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Calculate great-circle distance between two points in km using Haversine formula."""
    r = 6371.0  # Earth's radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return int(round(r * c))


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[int, str, str]:
    """Calculate forward initial azimuth bearing from (lat1, lon1) to (lat2, lon2).

    Returns:
        (bearing_degrees, compass_code, arrow_symbol)
        e.g. (45, "NE", "↗")
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    x = math.sin(delta_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    initial_bearing = math.atan2(x, y)
    degrees = (math.degrees(initial_bearing) + 360.0) % 360.0
    rounded_deg = int(round(degrees)) % 360

    code, arrow = "N", "↑"
    for low, high, c_code, c_arrow in COMPASS_DIRECTIONS:
        if low <= degrees < high:
            code, arrow = c_code, c_arrow
            break
    return rounded_deg, code, arrow


def get_entity_coordinates(
    mode: str,
    entity_id: int | None = None,
    name: str | None = None,
    db_path: Path | None = None,
) -> tuple[float, float] | None:
    """Retrieve (latitude, longitude) for a given entity in the specified game mode."""
    if mode not in MODE_TABLE_MAP:
        return None

    db_filename, table, name_col = MODE_TABLE_MAP[mode]
    path = db_path or (_DATA_DIR / db_filename)
    if not path.exists():
        return None

    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if name:
            clean_name = name.strip()
            row = cursor.execute(
                f"SELECT latitude, longitude FROM {table} WHERE LOWER({name_col}) = LOWER(?)",
                (clean_name,),
            ).fetchone()
            if not row and mode in ("countrydle", "country"):
                row = cursor.execute(
                    "SELECT latitude, longitude FROM countries WHERE LOWER(official_name) = LOWER(?)",
                    (clean_name,),
                ).fetchone()

        if not row and entity_id is not None and entity_id > 0:
            row = cursor.execute(
                f"SELECT latitude, longitude FROM {table} WHERE id = ?", (entity_id,)
            ).fetchone()
        conn.close()

        if row and row["latitude"] is not None and row["longitude"] is not None:
            return float(row["latitude"]), float(row["longitude"])
    except Exception:
        pass

    return None


def compute_guess_hint(
    mode: str,
    guess_number: int,
    max_guesses: int,
    is_correct: bool,
    guessed_coords: tuple[float, float] | None,
    target_coords: tuple[float, float] | None,
) -> dict:
    """Compute progressive distance and bearing hints for an incorrect guess.

    Rules:
    - If correct: distance = 0, no direction hint.
    - If incorrect and coordinates available:
      - 3-guess modes:
        - Guess 1: distance_km only.
        - Guess 2+: distance_km AND bearing (degrees, direction, arrow).
      - 2-guess mode (wojewodztwodle):
        - Guess 1: distance_km AND bearing (since guess 2 is already final).
    """
    hint = {
        "distance_km": None,
        "bearing_degrees": None,
        "bearing_direction": None,
        "bearing_arrow": None,
    }

    if is_correct:
        hint["distance_km"] = 0
        return hint

    if not guessed_coords or not target_coords:
        return hint

    dist = calculate_distance_km(
        guessed_coords[0], guessed_coords[1], target_coords[0], target_coords[1]
    )
    hint["distance_km"] = dist

    deg, direction, arrow = calculate_bearing(
        guessed_coords[0], guessed_coords[1], target_coords[0], target_coords[1]
    )

    # In 2-guess mode (e.g. wojewodztwodle), give direction on guess 1 immediately
    if max_guesses <= 2:
        hint["bearing_degrees"] = deg
        hint["bearing_direction"] = direction
        hint["bearing_arrow"] = arrow
    # In 3+ guess modes, give distance on guess 1, and distance + direction on guess 2+
    elif guess_number >= 2:
        hint["bearing_degrees"] = deg
        hint["bearing_direction"] = direction
        hint["bearing_arrow"] = arrow

    return hint


def enhance_guess_with_hint(
    mode: str,
    guess_record: Any,
    guess_number: int,
    max_guesses: int,
    target_id: int | None = None,
    target_name: str | None = None,
    target_coords: tuple[float, float] | None = None,
) -> dict:
    """Extract coordinates and compute hints for a guess, returning a dict of fields."""
    if target_coords is None:
        target_coords = get_entity_coordinates(
            mode, entity_id=target_id, name=target_name
        )
    guess_name = (
        getattr(guess_record, "guess", None)
        if not isinstance(guess_record, dict)
        else guess_record.get("guess")
    )

    id_attr_map = {
        "countrydle": "country_id",
        "country": "country_id",
        "us_statedle": "us_state_id",
        "us_states": "us_state_id",
        "wojewodztwodle": "wojewodztwo_id",
        "wojewodztwa": "wojewodztwo_id",
        "powiatdle": "powiat_id",
        "powiaty": "powiat_id",
        "continental": "country_id",
        "europe": "country_id",
        "asia": "country_id",
        "africa": "country_id",
        "americas": "country_id",
    }
    id_attr = id_attr_map.get(mode, "entity_id")
    guessed_id = (
        getattr(guess_record, id_attr, None)
        if not isinstance(guess_record, dict)
        else guess_record.get(id_attr)
    )

    is_correct = bool(
        getattr(guess_record, "answer", False)
        if not isinstance(guess_record, dict)
        else guess_record.get("answer")
    )

    guessed_coords = get_entity_coordinates(mode, entity_id=guessed_id, name=guess_name)

    return compute_guess_hint(
        mode=mode,
        guess_number=guess_number,
        max_guesses=max_guesses,
        is_correct=is_correct,
        guessed_coords=guessed_coords,
        target_coords=target_coords,
    )
