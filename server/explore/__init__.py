import logging
import random
import sqlite3
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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


class BorderHopVerifyRequest(BaseModel):
    mode: str = "countries"
    start: str
    target: str
    path: List[str]


class BorderHopVerifyResponse(BaseModel):
    valid: bool
    hops: int
    optimal_hops: Optional[int] = None
    is_optimal: bool
    rank: Optional[str] = None
    optimal_path: Optional[List[str]] = None
    error_step: Optional[List[str]] = None
    message: Optional[str] = None


BORDER_CANONICAL_ALIASES: Dict[str, str] = {
    "czechia": "Czech Republic",
    "dr congo": "Democratic Republic of the Congo",
    "democratic republic of the congo": "Democratic Republic of the Congo",
    "timor-leste": "East Timor",
    "east timor": "East Timor",
    "usa": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
}

_COUNTRY_ADJACENCY: Optional[Dict[str, Set[str]]] = None
_COUNTRY_LOOKUP: Optional[Dict[str, str]] = None
_COUNTRY_ISLANDS: Optional[Set[str]] = None
_COUNTRY_CONNECTED_PAIRS: Optional[List[Tuple[str, str, int]]] = None

_US_STATE_ADJACENCY: Optional[Dict[str, Set[str]]] = None
_US_STATE_LOOKUP: Optional[Dict[str, str]] = None
_US_STATE_ISLANDS: Optional[Set[str]] = None
_US_STATE_CONNECTED_PAIRS: Optional[List[Tuple[str, str, int]]] = None


def _get_country_graph() -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str]]:
    global _COUNTRY_ADJACENCY, _COUNTRY_LOOKUP, _COUNTRY_ISLANDS
    if _COUNTRY_ADJACENCY is not None and _COUNTRY_LOOKUP is not None and _COUNTRY_ISLANDS is not None:
        return _COUNTRY_ADJACENCY, _COUNTRY_LOOKUP, _COUNTRY_ISLANDS

    conn = get_db_connection("country_facts.sqlite")
    try:
        names = {r[0]: r[0] for r in conn.execute("SELECT app_country_name FROM countries")}
        lookup = {name.lower(): name for name in names}
        adj = {name: set() for name in names}

        rows = conn.execute("""
            SELECT c.app_country_name, b.border_country_name
            FROM countries c
            JOIN country_borders b ON c.id = b.country_id
        """).fetchall()

        for c_name, b_name in rows:
            b_clean = b_name.strip()
            b_canon = BORDER_CANONICAL_ALIASES.get(b_clean.lower(), b_clean)
            actual_b = lookup.get(b_canon.lower(), b_canon)
            if actual_b in adj and c_name in adj:
                adj[c_name].add(actual_b)
                adj[actual_b].add(c_name)

        islands = {name for name, nbrs in adj.items() if len(nbrs) == 0}

        _COUNTRY_ADJACENCY = adj
        _COUNTRY_LOOKUP = lookup
        _COUNTRY_ISLANDS = islands
        return _COUNTRY_ADJACENCY, _COUNTRY_LOOKUP, _COUNTRY_ISLANDS
    finally:
        conn.close()


def _get_us_state_graph() -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str]]:
    global _US_STATE_ADJACENCY, _US_STATE_LOOKUP, _US_STATE_ISLANDS
    if _US_STATE_ADJACENCY is not None and _US_STATE_LOOKUP is not None and _US_STATE_ISLANDS is not None:
        return _US_STATE_ADJACENCY, _US_STATE_LOOKUP, _US_STATE_ISLANDS

    conn = get_db_connection("us_state_facts.sqlite")
    try:
        names = {r[0]: r[0] for r in conn.execute("SELECT name FROM us_states")}
        lookup = {name.lower(): name for name in names}
        adj = {name: set() for name in names}

        rows = conn.execute("""
            SELECT s.name, b.border_state_name
            FROM us_states s
            JOIN us_state_borders_states b ON s.id = b.state_id
        """).fetchall()

        for s_name, b_name in rows:
            b_clean = b_name.strip()
            actual_b = lookup.get(b_clean.lower(), b_clean)
            if actual_b in adj and s_name in adj:
                adj[s_name].add(actual_b)
                adj[actual_b].add(s_name)

        islands = {name for name, nbrs in adj.items() if len(nbrs) == 0}

        _US_STATE_ADJACENCY = adj
        _US_STATE_LOOKUP = lookup
        _US_STATE_ISLANDS = islands
        return _US_STATE_ADJACENCY, _US_STATE_LOOKUP, _US_STATE_ISLANDS
    finally:
        conn.close()


def canonicalize_entity_name(name: str, mode: str = "countries") -> Optional[str]:
    clean = name.strip()
    if mode in ("countries", "countrydle"):
        _, lookup, _ = _get_country_graph()
        clean = BORDER_CANONICAL_ALIASES.get(clean.lower(), clean)
        return lookup.get(clean.lower())
    elif mode in ("us_states", "us_statedle"):
        _, lookup, _ = _get_us_state_graph()
        return lookup.get(clean.lower())
    return None


def find_shortest_border_path(start: str, target: str, mode: str = "countries") -> Optional[List[str]]:
    if mode in ("countries", "countrydle"):
        adj, _, _ = _get_country_graph()
    elif mode in ("us_states", "us_statedle"):
        adj, _, _ = _get_us_state_graph()
    else:
        return None

    canon_start = canonicalize_entity_name(start, mode)
    canon_target = canonicalize_entity_name(target, mode)

    if not canon_start or not canon_target:
        return None
    if canon_start == canon_target:
        return [canon_start]

    queue = deque([[canon_start]])
    visited = {canon_start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        for nbr in sorted(adj.get(node, [])):
            if nbr == canon_target:
                return path + [nbr]
            if nbr not in visited:
                visited.add(nbr)
                queue.append(path + [nbr])
    return None


def _get_connected_pairs(mode: str = "countries", min_hops: int = 3, max_hops: int = 5) -> List[Tuple[str, str, int]]:
    global _COUNTRY_CONNECTED_PAIRS, _US_STATE_CONNECTED_PAIRS
    if mode in ("countries", "countrydle"):
        if _COUNTRY_CONNECTED_PAIRS is not None:
            return _COUNTRY_CONNECTED_PAIRS
        adj, _, _ = _get_country_graph()
    elif mode in ("us_states", "us_statedle"):
        if _US_STATE_CONNECTED_PAIRS is not None:
            return _US_STATE_CONNECTED_PAIRS
        adj, _, _ = _get_us_state_graph()
    else:
        return []

    pairs: List[Tuple[str, str, int]] = []
    for start in adj:
        if not adj[start]:
            continue
        dist = {start: 0}
        q = deque([start])
        while q:
            curr = q.popleft()
            for nbr in sorted(adj[curr]):
                if nbr not in dist:
                    dist[nbr] = dist[curr] + 1
                    q.append(nbr)
        for target, d in dist.items():
            if min_hops <= d <= max_hops and start < target:
                pairs.append((start, target, d))

    pairs.sort()
    if mode in ("countries", "countrydle"):
        _COUNTRY_CONNECTED_PAIRS = pairs
    else:
        _US_STATE_CONNECTED_PAIRS = pairs
    return pairs

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
        raw_borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id = ?", (c_id,)).fetchall()]
        borders = deduplicate_border_names(raw_borders)
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


@router.get("/border-hop/challenge")
async def get_border_hop_challenge(
    mode: str = Query("countries"),
    target: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    seed: Optional[str] = Query(None),
):
    """Generate a deterministic border hop path-finding challenge."""
    if mode not in ("countries", "countrydle", "us_states", "us_statedle"):
        raise HTTPException(status_code=400, detail="Unsupported mode. Use 'countries' or 'us_states'.")

    normalized_mode = "us_states" if mode in ("us_states", "us_statedle") else "countries"

    if normalized_mode == "countries":
        adj, lookup, islands = _get_country_graph()
    else:
        adj, lookup, islands = _get_us_state_graph()

    if target:
        canon_target = canonicalize_entity_name(target, normalized_mode)
        if not canon_target:
            raise HTTPException(status_code=404, detail=f"Target '{target}' not found in {normalized_mode}.")

        if canon_target in islands or len(adj.get(canon_target, set())) == 0:
            return {
                "mode": normalized_mode,
                "start": None,
                "target": canon_target,
                "connected": False,
                "is_island": True,
                "optimal_hops": None,
                "optimal_path": None,
                "message": f"{canon_target} has no direct land borders.",
            }

        if origin:
            canon_origin = canonicalize_entity_name(origin, normalized_mode)
            if not canon_origin:
                raise HTTPException(status_code=404, detail=f"Origin '{origin}' not found in {normalized_mode}.")

            path = find_shortest_border_path(canon_origin, canon_target, normalized_mode)
            if not path or len(path) < 2:
                return {
                    "mode": normalized_mode,
                    "start": canon_origin,
                    "target": canon_target,
                    "connected": False,
                    "is_island": canon_origin in islands,
                    "optimal_hops": None,
                    "optimal_path": None,
                    "message": f"No land border connection between {canon_origin} and {canon_target}.",
                }

            return {
                "mode": normalized_mode,
                "start": canon_origin,
                "target": canon_target,
                "connected": True,
                "is_island": False,
                "optimal_hops": len(path) - 1,
                "optimal_path": path,
                "message": None,
            }

        # Select origin between 3 and 5 hops away from target
        dist = {canon_target: 0}
        q = deque([canon_target])
        while q:
            curr = q.popleft()
            for nbr in sorted(adj.get(curr, set())):
                if nbr not in dist:
                    dist[nbr] = dist[curr] + 1
                    q.append(nbr)

        candidates = [node for node, d in dist.items() if 3 <= d <= 5]
        if not candidates:
            # Fallback to any reachable node with d >= 1
            candidates = [node for node, d in dist.items() if d >= 1]

        if not candidates:
            return {
                "mode": normalized_mode,
                "start": None,
                "target": canon_target,
                "connected": False,
                "is_island": True,
                "optimal_hops": None,
                "optimal_path": None,
                "message": f"{canon_target} has no connected neighbors.",
            }

        candidates.sort()
        seed_val = seed or f"{date.today().isoformat()}:{canon_target}"
        rng = random.Random(seed_val)
        chosen_origin = rng.choice(candidates)
        path = find_shortest_border_path(chosen_origin, canon_target, normalized_mode)

        return {
            "mode": normalized_mode,
            "start": chosen_origin,
            "target": canon_target,
            "connected": True,
            "is_island": False,
            "optimal_hops": len(path) - 1 if path else None,
            "optimal_path": path,
            "message": None,
        }

    # Daily puzzle (no target provided)
    pairs = _get_connected_pairs(normalized_mode, min_hops=3, max_hops=5)
    if not pairs:
        pairs = _get_connected_pairs(normalized_mode, min_hops=2, max_hops=6)

    seed_val = seed or date.today().isoformat()
    rng = random.Random(seed_val)
    chosen_pair = rng.choice(pairs)

    if rng.random() < 0.5:
        start_entity, target_entity = chosen_pair[0], chosen_pair[1]
    else:
        start_entity, target_entity = chosen_pair[1], chosen_pair[0]

    path = find_shortest_border_path(start_entity, target_entity, normalized_mode)

    return {
        "mode": normalized_mode,
        "start": start_entity,
        "target": target_entity,
        "connected": True,
        "is_island": False,
        "optimal_hops": len(path) - 1 if path else None,
        "optimal_path": path,
        "message": None,
    }


@router.get("/border-hop/neighbors")
async def get_border_neighbors(
    name: str = Query(...),
    mode: str = Query("countries"),
):
    """Get bordering neighbors for a specific entity."""
    if mode not in ("countries", "countrydle", "us_states", "us_statedle"):
        raise HTTPException(status_code=400, detail="Unsupported mode. Use 'countries' or 'us_states'.")

    normalized_mode = "us_states" if mode in ("us_states", "us_statedle") else "countries"

    if normalized_mode == "countries":
        adj, _, _ = _get_country_graph()
    else:
        adj, _, _ = _get_us_state_graph()

    canon_name = canonicalize_entity_name(name, normalized_mode)
    if not canon_name:
        raise HTTPException(status_code=404, detail=f"'{name}' not found in {normalized_mode}.")

    nbrs = sorted(list(adj.get(canon_name, set())))
    return {
        "name": canon_name,
        "neighbors": nbrs,
        "is_island": len(nbrs) == 0,
    }


@router.post("/border-hop/verify", response_model=BorderHopVerifyResponse)
async def verify_border_hop(payload: BorderHopVerifyRequest):
    """Verify a completed border hop path against ground-truth borders."""
    mode = payload.mode
    if mode not in ("countries", "countrydle", "us_states", "us_statedle"):
        raise HTTPException(status_code=400, detail="Unsupported mode. Use 'countries' or 'us_states'.")

    normalized_mode = "us_states" if mode in ("us_states", "us_statedle") else "countries"

    if normalized_mode == "countries":
        adj, _, _ = _get_country_graph()
    else:
        adj, _, _ = _get_us_state_graph()

    canon_start = canonicalize_entity_name(payload.start, normalized_mode)
    canon_target = canonicalize_entity_name(payload.target, normalized_mode)

    if not canon_start:
        raise HTTPException(status_code=404, detail=f"Start entity '{payload.start}' not found.")
    if not canon_target:
        raise HTTPException(status_code=404, detail=f"Target entity '{payload.target}' not found.")

    if not payload.path:
        return BorderHopVerifyResponse(
            valid=False,
            hops=0,
            optimal_hops=None,
            is_optimal=False,
            rank=None,
            message="Path cannot be empty.",
        )

    canonical_path: List[str] = []
    for step in payload.path:
        c_step = canonicalize_entity_name(step, normalized_mode)
        if not c_step:
            return BorderHopVerifyResponse(
                valid=False,
                hops=len(payload.path) - 1,
                optimal_hops=None,
                is_optimal=False,
                rank=None,
                message=f"Entity '{step}' not recognized in {normalized_mode}.",
            )
        canonical_path.append(c_step)

    optimal_path = find_shortest_border_path(canon_start, canon_target, normalized_mode)
    optimal_hops = len(optimal_path) - 1 if optimal_path else None

    if canonical_path[0] != canon_start:
        return BorderHopVerifyResponse(
            valid=False,
            hops=len(canonical_path) - 1,
            optimal_hops=optimal_hops,
            is_optimal=False,
            rank=None,
            optimal_path=optimal_path,
            message=f"Path must start at '{canon_start}', but started at '{canonical_path[0]}'.",
        )

    if canonical_path[-1] != canon_target:
        return BorderHopVerifyResponse(
            valid=False,
            hops=len(canonical_path) - 1,
            optimal_hops=optimal_hops,
            is_optimal=False,
            rank=None,
            optimal_path=optimal_path,
            message=f"Path must end at '{canon_target}', but ended at '{canonical_path[-1]}'.",
        )

    for i in range(len(canonical_path) - 1):
        curr_node = canonical_path[i]
        next_node = canonical_path[i + 1]
        if next_node not in adj.get(curr_node, set()):
            return BorderHopVerifyResponse(
                valid=False,
                hops=len(canonical_path) - 1,
                optimal_hops=optimal_hops,
                is_optimal=False,
                rank=None,
                optimal_path=optimal_path,
                error_step=[curr_node, next_node],
                message=f"'{next_node}' does not share a land border with '{curr_node}'.",
            )

    hops = len(canonical_path) - 1
    is_optimal = (optimal_hops is not None and hops == optimal_hops)

    if is_optimal:
        rank = "gold"
    elif optimal_hops is not None and hops <= optimal_hops + 2:
        rank = "silver"
    else:
        rank = "bronze"

    return BorderHopVerifyResponse(
        valid=True,
        hops=hops,
        optimal_hops=optimal_hops,
        is_optimal=is_optimal,
        rank=rank,
        optimal_path=optimal_path,
    )


@router.get("/powiats/{name}")
async def get_powiat_detail(name: str):
    """Get full encyclopedic facts for a specific Polish powiat."""
    conn = get_db_connection("powiat_facts.sqlite")
    try:
        row = conn.execute(
            "SELECT * FROM powiats WHERE name = ? OR name LIKE ? LIMIT 1",
            (name, f"%{name}%")
        ).fetchone()

        if not row:
            alias_row = conn.execute(
                """
                SELECT p.* FROM powiats p 
                JOIN powiat_name_aliases a ON p.id = a.powiat_id 
                WHERE a.alias = ? OR a.alias LIKE ? LIMIT 1
                """,
                (name, f"%{name}%")
            ).fetchone()
            if alias_row:
                row = alias_row

        if not row:
            raise HTTPException(status_code=404, detail="Powiat not found in knowledge base.")

        powiat = dict(row)
        p_id = powiat["id"]

        powiat_borders = [r[0] for r in conn.execute("SELECT border_powiat_name FROM powiat_borders_powiats WHERE powiat_id = ? ORDER BY border_powiat_name", (p_id,)).fetchall()]
        voiv_borders = [r[0] for r in conn.execute("SELECT voivodeship FROM powiat_borders_voivodeships WHERE powiat_id = ? ORDER BY voivodeship", (p_id,)).fetchall()]
        country_borders = [r[0] for r in conn.execute("SELECT country_name FROM powiat_borders_countries WHERE powiat_id = ? ORDER BY country_name", (p_id,)).fetchall()]
        plates = [r[0] for r in conn.execute("SELECT plate_code FROM powiat_registration_plates WHERE powiat_id = ? ORDER BY plate_code", (p_id,)).fetchall()]
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM powiat_major_rivers WHERE powiat_id = ? ORDER BY river_name", (p_id,)).fetchall()]
        water = [r[0] for r in conn.execute("SELECT water_name FROM powiat_water_access WHERE powiat_id = ?", (p_id,)).fetchall()]
        regions = [r[0] for r in conn.execute("SELECT region_name FROM powiat_landform_regions WHERE powiat_id = ?", (p_id,)).fetchall()]

        powiat["neighboring_powiats"] = powiat_borders
        powiat["neighboring_voivodeships"] = voiv_borders
        powiat["neighboring_countries"] = country_borders
        powiat["registration_plates"] = plates
        powiat["major_rivers"] = rivers
        powiat["water_access"] = water
        powiat["landform_regions"] = regions

        return powiat
    finally:
        conn.close()
