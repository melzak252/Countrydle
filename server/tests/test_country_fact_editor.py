import shutil
import sqlite3

import pytest

from countrydle import local_answering
from countrydle.fact_editor import (
    FACT_MODE_CONFIGS,
    add_list_fact,
    add_local_list_fact,
    delete_list_fact,
    get_country_facts,
    get_local_facts,
    update_local_scalar_fact,
    update_scalar_fact,
)
from countrydle.local_answering import execute_local_plan


def contains_plan(relation: str, value: str) -> dict:
    return {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": relation},
        "right": {"value": value},
    }


@pytest.fixture
def editable_country_db(tmp_path):
    source = pytest.importorskip("pathlib").Path(__file__).resolve().parents[2] / "data" / "country_facts.sqlite"
    if not source.exists():
        pytest.skip("Countrydle local SQLite KB is missing")
    target = tmp_path / "country_facts.sqlite"
    shutil.copy(source, target)
    return target


def country_id(db_path, name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT id FROM countries WHERE app_country_name=?", (name,)).fetchone()
    assert row is not None
    return row[0]


def test_country_fact_editor_updates_scalar_fact(editable_country_db):
    poland_id = country_id(editable_country_db, "Poland")

    old_value, new_value, operation = update_scalar_fact(
        poland_id,
        "capital",
        "Krakow",
        db_path=editable_country_db,
    )

    facts = get_country_facts(poland_id, db_path=editable_country_db)
    capital = next(fact for fact in facts["scalar_facts"] if fact["relation"] == "capital")
    assert operation == "update"
    assert old_value == "Warsaw"
    assert new_value == "Krakow"
    assert capital["value"] == "Krakow"


def test_country_fact_editor_adds_and_deletes_list_value_used_by_answerer(editable_country_db, monkeypatch):
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", editable_country_db)
    poland_id = country_id(editable_country_db, "Poland")

    before = execute_local_plan(
        contains_plan("water_access", "Test Sea"),
        "Poland",
        "Does Poland have access to Test Sea?",
        "Test plan",
    )
    assert before is not None
    assert before.answer is False

    add_list_fact(poland_id, "water_access", "Test Sea", db_path=editable_country_db)
    after_add = execute_local_plan(
        contains_plan("water_access", "Test Sea"),
        "Poland",
        "Does Poland have access to Test Sea?",
        "Test plan",
    )
    assert after_add is not None
    assert after_add.answer is True

    delete_list_fact(poland_id, "water_access", "Test Sea", db_path=editable_country_db)
    after_delete = execute_local_plan(
        contains_plan("water_access", "Test Sea"),
        "Poland",
        "Does Poland have access to Test Sea?",
        "Test plan",
    )
    assert after_delete is not None
    assert after_delete.answer is False


def test_generic_fact_editor_updates_non_country_mode(tmp_path, monkeypatch):
    source = pytest.importorskip("pathlib").Path(__file__).resolve().parents[2] / "data" / "us_state_facts.sqlite"
    if not source.exists():
        pytest.skip("US state local SQLite KB is missing")
    target = tmp_path / "us_state_facts.sqlite"
    shutil.copy(source, target)
    config = FACT_MODE_CONFIGS["us_statedle"]
    patched_config = type(config)(
        game_type=config.game_type,
        db_path=target,
        entity_table=config.entity_table,
        name_column=config.name_column,
        fk_column=config.fk_column,
        scalar_relations=config.scalar_relations,
        list_relations=config.list_relations,
    )
    monkeypatch.setitem(FACT_MODE_CONFIGS, "us_statedle", patched_config)

    with sqlite3.connect(target) as conn:
        state_id = conn.execute("SELECT id FROM us_states WHERE name=?", ("California",)).fetchone()[0]

    old_value, new_value, operation = update_local_scalar_fact("us_statedle", state_id, "nickname", "Golden Test State")
    assert operation == "update"
    assert old_value
    assert new_value == "Golden Test State"

    add_local_list_fact("us_statedle", state_id, "regional_labels", "Test Region")
    facts = get_local_facts("us_statedle", entity_name="California")
    labels = next(fact for fact in facts["list_facts"] if fact["relation"] == "regional_labels")
    nickname = next(fact for fact in facts["scalar_facts"] if fact["relation"] == "nickname")
    assert facts["entity"]["name"] == "California"
    assert nickname["value"] == "Golden Test State"
    assert any(item["value"] == "Test Region" for item in labels["values"])
