"""Export static PostgreSQL `*_fragments` text into `data/rag_fragments.sqlite`.

Usage:
    python3 -m scripts.migrate_fragments_to_sqlite
    python3 -m scripts.migrate_fragments_to_sqlite --truncate-postgres

Without `--truncate-postgres`, PostgreSQL tables are left completely untouched.
With `--truncate-postgres`, after verifying exact row-count parity in SQLite,
the 4 static fragment tables are truncated and vacuumed to reclaim disk space.
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
from pathlib import Path

from sqlalchemy import text as sa_text

from db import AsyncSessionLocal
from utils.rag_fragments_store import default_fragments_db_path, init_fragments_db

FRAGMENT_SOURCES = (
    (
        "country",
        "country_fragments",
        "SELECT f.country_id, COALESCE(c.name, ''), f.text "
        "FROM country_fragments f LEFT JOIN countries c ON c.id = f.country_id ORDER BY f.id",
    ),
    (
        "powiat",
        "powiat_fragments",
        "SELECT f.powiat_id, COALESCE(p.nazwa, ''), f.text "
        "FROM powiat_fragments f LEFT JOIN powiaty p ON p.id = f.powiat_id ORDER BY f.id",
    ),
    (
        "wojewodztwo",
        "wojewodztwo_fragments",
        "SELECT f.wojewodztwo_id, COALESCE(w.nazwa, ''), f.text "
        "FROM wojewodztwo_fragments f LEFT JOIN wojewodztwa w ON w.id = f.wojewodztwo_id ORDER BY f.id",
    ),
    (
        "us_state",
        "us_state_fragments",
        "SELECT f.us_state_id, COALESCE(s.name, ''), f.text "
        "FROM us_state_fragments f LEFT JOIN us_states s ON s.id = f.us_state_id ORDER BY f.id",
    ),
)


async def migrate_fragments(*, db_path: Path | None = None, truncate_postgres: bool = False) -> dict[str, int]:
    target_path = init_fragments_db(db_path)
    tmp_path = target_path.with_suffix(".sqlite.tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    init_fragments_db(tmp_path)

    counts: dict[str, int] = {}
    sqlite_conn = sqlite3.connect(tmp_path)
    try:
        sqlite_conn.execute("PRAGMA journal_mode=OFF")
        sqlite_conn.execute("PRAGMA synchronous=OFF")
        async with AsyncSessionLocal() as session:
            for entity_type, pg_table, query in FRAGMENT_SOURCES:
                result = await session.execute(sa_text(query))
                rows = result.fetchall()
                sqlite_conn.executemany(
                    "INSERT INTO fragments (entity_type, entity_id, entity_name, text) VALUES (?, ?, ?, ?)",
                    [(entity_type, int(r[0]), str(r[1] or ""), str(r[2] or "")) for r in rows],
                )
                sqlite_conn.commit()
                counts[pg_table] = len(rows)
                print(f"Exported {len(rows):>6} rows from {pg_table} -> SQLite ({entity_type})")
        sqlite_conn.execute("VACUUM")
        sqlite_conn.commit()
    finally:
        sqlite_conn.close()

    # Verify exact row counts before swapping atomically
    verify_conn = sqlite3.connect(tmp_path)
    try:
        for entity_type, pg_table, _ in FRAGMENT_SOURCES:
            actual = verify_conn.execute(
                "SELECT COUNT(*) FROM fragments WHERE entity_type = ?",
                (entity_type,),
            ).fetchone()[0]
            if actual != counts[pg_table]:
                raise RuntimeError(
                    f"Parity mismatch for {pg_table}: expected {counts[pg_table]}, got {actual}"
                )
    finally:
        verify_conn.close()

    tmp_path.replace(target_path)
    size_mb = target_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {target_path} ({size_mb:.2f} MB, {sum(counts.values())} total rows).")

    if truncate_postgres:
        if sum(counts.values()) == 0:
            print("Skipping Postgres truncate because 0 rows were exported.")
            return counts
        async with AsyncSessionLocal() as session:
            await session.execute(
                sa_text(
                    "TRUNCATE TABLE country_fragments, powiat_fragments, "
                    "wojewodztwo_fragments, us_state_fragments"
                )
            )
            await session.commit()
        print("Truncated PostgreSQL fragment tables.")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate static RAG text fragments from Postgres to SQLite.")
    parser.add_argument("--db-path", type=Path, default=None, help="Override output SQLite path.")
    parser.add_argument(
        "--truncate-postgres",
        action="store_true",
        help="Truncate the 4 Postgres *_fragments tables after verified export.",
    )
    args = parser.parse_args()
    asyncio.run(migrate_fragments(db_path=args.db_path, truncate_postgres=args.truncate_postgres))


if __name__ == "__main__":
    main()
