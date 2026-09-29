import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/explore", tags=["explore"])


def get_data_dir() -> Path:
    base = Path(__file__).resolve().parent.parent
    if (base / "data").exists():
        return base / "data"
    if (base.parent / "data").exists():
        return base.parent / "data"
    return Path("data")


def get_db_connection(filename: str) -> sqlite3.Connection:
    path = get_data_dir() / filename
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Knowledge base {filename} not found.")
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


GAME_MODES = [
    {
        "id": "countrydle",
        "name": "Countrydle (World Countries)",
        "path": "/game",
        "entity_type": "World Countries",
        "entity_count": 195,
        "question_limit": 10,
        "guess_limit": 3,
        "description": "Deduce one of 195 sovereign nations across all seven continents using natural-language questions.",
        "strategy_tips": [
            "Start with macro-geographic bounds: Ask about hemispheres (Northern/Southern) and prime meridian (Eastern/Western).",
            "Check maritime access: Inquire if the mystery country has access to an ocean or sea (eliminates ~44 landlocked countries).",
            "Narrow down by population or area: 'Is the population greater than 20 million?' splits the candidate space rapidly.",
            "Ask about international borders: Asking if it borders a major regional hub (e.g. Brazil, Germany, China) isolates neighboring clusters.",
            "Target flag attributes: Colors and flag symbols (stars, stripes, crosses) can confirm your top candidate."
        ],
        "data_sources": ["Natural Earth", "CIA World Factbook", "REST Countries API", "OpenStreetMap"]
    },
    {
        "id": "us_statedle",
        "name": "US Statedle (50 States)",
        "path": "/us-states",
        "entity_type": "US States",
        "entity_count": 50,
        "question_limit": 8,
        "guess_limit": 3,
        "description": "Identify the secret American state among all 50 states using regional, historical, and demographic clues.",
        "strategy_tips": [
            "Use US Census Divisions: Ask if the state is in the West, Midwest, South, or Northeast.",
            "Check coastline access: Ask if the state borders the Atlantic Ocean, Pacific Ocean, or Gulf of Mexico.",
            "Inquire about the Mississippi River: Asking if it is east or west of the Mississippi cuts the country in half.",
            "Target admission order: Asking if it was one of the original 13 colonies isolates the Atlantic seaboard.",
            "Use physical geography: Mountain ranges (Rockies, Appalachians) and major interstate highways provide strong signals."
        ],
        "data_sources": ["US Census Bureau", "US Geological Survey (USGS)", "Natural Earth"]
    },
    {
        "id": "wojewodztwodle",
        "name": "Województwodle (16 Polish Voivodeships)",
        "path": "/wojewodztwa",
        "entity_type": "Polish Voivodeships",
        "entity_count": 16,
        "question_limit": 5,
        "guess_limit": 2,
        "description": "Master Poland's 16 administrative voivodeships using regional geography, rivers, and international frontiers.",
        "strategy_tips": [
            "Test Baltic Sea access: Immediately eliminates or isolates the 3 coastal regions (Pomorskie, Zachodniopomorskie, Warmińsko-Mazurskie).",
            "Inquire about international borders: Does it border Germany, the Czech Republic, Slovakia, Ukraine, Belarus, or Lithuania?",
            "Use macroregions: Check if the voivodeship lies in Poland's southern, northern, eastern, or western quadrant.",
            "Target major river systems: Rivers like the Vistula (Wisła) and Oder (Odra) traverse specific administrative paths."
        ],
        "data_sources": ["Główny Urząd Statystyczny (GUS)", "Państwowy Rejestr Granic (PRG)"]
    },
    {
        "id": "powiatdle",
        "name": "Powiatdle (380 Polish Counties)",
        "path": "/powiaty",
        "entity_type": "Polish Counties (Powiaty)",
        "entity_count": 380,
        "question_limit": 15,
        "guess_limit": 3,
        "description": "The ultimate test of Polish local geography across 380 counties, tested via vehicle registration codes, rivers, and roads.",
        "strategy_tips": [
            "Identify the voivodeship first: Knowing which of the 16 regions contains the powiat reduces 380 candidates down to 12–36.",
            "Ask about county type: Distinguish whether it is a city with powiat rights (miasto na prawach powiatu) or a rural county.",
            "Inquire about registration plates: Territorial code letters (e.g. KR, WZ, PO, DW) pinpoint specific administrative zones.",
            "Use transportation corridors: Check proximity to motorways (A1, A2, A4) or expressways (S7, S8, S3)."
        ],
        "data_sources": ["GUS TERYT Registry", "Generalna Dyrekcja Dróg Krajowych i Autostrad (GDDKiA)"]
    }
]


@router.get("/modes")
async def list_modes():
    """Returns educational and strategic overviews for all Countrydle game modes."""
    return GAME_MODES


@router.get("/countries")
async def list_countries(
    search: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(250, ge=1, le=300),
    offset: int = Query(0, ge=0),
):
    """List world countries with core geographic attributes."""
    conn = get_db_connection("country_facts.sqlite")
    try:
        query = """
            SELECT id, app_country_name, official_name, cca2, cca3, region, subregion, 
                   capital, population, area_km2, latitude, longitude, is_island, 
                   driving_side, government_type, dominant_religion
            FROM countries
            WHERE 1=1
        """
        params: List[Any] = []
        if search:
            query += " AND (app_country_name LIKE ? OR official_name LIKE ? OR capital LIKE ? OR cca3 LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term])
        if region:
            query += " AND region = ?"
            params.append(region)
        query += " ORDER BY app_country_name ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/countries/{identifier}")
async def get_country_detail(identifier: str):
    """Get full encyclopedic facts for a specific country by name, cca2, or cca3."""
    conn = get_db_connection("country_facts.sqlite")
    try:
        # Match by name, cca2, or cca3
        row = conn.execute(
            """
            SELECT * FROM countries 
            WHERE app_country_name LIKE ? OR cca2 = ? OR cca3 = ?
            LIMIT 1
            """,
            (identifier, identifier.upper(), identifier.upper())
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Country not found in knowledge base.")

        country = dict(row)
        c_id = country["id"]

        # Related lists
        continents = [r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id = ?", (c_id,)).fetchall()]
        borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id = ?", (c_id,)).fetchall()]
        water = [r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id = ?", (c_id,)).fetchall()]
        currencies = [r[0] for r in conn.execute("SELECT currency_name FROM country_currencies WHERE country_id = ?", (c_id,)).fetchall()]
        languages = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id = ?", (c_id,)).fetchall()]
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id = ?", (c_id,)).fetchall()]
        flag_colors = [r[0] for r in conn.execute("SELECT color FROM country_flag_colors WHERE country_id = ?", (c_id,)).fetchall()]
        flag_symbols = [r[0] for r in conn.execute("SELECT symbol FROM country_flag_symbols WHERE country_id = ?", (c_id,)).fetchall()]
        unions = [r[0] for r in conn.execute("SELECT union_name FROM country_historical_unions WHERE country_id = ?", (c_id,)).fetchall()]
        hemispheres = [r[0] for r in conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id = ?", (c_id,)).fetchall()]

        country["continents"] = continents
        country["borders"] = borders
        country["water_access"] = water
        country["currencies"] = currencies
        country["languages"] = languages
        country["major_rivers"] = rivers
        country["flag_colors"] = flag_colors
        country["flag_symbols"] = flag_symbols
        country["historical_unions"] = unions
        country["hemispheres"] = hemispheres

        return country
    finally:
        conn.close()


@router.get("/us-states")
async def list_us_states(
    search: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
):
    """List all 50 US states with key demographic and historical facts."""
    conn = get_db_connection("us_state_facts.sqlite")
    try:
        query = "SELECT * FROM us_states WHERE 1=1"
        params: List[Any] = []
        if search:
            query += " AND (name LIKE ? OR nickname LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term])
        if region:
            query += " AND region = ?"
            params.append(region)
        query += " ORDER BY name ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/us-states/{name}")
async def get_us_state_detail(name: str):
    """Get full encyclopedic facts for a specific US state."""
    conn = get_db_connection("us_state_facts.sqlite")
    try:
        row = conn.execute(
            "SELECT * FROM us_states WHERE name LIKE ? LIMIT 1",
            (name,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="US State not found in knowledge base.")

        state = dict(row)
        s_id = state["id"]

        state_borders = [r[0] for r in conn.execute("SELECT border_state_name FROM us_state_borders_states WHERE state_id = ?", (s_id,)).fetchall()]
        country_borders = [r[0] for r in conn.execute("SELECT country_name FROM us_state_borders_countries WHERE state_id = ?", (s_id,)).fetchall()]
        water = [r[0] for r in conn.execute("SELECT water_body FROM us_state_water_access WHERE state_id = ?", (s_id,)).fetchall()]
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM us_state_major_rivers WHERE state_id = ?", (s_id,)).fetchall()]
        mountains = [r[0] for r in conn.execute("SELECT range_name FROM us_state_mountain_ranges WHERE state_id = ?", (s_id,)).fetchall()]
        highways = [r[0] for r in conn.execute("SELECT highway_name FROM us_state_major_highways WHERE state_id = ?", (s_id,)).fetchall()]

        state["neighboring_states"] = state_borders
        state["neighboring_countries"] = country_borders
        state["water_access"] = water
        state["major_rivers"] = rivers
        state["mountain_ranges"] = mountains
        state["major_highways"] = highways

        return state
    finally:
        conn.close()


@router.get("/voivodeships")
async def list_voivodeships(search: Optional[str] = Query(None)):
    """List all 16 Polish voivodeships with administrative statistics."""
    conn = get_db_connection("voivodeship_facts.sqlite")
    try:
        query = "SELECT * FROM voivodeships WHERE 1=1"
        params: List[Any] = []
        if search:
            query += " AND (name LIKE ? OR seat LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term])
        query += " ORDER BY name ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/voivodeships/{name}")
async def get_voivodeship_detail(name: str):
    """Get full encyclopedic facts for a specific Polish voivodeship."""
    conn = get_db_connection("voivodeship_facts.sqlite")
    try:
        row = conn.execute(
            "SELECT * FROM voivodeships WHERE name LIKE ? LIMIT 1",
            (name,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Voivodeship not found in knowledge base.")

        voivodeship = dict(row)
        v_id = voivodeship["id"]

        voiv_borders = [r[0] for r in conn.execute("SELECT border_voivodeship_name FROM voivodeship_borders_voivodeships WHERE voivodeship_id = ?", (v_id,)).fetchall()]
        country_borders = [r[0] for r in conn.execute("SELECT country_name FROM voivodeship_borders_countries WHERE voivodeship_id = ?", (v_id,)).fetchall()]
        water = [r[0] for r in conn.execute("SELECT water_body FROM voivodeship_water_access WHERE voivodeship_id = ?", (v_id,)).fetchall()]
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM voivodeship_major_rivers WHERE voivodeship_id = ?", (v_id,)).fetchall()]
        mountains = [r[0] for r in conn.execute("SELECT range_name FROM voivodeship_mountain_ranges WHERE voivodeship_id = ?", (v_id,)).fetchall()]
        historical = [r[0] for r in conn.execute("SELECT region_name FROM voivodeship_historical_regions WHERE voivodeship_id = ?", (v_id,)).fetchall()]

        voivodeship["neighboring_voivodeships"] = voiv_borders
        voivodeship["neighboring_countries"] = country_borders
        voivodeship["water_access"] = water
        voivodeship["major_rivers"] = rivers
        voivodeship["mountain_ranges"] = mountains
        voivodeship["historical_regions"] = historical

        return voivodeship
    finally:
        conn.close()
