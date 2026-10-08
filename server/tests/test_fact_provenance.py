"""H10 executable source -> editor -> evaluator -> postgame wire contract.

Selected families are demonstrated temporal/semantic risks, NOT a measured
player-impact ranking. No geography values are corrected by these tests.

Frozen representation: country_fact_provenance(country_id, relation, value_json,
provenance_json), PK(country_id, relation, value_json). Canonical JSON `null`
means evidence about the COMPLETE relation/set (including an absent member),
not a fictitious list value. Other value_json keys bind evidence to one value.
Every API uses fact_provenance=[{relation, value, provenance}]. Provenance has
exactly the keys below; unknown dates are null, never the build timestamp.
Admin PATCH /countrydle/admin/country-facts/provenance edits evidence without
changing facts; POST list-values accepts metadata.provenance for a new value.
LocalAnswer and QuestionCreate carry fact_provenance internally; admin evaluation
exposes it. Public question/state JSON exposes [] until terminal, then only the
facts actually used in each answer, not the entire target's database.

Fixtures are synthetic snapshots. Poland's accession citation/date were read
from NATO's primary page; retrieval/update dates of the source KB are unknown.
The Sao Tome dispute is the existing audit record 14477, not independently
verified primary evidence: its source URL/effective dates remain explicitly
unknown. The quoted coordinate is a disputed claim, not an adopted correction.

Frontend contract: AdminFactsTab presents these same records alongside the
membership/hemisphere families, including aggregate evidence when the list is
empty. It labels null citation/source/dates explicitly unknown and displays the
convention, without deriving dates from country.updated_at. Question history
renders detailed source links/citations only from terminal fact_provenance;
active responses contain no detailed evidence to accidentally render.
"""
from contextlib import closing, nullcontext
from datetime import date, datetime, timezone
from io import BytesIO
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from countrydle import fact_editor, local_answering
from countrydle.local_planner import QuestionPlan
from scripts import build_country_facts_sqlite as builder
from scripts import populate_country_bounding_boxes_and_hemispheres as boxes
from schemas.country_facts import CountryFactsResponse, ListFactCreate
from schemas.countrydle import QuestionCreate

NATO_URL = "https://www.nato.int/en/about-us/nato-history/history-by-theme/my-country-and-nato/poland-and-nato"
UNKNOWN = {
    "status": "unknown", "citation": None, "source_url": None,
    "effective_from": None, "effective_to": None, "retrieved_at": None,
    "updated_at": None, "convention": None,
}
POLAND_NATO = {
    **UNKNOWN, "status": "cited", "source_url": NATO_URL,
    "citation": "NATO, Poland and NATO: On 12 March 1999, the Polish Foreign Minister submitted the country's Instrument of Accession to the US Secretary of State.",
    "effective_from": "1999-03-12",
    "convention": "Current membership; accession inclusive. Null effective_to means no recorded end, not proof of historical membership before accession.",
}
DISPUTED_HEMISPHERE = {
    **UNKNOWN,
    "citation": "Unverified audit claim, report.json record 14477: São Tomé and Príncipe; Ilhéu das Rolas 00°00′17″S; Southern expected true, stored false.",
    "convention": "Stored classification uses the bundled geometry and existing sovereign-territory overrides; any-territory versus representative-point remains disputed. No silent value correction.",
}


def record(relation, value, provenance):
    return {"relation": relation, "value": value, "provenance": dict(provenance)}


def rest_country(name="Poland", cca3="POL"):
    return {
        "name": {"common": name, "official": name}, "cca2": cca3[:2],
        "cca3": cca3, "region": "Europe", "subregion": "Central Europe",
        "capital": ["Warsaw"], "population": 1, "area": 1,
        "latlng": [52, 20], "landlocked": False, "borders": [],
        "car": {"side": "right"},
    }


@pytest.fixture
def facts_db(tmp_path, monkeypatch):
    path = tmp_path / "facts.sqlite"
    with closing(builder.init_db(path)) as conn:
        for name, code in (("Poland", "POL"), ("Japan", "JPN"), ("São Tomé and Príncipe", "STP")):
            builder.insert_country(conn, name, rest_country(name, code), {}, None)
        conn.execute("INSERT INTO country_hemispheres VALUES (3, 'Northern')")
        conn.execute("INSERT INTO country_hemispheres VALUES (3, 'Eastern')")
        conn.commit()
    monkeypatch.setattr(fact_editor, "DEFAULT_DB_PATH", path)
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", path)
    return path


def seed(path, country_id, relation, value, provenance):
    # Seed the agreed storage directly so existing editor/evaluator assertions
    # fail behaviorally, rather than raising missing-module/table errors.
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS country_fact_provenance (
            country_id INTEGER NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
            relation TEXT NOT NULL, value_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            PRIMARY KEY(country_id, relation, value_json))""")
        conn.execute("INSERT OR REPLACE INTO country_fact_provenance VALUES (?, ?, ?, ?)",
                     (country_id, relation, json.dumps(value, ensure_ascii=False), json.dumps(provenance, ensure_ascii=False)))


def evidence(payload, relation, value):
    records = payload.get("fact_provenance")
    assert isinstance(records, list), "Fact response must expose explicit per-fact provenance"
    matches = [item for item in records if item["relation"] == relation and item["value"] == value]
    assert len(matches) == 1, f"Expected one provenance record for {relation}={value!r}"
    assert set(matches[0]) == {"relation", "value", "provenance"}
    assert set(matches[0]["provenance"]) == set(UNKNOWN)
    return matches[0]["provenance"]


def test_builder_marks_selected_families_unknown_without_fabricating_source_dates(facts_db):
    payload = fact_editor.get_country_facts(1, db_path=facts_db)
    assert evidence(payload, "membership", None) == UNKNOWN
    assert evidence(payload, "membership", "NATO") == UNKNOWN
    assert evidence(fact_editor.get_country_facts(2, db_path=facts_db), "membership", None) == UNKNOWN
    assert evidence(fact_editor.get_country_facts(3, db_path=facts_db), "hemisphere", None) == UNKNOWN


def test_editor_and_response_schema_preserve_citation_interval_and_disputed_convention(facts_db):
    seed(facts_db, 1, "membership", "NATO", POLAND_NATO)
    seed(facts_db, 3, "hemisphere", None, DISPUTED_HEMISPHERE)
    for entity_id, relation, value, expected in (
        (1, "membership", "NATO", POLAND_NATO),
        (3, "hemisphere", None, DISPUTED_HEMISPHERE),
    ):
        raw = fact_editor.get_country_facts(entity_id, db_path=facts_db)
        assert evidence(raw, relation, value) == expected
        wire = CountryFactsResponse.model_validate(raw).model_dump(mode="json")
        assert evidence(wire, relation, value) == expected
    with sqlite3.connect(facts_db) as conn:
        assert conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id=3 ORDER BY hemisphere").fetchall() == [("Eastern",), ("Northern",)]


def test_list_create_schema_does_not_discard_provenance(facts_db):
    payload = ListFactCreate(country_id=2, relation="membership", value="Test organization", metadata={"provenance": UNKNOWN})
    fact_editor.add_list_fact(2, payload.relation, payload.value, payload.metadata, db_path=facts_db)
    assert evidence(fact_editor.get_country_facts(2, db_path=facts_db), "membership", "Test organization") == UNKNOWN


def test_unrelated_admin_edit_preserves_unchanged_fact_evidence(facts_db):
    seed(facts_db, 1, "membership", "NATO", POLAND_NATO)
    fact_editor.update_scalar_fact(1, "capital", "Test capital", db_path=facts_db)
    assert evidence(fact_editor.get_country_facts(1, db_path=facts_db), "membership", "NATO") == POLAND_NATO


def test_delete_then_readd_never_resurrects_obsolete_evidence(facts_db):
    seed(facts_db, 1, "membership", "NATO", POLAND_NATO)
    seed(facts_db, 1, "membership", None, POLAND_NATO)
    fact_editor.delete_list_fact(1, "membership", "NATO", db_path=facts_db)
    fact_editor.add_list_fact(1, "membership", "NATO", db_path=facts_db)
    payload = fact_editor.get_country_facts(1, db_path=facts_db)
    assert evidence(payload, "membership", "NATO") == UNKNOWN
    assert evidence(payload, "membership", None) == UNKNOWN
    with sqlite3.connect(facts_db) as conn:
        rows = conn.execute("SELECT provenance_json FROM country_fact_provenance WHERE country_id=1 AND relation='membership'").fetchall()
    assert all(NATO_URL not in row[0] for row in rows), "Obsolete evidence must be removed, not merely hidden in the API"


def test_legacy_upgrade_is_additive_and_keeps_country_ids_and_fact_rows(facts_db):
    with sqlite3.connect(facts_db) as conn:
        conn.execute("DROP TABLE IF EXISTS country_fact_provenance")
        before = conn.execute("SELECT * FROM countries ORDER BY id").fetchall()
        memberships = conn.execute("SELECT * FROM country_memberships ORDER BY country_id, organization").fetchall()
    with closing(builder.init_db(facts_db)) as conn:
        assert conn.execute("SELECT * FROM countries ORDER BY id").fetchall() == before, "Initialization must upgrade existing KBs, not unlink them"
        assert conn.execute("SELECT * FROM country_memberships ORDER BY country_id, organization").fetchall() == memberships
    assert evidence(fact_editor.get_country_facts(1, db_path=facts_db), "membership", "NATO") == UNKNOWN


@pytest.mark.parametrize("membership_changed", [False, True])
def test_rebuild_preserves_same_fact_evidence_but_invalidates_changed_relation(facts_db, monkeypatch, membership_changed):
    seed(facts_db, 1, "membership", "NATO", POLAND_NATO)
    seed(facts_db, 1, "membership", None, POLAND_NATO)
    if membership_changed:
        monkeypatch.setattr(builder, "NATO_MEMBERS", set(builder.NATO_MEMBERS) - {"POL"})
    with closing(builder.init_db(facts_db)) as conn:
        builder.insert_country(conn, "Poland", rest_country(), {}, None)
        conn.commit()
    payload = fact_editor.get_country_facts(1, db_path=facts_db)
    assert payload["country"]["name"] == "Poland"
    if membership_changed:
        assert evidence(payload, "membership", None) == UNKNOWN
        assert not any(item["relation"] == "membership" and item["value"] == "NATO" for item in payload["fact_provenance"])
    else:
        assert evidence(payload, "membership", "NATO") == POLAND_NATO
        assert evidence(payload, "membership", None) == POLAND_NATO


@pytest.mark.parametrize("changed", [False, True])
def test_geometry_repopulation_preserves_or_invalidates_aggregate_evidence(facts_db, monkeypatch, changed):
    seed(facts_db, 3, "hemisphere", None, DISPUTED_HEMISPHERE)
    features = []
    for code in ("POL", "JPN", "STP"):
        southern = code == "STP" and changed
        features.append({"properties": {"ISO3166-1-Alpha-3": code}, "geometry": {
            "type": "Polygon", "coordinates": [[[1, -1 if southern else 1], [2, 2], [1, 1]]],
        }})
    monkeypatch.setattr(boxes.urllib.request, "urlopen", lambda *a, **kw: BytesIO(json.dumps({"features": features}).encode()))
    boxes.populate_boxes_and_hemispheres(facts_db)
    expected = UNKNOWN if changed else DISPUTED_HEMISPHERE
    assert evidence(fact_editor.get_country_facts(3, db_path=facts_db), "hemisphere", None) == expected


def contains(relation, value):
    return {"operator": "contains", "left": {"entity": "target_country", "relation": relation}, "right": {"value": value}}


@pytest.mark.parametrize("entity_id,name,relation,value,answer,source", [
    (1, "Poland", "membership", "NATO", True, POLAND_NATO),
    (2, "Japan", "membership", "NATO", False, UNKNOWN),
    (3, "São Tomé and Príncipe", "hemisphere", "Southern", False, DISPUTED_HEMISPHERE),
])
def test_actual_evaluator_attaches_value_or_aggregate_evidence_without_changing_answer(facts_db, entity_id, name, relation, value, answer, source):
    key = value if answer else None
    seed(facts_db, entity_id, relation, key, source)
    result = local_answering.execute_local_plan(contains(relation, value), name, "Is it a member?" if relation == "membership" else "Is it in the Southern hemisphere?")
    assert result is not None and result.answer is answer
    assert evidence({"fact_provenance": getattr(result, "fact_provenance", None)}, relation, key) == source




@pytest.fixture
async def http_client(facts_db, monkeypatch):
    import countrydle
    from admin.question_tests import router as evaluation_router
    from db import get_db
    from users.utils import get_admin_user, get_current_or_guest_user

    class Session:
        no_autoflush = nullcontext()

        async def execute(self, statement):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: SimpleNamespace(id=1, name="Poland")))

        async def commit(self):
            pass

    async def log_create(*args, **kwargs):
        return SimpleNamespace(id=1)

    monkeypatch.setattr(countrydle.CountryFactChangeLogRepository, "create", log_create)
    app = FastAPI()
    app.include_router(countrydle.router)
    app.include_router(evaluation_router, prefix="/admin")
    app.dependency_overrides[get_db] = lambda: Session()
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=7, is_admin=True)
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_actual_admin_http_reads_and_edits_per_value_and_absent_relation_provenance(http_client, facts_db):
    for entity_id, relation, value, source in ((1, "membership", "NATO", POLAND_NATO), (3, "hemisphere", None, DISPUTED_HEMISPHERE)):
        response = await http_client.patch("/countrydle/admin/country-facts/provenance", json={
            "country_id": entity_id, "relation": relation, "value": value, "provenance": source,
        })
        assert response.status_code == 200, response.text
        assert evidence(response.json(), relation, value) == source
        read = await http_client.get("/countrydle/admin/country-facts", params={
            "country_name": "Poland" if entity_id == 1 else "São Tomé and Príncipe",
        })
        assert read.status_code == 200, read.text
        assert evidence(read.json(), relation, value) == source
    with sqlite3.connect(facts_db) as conn:
        assert conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id=3 ORDER BY hemisphere").fetchall() == [("Eastern",), ("Northern",)]


@pytest.mark.anyio
async def test_actual_admin_http_list_edit_round_trips_evidence_and_invalidates_old_set(http_client, facts_db):
    seed(facts_db, 2, "membership", None, POLAND_NATO)
    response = await http_client.post("/countrydle/admin/country-facts/list-values", json={
        "country_id": 2, "relation": "membership", "value": "Test organization",
        "metadata": {"provenance": UNKNOWN}, "note": "Synthetic test addition",
    })
    assert response.status_code == 200, response.text
    assert evidence(response.json(), "membership", "Test organization") == UNKNOWN
    assert evidence(response.json(), "membership", None) == UNKNOWN


@pytest.mark.anyio
async def test_actual_admin_evaluation_exposes_same_fact_provenance(http_client, facts_db, monkeypatch):
    import countrydle.utils as utilities
    seed(facts_db, 1, "membership", "NATO", POLAND_NATO)
    plan = QuestionPlan(original_question="Is it in NATO?", valid=True, supported=True,
                        improved_question="Is it in NATO?", explanation="Check membership",
                        plan=contains("membership", "NATO"), fallback_reason=None)
    monkeypatch.setattr(utilities, "analyze_question_for_local_plan", lambda *a, **kw: plan)

    async def get_country(*args, **kwargs):
        return SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland")

    monkeypatch.setattr(utilities.CountryRepository, "get", get_country)
    response = await http_client.post("/admin/question-tests", json={"mode": "countrydle", "entity_id": 1, "question": "Is it in NATO?"})
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is True
    assert evidence(response.json(), "membership", "NATO") == POLAND_NATO


@pytest.mark.anyio
@pytest.mark.parametrize("terminal", [False, True])
async def test_actual_guest_state_redacts_sources_until_terminal_then_exposes_detailed_citations(http_client, monkeypatch, terminal):
    import countrydle
    records = [record("hemisphere", None, DISPUTED_HEMISPHERE), record("membership", "NATO", POLAND_NATO)]
    question = SimpleNamespace(id=7, original_question="Is it in NATO?", question="Is it in NATO?",
                               valid=True, answer=True, explanation="Membership fact", user_id=None,
                               day_id=1, asked_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
                               context="local_kb:membership", fact_provenance=records)

    async def get_day(*args, **kwargs):
        return SimpleNamespace(id=1, country_id=1, date=date(2026, 10, 7))

    async def get_country(*args, **kwargs):
        return SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md")

    async def progress(*args, **kwargs):
        return SimpleNamespace(guesses_made=0, questions_asked=1, won=terminal), [], [question]

    monkeypatch.setattr(countrydle.CountrydleRepository, "get_today_country", get_day)
    monkeypatch.setattr(countrydle.CountryRepository, "get", get_country)
    monkeypatch.setattr(countrydle, "get_guest_progress", progress)
    response = await http_client.get("/countrydle/state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"]["is_game_over"] is terminal
    if terminal:
        assert payload["questions"][0].get("fact_provenance") == records
        assert NATO_URL in response.text
        assert "00°00′17″S" in response.text
    else:
        assert payload["questions"][0].get("fact_provenance") == []
        for private in (NATO_URL, "Poland", "São Tomé", "Ilhéu", "00°00", "1999-03-12"):
            assert private not in response.text
        assert payload["country"] is None
    end = await http_client.get("/countrydle/end/state")
    assert end.status_code == (200 if terminal else 400)
    if terminal:
        assert end.json()["questions"][0]["fact_provenance"] == records


@pytest.mark.anyio
async def test_answered_template_keeps_named_facts_for_postgame_review(facts_db):
    import countrydle.utils as utilities

    with sqlite3.connect(facts_db) as connection:
        connection.execute("DELETE FROM country_continents WHERE country_id=1")
        connection.execute("INSERT INTO country_continents VALUES (1, 'Europe')")

    result, plan = await utilities.analyze_and_answer_locally(
        "Is it in Europe?", SimpleNamespace(id=4, country_id=1), None, SimpleNamespace(),
    )
    assert plan.valid and plan.supported
    assert result.answer is True
    assert "Poland" in result.explanation
    assert "Europe" in result.explanation
