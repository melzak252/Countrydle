import sqlite3
from contextlib import closing

import pytest
from httpx import ASGITransport, AsyncClient

import explore
from app import app
from powiat_names import build_powiat_aliases


POWIATS = [
    "Powiat tatrzański",
    "Powiat nowotarski",
    "Powiat suski",
    "Powiat wadowicki",
    "Powiat oświęcimski",
    "Powiat sejneński",
]
COUNTRIES = ["Portugal", "Spain", "France", "Germany", "Poland", "Japan"]
US_STATES = ["California", "Nevada", "Utah", "Colorado", "Kansas", "Hawaii"]


@pytest.fixture
def border_hop_data(tmp_path, monkeypatch):
    powiat_path = tmp_path / "powiat_facts.sqlite"
    with closing(sqlite3.connect(powiat_path)) as conn, conn:
        conn.executescript(
            "CREATE TABLE powiats ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL, voivodeship TEXT NOT NULL, "
            "is_city_county INTEGER NOT NULL);"
            "CREATE TABLE powiat_name_aliases ("
            "alias TEXT NOT NULL, powiat_id INTEGER NOT NULL, PRIMARY KEY(alias, powiat_id));"
            "CREATE TABLE powiat_borders_powiats ("
            "powiat_id INTEGER NOT NULL, border_powiat_name TEXT NOT NULL, "
            "PRIMARY KEY(powiat_id, border_powiat_name));"
        )
        catalog = [
            {
                "id": index,
                "name": name,
                "voivodeship": "małopolskie" if index < 6 else "podlaskie",
                "is_city_county": 0,
            }
            for index, name in enumerate(POWIATS, start=1)
        ]
        conn.executemany(
            "INSERT INTO powiats (id, name, voivodeship, is_city_county) VALUES (?, ?, ?, ?)",
            [
                (row["id"], row["name"], row["voivodeship"], row["is_city_county"])
                for row in catalog
            ],
        )
        aliases = build_powiat_aliases(catalog)
        conn.executemany(
            "INSERT INTO powiat_name_aliases (alias, powiat_id) VALUES (?, ?)",
            [(alias, powiat_id) for alias, ids in aliases.items() for powiat_id in ids],
        )
        # One-sided source rows ensure the Border Hop graph is made bidirectional.
        conn.executemany(
            "INSERT INTO powiat_borders_powiats (powiat_id, border_powiat_name) VALUES (?, ?)",
            [(index, POWIATS[index]) for index in range(1, 5)],
        )

    country_path = tmp_path / "country_facts.sqlite"
    with closing(sqlite3.connect(country_path)) as conn, conn:
        conn.executescript(
            "CREATE TABLE countries (id INTEGER PRIMARY KEY, app_country_name TEXT NOT NULL);"
            "CREATE TABLE country_borders (country_id INTEGER NOT NULL, border_country_name TEXT NOT NULL);"
        )
        conn.executemany(
            "INSERT INTO countries (id, app_country_name) VALUES (?, ?)",
            list(enumerate(COUNTRIES, start=1)),
        )
        conn.executemany(
            "INSERT INTO country_borders (country_id, border_country_name) VALUES (?, ?)",
            [(index, COUNTRIES[index]) for index in range(1, 5)],
        )

    state_path = tmp_path / "us_state_facts.sqlite"
    with closing(sqlite3.connect(state_path)) as conn, conn:
        conn.executescript(
            "CREATE TABLE us_states (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
            "CREATE TABLE us_state_borders_states (state_id INTEGER NOT NULL, border_state_name TEXT NOT NULL);"
        )
        conn.executemany(
            "INSERT INTO us_states (id, name) VALUES (?, ?)",
            list(enumerate(US_STATES, start=1)),
        )
        conn.executemany(
            "INSERT INTO us_state_borders_states (state_id, border_state_name) VALUES (?, ?)",
            [(index, US_STATES[index]) for index in range(1, 5)],
        )

    monkeypatch.setattr(explore, "get_data_dir", lambda: tmp_path)
    for cache_name in (
        "_COUNTRY_ADJACENCY",
        "_COUNTRY_LOOKUP",
        "_COUNTRY_ISLANDS",
        "_COUNTRY_CONNECTED_PAIRS",
        "_US_STATE_ADJACENCY",
        "_US_STATE_LOOKUP",
        "_US_STATE_ISLANDS",
        "_US_STATE_CONNECTED_PAIRS",
        "_POWIAT_ADJACENCY",
        "_POWIAT_LOOKUP",
        "_POWIAT_ISLANDS",
        "_POWIAT_CONNECTED_PAIRS",
    ):
        if hasattr(explore, cache_name):
            monkeypatch.setattr(explore, cache_name, None)


@pytest.mark.anyio
async def test_powiat_mode_canonicalizes_catalog_names_and_neighbors(border_hop_data):
    assert explore.canonicalize_entity_name("  pOWIAT tatrzanski  ", "powiaty") == POWIATS[0]
    assert explore.canonicalize_entity_name("tatrzańskiego", "powiaty") == POWIATS[0]

    adjacency, _, islands = explore._get_powiat_graph()
    assert adjacency[POWIATS[0]] == {POWIATS[1]}
    assert adjacency[POWIATS[1]] == {POWIATS[0], POWIATS[2]}
    assert islands == {POWIATS[5]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/explore/border-hop/neighbors",
            params={"name": "nowotarski", "mode": "powiaty"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "name": POWIATS[1],
        "neighbors": [POWIATS[2], POWIATS[0]],
        "is_island": False,
    }


@pytest.mark.anyio
async def test_powiat_challenge_uses_shortest_path_connected_pairs_and_islands(border_hop_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        challenge = await client.get(
            "/explore/border-hop/challenge",
            params={"mode": "powiaty", "origin": POWIATS[0], "target": POWIATS[4]},
        )
        daily_first = await client.get(
            "/explore/border-hop/challenge", params={"mode": "powiaty", "seed": "fixed-powiat-seed"}
        )
        daily_second = await client.get(
            "/explore/border-hop/challenge", params={"mode": "powiaty", "seed": "fixed-powiat-seed"}
        )
        island = await client.get(
            "/explore/border-hop/challenge", params={"mode": "powiaty", "target": POWIATS[5]}
        )

    assert challenge.status_code == 200
    assert challenge.json() == {
        "mode": "powiaty",
        "start": POWIATS[0],
        "target": POWIATS[4],
        "connected": True,
        "is_island": False,
        "optimal_hops": 4,
        "optimal_path": POWIATS[:5],
        "message": None,
    }
    assert daily_first.status_code == daily_second.status_code == 200
    assert daily_first.json() == daily_second.json()
    assert daily_first.json()["mode"] == "powiaty"
    assert daily_first.json()["connected"] is True
    assert daily_first.json()["optimal_hops"] >= 2
    assert island.status_code == 200
    assert island.json()["connected"] is False
    assert island.json()["is_island"] is True
    assert island.json()["target"] == POWIATS[5]


@pytest.mark.anyio
async def test_powiat_verify_accepts_valid_path_and_rejects_non_neighbor_step(border_hop_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        valid = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "powiaty",
                "start": "tatrzański",
                "target": "oświęcimskiego",
                "path": ["tatrzański", "nowotarski", "suski", "wadowicki", "oświęcimskiego"],
            },
        )
        invalid = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "powiaty",
                "start": POWIATS[0],
                "target": POWIATS[4],
                "path": [POWIATS[0], POWIATS[2], POWIATS[3], POWIATS[4]],
            },
        )

    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["hops"] == valid.json()["optimal_hops"] == 4
    assert valid.json()["is_optimal"] is True
    assert valid.json()["rank"] == "gold"
    assert valid.json()["optimal_path"] == POWIATS[:5]
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert invalid.json()["error_step"] == [POWIATS[0], POWIATS[2]]


@pytest.mark.anyio
async def test_country_and_us_state_border_hop_contracts_remain_unchanged(border_hop_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        country_challenge = await client.get(
            "/explore/border-hop/challenge",
            params={"mode": "countrydle", "origin": "Portugal", "target": "Poland"},
        )
        country_neighbors = await client.get(
            "/explore/border-hop/neighbors", params={"mode": "countries", "name": "Portugal"}
        )
        country_verify = await client.post(
            "/explore/border-hop/verify",
            json={"mode": "countries", "start": "Portugal", "target": "Poland", "path": COUNTRIES[:5]},
        )
        state_challenge = await client.get(
            "/explore/border-hop/challenge",
            params={"mode": "us_statedle", "origin": "California", "target": "Colorado"},
        )
        state_neighbors = await client.get(
            "/explore/border-hop/neighbors", params={"mode": "us_states", "name": "Utah"}
        )
        state_verify = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "us_states",
                "start": "California",
                "target": "Colorado",
                "path": US_STATES[:4],
            },
        )

    assert country_challenge.status_code == 200
    assert country_challenge.json()["mode"] == "countries"
    assert country_challenge.json()["optimal_path"] == COUNTRIES[:5]
    assert country_neighbors.status_code == 200
    assert country_neighbors.json()["neighbors"] == ["Spain"]
    assert country_verify.status_code == 200
    assert country_verify.json()["valid"] is True
    assert country_verify.json()["rank"] == "gold"

    assert state_challenge.status_code == 200
    assert state_challenge.json()["mode"] == "us_states"
    assert state_challenge.json()["optimal_path"] == US_STATES[:4]
    assert state_neighbors.status_code == 200
    assert state_neighbors.json()["neighbors"] == ["Colorado", "Nevada"]
    assert state_verify.status_code == 200
    assert state_verify.json()["valid"] is True
    assert state_verify.json()["rank"] == "gold"
