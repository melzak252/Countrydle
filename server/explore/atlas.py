import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Response

from powiatdle.heraldry import (
    get_or_fetch_herb_svg,
    get_or_fetch_herb_thumb,
    get_source_attribution,
    polish_sort_key,
)

router = APIRouter()


def get_data_dir() -> Path:
    base = Path(__file__).resolve().parent.parent
    if (base / "data").exists():
        return base / "data"
    if (base.parent / "data").exists():
        return base.parent / "data"
    return Path("data")


def get_db_connection(filename: str) -> sqlite3.Connection:
    pkg = sys.modules.get("explore")
    data_dir = pkg.get_data_dir() if pkg is not None and hasattr(pkg, "get_data_dir") else get_data_dir()
    path = data_dir / filename
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Knowledge base {filename} not found.")
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def deduplicate_border_names(borders: List[str]) -> List[str]:
    """Deduplicate canonical country names and aliases for human display."""
    canonical_aliases = {
        "dr congo": "Democratic Republic of the Congo",
        "democratic republic of the congo": "Democratic Republic of the Congo",
        "czech republic": "Czechia",
        "czechia": "Czechia",
        "usa": "United States",
        "united states": "United States",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
    }
    seen = set()
    result = []
    for b in borders:
        clean = b.strip()
        canonical = canonical_aliases.get(clean.lower(), clean)
        canon_key = canonical.lower()
        if canon_key not in seen:
            seen.add(canon_key)
            result.append(canonical)
    return sorted(result)


def _fetch_relations(
    conn: sqlite3.Connection,
    entity_id: int,
    specs: List[Tuple[str, str]],
) -> Dict[str, List[str]]:
    return {
        field: [r[0] for r in conn.execute(sql, (entity_id,)).fetchall()]
        for field, sql in specs
    }


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
            "Target flag attributes: Colors and flag symbols (stars, stripes, crosses) can confirm your top candidate.",
        ],
        "data_sources": ["Natural Earth", "CIA World Factbook", "REST Countries API", "OpenStreetMap"],
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
            "Use physical geography: Mountain ranges (Rockies, Appalachians) and major interstate highways provide strong signals.",
        ],
        "data_sources": ["US Census Bureau", "US Geological Survey (USGS)", "Natural Earth"],
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
            "Target major river systems: Rivers like the Vistula (Wisła) and Oder (Odra) traverse specific administrative paths.",
        ],
        "data_sources": ["Główny Urząd Statystyczny (GUS)", "Państwowy Rejestr Granic (PRG)"],
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
            "Use transportation corridors: Check proximity to motorways (A1, A2, A4) or expressways (S7, S8, S3).",
        ],
        "data_sources": ["GUS TERYT Registry", "Generalna Dyrekcja Dróg Krajowych i Autostrad (GDDKiA)"],
    },
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
        row = conn.execute(
            """
            SELECT * FROM countries
            WHERE app_country_name LIKE ? OR cca2 = ? OR cca3 = ?
            LIMIT 1
            """,
            (identifier, identifier.upper(), identifier.upper()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Country not found in knowledge base.")

        country = dict(row)
        c_id = country["id"]
        relations = _fetch_relations(
            conn,
            c_id,
            [
                ("continents", "SELECT continent FROM country_continents WHERE country_id = ?"),
                ("borders", "SELECT border_country_name FROM country_borders WHERE country_id = ?"),
                ("water_access", "SELECT water_body FROM country_water_access WHERE country_id = ?"),
                ("currencies", "SELECT currency_name FROM country_currencies WHERE country_id = ?"),
                ("languages", "SELECT language_name FROM country_languages WHERE country_id = ?"),
                ("major_rivers", "SELECT river_name FROM country_major_rivers WHERE country_id = ?"),
                ("flag_colors", "SELECT color FROM country_flag_colors WHERE country_id = ?"),
                ("flag_symbols", "SELECT symbol FROM country_flag_symbols WHERE country_id = ?"),
                ("historical_unions", "SELECT union_name FROM country_historical_unions WHERE country_id = ?"),
                ("hemispheres", "SELECT hemisphere FROM country_hemispheres WHERE country_id = ?"),
            ],
        )
        relations["borders"] = deduplicate_border_names(relations["borders"])
        country.update(relations)
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
        row = conn.execute("SELECT * FROM us_states WHERE name LIKE ? LIMIT 1", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="US State not found in knowledge base.")

        state = dict(row)
        state.update(
            _fetch_relations(
                conn,
                state["id"],
                [
                    ("neighboring_states", "SELECT border_state_name FROM us_state_borders_states WHERE state_id = ?"),
                    ("neighboring_countries", "SELECT country_name FROM us_state_borders_countries WHERE state_id = ?"),
                    ("water_access", "SELECT water_body FROM us_state_water_access WHERE state_id = ?"),
                    ("major_rivers", "SELECT river_name FROM us_state_major_rivers WHERE state_id = ?"),
                    ("mountain_ranges", "SELECT range_name FROM us_state_mountain_ranges WHERE state_id = ?"),
                    ("major_highways", "SELECT highway_name FROM us_state_major_highways WHERE state_id = ?"),
                ],
            )
        )
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
        row = conn.execute("SELECT * FROM voivodeships WHERE name LIKE ? LIMIT 1", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Voivodeship not found in knowledge base.")

        voivodeship = dict(row)
        voivodeship.update(
            _fetch_relations(
                conn,
                voivodeship["id"],
                [
                    ("neighboring_voivodeships", "SELECT border_voivodeship_name FROM voivodeship_borders_voivodeships WHERE voivodeship_id = ?"),
                    ("neighboring_countries", "SELECT country_name FROM voivodeship_borders_countries WHERE voivodeship_id = ?"),
                    ("water_access", "SELECT water_body FROM voivodeship_water_access WHERE voivodeship_id = ?"),
                    ("major_rivers", "SELECT river_name FROM voivodeship_major_rivers WHERE voivodeship_id = ?"),
                    ("mountain_ranges", "SELECT range_name FROM voivodeship_mountain_ranges WHERE voivodeship_id = ?"),
                    ("historical_regions", "SELECT region_name FROM voivodeship_historical_regions WHERE voivodeship_id = ?"),
                ],
            )
        )
        return voivodeship
    finally:
        conn.close()


@router.get("/powiats")
async def list_powiats(
    search: Optional[str] = Query(None, description="Search by county name, seat, or plate code"),
    voivodeship: Optional[str] = Query(None, description="Filter by voivodeship name"),
    county_type: Optional[str] = Query(None, description="Filter by type: 'city' or 'land'"),
):
    """List all 380 Polish counties with basic facts, registration plates, and coat-of-arms URL."""
    conn = get_db_connection("powiat_facts.sqlite")
    try:
        rows = conn.execute(
            """
            SELECT id, name, voivodeship, is_city_county, seat, terc,
                   population, area_km2, population_density, urbanization_percent, gmina_count
            FROM powiats
            """
        ).fetchall()
        plate_rows = conn.execute(
            "SELECT powiat_id, plate_code FROM powiat_registration_plates ORDER BY plate_code ASC"
        ).fetchall()
        plates_by_id: Dict[int, List[str]] = {}
        for pr in plate_rows:
            plates_by_id.setdefault(int(pr["powiat_id"]), []).append(str(pr["plate_code"]))

        items: List[Dict[str, Any]] = []
        voiv_filter = voivodeship.strip().lower() if voivodeship else None
        search_filter = search.strip().lower() if search else None

        for r in rows:
            pid = int(r["id"])
            name_val = str(r["name"])
            voiv_val = str(r["voivodeship"])
            is_city = bool(r["is_city_county"])
            seat_val = str(r["seat"]) if r["seat"] else None
            plates = plates_by_id.get(pid, [])

            if voiv_filter and voiv_val.lower() != voiv_filter:
                continue
            if county_type == "city" and not is_city:
                continue
            if county_type == "land" and is_city:
                continue
            if search_filter:
                haystack = " ".join(
                    [name_val.lower(), (seat_val or "").lower(), voiv_val.lower()]
                    + [p.lower() for p in plates]
                )
                if search_filter not in haystack:
                    continue

            items.append(
                {
                    "id": pid,
                    "name": name_val,
                    "voivodeship": voiv_val,
                    "is_city_county": is_city,
                    "seat": seat_val,
                    "terc": r["terc"],
                    "population": r["population"],
                    "area_km2": r["area_km2"],
                    "population_density": r["population_density"],
                    "urbanization_percent": r["urbanization_percent"],
                    "gmina_count": r["gmina_count"],
                    "registration_plates": plates,
                    "coat_of_arms_url": f"/explore/powiats/{pid}/coat",
                    "coat_thumb_url": f"/explore/powiats/{pid}/coat?size=thumb",
                }
            )

        items.sort(key=lambda c: polish_sort_key(c["name"]))
        return items
    finally:
        conn.close()


@router.get("/powiats/{powiat_id}/coat")
async def get_powiat_coat_svg(
    powiat_id: int,
    size: Optional[str] = Query(None, description="'thumb' for low-res PNG thumbnail, or omit for full vector SVG"),
    width: int = Query(80, ge=32, le=240),
):
    """Serve the coat of arms (low-res thumbnail or full SVG) for a Polish county."""
    conn = get_db_connection("powiat_facts.sqlite")
    try:
        row = conn.execute("SELECT id, name FROM powiats WHERE id = ? LIMIT 1", (powiat_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Powiat not found.")

    if size == "thumb":
        body, media_type = await asyncio.to_thread(
            get_or_fetch_herb_thumb, int(row["id"]), str(row["name"]), width
        )
        return Response(
            content=body,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )

    svg_bytes = await asyncio.to_thread(get_or_fetch_herb_svg, int(row["id"]), str(row["name"]))
    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/powiats/{name}")
async def get_powiat_detail(name: str):
    """Get full encyclopedic facts and coat-of-arms metadata for a specific Polish powiat."""
    conn = get_db_connection("powiat_facts.sqlite")
    try:
        row = None
        if name.strip().isdigit():
            row = conn.execute("SELECT * FROM powiats WHERE id = ? LIMIT 1", (int(name.strip()),)).fetchone()

        if not row:
            row = conn.execute(
                "SELECT * FROM powiats WHERE LOWER(name) = LOWER(?) OR LOWER(name) LIKE LOWER(?) LIMIT 1",
                (name, f"%{name}%"),
            ).fetchone()

        if not row:
            row = conn.execute(
                """
                SELECT p.* FROM powiats p
                JOIN powiat_name_aliases a ON p.id = a.powiat_id
                WHERE LOWER(a.alias) = LOWER(?) OR LOWER(a.alias) LIKE LOWER(?) LIMIT 1
                """,
                (name, f"%{name}%"),
            ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Powiat not found in knowledge base.")

        powiat = dict(row)
        p_id = int(powiat["id"])
        powiat["is_city_county"] = bool(powiat.get("is_city_county"))
        powiat.update(
            _fetch_relations(
                conn,
                p_id,
                [
                    ("neighboring_powiats", "SELECT border_powiat_name FROM powiat_borders_powiats WHERE powiat_id = ? ORDER BY border_powiat_name"),
                    ("neighboring_voivodeships", "SELECT voivodeship FROM powiat_borders_voivodeships WHERE powiat_id = ? ORDER BY voivodeship"),
                    ("neighboring_countries", "SELECT country_name FROM powiat_borders_countries WHERE powiat_id = ? ORDER BY country_name"),
                    ("registration_plates", "SELECT plate_code FROM powiat_registration_plates WHERE powiat_id = ? ORDER BY plate_code"),
                    ("major_rivers", "SELECT river_name FROM powiat_major_rivers WHERE powiat_id = ? ORDER BY river_name"),
                    ("major_roads", "SELECT road_name FROM powiat_major_roads WHERE powiat_id = ? ORDER BY road_name"),
                    ("water_access", "SELECT water_name FROM powiat_water_access WHERE powiat_id = ?"),
                    ("landform_regions", "SELECT region_name FROM powiat_landform_regions WHERE powiat_id = ?"),
                    ("historical_regions", "SELECT region_name FROM powiat_historical_regions WHERE powiat_id = ?"),
                    ("historical_partitions", "SELECT partition_name FROM powiat_historical_partitions WHERE powiat_id = ?"),
                    ("national_parks", "SELECT park_name FROM powiat_national_parks WHERE powiat_id = ?"),
                    ("lakes", "SELECT lake_name FROM powiat_lakes WHERE powiat_id = ?"),
                    ("health_resorts", "SELECT resort_name FROM powiat_health_resorts WHERE powiat_id = ?"),
                    ("unesco_sites", "SELECT site_name FROM powiat_unesco_sites WHERE powiat_id = ?"),
                ],
            )
        )
        powiat["coat_of_arms_url"] = f"/explore/powiats/{p_id}/coat"
        attr = get_source_attribution(p_id)
        powiat["source_attribution"] = attr.model_dump() if attr else None
        return powiat
    finally:
        conn.close()
