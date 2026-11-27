#!/usr/bin/env python3
"""Fetch, simplify, and validate OGL v3.0 GeoJSON boundaries for UK map quizzes.

Generates:
  - client/public/london-boroughs.geojson  (32 London boroughs)
  - client/public/england-counties.geojson (48 English ceremonial counties)

Both files are validated for 100% ID and name parity against:
  - server/regional_symbols/data/london_boroughs/entities.json
  - server/regional_symbols/data/england_counties/entities.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGIONAL_DATA_ROOT = REPO_ROOT / "server" / "regional_symbols" / "data"
CLIENT_PUBLIC = REPO_ROOT / "client" / "public"

LONDON_ARCGIS_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/ArcGIS/rest/services/"
    "Local_Authority_Districts_May_2026_Boundaries_UK_BSC/FeatureServer/0/query"
)
ENGLAND_ARCGIS_URL = (
    "https://services.arcgis.com/qHLhLQrcvEnxjtPr/arcgis/rest/services/"
    "OS_OpenBoundaryLine/FeatureServer/4/query"
)

USER_AGENT = "Countrydle-UK-GeoJSON-Builder/1.0"


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(value.casefold().replace("-", " ").replace("&", "and").split())


def fetch_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_geojson_features(url: str, base_params: dict[str, Any]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    offset = 0
    page_size = 200
    while True:
        params = {
            **base_params,
            "f": "geojson",
            "outSR": 4326,
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        payload = fetch_json(url, params)
        batch = payload.get("features") or []
        features.extend(batch)
        if not payload.get("properties", {}).get("exceededTransferLimit") and len(batch) < page_size:
            break
        if not batch:
            break
        offset += len(batch)
    return features


def _ring_area(ring: list[list[float]]) -> float:
    """Shoelace area in square degrees (for relative filtering only)."""
    if len(ring) < 4:
        return 0.0
    total = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        total += x1 * y2 - x2 * y1
    return abs(total) * 0.5


def _round_ring(ring: list[list[float]], precision: int) -> list[list[float]]:
    rounded: list[list[float]] = []
    for pt in ring:
        coord = [round(float(pt[0]), precision), round(float(pt[1]), precision)]
        if not rounded or rounded[-1] != coord:
            rounded.append(coord)
    if len(rounded) >= 3 and rounded[0] != rounded[-1]:
        rounded.append(rounded[0])
    return rounded


def clean_geometry(geometry: dict[str, Any], precision: int, min_island_area: float) -> dict[str, Any]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        polygons = [coords]
    elif gtype == "MultiPolygon":
        polygons = list(coords)
    else:
        raise ValueError(f"Unsupported geometry type: {gtype}")

    cleaned_polygons: list[list[list[list[float]]]] = []
    poly_areas: list[tuple[float, list[list[list[float]]]]] = []
    for poly in polygons:
        if not poly:
            continue
        outer = _round_ring(poly[0], precision)
        if len(outer) < 4:
            continue
        area = _ring_area(outer)
        holes = []
        for hole in poly[1:]:
            rh = _round_ring(hole, precision)
            if len(rh) >= 4 and _ring_area(rh) >= min_island_area:
                holes.append(rh)
        poly_areas.append((area, [outer, *holes]))

    if not poly_areas:
        raise ValueError("Geometry collapsed to empty after cleaning")

    # Always keep the largest polygon even if smaller than min_island_area (e.g. City of London).
    poly_areas.sort(key=lambda item: item[0], reverse=True)
    largest_area, largest_poly = poly_areas[0]
    cleaned_polygons.append(largest_poly)
    for area, poly in poly_areas[1:]:
        if area >= min_island_area and area >= largest_area * 0.0005:
            cleaned_polygons.append(poly)

    if len(cleaned_polygons) == 1:
        return {"type": "Polygon", "coordinates": cleaned_polygons[0]}
    return {"type": "MultiPolygon", "coordinates": cleaned_polygons}


def load_entities(scope: str) -> list[dict[str, Any]]:
    path = REGIONAL_DATA_ROOT / scope / "entities.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["entities"]


def build_london_boroughs() -> dict[str, Any]:
    entities = load_entities("london_boroughs")
    by_ons = {e["ons_code"]: e for e in entities}

    raw_features = fetch_all_geojson_features(
        LONDON_ARCGIS_URL,
        {
            "where": "LAD26CD LIKE 'E09000%'",
            "outFields": "LAD26CD,LAD26NM",
            "geometryPrecision": 5,
            "maxAllowableOffset": 0.0004,
        },
    )

    out_features: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for feat in raw_features:
        props = feat.get("properties") or {}
        ons = props.get("LAD26CD")
        if ons not in by_ons:
            continue
        entity = by_ons[ons]
        if entity["id"] in seen_ids:
            continue
        seen_ids.add(entity["id"])
        geom = clean_geometry(feat["geometry"], precision=5, min_island_area=1e-7)
        out_features.append(
            {
                "type": "Feature",
                "id": entity["id"],
                "properties": {
                    "id": entity["id"],
                    "name": entity["name"],
                    "ons_code": entity["ons_code"],
                },
                "geometry": geom,
            }
        )

    out_features.sort(key=lambda f: f["properties"]["id"])
    return {"type": "FeatureCollection", "features": out_features}


ENGLAND_SOURCE_NAME_ALIASES = {
    "city and county of the city of london": "city of london",
}


def build_england_counties() -> dict[str, Any]:
    entities = load_entities("england_counties")
    by_norm_name: dict[str, dict[str, Any]] = {}
    for entity in entities:
        for candidate in [entity["name"], *entity.get("aliases", [])]:
            by_norm_name[normalize_name(candidate)] = entity

    raw_features = fetch_all_geojson_features(
        ENGLAND_ARCGIS_URL,
        {
            "where": "1=1",
            "outFields": "NAME",
            "geometryPrecision": 4,
            "maxAllowableOffset": 0.0015,
        },
    )

    out_features: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for feat in raw_features:
        props = feat.get("properties") or {}
        raw_name = props.get("NAME") or ""
        norm = normalize_name(raw_name)
        norm = ENGLAND_SOURCE_NAME_ALIASES.get(norm, norm)
        entity = by_norm_name.get(norm)
        if entity is None:
            continue
        if entity["id"] in seen_ids:
            continue
        seen_ids.add(entity["id"])
        geom = clean_geometry(feat["geometry"], precision=4, min_island_area=5e-5)
        out_features.append(
            {
                "type": "Feature",
                "id": entity["id"],
                "properties": {
                    "id": entity["id"],
                    "name": entity["name"],
                },
                "geometry": geom,
            }
        )

    out_features.sort(key=lambda f: f["properties"]["id"])
    return {"type": "FeatureCollection", "features": out_features}


def validate_geojson(scope: str, geojson_path: Path) -> tuple[int, int]:
    entities = load_entities(scope)
    expected = {(e["id"], e["name"]) for e in entities}

    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        raise AssertionError(f"{geojson_path}: expected FeatureCollection")
    features = data.get("features")
    if not isinstance(features, list):
        raise AssertionError(f"{geojson_path}: missing features list")

    actual: set[tuple[int, str]] = set()
    for feat in features:
        props = feat.get("properties") or {}
        eid, name = props.get("id"), props.get("name")
        if not isinstance(eid, int) or not isinstance(name, str):
            raise AssertionError(f"{geojson_path}: invalid properties {props}")
        if (eid, name) in actual:
            raise AssertionError(f"{geojson_path}: duplicate entity {(eid, name)}")
        actual.add((eid, name))

        geom = feat.get("geometry") or {}
        if geom.get("type") not in {"Polygon", "MultiPolygon"} or not geom.get("coordinates"):
            raise AssertionError(f"{geojson_path}: invalid geometry for {name}")
        _validate_coords_in_uk(geom["coordinates"], name)

    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise AssertionError(
            f"{geojson_path}: parity mismatch! missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return len(actual), geojson_path.stat().st_size


def _validate_coords_in_uk(obj: Any, name: str) -> None:
    if isinstance(obj, list) and obj and isinstance(obj[0], (int, float)):
        lon, lat = float(obj[0]), float(obj[1])
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise AssertionError(f"{name}: non-finite coordinate {(lon, lat)}")
        if not (-9.0 <= lon <= 3.0 and 49.0 <= lat <= 61.5):
            raise AssertionError(f"{name}: coordinate outside UK bounds {(lon, lat)}")
        return
    if isinstance(obj, list):
        for item in obj:
            _validate_coords_in_uk(item, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing GeoJSON files without fetching from ArcGIS.",
    )
    args = parser.parse_args()

    london_path = CLIENT_PUBLIC / "london-boroughs.geojson"
    england_path = CLIENT_PUBLIC / "england-counties.geojson"

    if not args.validate_only:
        print("Fetching London boroughs (ONS LAD May 2026 BSC)...")
        london_fc = build_london_boroughs()
        london_path.write_text(
            json.dumps(london_fc, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        print("Fetching English ceremonial counties (OS Boundary-Line)...")
        england_fc = build_england_counties()
        england_path.write_text(
            json.dumps(england_fc, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    l_count, l_size = validate_geojson("london_boroughs", london_path)
    e_count, e_size = validate_geojson("england_counties", england_path)
    print(f"OK london-boroughs.geojson: {l_count}/32 features ({l_size / 1024:.1f} KB)")
    print(f"OK england-counties.geojson: {e_count}/48 features ({e_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
