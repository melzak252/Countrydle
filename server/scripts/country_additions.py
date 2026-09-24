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
from pathlib import Path

SOURCE_DIR = Path(__file__).with_name("country_sources")


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
    columns = ", ".join(country)
    placeholders = ", ".join("?" for _ in country)
    country_id = connection.execute(
        f"INSERT INTO countries ({columns}) VALUES ({placeholders})", tuple(country.values())
    ).lastrowid
    # The base schema predates these three enrichment tables.
    for table, column in (
        ("country_flag_colors", "color"),
        ("country_flag_symbols", "symbol"),
        ("country_historical_unions", "union_name"),
    ):
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            f"country_id INTEGER NOT NULL REFERENCES countries(id), {column} TEXT NOT NULL, "
            f"PRIMARY KEY (country_id, {column}))"
        )
    for key, table, columns in (
        ("continents", "country_continents", "continent"),
        ("regions", "country_regions", "region_name"),
        ("subregions", "country_subregions", "subregion_name"),
        ("borders", "country_borders", "border_country_name, border_cca3"),
        ("currencies", "country_currencies", "currency_code, currency_name, currency_symbol"),
        ("languages", "country_languages", "language_code, language_name"),
        ("memberships", "country_memberships", "organization"),
        ("water_access", "country_water_access", "water_body"),
        ("major_rivers", "country_major_rivers", "river_name"),
        ("flag_colors", "country_flag_colors", "color"),
        ("flag_symbols", "country_flag_symbols", "symbol"),
        ("historical_unions", "country_historical_unions", "union_name"),
    ):
        for value in seed[key]:
            values = value if isinstance(value, list) else [value]
            placeholders = ", ".join("?" for _ in range(len(values) + 1))
            connection.execute(
                f"INSERT OR IGNORE INTO {table} (country_id, {columns}) VALUES ({placeholders})",
                (country_id, *values),
            )
    for border_name, _ in seed["borders"]:
        connection.execute(
            "INSERT INTO country_borders (country_id, border_country_name, border_cca3) "
            "SELECT id, 'Kosovo', 'XKX' FROM countries WHERE app_country_name = ? "
            "ON CONFLICT (country_id, border_country_name) DO UPDATE SET border_cca3 = excluded.border_cca3",
            (border_name,),
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
