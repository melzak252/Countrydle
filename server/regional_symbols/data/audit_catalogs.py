#!/usr/bin/env python3
"""Audit packaged regional entity and symbol catalogs; report JSON to stdout."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SCOPES = {"voivodeships": 16, "london_boroughs": 32, "england_counties": 48}

def https_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def valid_credits(source):
    if not isinstance(source, dict) or not https_url(source.get("url")):
        return False
    license_name = source.get("license")
    if not isinstance(license_name, str) or not license_name.strip():
        return False
    if license_name.strip().casefold() != "public domain":
        if not isinstance(source.get("attribution"), str) or not source["attribution"].strip() or not https_url(source.get("license_url")):
            return False
    credits = source.get("component_credits", [])
    if not isinstance(credits, list):
        return False
    for credit in credits:
        if not isinstance(credit, dict) or not https_url(credit.get("url")):
            return False
        if any(not isinstance(credit.get(key), str) or not credit[key].strip() for key in ("title", "author", "license")):
            return False
        if credit["license"].strip().casefold() != "public domain" and not https_url(credit.get("license_url")):
            return False
    return True


def audit():
    result = {"scopes": {}, "errors": [], "fairness_issues": []}
    for scope, expected in SCOPES.items():
        folder = ROOT / scope
        entities = json.loads((folder / "entities.json").read_text(encoding="utf-8"))["entities"]
        source = json.loads((folder / "source_audit.json").read_text(encoding="utf-8"))["entities"]
        ids = [e["id"] for e in entities]
        report = {"entity_count": len(ids), "source_audit_count": len(source), "pools": {}}
        result["scopes"][scope] = report
        if len(ids) != expected or len(set(ids)) != expected or {e["id"] for e in source} != set(ids):
            result["errors"].append(f"{scope}: entity or audit coverage mismatch")
        for mode in ("flags", "coats"):
            file = folder / f"{mode}_catalog.json"
            if not file.exists():
                report["pools"][mode] = {"status": "unavailable", "eligible": 0}
                continue
            catalog = json.loads(file.read_text(encoding="utf-8"))
            entries = catalog["entities"]
            daily_file = folder / f"daily_{mode}_v1.json"
            daily = json.loads(daily_file.read_text(encoding="utf-8"))
            pool_ids = [entry["id"] for entry in entries]
            pool_report = {"status": "published" if len(entries) >= 2 else "withheld", "eligible": len(entries), "daily_ids": daily, "assets": []}
            report["pools"][mode] = pool_report
            if catalog.get("build_complete") is not True or len(pool_ids) != len(set(pool_ids)) or not set(pool_ids) <= set(ids) or set(daily) != set(pool_ids):
                result["errors"].append(f"{scope}/{mode}: invalid catalog or daily pool")
            if len(entries) < 8:
                result["fairness_issues"].append(f"{scope}/{mode}: only {len(entries)} eligible targets; repeated daily answers likely")
            hashes = {}
            for entry in entries:
                name = entry["filename"]
                if Path(name).name != name:
                    result["errors"].append(f"{scope}/{mode}: invalid filename")
                    continue
                data = (folder / "assets" / name).read_bytes()
                sha1 = hashlib.sha1(data).hexdigest()
                source_info = entry["source"]
                if not valid_credits(source_info):
                    result["errors"].append(f"{scope}/{mode}/{name}: invalid source or component credits")
                item = {"id": entry["id"], "filename": name, "bytes": len(data), "sha1": sha1}
                pool_report["assets"].append(item)
                if sha1 != source_info.get("asset_sha1"):
                    result["errors"].append(f"{scope}/{mode}/{name}: delivered hash mismatch")
                if sha1 in hashes:
                    result["fairness_issues"].append(f"{scope}/{mode}: identical bytes for IDs {hashes[sha1]} and {entry['id']}")
                hashes[sha1] = entry["id"]
                if name.endswith(".svg"):
                    try:
                        root = ET.fromstring(data)
                        if root.tag != "{http://www.w3.org/2000/svg}svg":
                            raise ValueError("missing SVG namespace")
                        item["mime"] = "image/svg+xml"
                    except (ET.ParseError, ValueError) as exc:
                        result["errors"].append(f"{scope}/{mode}/{name}: {exc}")
                else:
                    result["errors"].append(f"{scope}/{mode}/{name}: unsupported asset type")
    return result


if __name__ == "__main__":
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(bool(report["errors"]))
