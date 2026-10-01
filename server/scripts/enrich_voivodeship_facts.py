"""Enrich Wojewodztwodle local facts with major roads (motorways and expressways)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
VOIVODESHIP_DB = ROOT_DIR / "data" / "voivodeship_facts.sqlite"
POWIAT_DB = ROOT_DIR / "data" / "powiat_facts.sqlite"


def enrich_voivodeships():
    print(f"Connecting to {VOIVODESHIP_DB}...")
    conn_v = sqlite3.connect(VOIVODESHIP_DB)
    conn_v.row_factory = sqlite3.Row

    print(f"Reading roads from {POWIAT_DB}...")
    conn_p = sqlite3.connect(POWIAT_DB)
    conn_p.row_factory = sqlite3.Row

    # Aggregate roads by voivodeship
    rows = conn_p.execute("""
        SELECT DISTINCT p.voivodeship, r.road_name
        FROM powiat_major_roads r
        JOIN powiats p ON p.id = r.powiat_id
        ORDER BY r.road_name, p.voivodeship
    """).fetchall()
    conn_p.close()

    voiv_rows = conn_v.execute("SELECT id, name FROM voivodeships").fetchall()
    voiv_id_map = {v["name"].lower(): v["id"] for v in voiv_rows}

    with conn_v:
        conn_v.execute("""
            CREATE TABLE IF NOT EXISTS voivodeship_major_roads (
                voivodeship_id INTEGER NOT NULL,
                road_name TEXT NOT NULL,
                PRIMARY KEY (voivodeship_id, road_name),
                FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
            )
        """)
        conn_v.execute("CREATE INDEX IF NOT EXISTS idx_voivodeship_roads ON voivodeship_major_roads(road_name)")
        conn_v.execute("DELETE FROM voivodeship_major_roads")

        inserts = []
        for r in rows:
            woj = r["voivodeship"].lower()
            vid = voiv_id_map.get(woj)
            if vid is None:
                print(f"  WARNING: Could not find voivodeship id for '{woj}'")
                continue
            inserts.append((vid, r["road_name"]))

        conn_v.executemany("INSERT OR IGNORE INTO voivodeship_major_roads (voivodeship_id, road_name) VALUES (?, ?)", inserts)
        print(f"  -> Inserted {len(inserts)} motorway and expressway records into voivodeship_major_roads.")

    conn_v.close()
    print("Voivodeship enrichment complete!")


if __name__ == "__main__":
    enrich_voivodeships()
