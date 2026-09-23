import pytest
from httpx import AsyncClient
from datetime import date
from sqlalchemy import select
from db import AsyncSessionLocal
from db.models import Country, CountrydleDay, Wojewodztwo, WojewodztwodleDay, USState, USStatedleDay, Powiat, PowiatdleDay
from db.models.continental import ContinentalDay, ContinentCode, ContinentalGuess
from db.models.flagdle import FlagdleDay, FlagdleGuess
from db.models.guess import CountrydleGuess
from db.models.powiatdle import PowiatdleGuess
from db.models.us_statedle import USStatedleGuess
from db.models.wojewodztwodle import WojewodztwodleGuess


@pytest.mark.anyio
@pytest.mark.real_database
async def test_guest_guesses_saved_to_database_across_modes(async_client: AsyncClient):
    async_client.cookies.clear()
    
    async with AsyncSessionLocal() as session:
        # 1. Setup daily rows for all modes if not present
        today = date.today()
        
        # Countrydle
        country = (await session.execute(select(Country).limit(1))).scalar_one()
        c_day = (await session.execute(select(CountrydleDay).where(CountrydleDay.date == today))).scalar_one_or_none()
        if not c_day:
            c_day = CountrydleDay(date=today, country_id=country.id)
            session.add(c_day)
            await session.commit()
            await session.refresh(c_day)

        # Continental Europe
        eur_day = (await session.execute(select(ContinentalDay).where(ContinentalDay.date == today, ContinentalDay.continent == ContinentCode.EUROPE))).scalar_one_or_none()
        if not eur_day:
            eur_day = ContinentalDay(date=today, continent=ContinentCode.EUROPE, country_id=country.id)
            session.add(eur_day)
            await session.commit()
            await session.refresh(eur_day)

        # Flagdle
        f_day = (await session.execute(select(FlagdleDay).where(FlagdleDay.date == today))).scalar_one_or_none()
        if not f_day:
            f_day = FlagdleDay(date=today, country_id=country.id)
            session.add(f_day)
            await session.commit()
            await session.refresh(f_day)

        # US Statedle
        us_state = (await session.execute(select(USState).limit(1))).scalar_one_or_none()
        if us_state:
            us_day = (await session.execute(select(USStatedleDay).where(USStatedleDay.date == today))).scalar_one_or_none()
            if not us_day:
                us_day = USStatedleDay(date=today, us_state_id=us_state.id)
                session.add(us_day)
                await session.commit()
                await session.refresh(us_day)

        # Powiatdle
        powiat = (await session.execute(select(Powiat).limit(1))).scalar_one_or_none()
        if powiat:
            p_day = (await session.execute(select(PowiatdleDay).where(PowiatdleDay.date == today))).scalar_one_or_none()
            if not p_day:
                p_day = PowiatdleDay(date=today, powiat_id=powiat.id)
                session.add(p_day)
                await session.commit()
                await session.refresh(p_day)

        # Wojewodztwodle
        woj = (await session.execute(select(Wojewodztwo).limit(1))).scalar_one_or_none()
        if woj:
            w_day = (await session.execute(select(WojewodztwodleDay).where(WojewodztwodleDay.date == today))).scalar_one_or_none()
            if not w_day:
                w_day = WojewodztwodleDay(date=today, wojewodztwo_id=woj.id)
                session.add(w_day)
                await session.commit()
                await session.refresh(w_day)

    # 2. Make guest guesses via API
    # Countrydle
    res_c = await async_client.post("/countrydle/guess", json={"guess": "France", "country_id": 9999})
    assert res_c.status_code == 200
    guess_id_c = res_c.json()["id"]
    assert guess_id_c > 0

    # Continental Europe
    res_eur = await async_client.post("/continental/europe/guess", json={"guess": "France", "country_id": 9999})
    assert res_eur.status_code == 200
    guess_id_eur = res_eur.json()["id"]
    assert guess_id_eur > 0

    # Flagdle
    res_f = await async_client.post("/flagdle/guess", json={"guess": "France", "country_id": 9999})
    assert res_f.status_code == 200
    guess_id_f = res_f.json()["id"]
    assert guess_id_f > 0

    # US Statedle
    if us_state:
        res_us = await async_client.post("/us_statedle/guess", json={"guess": "California", "us_state_id": us_state.id})
        assert res_us.status_code == 200
        assert res_us.json()["id"] > 0

    # Powiatdle
    if powiat:
        res_p = await async_client.post("/powiatdle/guess", json={"guess": powiat.nazwa, "powiat_id": powiat.id})
        assert res_p.status_code == 200
        assert res_p.json()["id"] > 0

    # Wojewodztwodle
    if woj:
        res_w = await async_client.post("/wojewodztwodle/guess", json={"guess": woj.nazwa, "wojewodztwo_id": woj.id})
        assert res_w.status_code == 200
        assert res_w.json()["id"] > 0

    # 3. Verify in PostgreSQL database that rows exist with user_id = None
    async with AsyncSessionLocal() as session:
        # Countrydle
        cg = (await session.execute(select(CountrydleGuess).where(CountrydleGuess.id == guess_id_c))).scalar_one()
        assert cg.user_id is None
        assert cg.guess == "France"

        # Continental
        eg = (await session.execute(select(ContinentalGuess).where(ContinentalGuess.id == guess_id_eur))).scalar_one()
        assert eg.user_id is None
        assert eg.guess == "France"

        # Flagdle
        fg = (await session.execute(select(FlagdleGuess).where(FlagdleGuess.id == guess_id_f))).scalar_one()
        assert fg.user_id is None
