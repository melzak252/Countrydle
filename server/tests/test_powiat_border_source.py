import json
import sqlite3
from contextlib import closing
from dataclasses import replace

import pytest
from shapely.geometry import Polygon

from local_kb_question import QuestionPlan, execute_plan
from powiatdle.utils import LOCAL_CONFIG
from scripts.build_powiat_borders import derive_borders, load_boundaries
from scripts.build_powiat_facts_sqlite import init_db, refresh_borders


def test_shared_line_counts_but_point_contact_does_not():
    boundaries = {
        "0001": Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
        "0002": Polygon([(2, 0), (4, 0), (4, 2), (2, 2)]),
        "0003": Polygon([(4, 2), (6, 2), (6, 4), (4, 4)]),
    }
    assert derive_borders(boundaries) == [["0001", "0002"]]


def test_gml_preserves_enclave_and_detached_polygon_with_inherited_crs(tmp_path):
    source = tmp_path / "counties.gml"
    source.write_text(
        '''<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
            xmlns:gml="http://www.opengis.net/gml/3.2"
            xmlns:ms="http://mapserver.gis.umn.edu/mapserver" numberReturned="1">
          <wfs:member><ms:A02_Granice_powiatow>
            <ms:JPT_KOD_JE>0001</ms:JPT_KOD_JE><ms:JPT_SJR_KO>POW</ms:JPT_SJR_KO>
            <ms:JPT_NAZWA_>powiat testowy</ms:JPT_NAZWA_>
            <ms:msGeometry><gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::2180">
              <gml:surfaceMember><gml:Polygon>
                <gml:exterior><gml:LinearRing><gml:posList srsDimension="2">
                  0 0 4 0 4 4 0 4 0 0
                </gml:posList></gml:LinearRing></gml:exterior>
                <gml:interior><gml:LinearRing><gml:posList srsDimension="2">
                  1 1 2 1 2 2 1 2 1 1
                </gml:posList></gml:LinearRing></gml:interior>
              </gml:Polygon></gml:surfaceMember>
              <gml:surfaceMember><gml:Polygon>
                <gml:exterior><gml:LinearRing><gml:posList srsDimension="2">
                  5 0 6 0 6 1 5 1 5 0
                </gml:posList></gml:LinearRing></gml:exterior>
              </gml:Polygon></gml:surfaceMember>
            </gml:MultiSurface></ms:msGeometry>
          </ms:A02_Granice_powiatow></wfs:member>
        </wfs:FeatureCollection>''',
        encoding="utf-8",
    )
    _, boundaries = load_boundaries(source)
    boundaries["0002"] = Polygon([(1, 1), (2, 1), (2, 2), (1, 2)])
    boundaries["0003"] = Polygon([(6, 0), (7, 0), (7, 1), (6, 1)])
    assert derive_borders(boundaries) == [["0001", "0002"], ["0001", "0003"]]


@pytest.fixture
def existing_facts(tmp_path):
    path = tmp_path / "powiat_facts.sqlite"
    with closing(init_db(path)) as conn, conn:
        conn.executemany(
            "INSERT INTO powiats (id, name, voivodeship, is_city_county, terc, population, md_file) "
            "VALUES (?, ?, ?, ?, ?, ?, 'manual-edits.md')",
            [
                (19, "Powiat testowy", "śląskie", 0, "2401", 123456),
                (7, "Miasto", "śląskie", 1, "2461000", 654321),
                (31, "Powiat próbny", "małopolskie", 0, "1201", 111111),
            ],
        )
        conn.execute("INSERT INTO powiat_major_rivers VALUES (19, 'Ręcznie poprawiona rzeka')")
        conn.execute("INSERT INTO powiat_borders_powiats VALUES (19, 'Nieaktualny sąsiad')")
    snapshot_path = tmp_path / "borders.json"
    snapshot_path.write_text(json.dumps({
        "schema_version": 1,
        "counties": ["1201", "2401", "2461"],
        "borders": [["1201", "2461"], ["2401", "2461"]],
    }), encoding="utf-8")
    return path, snapshot_path


def _answer(config, target, relation, value):
    plan = QuestionPlan(
        original_question="Czy graniczy?", valid=True, supported=True,
        improved_question=None, explanation=None,
        plan={
            "operator": "contains_exact",
            "left": {"entity": "target_powiat", "relation": relation},
            "right": {"value": value},
        },
    )
    answer = execute_plan(config, target, plan)
    assert answer is not None
    return answer.answer


def test_refresh_joins_teryt_preserves_edits_and_installs_complete_bidirectional_borders(existing_facts):
    path, snapshot = existing_facts
    refresh_borders(path, snapshot)
    config = replace(LOCAL_CONFIG, db_path=path)
    assert _answer(config, "Powiat testowy", "borders_powiat", "Miasto") is True
    assert _answer(config, "Miasto", "borders_powiat", "powiatem testowym") is True
    assert _answer(config, "Powiat testowy", "borders_powiat", "powiatem próbnym") is False
    assert _answer(config, "Powiat testowy", "borders_voivodeship", "małopolskie") is False
    assert _answer(config, "Miasto", "borders_voivodeship", "małopolskie") is True
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT population FROM powiats WHERE id = 19").fetchone()[0] == 123456
        assert conn.execute("SELECT river_name FROM powiat_major_rivers WHERE powiat_id = 19").fetchone()[0] == "Ręcznie poprawiona rzeka"
        assert conn.execute("SELECT COUNT(*) FROM powiat_borders_powiats WHERE border_powiat_name = 'Nieaktualny sąsiad'").fetchone()[0] == 0


def test_snapshot_catalog_mismatch_leaves_existing_database_unchanged(existing_facts):
    path, snapshot_path = existing_facts
    with closing(sqlite3.connect(path)) as conn:
        before = list(conn.iterdump())
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["counties"].append("9999")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError):
        refresh_borders(path, snapshot_path)
    with closing(sqlite3.connect(path)) as conn:
        assert list(conn.iterdump()) == before
