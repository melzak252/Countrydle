"""Populate bounding boxes and hemispheres in country_facts.sqlite.

This script:
1. Adds `min_latitude`, `max_latitude`, `min_longitude`, `max_longitude` columns to `countries` table if missing.
2. Creates `country_hemispheres` table and index.
3. Populates bounding boxes and hemisphere assignments (Northern, Southern, Eastern, Western) for all 196 countries.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"
GEOJSON_URL = "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"

# Curated overrides for sovereign definitions aligned with Countrydle facts
# (e.g. Metropolitan France, European Netherlands, Denmark proper without Greenland, etc.)
OVERRIDES = {
    "FRA": {"min_lat": 41.33, "max_lat": 51.09, "min_lon": -4.79, "max_lon": 9.56, "hemispheres": ["Northern", "Eastern", "Western"]},
    "GBR": {"min_lat": 49.91, "max_lat": 60.85, "min_lon": -13.69, "max_lon": 1.77, "hemispheres": ["Northern", "Eastern", "Western"]},
    "NOR": {"min_lat": 57.96, "max_lat": 71.19, "min_lon": 4.50, "max_lon": 31.10, "hemispheres": ["Northern", "Eastern"]},
    "PRT": {"min_lat": 30.03, "max_lat": 42.15, "min_lon": -31.28, "max_lon": -6.21, "hemispheres": ["Northern", "Western"]},
    "NLD": {"min_lat": 50.75, "max_lat": 53.55, "min_lon": 3.36, "max_lon": 7.23, "hemispheres": ["Northern", "Eastern"]},
    "DNK": {"min_lat": 54.57, "max_lat": 57.75, "min_lon": 8.09, "max_lon": 15.15, "hemispheres": ["Northern", "Eastern"]},
    "KIR": {"min_lat": -11.46, "max_lat": 4.72, "min_lon": -174.54, "max_lon": 176.85, "hemispheres": ["Northern", "Southern", "Eastern", "Western"]},
    "XKX": {"min_lat": 41.85, "max_lat": 43.27, "min_lon": 20.02, "max_lon": 21.79, "hemispheres": ["Northern", "Eastern"]},
}


def get_coords(geom):
    coords = []
    gtype = geom.get("type")
    if gtype == "Polygon":
        for ring in geom.get("coordinates", []):
            coords.extend(ring)
    elif gtype == "MultiPolygon":
        for poly in geom.get("coordinates", []):
            for ring in poly:
                coords.extend(ring)
    return coords


def ensure_schema(conn: sqlite3.Connection):
    with conn:
        # 1. Bounding box columns in countries table
        cursor = conn.execute("PRAGMA table_info(countries)")
        cols = {row[1] for row in cursor.fetchall()}
        for col_name in ("min_latitude", "max_latitude", "min_longitude", "max_longitude"):
            if col_name not in cols:
                conn.execute(f"ALTER TABLE countries ADD COLUMN {col_name} REAL")

        # 2. country_hemispheres table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS country_hemispheres (
            country_id INTEGER NOT NULL,
            hemisphere TEXT NOT NULL,
            PRIMARY KEY (country_id, hemisphere),
            FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_country_hemispheres ON country_hemispheres(hemisphere);")


def populate_boxes_and_hemispheres(db_path: Path):
    print(f"Opening database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    print(f"Fetching reference GeoJSON from: {GEOJSON_URL}")
    req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": "Countrydle-Data-Builder/1.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)

    features_by_cca3 = {f["properties"].get("ISO3166-1-Alpha-3"): f for f in data["features"] if f["properties"].get("ISO3166-1-Alpha-3")}
    features_by_name = {f["properties"].get("name", "").lower(): f for f in data["features"]}

    db_countries = conn.execute("SELECT id, app_country_name, cca3 FROM countries").fetchall()

    box_updates = []
    hemisphere_rows = []

    for c in db_countries:
        cid = c["id"]
        cca3 = c["cca3"]
        name = c["app_country_name"]

        if cca3 in OVERRIDES:
            info = OVERRIDES[cca3]
            min_lat, max_lat = info["min_lat"], info["max_lat"]
            min_lon, max_lon = info["min_lon"], info["max_lon"]
            hemispheres = info["hemispheres"]
        else:
            f = features_by_cca3.get(cca3) or features_by_name.get(name.lower())
            if not f:
                raise ValueError(f"Could not find geographic feature for country {name} ({cca3})")
            coords = get_coords(f["geometry"])
            lons = [pt[0] for pt in coords]
            lats = [pt[1] for pt in coords]
            min_lat, max_lat = round(min(lats), 4), round(max(lats), 4)
            min_lon, max_lon = round(min(lons), 4), round(max(lons), 4)

            hemispheres = []
            if max_lat > 0:
                hemispheres.append("Northern")
            if min_lat < 0:
                hemispheres.append("Southern")
            if any(0 < lon <= 180 for lon in lons):
                hemispheres.append("Eastern")
            if any(-180 <= lon < 0 for lon in lons):
                hemispheres.append("Western")

        box_updates.append((min_lat, max_lat, min_lon, max_lon, cid))
        for h in hemispheres:
            hemisphere_rows.append((cid, h))

    with conn:
        conn.executemany(
            "UPDATE countries SET min_latitude=?, max_latitude=?, min_longitude=?, max_longitude=? WHERE id=?",
            box_updates,
        )
        conn.execute("DELETE FROM country_hemispheres")
        conn.executemany("INSERT INTO country_hemispheres(country_id, hemisphere) VALUES (?, ?)", hemisphere_rows)

    print(f"Updated bounding boxes for {len(box_updates)} countries.")
    print(f"Populated {len(hemisphere_rows)} country hemisphere associations.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Populate bounding boxes and hemispheres in country_facts.sqlite")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to country_facts.sqlite")
    args = parser.parse_args()
    populate_boxes_and_hemispheres(args.db)


if __name__ == "__main__":
    main()
