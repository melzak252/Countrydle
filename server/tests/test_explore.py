import pytest
from httpx import AsyncClient, ASGITransport
from app import app


@pytest.mark.anyio
async def test_explore_modes_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/explore/modes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        mode_ids = {m["id"] for m in data}
        assert "countrydle" in mode_ids
        assert "us_statedle" in mode_ids
        assert "wojewodztwodle" in mode_ids
        assert "powiatdle" in mode_ids


@pytest.mark.anyio
async def test_explore_countries_list_and_detail():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # List
        response = await client.get("/explore/countries?limit=10")
        assert response.status_code == 200
        countries = response.json()
        assert len(countries) > 0
        assert "app_country_name" in countries[0]
        assert "capital" in countries[0]

        # Detail by cca3
        response = await client.get("/explore/countries/POL")
        assert response.status_code == 200
        poland = response.json()
        assert poland["app_country_name"] == "Poland"
        assert poland["capital"] == "Warsaw"
        assert "borders" in poland
        assert "languages" in poland
        assert "continents" in poland


@pytest.mark.anyio
async def test_explore_us_states_list_and_detail():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # List
        response = await client.get("/explore/us-states")
        assert response.status_code == 200
        states = response.json()
        assert len(states) == 50
        assert any(s["name"] == "California" for s in states)

        # Detail
        response = await client.get("/explore/us-states/California")
        assert response.status_code == 200
        california = response.json()
        assert california["name"] == "California"
        assert "Sacramento" in california.get("nickname", "") or california.get("admission_order") == 31
        assert "neighboring_states" in california


@pytest.mark.anyio
async def test_explore_voivodeships_list_and_detail():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # List
        response = await client.get("/explore/voivodeships")
        assert response.status_code == 200
        voivs = response.json()
        assert len(voivs) == 16

        # Detail
        response = await client.get("/explore/voivodeships/Małopolskie")
        assert response.status_code == 200
        malopolska = response.json()
        assert malopolska["name"] == "Małopolskie"
        assert malopolska["seat"] == "Kraków"
        assert "neighboring_voivodeships" in malopolska


@pytest.mark.anyio
async def test_sitemap_includes_explore_routes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "https://countrydle.online/explore" in content
        assert "https://countrydle.online/explore/modes/countrydle" in content
        assert "https://countrydle.online/explore/modes/us-states" in content
        assert "https://countrydle.online/explore/modes/wojewodztwa" in content
        assert "https://countrydle.online/explore/modes/powiaty" in content


@pytest.mark.anyio
async def test_border_hop_challenge_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Target with specified origin: Portugal -> Poland
        res = await client.get("/explore/border-hop/challenge?mode=countries&origin=Portugal&target=Poland")
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is True
        assert data["is_island"] is False
        assert data["start"] == "Portugal"
        assert data["target"] == "Poland"
        assert data["optimal_hops"] == 4
        assert data["optimal_path"] == ["Portugal", "Spain", "France", "Germany", "Poland"]

        # 2. Target without origin selects candidate 3-5 hops away
        res_cand = await client.get("/explore/border-hop/challenge?mode=countries&target=Poland&seed=test123")
        assert res_cand.status_code == 200
        data_cand = res_cand.json()
        assert data_cand["connected"] is True
        assert data_cand["is_island"] is False
        assert data_cand["target"] == "Poland"
        assert 3 <= data_cand["optimal_hops"] <= 5
        assert data_cand["optimal_path"][-1] == "Poland"
        assert data_cand["optimal_path"][0] == data_cand["start"]

        # 3. Island nation with 0 land borders (Japan)
        res_island = await client.get("/explore/border-hop/challenge?mode=countries&target=Japan")
        assert res_island.status_code == 200
        data_island = res_island.json()
        assert data_island["connected"] is False
        assert data_island["is_island"] is True
        assert data_island["optimal_hops"] is None

        # 4. Daily challenge (no target specified)
        res_daily = await client.get("/explore/border-hop/challenge?mode=countries&seed=2026-10-04")
        assert res_daily.status_code == 200
        data_daily = res_daily.json()
        assert data_daily["connected"] is True
        assert data_daily["is_island"] is False
        assert 3 <= data_daily["optimal_hops"] <= 5
        assert len(data_daily["optimal_path"]) == data_daily["optimal_hops"] + 1

        # 5. US States mode challenge
        res_us = await client.get("/explore/border-hop/challenge?mode=us_states&origin=California&target=New York")
        assert res_us.status_code == 200
        data_us = res_us.json()
        assert data_us["connected"] is True
        assert data_us["is_island"] is False
        assert data_us["start"] == "California"
        assert data_us["target"] == "New York"
        assert data_us["optimal_hops"] >= 6

        # 6. US States island/exclave state (Hawaii)
        res_hi = await client.get("/explore/border-hop/challenge?mode=us_states&target=Hawaii")
        assert res_hi.status_code == 200
        assert res_hi.json()["is_island"] is True
        assert res_hi.json()["connected"] is False


@pytest.mark.anyio
async def test_border_hop_neighbors_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Poland neighbors
        res = await client.get("/explore/border-hop/neighbors?name=Poland&mode=countries")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Poland"
        assert "Germany" in data["neighbors"]
        assert "Czech Republic" in data["neighbors"]
        assert "Slovakia" in data["neighbors"]
        assert data["is_island"] is False

        # Island country (Madagascar)
        res_m = await client.get("/explore/border-hop/neighbors?name=Madagascar&mode=countries")
        assert res_m.status_code == 200
        assert res_m.json()["is_island"] is True
        assert res_m.json()["neighbors"] == []

        # Unknown country -> 404
        res_404 = await client.get("/explore/border-hop/neighbors?name=Atlantis&mode=countries")
        assert res_404.status_code == 404


@pytest.mark.anyio
async def test_border_hop_verify_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Optimal path: Gold rank
        res_gold = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "countries",
                "start": "Portugal",
                "target": "Poland",
                "path": ["Portugal", "Spain", "France", "Germany", "Poland"],
            },
        )
        assert res_gold.status_code == 200
        data_gold = res_gold.json()
        assert data_gold["valid"] is True
        assert data_gold["hops"] == 4
        assert data_gold["optimal_hops"] == 4
        assert data_gold["is_optimal"] is True
        assert data_gold["rank"] == "gold"

        # 2. Sub-optimal path: Silver rank (+1 hop via Belgium)
        res_silver = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "countries",
                "start": "Portugal",
                "target": "Poland",
                "path": ["Portugal", "Spain", "France", "Belgium", "Germany", "Poland"],
            },
        )
        assert res_silver.status_code == 200
        data_silver = res_silver.json()
        assert data_silver["valid"] is True
        assert data_silver["hops"] == 5
        assert data_silver["optimal_hops"] == 4
        assert data_silver["is_optimal"] is False
        assert data_silver["rank"] == "silver"

        # 3. Invalid consecutive step (Italy does not border Poland)
        res_invalid = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "countries",
                "start": "Portugal",
                "target": "Poland",
                "path": ["Portugal", "Spain", "France", "Italy", "Poland"],
            },
        )
        assert res_invalid.status_code == 200
        data_invalid = res_invalid.json()
        assert data_invalid["valid"] is False
        assert data_invalid["error_step"] == ["Italy", "Poland"]

        # 4. Wrong start country
        res_wrong_start = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "countries",
                "start": "Portugal",
                "target": "Poland",
                "path": ["Spain", "France", "Germany", "Poland"],
            },
        )
        assert res_wrong_start.status_code == 200
        assert res_wrong_start.json()["valid"] is False


@pytest.mark.anyio
async def test_explore_powiat_detail_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid powiat
        res = await client.get("/explore/powiats/Biała Podlaska")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Biała Podlaska"
        assert data["voivodeship"] == "lubelskie"
        assert data["seat"] == "Biała Podlaska"
        assert "registration_plates" in data
        assert "LB" in data["registration_plates"]
        assert "neighboring_powiats" in data

        # Another powiat (Kraków)
        res_kr = await client.get("/explore/powiats/Kraków")
        assert res_kr.status_code == 200
        data_kr = res_kr.json()
        assert data_kr["name"] == "Kraków"
        assert "KR" in data_kr["registration_plates"]
        assert "Powiat wielicki" in data_kr["neighboring_powiats"]

        # Unknown powiat -> 404
        res_404 = await client.get("/explore/powiats/NieistniejącyPowiat123")
        assert res_404.status_code == 404
