import sqlite3

import pytest

from powiat_names import build_powiat_aliases, resolve_powiat_name


COUNTIES = [
    {"id": 1, "name": "Powiat częstochowski", "voivodeship": "śląskie", "is_city_county": 0},
    {"id": 2, "name": "Częstochowa", "voivodeship": "śląskie", "is_city_county": 1},
    {"id": 3, "name": "Powiat bielski (śląskie)", "voivodeship": "śląskie", "is_city_county": 0},
    {"id": 4, "name": "Powiat bielski (podlaskie)", "voivodeship": "podlaskie", "is_city_county": 0},
    {"id": 5, "name": "Powiat łódzki wschodni", "voivodeship": "łódzkie", "is_city_county": 0},
    {"id": 6, "name": "Powiat bieruńsko-lędziński", "voivodeship": "śląskie", "is_city_county": 0},
]


@pytest.fixture
def conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE powiats (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE powiat_name_aliases ("
        "alias TEXT NOT NULL, powiat_id INTEGER NOT NULL, PRIMARY KEY(alias, powiat_id))"
    )
    conn.executemany(
        "INSERT INTO powiats (id, name) VALUES (?, ?)",
        [(row["id"], row["name"]) for row in COUNTIES],
    )
    aliases = build_powiat_aliases(COUNTIES)
    conn.executemany(
        "INSERT INTO powiat_name_aliases (alias, powiat_id) VALUES (?, ?)",
        [(alias, powiat_id) for alias, ids in aliases.items() for powiat_id in ids],
    )
    try:
        yield conn
    finally:
        conn.close()


def test_catalog_adjective_forms_resolve_to_county_not_city(conn):
    assert resolve_powiat_name(conn, "częstochowskim") == "Powiat częstochowski"
    assert resolve_powiat_name(conn, "częstochowskiego") == "Powiat częstochowski"
    assert resolve_powiat_name(conn, "powiecie częstochowskim") == "Powiat częstochowski"
    assert resolve_powiat_name(conn, "Częstochowa") == "Częstochowa"
    assert resolve_powiat_name(conn, "Częstochowie") == "Częstochowa"


def test_ambiguous_unqualified_alias_stays_unknown_but_qualifiers_resolve(conn):
    assert resolve_powiat_name(conn, "bielski") is None
    assert resolve_powiat_name(conn, "bielski śląskie") == "Powiat bielski (śląskie)"
    assert resolve_powiat_name(conn, "bielski podlaskie") == "Powiat bielski (podlaskie)"


def test_compound_adjectives_and_county_prefixes_resolve(conn):
    assert resolve_powiat_name(conn, "łódzkim wschodnim") == "Powiat łódzki wschodni"
    assert resolve_powiat_name(conn, "bieruńsko-lędzińskim") == "Powiat bieruńsko-lędziński"
    assert resolve_powiat_name(conn, "powiatem częstochowski") == "Powiat częstochowski"


def test_non_strings_unknown_and_unsupported_forms_stay_unknown(conn):
    assert resolve_powiat_name(conn, None) is None
    assert resolve_powiat_name(conn, 1) is None
    assert resolve_powiat_name(conn, "częstochowską") is None
    assert resolve_powiat_name(conn, "wschodni") is None
