"""Provision versioned country additions into persisted datasets and RAG storage.

The source bundle is tracked outside the ignored/mounted data directory. Existing
country facts and articles are never overwritten, so admin edits survive startup.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).with_name("country_sources")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def provision_country_sources(data_dir: Path) -> None:
    """Add the CSV entry and source article without replacing the existing corpus."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    article = data_dir / "countries" / "Kosovo.md"
    article.parent.mkdir(parents=True, exist_ok=True)
    if not article.exists():
        article.write_text((SOURCE_DIR / "Kosovo.md").read_text(encoding="utf-8"), encoding="utf-8")
    csv_path = data_dir / "countries.csv"
    if not csv_path.exists():
        # An empty volume is not a complete country corpus; do not manufacture one.
        return
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if any(row["name"].strip() == "Kosovo" for row in rows):
        return
    with csv_path.open("a", encoding="utf-8", newline="") as file:
        # Existing distributed CSVs do not necessarily have a terminal newline.
        if csv_path.stat().st_size and not csv_path.read_bytes().endswith((b"\n", b"\r")):
            file.write("\n")
        csv.writer(file).writerow(["Kosovo", "data/countries/Kosovo.md"])


def add_kosovo_facts(connection: sqlite3.Connection) -> bool:
    """Insert the complete sourced record once, in the caller's transaction."""
    if connection.execute(
        "SELECT 1 FROM countries WHERE app_country_name = 'Kosovo'"
    ).fetchone():
        return False
    seed = json.loads((SOURCE_DIR / "kosovo.json").read_text(encoding="utf-8"))
    country = seed["country"]
    country_id = connection.execute(
        "INSERT INTO countries ("
        "app_country_name, official_name, cca2, cca3, region, subregion, capital, "
        "population, area_km2, latitude, longitude, is_island, driving_side, "
        "government_type, dominant_religion, source"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            country["app_country_name"],
            country["official_name"],
            country["cca2"],
            country["cca3"],
            country["region"],
            country["subregion"],
            country["capital"],
            country["population"],
            country["area_km2"],
            country["latitude"],
            country["longitude"],
            country["is_island"],
            country["driving_side"],
            country["government_type"],
            country["dominant_religion"],
            country["source"],
        ),
    ).lastrowid
    # The base schema predates these three enrichment tables.
    for ddl in (
        "CREATE TABLE IF NOT EXISTS country_flag_colors ("
        "country_id INTEGER NOT NULL REFERENCES countries(id), color TEXT NOT NULL, "
        "PRIMARY KEY (country_id, color))",
        "CREATE TABLE IF NOT EXISTS country_flag_symbols ("
        "country_id INTEGER NOT NULL REFERENCES countries(id), symbol TEXT NOT NULL, "
        "PRIMARY KEY (country_id, symbol))",
        "CREATE TABLE IF NOT EXISTS country_historical_unions ("
        "country_id INTEGER NOT NULL REFERENCES countries(id), union_name TEXT NOT NULL, "
        "PRIMARY KEY (country_id, union_name))",
    ):
        connection.execute(ddl)
    for key, sql in (
        ("continents", "INSERT OR IGNORE INTO country_continents (country_id, continent) VALUES (?, ?)"),
        ("regions", "INSERT OR IGNORE INTO country_regions (country_id, region_name) VALUES (?, ?)"),
        ("subregions", "INSERT OR IGNORE INTO country_subregions (country_id, subregion_name) VALUES (?, ?)"),
        ("borders", "INSERT OR IGNORE INTO country_borders (country_id, border_country_name, border_cca3) VALUES (?, ?, ?)"),
        ("currencies", "INSERT OR IGNORE INTO country_currencies (country_id, currency_code, currency_name, currency_symbol) VALUES (?, ?, ?, ?)"),
        ("languages", "INSERT OR IGNORE INTO country_languages (country_id, language_code, language_name) VALUES (?, ?, ?)"),
        ("memberships", "INSERT OR IGNORE INTO country_memberships (country_id, organization) VALUES (?, ?)"),
        ("water_access", "INSERT OR IGNORE INTO country_water_access (country_id, water_body) VALUES (?, ?)"),
        ("major_rivers", "INSERT OR IGNORE INTO country_major_rivers (country_id, river_name) VALUES (?, ?)"),
        ("flag_colors", "INSERT OR IGNORE INTO country_flag_colors (country_id, color) VALUES (?, ?)"),
        ("flag_symbols", "INSERT OR IGNORE INTO country_flag_symbols (country_id, symbol) VALUES (?, ?)"),
        ("historical_unions", "INSERT OR IGNORE INTO country_historical_unions (country_id, union_name) VALUES (?, ?)"),
    ):
        for value in seed[key]:
            values = value if isinstance(value, list) else [value]
            connection.execute(sql, (country_id, *values))
    for border_name, _ in seed["borders"]:
        connection.execute(
            "INSERT INTO country_borders (country_id, border_country_name, border_cca3) "
            "SELECT id, 'Kosovo', 'XKX' FROM countries WHERE app_country_name = ? "
            "ON CONFLICT (country_id, border_country_name) DO UPDATE SET border_cca3 = excluded.border_cca3",
            (border_name,),
        )
    from country_fact_provenance import ensure_schema
    ensure_schema(connection)
    return True

def add_turkey_sea_of_marmara(connection: sqlite3.Connection) -> bool:
    """Ensure Turkey includes Sea of Marmara in country_water_access."""
    row = connection.execute(
        "SELECT id FROM countries WHERE app_country_name = 'Turkey'"
    ).fetchone()
    if not row:
        return False
    connection.execute(
        "INSERT OR IGNORE INTO country_water_access (country_id, water_body) VALUES (?, 'Sea of Marmara')",
        (row[0],),
    )
    return True


def provision_country_additions(data_dir: Path) -> None:
    """Apply additions to an existing mounted corpus without rebuilding other facts."""
    data_dir = Path(data_dir)
    provision_country_sources(data_dir)
    db_path = data_dir / "country_facts.sqlite"
    if not db_path.exists():
        return
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        add_kosovo_facts(connection)
        add_turkey_sea_of_marmara(connection)
async def provision_country_addition_fragments(session) -> None:
    """Embed Kosovo once and upsert its real fragments using existing Qdrant IDs.

    Run separately after migrations and Qdrant collection initialization so an
    external embedding quota cannot prevent the game server from starting.
    Committed embeddings are reused when retrying a failed Qdrant upload.
    """
    from sqlalchemy import select, text
    from db.models import Country, CountryFragment
    import qdrant
    from qdrant_client.models import PointStruct
    from qdrant.utils import get_bulk_embedding, split_document

    await session.execute(text("SELECT pg_advisory_xact_lock(20260923, 1)"))
    country = (await session.execute(select(Country).where(Country.name == "Kosovo"))).scalar_one()
    fragments = list((await session.execute(
        select(CountryFragment).where(CountryFragment.country_id == country.id).order_by(CountryFragment.id)
    )).scalars())
    if not fragments:
        article = (SOURCE_DIR / "Kosovo.md").read_text(encoding="utf-8")
        texts = [fragment.page_content for fragment in split_document(article)]
        embeddings = await asyncio.to_thread(
            get_bulk_embedding, texts, os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        )
        if len(embeddings) != len(texts):
            raise ValueError("Kosovo embedding count does not match source fragments")
        fragments = [
            CountryFragment(country_id=country.id, text=content, embedding=embedding)
            for content, embedding in zip(texts, embeddings)
        ]
        session.add_all(fragments)
        await session.flush()
    points = [
        PointStruct(id=int(fragment.id), vector=list(fragment.embedding), payload={
            "country_id": country.id, "fragment_text": fragment.text,
        })
        for fragment in fragments
    ]
    await session.commit()
    await asyncio.to_thread(qdrant.client.upsert, collection_name="countries", points=points, wait=True)


async def main() -> None:
    """Run with `python -m scripts.country_additions` from the server directory."""
    from db import AsyncSessionLocal, get_engine
    from qdrant import close_qdrant_client

    try:
        async with AsyncSessionLocal() as session:
            await provision_country_addition_fragments(session)
    finally:
        close_qdrant_client()
        await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
