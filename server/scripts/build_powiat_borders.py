"""Derive county adjacency from an unmodified, full-resolution PRG WFS response."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import MultiPolygon, Polygon
from shapely.strtree import STRtree


NAMESPACES = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
}
SOURCE_URL = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
    "?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms%3AA02_Granice_powiatow"
    "&count=380&srsName=urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A2180"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "powiatdle/local_kb/borders.json"


def _ring_coordinates(ring: ET.Element) -> list[tuple[float, float]]:
    positions = ring.find("gml:posList", NAMESPACES)
    if positions is None or positions.get("srsDimension", "2") != "2":
        raise ValueError("Expected two-dimensional GML posList")
    ordinates = [float(value) for value in (positions.text or "").split()]
    if len(ordinates) < 8 or len(ordinates) % 2:
        raise ValueError("Invalid county boundary ring")
    coordinates = list(zip(ordinates[::2], ordinates[1::2]))
    if coordinates[0] != coordinates[-1]:
        raise ValueError("County boundary rings must be closed")
    return coordinates


def load_boundaries(path: Path) -> tuple[dict, dict[str, Polygon | MultiPolygon]]:
    root = ET.parse(path).getroot()
    members = root.findall("wfs:member", NAMESPACES)
    if not members or root.get("numberReturned") != str(len(members)):
        raise ValueError("Incomplete WFS county response")
    boundaries = {}
    county_names = {}
    versions = set()
    for member in members:
        if len(member) != 1:
            raise ValueError("Expected one county per WFS member")
        feature = member[0]
        code = feature.findtext("ms:JPT_KOD_JE", namespaces=NAMESPACES)
        if not code or not re.fullmatch(r"\d{4}", code) or code in boundaries:
            raise ValueError(f"Missing, duplicate or invalid county TERYT: {code!r}")
        if feature.findtext("ms:JPT_SJR_KO", namespaces=NAMESPACES) != "POW":
            raise ValueError(f"Non-county feature: {code}")
        geometry_node = feature.find("ms:msGeometry", NAMESPACES)
        if geometry_node is None or len(geometry_node) != 1:
            raise ValueError(f"Missing county geometry: {code}")
        source_crs = geometry_node[0].get("srsName")
        if source_crs != "urn:ogc:def:crs:EPSG::2180":
            raise ValueError(f"Expected PRG EPSG:2180 geometry: {code}")
        polygons = []
        for polygon in geometry_node.findall(".//gml:Polygon", NAMESPACES):
            if polygon.get("srsName", source_crs) != source_crs:
                raise ValueError(f"Expected unsimplified PRG EPSG:2180 geometry: {code}")
            exterior = polygon.find("gml:exterior/gml:LinearRing", NAMESPACES)
            if exterior is None:
                raise ValueError(f"Missing exterior ring: {code}")
            holes = [
                _ring_coordinates(ring)
                for ring in polygon.findall("gml:interior/gml:LinearRing", NAMESPACES)
            ]
            polygons.append(Polygon(_ring_coordinates(exterior), holes))
        if not polygons:
            raise ValueError(f"Missing county polygons: {code}")
        geometry = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid county geometry: {code}")
        boundaries[code] = geometry
        county_names[code] = feature.findtext("ms:JPT_NAZWA_", namespaces=NAMESPACES)
        version = feature.findtext("ms:WERSJA_OD", namespaces=NAMESPACES)
        if version:
            versions.add(version)
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    metadata = {
        "source_url": SOURCE_URL,
        "source_sha256": digest,
        "wfs_timestamp": root.get("timeStamp"),
        "crs": "EPSG:2180",
        "feature_version_range": [min(versions), max(versions)] if versions else None,
        "county_names": county_names,
    }
    return metadata, boundaries


def derive_borders(boundaries: dict[str, Polygon | MultiPolygon]) -> list[list[str]]:
    """Shared lines are borders; point contacts and nearby polygons are not."""
    codes = sorted(boundaries)
    geometries = [boundaries[code] for code in codes]
    lines = [geometry.boundary for geometry in geometries]
    tree = STRtree(geometries)
    edges = []
    for index, geometry in enumerate(geometries):
        for neighbor in sorted(tree.query(geometry)):
            if neighbor <= index:
                continue
            if lines[index].intersection(lines[neighbor]).length > 0:
                edges.append([codes[index], codes[neighbor]])
    return edges


def build_snapshot(source_path: Path, output_path: Path) -> dict:
    metadata, boundaries = load_boundaries(source_path)
    edges = derive_borders(boundaries)
    incident = {code for edge in edges for code in edge}
    if incident != boundaries.keys():
        raise ValueError(f"Counties without a shared boundary: {sorted(boundaries.keys() - incident)}")
    snapshot = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": metadata,
        "adjacency_rule": "Positive-length shared polygon boundary; point contact excluded; no simplification or buffering.",
        "counties": sorted(boundaries),
        "borders": edges,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Raw PRG county WFS GML in EPSG:2180")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = build_snapshot(args.input, args.output)
    print(json.dumps({"counties": len(snapshot["counties"]), "undirected_borders": len(snapshot["borders"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
