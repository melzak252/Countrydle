"""Build and verify coats-of-arms SVG and attribution cache for Polish counties.

Resolves coat of arms SVGs via pl.wikipedia.org -> Wikidata P94 -> Wikimedia Commons
and saves them to data/powiat_herb_cache/{powiat_id}.svg and {powiat_id}.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from powiatdle.heraldry import (  # noqa: E402
    atomic_write,
    get_db_path,
    get_herb_cache_dir,
    resolve_and_fetch_heraldry,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_powiat_heraldry")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Populate and verify the Polish county heraldry cache."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to powiat_facts.sqlite database.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Path to powiat_herb_cache output directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of counties to process.",
    )
    parser.add_argument(
        "--powiat-id",
        type=int,
        default=None,
        help="Process only a single powiat ID.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and overwrite existing cached assets.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify integrity of cached files without downloading.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay in seconds between Wikipedia/Commons requests (default: 0.2).",
    )
    return parser.parse_args(argv)


def get_counties(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county FROM powiats ORDER BY id ASC"
        )
        return [
            {
                "id": int(r["id"]),
                "name": str(r["name"]),
                "voivodeship": str(r["voivodeship"]),
                "is_city_county": bool(r["is_city_county"]),
            }
            for r in cur.fetchall()
        ]


def verify_entry(svg_file: Path, json_file: Path) -> tuple[bool, str]:
    if not svg_file.exists():
        return False, "Missing .svg file"
    if not json_file.exists():
        return False, "Missing .json file"

    try:
        svg_content = svg_file.read_bytes()
        if len(svg_content) < 50:
            return False, "SVG file too small"
        if b"<svg" not in svg_content and b"<?xml" not in svg_content:
            return False, "File does not contain SVG XML markers"
    except Exception as exc:
        return False, f"Failed to read SVG: {exc}"

    try:
        json_content = json.loads(json_file.read_text(encoding="utf-8"))
        if not isinstance(json_content, dict):
            return False, "JSON content is not a dict"
        if "attribution" not in json_content:
            return False, "JSON missing attribution key"
    except Exception as exc:
        return False, f"Failed to parse JSON: {exc}"

    return True, "OK"


def build_heraldry(args: argparse.Namespace) -> int:
    db_path = args.db or get_db_path()
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return 1

    cache_dir = args.cache_dir or (db_path.parent / "powiat_herb_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    counties = get_counties(db_path)
    if args.powiat_id is not None:
        counties = [c for c in counties if c["id"] == args.powiat_id]
        if not counties:
            logger.error(f"No powiat found with ID {args.powiat_id}")
            return 1

    if args.limit is not None and args.limit > 0:
        counties = counties[: args.limit]

    logger.info(
        f"Processing {len(counties)} counties against cache directory: {cache_dir}"
    )

    verified_count = 0
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, county in enumerate(counties, 1):
        cid = county["id"]
        cname = county["name"]
        svg_file = cache_dir / f"{cid}.svg"
        json_file = cache_dir / f"{cid}.json"

        if args.verify:
            ok, msg = verify_entry(svg_file, json_file)
            if ok:
                verified_count += 1
                logger.info(f"[{idx}/{len(counties)}] ID {cid}: {cname} -> VALID")
            else:
                failed_count += 1
                logger.warning(
                    f"[{idx}/{len(counties)}] ID {cid}: {cname} -> INVALID ({msg})"
                )
            continue

        # Check if already cached
        if not args.force:
            ok, _ = verify_entry(svg_file, json_file)
            if ok:
                skipped_count += 1
                logger.debug(f"[{idx}/{len(counties)}] ID {cid}: {cname} -> CACHED")
                continue

        logger.info(f"[{idx}/{len(counties)}] ID {cid}: {cname} -> Fetching...")
        try:
            svg_bytes, meta = resolve_and_fetch_heraldry(cname)
            atomic_write(svg_file, svg_bytes)
            atomic_write(json_file, json.dumps(meta, ensure_ascii=False, indent=2))
            downloaded_count += 1
            logger.info(
                f"[{idx}/{len(counties)}] ID {cid}: {cname} -> SAVED ({len(svg_bytes)} bytes)"
            )
        except Exception as exc:
            failed_count += 1
            logger.error(f"[{idx}/{len(counties)}] ID {cid}: {cname} -> FAILED: {exc}")

        if args.delay > 0:
            time.sleep(args.delay)

    logger.info("=" * 60)
    if args.verify:
        logger.info(
            f"Verification summary: {verified_count} valid, {failed_count} invalid/missing (total {len(counties)})"
        )
    else:
        logger.info(
            f"Build summary: {downloaded_count} downloaded, {skipped_count} skipped, {failed_count} failed (total {len(counties)})"
        )

    return 0 if failed_count == 0 else 1


def main() -> None:
    args = parse_args()
    sys.exit(build_heraldry(args))


if __name__ == "__main__":
    main()
