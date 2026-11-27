import logging
import random
import sys
from collections import deque
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.user import User
from explore.atlas import get_db_connection
from powiat_names import resolve_powiat_name
from users.utils import get_current_or_guest_user
from utils.guest_session import get_guest_identity

logger = logging.getLogger(__name__)
router = APIRouter()


class BorderHopVerifyRequest(BaseModel):
    mode: str = "countries"
    start: str
    target: str
    path: List[str]
    is_daily: Optional[bool] = None
    elapsed_seconds: Optional[float] = None


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


def _cache_holder():
    return sys.modules.get("explore") or sys.modules[__name__]


def _get_cache(name: str) -> Any:
    return getattr(_cache_holder(), name, None)


def _set_cache(name: str, value: Any) -> None:
    setattr(_cache_holder(), name, value)


def _normalize_mode(mode: str) -> str:
    if mode not in ("countries", "countrydle", "us_states", "us_statedle", "powiaty"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported mode. Use 'countries', 'us_states', or 'powiaty'.",
        )
    if mode in ("us_states", "us_statedle"):
        return "us_states"
    if mode == "powiaty":
        return "powiaty"
    return "countries"


def _get_country_graph() -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str]]:
    adj = _get_cache("_COUNTRY_ADJACENCY")
    lookup = _get_cache("_COUNTRY_LOOKUP")
    islands = _get_cache("_COUNTRY_ISLANDS")
    if adj is not None and lookup is not None and islands is not None:
        return adj, lookup, islands

    conn = get_db_connection("country_facts.sqlite")
    try:
        names = {r[0]: r[0] for r in conn.execute("SELECT app_country_name FROM countries")}
        lookup = {name.lower(): name for name in names}
        adj = {name: set() for name in names}

        rows = conn.execute(
            """
            SELECT c.app_country_name, b.border_country_name
            FROM countries c
            JOIN country_borders b ON c.id = b.country_id
            """
        ).fetchall()

        for c_name, b_name in rows:
            b_clean = b_name.strip()
            b_canon = BORDER_CANONICAL_ALIASES.get(b_clean.lower(), b_clean)
            actual_b = lookup.get(b_canon.lower(), b_canon)
            if actual_b in adj and c_name in adj:
                adj[c_name].add(actual_b)
                adj[actual_b].add(c_name)

        islands = {name for name, nbrs in adj.items() if len(nbrs) == 0}
        _set_cache("_COUNTRY_ADJACENCY", adj)
        _set_cache("_COUNTRY_LOOKUP", lookup)
        _set_cache("_COUNTRY_ISLANDS", islands)
        return adj, lookup, islands
    finally:
        conn.close()


def _get_us_state_graph() -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str]]:
    adj = _get_cache("_US_STATE_ADJACENCY")
    lookup = _get_cache("_US_STATE_LOOKUP")
    islands = _get_cache("_US_STATE_ISLANDS")
    if adj is not None and lookup is not None and islands is not None:
        return adj, lookup, islands

    conn = get_db_connection("us_state_facts.sqlite")
    try:
        names = {r[0]: r[0] for r in conn.execute("SELECT name FROM us_states")}
        lookup = {name.lower(): name for name in names}
        adj = {name: set() for name in names}

        rows = conn.execute(
            """
            SELECT s.name, b.border_state_name
            FROM us_states s
            JOIN us_state_borders_states b ON s.id = b.state_id
            """
        ).fetchall()

        for s_name, b_name in rows:
            b_clean = b_name.strip()
            actual_b = lookup.get(b_clean.lower(), b_clean)
            if actual_b in adj and s_name in adj:
                adj[s_name].add(actual_b)
                adj[actual_b].add(s_name)

        islands = {name for name, nbrs in adj.items() if len(nbrs) == 0}
        _set_cache("_US_STATE_ADJACENCY", adj)
        _set_cache("_US_STATE_LOOKUP", lookup)
        _set_cache("_US_STATE_ISLANDS", islands)
        return adj, lookup, islands
    finally:
        conn.close()


def _get_powiat_graph() -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str]]:
    adj = _get_cache("_POWIAT_ADJACENCY")
    lookup = _get_cache("_POWIAT_LOOKUP")
    islands = _get_cache("_POWIAT_ISLANDS")
    if adj is not None and lookup is not None and islands is not None:
        return adj, lookup, islands

    conn = get_db_connection("powiat_facts.sqlite")
    try:
        rows = conn.execute("SELECT id, name FROM powiats").fetchall()
        names = {row[1] for row in rows}
        lookup = {name.lower(): name for name in names}
        adj = {name: set() for name in names}

        borders = conn.execute(
            """
            SELECT p.name, b.border_powiat_name
            FROM powiats p
            JOIN powiat_borders_powiats b ON p.id = b.powiat_id
            """
        ).fetchall()
        for powiat_name, border_name in borders:
            actual_border = lookup.get(border_name.strip().lower())
            if actual_border in adj and powiat_name in adj:
                adj[powiat_name].add(actual_border)
                adj[actual_border].add(powiat_name)

        islands = {name for name, neighbors in adj.items() if not neighbors}
        _set_cache("_POWIAT_ADJACENCY", adj)
        _set_cache("_POWIAT_LOOKUP", lookup)
        _set_cache("_POWIAT_ISLANDS", islands)
        return adj, lookup, islands
    finally:
        conn.close()


def _get_graph_for_mode(normalized_mode: str) -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str]]:
    if normalized_mode == "countries":
        return _get_country_graph()
    if normalized_mode == "us_states":
        return _get_us_state_graph()
    return _get_powiat_graph()


def canonicalize_entity_name(name: str, mode: str = "countries") -> Optional[str]:
    clean = name.strip()
    if mode in ("countries", "countrydle"):
        _, lookup, _ = _get_country_graph()
        clean = BORDER_CANONICAL_ALIASES.get(clean.lower(), clean)
        return lookup.get(clean.lower())
    if mode in ("us_states", "us_statedle"):
        _, lookup, _ = _get_us_state_graph()
        return lookup.get(clean.lower())
    if mode == "powiaty":
        _, lookup, _ = _get_powiat_graph()
        canonical_name = lookup.get(clean.lower())
        if canonical_name:
            return canonical_name
        conn = get_db_connection("powiat_facts.sqlite")
        try:
            return resolve_powiat_name(conn, clean)
        finally:
            conn.close()
    return None


def find_shortest_border_path(start: str, target: str, mode: str = "countries") -> Optional[List[str]]:
    if mode in ("countries", "countrydle"):
        adj, _, _ = _get_country_graph()
    elif mode in ("us_states", "us_statedle"):
        adj, _, _ = _get_us_state_graph()
    elif mode == "powiaty":
        adj, _, _ = _get_powiat_graph()
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
    if mode in ("countries", "countrydle"):
        cache_key = "_COUNTRY_CONNECTED_PAIRS"
        adj_loader = _get_country_graph
    elif mode in ("us_states", "us_statedle"):
        cache_key = "_US_STATE_CONNECTED_PAIRS"
        adj_loader = _get_us_state_graph
    elif mode == "powiaty":
        cache_key = "_POWIAT_CONNECTED_PAIRS"
        adj_loader = _get_powiat_graph
    else:
        return []

    cached = _get_cache(cache_key)
    if cached is not None:
        return cached
    adj, _, _ = adj_loader()

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
    _set_cache(cache_key, pairs)
    return pairs


def _get_daily_border_hop_pair(normalized_mode: str, challenge_date: date) -> Optional[Tuple[str, str]]:
    pairs = _get_connected_pairs(normalized_mode, min_hops=3, max_hops=5)
    if not pairs:
        pairs = _get_connected_pairs(normalized_mode, min_hops=2, max_hops=6)
    if not pairs:
        return None
    rng = random.Random(challenge_date.isoformat())
    chosen_pair = rng.choice(pairs)
    if rng.random() < 0.5:
        return chosen_pair[0], chosen_pair[1]
    return chosen_pair[1], chosen_pair[0]


@router.get("/border-hop/challenge")
async def get_border_hop_challenge(
    mode: str = Query("countries"),
    target: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    seed: Optional[str] = Query(None),
):
    """Generate a deterministic border hop path-finding challenge."""
    normalized_mode = _normalize_mode(mode)
    adj, _, islands = _get_graph_for_mode(normalized_mode)

    if target:
        canon_target = canonicalize_entity_name(target, normalized_mode)
        if not canon_target:
            raise HTTPException(status_code=404, detail=f"Target '{target}' not found in {normalized_mode}.")

        if canon_target in islands or len(adj.get(canon_target, set())) == 0:
            return {
                "mode": normalized_mode, "start": None, "target": canon_target,
                "connected": False, "is_island": True, "optimal_hops": None,
                "optimal_path": None, "message": f"{canon_target} has no direct land borders.",
            }

        if origin:
            canon_origin = canonicalize_entity_name(origin, normalized_mode)
            if not canon_origin:
                raise HTTPException(status_code=404, detail=f"Origin '{origin}' not found in {normalized_mode}.")

            path = find_shortest_border_path(canon_origin, canon_target, normalized_mode)
            if not path or len(path) < 2:
                return {
                    "mode": normalized_mode, "start": canon_origin, "target": canon_target,
                    "connected": False, "is_island": canon_origin in islands, "optimal_hops": None,
                    "optimal_path": None, "message": f"No land border connection between {canon_origin} and {canon_target}.",
                }
            return {
                "mode": normalized_mode, "start": canon_origin, "target": canon_target,
                "connected": True, "is_island": False, "optimal_hops": len(path) - 1,
                "optimal_path": path, "message": None,
            }

        dist = {canon_target: 0}
        q = deque([canon_target])
        while q:
            curr = q.popleft()
            for nbr in sorted(adj.get(curr, set())):
                if nbr not in dist:
                    dist[nbr] = dist[curr] + 1
                    q.append(nbr)

        candidates = [node for node, d in dist.items() if 3 <= d <= 5] or [node for node, d in dist.items() if d >= 1]
        if not candidates:
            return {
                "mode": normalized_mode, "start": None, "target": canon_target,
                "connected": False, "is_island": True, "optimal_hops": None,
                "optimal_path": None, "message": f"{canon_target} has no connected neighbors.",
            }

        candidates.sort()
        rng = random.Random(seed or f"{date.today().isoformat()}:{canon_target}")
        chosen_origin = rng.choice(candidates)
        path = find_shortest_border_path(chosen_origin, canon_target, normalized_mode)
        return {
            "mode": normalized_mode, "start": chosen_origin, "target": canon_target,
            "connected": True, "is_island": False, "optimal_hops": len(path) - 1 if path else None,
            "optimal_path": path, "message": None,
        }

    if normalized_mode in ("powiaty", "us_states"):
        pairs = _get_connected_pairs(normalized_mode, min_hops=2, max_hops=1000)
    else:
        pairs = _get_connected_pairs(normalized_mode, min_hops=3, max_hops=5)
        if not pairs:
            pairs = _get_connected_pairs(normalized_mode, min_hops=2, max_hops=6)

    rng = random.Random(seed or date.today().isoformat())
    chosen_pair = rng.choice(pairs)
    start_entity, target_entity = (chosen_pair[0], chosen_pair[1]) if rng.random() < 0.5 else (chosen_pair[1], chosen_pair[0])
    path = find_shortest_border_path(start_entity, target_entity, normalized_mode)
    return {
        "mode": normalized_mode, "start": start_entity, "target": target_entity,
        "connected": True, "is_island": False, "optimal_hops": len(path) - 1 if path else None,
        "optimal_path": path, "message": None,
    }


@router.get("/border-hop/neighbors")
async def get_border_neighbors(
    name: str = Query(...),
    mode: str = Query("countries"),
):
    """Get bordering neighbors for a specific entity."""
    normalized_mode = _normalize_mode(mode)
    adj, _, _ = _get_graph_for_mode(normalized_mode)

    canon_name = canonicalize_entity_name(name, normalized_mode)
    if not canon_name:
        raise HTTPException(status_code=404, detail=f"'{name}' not found in {normalized_mode}.")

    nbrs = sorted(list(adj.get(canon_name, set())))
    return {"name": canon_name, "neighbors": nbrs, "is_island": len(nbrs) == 0}


@router.post("/border-hop/verify", response_model=BorderHopVerifyResponse)
async def verify_border_hop(
    payload: BorderHopVerifyRequest,
    request: Request,
    response: Response,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Verify a completed border hop path against ground-truth borders."""
    normalized_mode = _normalize_mode(payload.mode)
    adj, _, _ = _get_graph_for_mode(normalized_mode)

    canon_start = canonicalize_entity_name(payload.start, normalized_mode)
    canon_target = canonicalize_entity_name(payload.target, normalized_mode)
    if not canon_start:
        raise HTTPException(status_code=404, detail=f"Start entity '{payload.start}' not found.")
    if not canon_target:
        raise HTTPException(status_code=404, detail=f"Target entity '{payload.target}' not found.")

    if not payload.path:
        return BorderHopVerifyResponse(
            valid=False, hops=0, optimal_hops=None, is_optimal=False, rank=None, message="Path cannot be empty."
        )

    canonical_path: List[str] = []
    for step in payload.path:
        c_step = canonicalize_entity_name(step, normalized_mode)
        if not c_step:
            return BorderHopVerifyResponse(
                valid=False, hops=len(payload.path) - 1, optimal_hops=None, is_optimal=False, rank=None,
                message=f"Entity '{step}' not recognized in {normalized_mode}.",
            )
        canonical_path.append(c_step)

    optimal_path = find_shortest_border_path(canon_start, canon_target, normalized_mode)
    optimal_hops = len(optimal_path) - 1 if optimal_path else None

    if canonical_path[0] != canon_start:
        return BorderHopVerifyResponse(
            valid=False, hops=len(canonical_path) - 1, optimal_hops=optimal_hops, is_optimal=False, rank=None,
            optimal_path=optimal_path,
            message=f"Path must start at '{canon_start}', but started at '{canonical_path[0]}'.",
        )
    if canonical_path[-1] != canon_target:
        return BorderHopVerifyResponse(
            valid=False, hops=len(canonical_path) - 1, optimal_hops=optimal_hops, is_optimal=False, rank=None,
            optimal_path=optimal_path,
            message=f"Path must end at '{canon_target}', but ended at '{canonical_path[-1]}'.",
        )

    for i in range(len(canonical_path) - 1):
        curr_node, next_node = canonical_path[i], canonical_path[i + 1]
        if next_node not in adj.get(curr_node, set()):
            return BorderHopVerifyResponse(
                valid=False, hops=len(canonical_path) - 1, optimal_hops=optimal_hops, is_optimal=False, rank=None,
                optimal_path=optimal_path, error_step=[curr_node, next_node],
                message=f"'{next_node}' does not share a land border with '{curr_node}'.",
            )

    hops = len(canonical_path) - 1
    is_optimal = optimal_hops is not None and hops == optimal_hops
    if is_optimal:
        rank, points = "gold", 1000
    elif optimal_hops is not None and hops <= optimal_hops + 2:
        rank, points = "silver", 700
    else:
        rank, points = "bronze", 400

    today_utc = datetime.now(timezone.utc).date()
    should_record = payload.is_daily is True
    if not should_record and payload.is_daily is not False:
        daily_pair = _get_daily_border_hop_pair(normalized_mode, today_utc)
        if daily_pair == (canon_start, canon_target):
            should_record = True
        elif date.today() != today_utc and _get_daily_border_hop_pair(normalized_mode, date.today()) == (canon_start, canon_target):
            should_record = True

    if should_record:
        try:
            from stats.service import record_mode_result

            record_mode = (
                "border_hop"
                if normalized_mode == "countries"
                else ("border_hop:powiaty" if normalized_mode == "powiaty" else "border_hop:us_states")
            )
            user_id = user.id if user is not None else None
            guest_id = None if user is not None else get_guest_identity(request, response)
            await record_mode_result(
                session,
                mode=record_mode,
                record_date=today_utc,
                user_id=user_id,
                guest_id=guest_id,
                completed=True,
                won=True,
                points=points,
                guesses_used=hops,
                score=hops,
                max_score=optimal_hops,
                elapsed_seconds=payload.elapsed_seconds,
            )
        except Exception as exc:
            logger.warning("Could not record border_hop daily result: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass

    return BorderHopVerifyResponse(
        valid=True, hops=hops, optimal_hops=optimal_hops, is_optimal=is_optimal, rank=rank, optimal_path=optimal_path
    )
