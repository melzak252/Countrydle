import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("layout", ["host", "container"])
def test_enrichment_aggregates_distinct_county_roads_in_supported_layouts(tmp_path, layout):
    app_dir = tmp_path / "server" if layout == "host" else tmp_path / "app"
    data_dir = tmp_path / "data" if layout == "host" else app_dir / "data"
    scripts_dir = app_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    script = scripts_dir / "enrich_voivodeship_facts.py"
    shutil.copy2(Path(__file__).resolve().parents[1] / "scripts" / script.name, script)

    with sqlite3.connect(data_dir / "voivodeship_facts.sqlite") as db:
        db.execute("CREATE TABLE voivodeships (id INTEGER PRIMARY KEY, name TEXT)")
        db.executemany("INSERT INTO voivodeships VALUES (?, ?)", [(1, "Mazowieckie"), (2, "Pomorskie")])
    with sqlite3.connect(data_dir / "powiat_facts.sqlite") as db:
        db.execute("CREATE TABLE powiats (id INTEGER PRIMARY KEY, voivodeship TEXT)")
        db.execute("CREATE TABLE powiat_major_roads (powiat_id INTEGER, road_name TEXT)")
        db.executemany("INSERT INTO powiats VALUES (?, ?)", [(1, "mazowieckie"), (2, "mazowieckie"), (3, "pomorskie")])
        db.executemany("INSERT INTO powiat_major_roads VALUES (?, ?)", [(1, "S7"), (2, "S7"), (3, "A1")])

    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(data_dir / "voivodeship_facts.sqlite") as db:
        assert db.execute(
            "SELECT voivodeship_id, road_name FROM voivodeship_major_roads ORDER BY voivodeship_id"
        ).fetchall() == [(1, "S7"), (2, "A1")]
