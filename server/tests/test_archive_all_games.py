from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from db.models.continental import ContinentCode


@pytest.mark.anyio
async def test_all_nine_history_endpoints(async_client):
    """Verify that all 9 game mode history endpoints respond with 200 OK and valid schemas."""

    mock_country = MagicMock()
    mock_country.id = 1
    mock_country.name = "Poland"
    mock_country.official_name = "Republic of Poland"
    mock_country.md_file = "Poland.md"

    # 1. Countrydle: GET /countrydle/statistics/history
    with (
        patch("db.repositories.countrydle.CountrydleRepository.get_countrydle_history", new_callable=AsyncMock) as m_c_hist,
        patch("db.repositories.countrydle.CountrydleRepository.get_countries_count", new_callable=AsyncMock) as m_c_count,
    ):
        mock_c_day = MagicMock()
        mock_c_day.id = 101
        mock_c_day.country_id = 1
        mock_c_day.country = mock_country
        mock_c_day.date = date(2026, 9, 25)
        m_c_hist.return_value = [mock_c_day]
        m_c_count.return_value = []

        res = await async_client.get("/countrydle/statistics/history")
        assert res.status_code == 200
        data = res.json()
        assert "daily_countries" in data
        assert len(data["daily_countries"]) == 1
        assert data["daily_countries"][0]["country"]["name"] == "Poland"

    # 2. Flagdle: GET /flagdle/history
    with patch("db.repositories.flagdle.FlagdleDayRepository.get_history", new_callable=AsyncMock) as m_f_hist:
        mock_f_day = MagicMock()
        mock_f_day.id = 201
        mock_f_day.country_id = 1
        mock_f_day.country = mock_country
        mock_f_day.date = date(2026, 9, 25)
        m_f_hist.return_value = [mock_f_day]

        res = await async_client.get("/flagdle/history")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["id"] == 201
        assert data[0]["country"]["name"] == "Poland"

    # 3-6. Continental: GET /continental/{continent}/history
    continents = [
        (ContinentCode.EUROPE, "europe"),
        (ContinentCode.ASIA, "asia"),
        (ContinentCode.AFRICA, "africa"),
        (ContinentCode.AMERICAS, "americas"),
    ]
    for code, slug in continents:
        with patch("db.repositories.continental.ContinentalDayRepository.get_history", new_callable=AsyncMock) as m_cont_hist:
            mock_cont_day = MagicMock()
            mock_cont_day.id = 301
            mock_cont_day.continent = code
            mock_cont_day.country_id = 1
            mock_cont_day.country = mock_country
            mock_cont_day.date = date(2026, 9, 25)
            m_cont_hist.return_value = [mock_cont_day]

            res = await async_client.get(f"/continental/{slug}/history")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["continent"] == slug
            assert data[0]["country"]["name"] == "Poland"

    # 7. US States: GET /us_statedle/history
    mock_state = MagicMock()
    mock_state.id = 1
    mock_state.name = "California"
    mock_state.code = "CA"
    mock_state.capital = "Sacramento"
    with patch("db.repositories.us_statedle.USStatedleDayRepository.get_history", new_callable=AsyncMock) as m_us_hist:
        mock_us_day = MagicMock()
        mock_us_day.id = 401
        mock_us_day.us_state_id = 1
        mock_us_day.us_state = mock_state
        mock_us_day.date = date(2026, 9, 25)
        m_us_hist.return_value = [mock_us_day]

        res = await async_client.get("/us_statedle/history")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["us_state"]["name"] == "California"

    # 8. Wojewodztwa: GET /wojewodztwodle/history
    mock_woj = MagicMock()
    mock_woj.id = 1
    mock_woj.nazwa = "Mazowieckie"
    mock_woj.kod = "MZ"
    mock_woj.stolica = "Warszawa"
    with patch("db.repositories.wojewodztwodle.WojewodztwodleDayRepository.get_history", new_callable=AsyncMock) as m_woj_hist:
        mock_woj_day = MagicMock()
        mock_woj_day.id = 501
        mock_woj_day.wojewodztwo_id = 1
        mock_woj_day.wojewodztwo = mock_woj
        mock_woj_day.date = date(2026, 9, 25)
        m_woj_hist.return_value = [mock_woj_day]

        res = await async_client.get("/wojewodztwodle/history")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["wojewodztwo"]["nazwa"] == "Mazowieckie"

    # 9. Powiaty: GET /powiatdle/history
    mock_powiat = MagicMock()
    mock_powiat.id = 1
    mock_powiat.nazwa = "krakowski"
    mock_powiat.kod_teryt = "1206"
    mock_powiat.siedziba = "Krakow"
    with patch("db.repositories.powiatdle.PowiatdleDayRepository.get_history", new_callable=AsyncMock) as m_pow_hist:
        mock_pow_day = MagicMock()
        mock_pow_day.id = 601
        mock_pow_day.powiat_id = 1
        mock_pow_day.powiat = mock_powiat
        mock_pow_day.date = date(2026, 9, 25)
        m_pow_hist.return_value = [mock_pow_day]

        res = await async_client.get("/powiatdle/history")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["powiat"]["nazwa"] == "krakowski"
