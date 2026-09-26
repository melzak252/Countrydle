from contextlib import closing
import sqlite3

import pytest

from scripts.build_country_facts_sqlite import init_db, insert_country
from scripts import populate_country_flags_and_history


@pytest.fixture
def country_facts_db(tmp_path):
    with closing(init_db(tmp_path / "country_facts.sqlite")) as connection:
        yield connection


def rest_country(cca3, borders=(), *, landlocked=False):
    return {
        "name": {"common": cca3, "official": cca3},
        "cca2": cca3[:2],
        "cca3": cca3,
        "region": "Test region",
        "subregion": "Test subregion",
        "capital": ["Capital"],
        "population": 1,
        "area": 1,
        "latlng": [0, 0],
        "landlocked": landlocked,
        "borders": list(borders),
        "car": {"side": "right"},
    }


@pytest.mark.parametrize(
    ("name", "cca3", "borders"),
    [
        ("Brunei", "BRN", ("MYS",)),
        ("Dominican Republic", "DOM", ("HTI",)),
        ("Haiti", "HTI", ("DOM",)),
        ("Indonesia", "IDN", ("MYS", "PNG", "TLS")),
        ("Ireland", "IRL", ("GBR",)),
        ("Papua New Guinea", "PNG", ("IDN",)),
        ("East Timor", "TLS", ("IDN",)),
        ("United Kingdom", "GBR", ("IRL",)),
    ],
)
def test_builder_keeps_shared_island_border_countries_island_countries(
    country_facts_db, name, cca3, borders
):
    country = rest_country(cca3, borders)
    country["name"]["common"] = name
    country["name"]["official"] = name
    insert_country(country_facts_db, name, country, {}, None)

    row = country_facts_db.execute(
        "SELECT is_island FROM countries WHERE app_country_name = ?", (name,)
    ).fetchone()
    assert row == (1,)


@pytest.mark.parametrize(
    ("name", "cca3", "borders", "landlocked"),
    [
        ("Austria", "AUT", ("CZE", "DEU"), True),
        ("Portugal", "PRT", ("ESP",), False),
        ("Australia", "AUS", (), False),
    ],
)
def test_builder_does_not_classify_landlocked_or_continental_countries_as_islands(
    country_facts_db, name, cca3, borders, landlocked
):
    country = rest_country(cca3, borders, landlocked=landlocked)
    country["name"]["common"] = name
    country["name"]["official"] = name
    insert_country(country_facts_db, name, country, {}, None)

    row = country_facts_db.execute(
        "SELECT is_island FROM countries WHERE app_country_name = ?", (name,)
    ).fetchone()
    assert row == (0,)


@pytest.mark.parametrize(
    ("name", "cca3"),
    [("Belgium", "BEL"), ("Luxembourg", "LUX"), ("Netherlands", "NLD")],
)
def test_builder_persists_active_benelux_membership(country_facts_db, name, cca3):
    country = rest_country(cca3)
    country["name"]["common"] = name
    country["name"]["official"] = name
    insert_country(country_facts_db, name, country, {}, None)

    memberships = country_facts_db.execute(
        "SELECT organization FROM country_memberships WHERE country_id = "
        "(SELECT id FROM countries WHERE app_country_name = ?)",
        (name,),
    ).fetchall()
    assert ("Benelux",) in memberships


def test_active_benelux_membership_is_not_written_as_a_historical_union(tmp_path, monkeypatch):
    db_path = tmp_path / "country_facts.sqlite"
    with closing(init_db(db_path)) as connection:
        for name, cca3 in (("Belgium", "BEL"), ("Luxembourg", "LUX"), ("Netherlands", "NLD")):
            country = rest_country(cca3)
            country["name"]["common"] = name
            country["name"]["official"] = name
            insert_country(connection, name, country, {}, None)
        connection.commit()

    monkeypatch.setattr(populate_country_flags_and_history, "DB_PATH", db_path)
    populate_country_flags_and_history.main()

    with sqlite3.connect(db_path) as connection:
        membership = {
            row[0]
            for row in connection.execute(
                "SELECT c.app_country_name FROM country_memberships m "
                "JOIN countries c ON c.id = m.country_id WHERE m.organization = 'Benelux'"
            )
        }
        historical_union = {
            row[0]
            for row in connection.execute(
                "SELECT c.app_country_name FROM country_historical_unions h "
                "JOIN countries c ON c.id = h.country_id WHERE h.union_name = 'Benelux'"
            )
        }

    assert membership == {"Belgium", "Luxembourg", "Netherlands"}
    assert historical_union == set()
