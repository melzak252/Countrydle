from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country
from db.models.continental import ContinentCode
from schemas.continental import ContinentalGuessDisplay
from utils.geo import enhance_guess_with_hint


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"


CONTINENT_MAP: dict[ContinentCode, list[str]] = {
    ContinentCode.EUROPE: ["Europe"],
    ContinentCode.ASIA: ["Asia"],
    ContinentCode.AFRICA: ["Africa"],
    ContinentCode.AMERICAS: ["North America", "South America"],
}

CONTINENT_TITLE_MAP: dict[ContinentCode, str] = {
    ContinentCode.EUROPE: "Europedle",
    ContinentCode.ASIA: "Asiadle",
    ContinentCode.AFRICA: "Africadle",
    ContinentCode.AMERICAS: "Americadle",
}


def get_continent_country_names(continent: ContinentCode, db_path: Path | None = None) -> list[str]:
    """Retrieve all eligible country names for a given continent from SQLite."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    try:
        c = conn.cursor()
        continents = CONTINENT_MAP[continent]
        placeholders = ",".join("?" for _ in continents)
        c.execute(
            f"""
            SELECT DISTINCT c.app_country_name
            FROM countries c
            JOIN country_continents cc ON c.id = cc.country_id
            WHERE cc.continent IN ({placeholders})
            ORDER BY c.app_country_name
            """,
            continents,
        )
        return [row[0] for row in c.fetchall()]
    finally:
        conn.close()


async def get_continent_country_ids(
    continent: ContinentCode, session: AsyncSession, db_path: Path | None = None
) -> list[int]:
    """Retrieve all eligible Postgres country IDs for a given continent."""
    names = get_continent_country_names(continent, db_path=db_path)
    result = await session.execute(
        select(Country.id).where(Country.name.in_(names))
    )
    return list(result.scalars().all())


async def get_continent_countries(
    continent: ContinentCode, session: AsyncSession, db_path: Path | None = None
) -> list[Country]:
    """Retrieve Country objects for all eligible nations of a continent."""
    names = get_continent_country_names(continent, db_path=db_path)
    result = await session.execute(
        select(Country).where(Country.name.in_(names)).order_by(Country.name)
    )
    return list(result.scalars().all())


def is_eligible_candidate(
    guess_name: str, continent: ContinentCode, db_path: Path | None = None
) -> bool:
    """Check if a country name or candidate is eligible for the continental mode."""
    if not guess_name:
        return False
    clean_guess = guess_name.strip().lower()
    names = get_continent_country_names(continent, db_path=db_path)
    return any(name.strip().lower() == clean_guess for name in names)


def format_continental_guesses(
    guesses: list,
    target_country_id: int,
    target_name: str | None = None,
    max_guesses: int = 3,
) -> list[ContinentalGuessDisplay]:
    """Enhance a list of continental guesses with distance and bearing hints."""
    from datetime import datetime

    formatted: list[ContinentalGuessDisplay] = []
    for idx, g in enumerate(guesses):
        guess_str = getattr(g, "guess", "")
        c_id = getattr(g, "country_id", None)
        ans = bool(getattr(g, "answer", False))
        g_at = getattr(g, "guessed_at", None) or datetime.now()
        el_sec = getattr(g, "elapsed_seconds", None)
        g_id = getattr(g, "id", 0) or 0

        hint = enhance_guess_with_hint(
            mode="countrydle",
            guess_record=g,
            guess_number=idx + 1,
            max_guesses=max_guesses,
            target_id=target_country_id,
            target_name=target_name,
        )

        formatted.append(
            ContinentalGuessDisplay(
                id=g_id,
                guess=guess_str,
                country_id=c_id,
                answer=ans,
                guessed_at=g_at,
                elapsed_seconds=el_sec,
                distance_km=hint.get("distance_km"),
                bearing_degrees=hint.get("bearing_degrees"),
                bearing_direction=hint.get("bearing_direction"),
                bearing_arrow=hint.get("bearing_arrow"),
            )
        )
    return formatted
