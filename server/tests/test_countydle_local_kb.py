import json
import sqlite3
import sys
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from countydle.utils import LOCAL_CONFIG
from local_kb_question import QuestionPlan, execute_plan

ENTITIES_JSON = SERVER_DIR / "regional_symbols" / "data" / "england_counties" / "entities.json"
SQLITE_PATH = SERVER_DIR / "data" / "english_county_facts.sqlite"


def _make_plan(original_question: str, ast: dict) -> QuestionPlan:
    return QuestionPlan(
        original_question=original_question,
        valid=True,
        supported=True,
        improved_question=original_question,
        explanation="test",
        plan=ast,
    )


def test_all_48_ceremonial_counties_exist_and_match_entities_json():
    assert SQLITE_PATH.is_file(), f"Missing {SQLITE_PATH}"
    entities = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))["entities"]
    assert len(entities) == 48

    with sqlite3.connect(SQLITE_PATH) as conn:
        rows = conn.execute(
            "SELECT id, name, county_town, region, is_coastal, is_metropolitan, population, area_km2, latitude, longitude "
            "FROM english_counties ORDER BY id"
        ).fetchall()

    assert len(rows) == 48
    db_by_id = {row[0]: row for row in rows}
    for entity in entities:
        cid = entity["id"]
        assert cid in db_by_id
        row = db_by_id[cid]
        assert row[1] == entity["name"]
        assert row[2]  # county_town
        assert row[3]  # region
        assert row[6] > 0  # population
        assert row[7] > 0  # area_km2
        assert abs(row[8] - entity["latitude"]) < 1e-6
        assert abs(row[9] - entity["longitude"]) < 1e-6


def test_county_borders_are_strictly_symmetric_and_valid():
    with sqlite3.connect(SQLITE_PATH) as conn:
        id_to_name = dict(conn.execute("SELECT id, name FROM english_counties").fetchall())
        edges = conn.execute(
            "SELECT county_id, border_county_name FROM english_county_borders_counties"
        ).fetchall()

    adjacency: dict[str, set[str]] = {name: set() for name in id_to_name.values()}
    for cid, neighbor in edges:
        county_name = id_to_name[cid]
        assert neighbor in adjacency, f"Unknown neighbor {neighbor} for {county_name}"
        assert neighbor != county_name, f"Self-border stored for {county_name}"
        adjacency[county_name].add(neighbor)

    for county_name, neighbors in adjacency.items():
        for neighbor in neighbors:
            assert county_name in adjacency[neighbor], (
                f"Asymmetric border: {county_name} -> {neighbor} missing reverse edge"
            )

    # Isle of Wight is an island county with 0 land borders
    assert adjacency["Isle of Wight"] == set()
    # Cornwall borders only Devon
    assert adjacency["Cornwall"] == {"Devon"}
    # City of London is enclaved inside Greater London
    assert adjacency["City of London"] == {"Greater London"}


@pytest.mark.parametrize(
    ("target_county", "question", "ast", "expected"),
    [
        (
            "Cornwall",
            "Is it a coastal county?",
            {
                "operator": "equals",
                "left": {"entity": "target_county", "relation": "is_coastal"},
                "right": {"value": 1},
            },
            True,
        ),
        (
            "Oxfordshire",
            "Czy to hrabstwo ma dostęp do morza?",
            {
                "operator": "equals",
                "left": {"entity": "target_county", "relation": "is_coastal"},
                "right": {"value": 1},
            },
            False,
        ),
        (
            "Northumberland",
            "Does it border Scotland?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "borders_country"},
                "right": {"value": "Scotland"},
            },
            True,
        ),
        (
            "Herefordshire",
            "Czy graniczy z Walią?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "borders_country"},
                "right": {"value": "Walia"},
            },
            True,
        ),
        (
            "Cornwall",
            "Does it border Devon?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "borders_county"},
                "right": {"value": "Devon"},
            },
            True,
        ),
        (
            "Northumberland",
            "Does it border County Durham?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "borders_county"},
                "right": {"value": "County Durham"},
            },
            True,
        ),
        (
            "Norfolk",
            "Is its county town Norwich?",
            {
                "operator": "equals",
                "left": {"entity": "target_county", "relation": "county_town"},
                "right": {"value": "Norwich"},
            },
            True,
        ),
        (
            "West Yorkshire",
            "Is it in Yorkshire?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "regional_labels"},
                "right": {"value": "Yorkshire"},
            },
            True,
        ),
        (
            "Kent",
            "Czy należy do Home Counties?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "regional_labels"},
                "right": {"value": "Home Counties"},
            },
            True,
        ),
        (
            "Greater Manchester",
            "Is it a metropolitan county?",
            {
                "operator": "equals",
                "left": {"entity": "target_county", "relation": "is_metropolitan"},
                "right": {"value": 1},
            },
            True,
        ),
        (
            "Cumbria",
            "Is it north of Oxfordshire?",
            {
                "operator": "north_of",
                "left": {"entity": "target_county", "relation": "latitude"},
                "right": {"entity": "Oxfordshire", "relation": "latitude"},
            },
            True,
        ),
        (
            "Norfolk",
            "Does it have access to the North Sea?",
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "water_access"},
                "right": {"value": "North Sea"},
            },
            True,
        ),
    ],
)
def test_countydle_local_kb_questions_en_and_pl(target_county, question, ast, expected):
    plan = _make_plan(question, ast)
    result = execute_plan(LOCAL_CONFIG, target_county, plan)
    assert result is not None
    assert result.answer is expected
    assert result.explanation
