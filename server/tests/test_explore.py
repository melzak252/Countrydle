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
