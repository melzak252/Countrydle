"""Additive SQLite provenance, with read-only legacy fallback and set invalidation."""
import json

from schemas.fact_provenance import FactProvenance

RELATIONS = {
    "membership": ("country_memberships", "organization"),
    "hemisphere": ("country_hemispheres", "hemisphere"),
}
UNKNOWN = FactProvenance().model_dump(mode="json")
SCHEMA = """CREATE TABLE IF NOT EXISTS country_fact_provenance (
    country_id INTEGER NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    relation TEXT NOT NULL, value_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
    PRIMARY KEY(country_id, relation, value_json))"""
GEOMETRY_CONVENTION = (
    "Stored classification uses bundled GeoJSON bounding geometry and the existing "
    "sovereign-territory overrides (including metropolitan France, European Netherlands "
    "and Denmark proper). Hemisphere inclusion follows coordinate signs, not a "
    "representative point. Any-territory scope remains disputed for São Tomé and Príncipe "
    "(unverified audit record 14477); no silent value correction."
)

def key(value):
    return json.dumps(value, ensure_ascii=False)


def values(conn, country_id, relation):
    table, column = RELATIONS[relation]
    return {row[0] for row in conn.execute(f"SELECT {column} FROM {table} WHERE country_id=?", (country_id,))}


def read_record(conn, country_id, relation, value):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='country_fact_provenance'").fetchone()
    row = conn.execute(
        "SELECT provenance_json FROM country_fact_provenance WHERE country_id=? AND relation=? AND value_json=?",
        (country_id, relation, key(value)),
    ).fetchone() if exists else None
    provenance = FactProvenance.model_validate(json.loads(row[0])).model_dump(mode="json") if row else dict(UNKNOWN)
    return {"relation": relation, "value": value, "provenance": provenance}


def read_all(conn, country_id):
    return [read_record(conn, country_id, relation, value)
            for relation in RELATIONS for value in [None, *sorted(values(conn, country_id, relation))]]


def put(conn, country_id, relation, value, provenance):
    validated = FactProvenance.model_validate(provenance).model_dump(mode="json")
    conn.execute("INSERT OR REPLACE INTO country_fact_provenance VALUES (?, ?, ?, ?)",
                 (country_id, relation, key(value), json.dumps(validated, ensure_ascii=False)))


def ensure_schema(conn):
    """Explicit writer upgrade only; never called by evaluator/read endpoints."""
    conn.execute(SCHEMA)
    for (country_id,) in conn.execute("SELECT id FROM countries").fetchall():
        for relation in RELATIONS:
            for value in [None, *sorted(values(conn, country_id, relation))]:
                conn.execute("INSERT OR IGNORE INTO country_fact_provenance VALUES (?, ?, ?, ?)",
                             (country_id, relation, key(value), json.dumps(UNKNOWN)))


def reconcile(conn, country_id, relation, previous):
    """Keep unchanged values; discard deleted evidence and invalidate changed sets."""
    current = values(conn, country_id, relation)
    if current != previous:
        put(conn, country_id, relation, None, UNKNOWN)
    stored = conn.execute("SELECT value_json FROM country_fact_provenance WHERE country_id=? AND relation=?",
                          (country_id, relation)).fetchall()
    for (encoded,) in stored:
        value = json.loads(encoded)
        if value is not None and value not in current:
            conn.execute("DELETE FROM country_fact_provenance WHERE country_id=? AND relation=? AND value_json=?",
                         (country_id, relation, encoded))
    for value in current - previous:
        put(conn, country_id, relation, value, UNKNOWN)
    for value in [None, *sorted(current)]:
        conn.execute("INSERT OR IGNORE INTO country_fact_provenance VALUES (?, ?, ?, ?)",
                     (country_id, relation, key(value), json.dumps(UNKNOWN)))


def import_source(conn, records):
    """Explicit source refresh: never infer evidence from a build timestamp."""
    from schemas.fact_provenance import FactProvenanceRecord
    ensure_schema(conn)
    validated = []
    for source in records:
        record = FactProvenanceRecord.model_validate({
            key: value for key, value in source.items() if key != "country_name"
        }).model_dump(mode="json")
        country = conn.execute("SELECT id FROM countries WHERE app_country_name=?", (source["country_name"],)).fetchone()
        if country is None:
            raise ValueError(f"Source country not present: {source['country_name']}")
        if record["value"] is not None and record["value"] not in values(conn, country[0], record["relation"]):
            raise ValueError("Source evidence does not match a current fact value")
        validated.append((country[0], record))
    for country_id, record in validated:
        put(conn, country_id, record["relation"], record["value"], record["provenance"])
