from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter

# Graph caches kept on the package module for backwards-compatible test monkeypatching.
_COUNTRY_ADJACENCY: Optional[Dict[str, Set[str]]] = None
_COUNTRY_LOOKUP: Optional[Dict[str, str]] = None
_COUNTRY_ISLANDS: Optional[Set[str]] = None
_COUNTRY_CONNECTED_PAIRS: Optional[List[Tuple[str, str, int]]] = None

_US_STATE_ADJACENCY: Optional[Dict[str, Set[str]]] = None
_US_STATE_LOOKUP: Optional[Dict[str, str]] = None
_US_STATE_ISLANDS: Optional[Set[str]] = None
_US_STATE_CONNECTED_PAIRS: Optional[List[Tuple[str, str, int]]] = None

_POWIAT_ADJACENCY: Optional[Dict[str, Set[str]]] = None
_POWIAT_LOOKUP: Optional[Dict[str, str]] = None
_POWIAT_ISLANDS: Optional[Set[str]] = None
_POWIAT_CONNECTED_PAIRS: Optional[List[Tuple[str, str, int]]] = None

from explore import atlas, border_hop  # noqa: E402
from explore.atlas import (  # noqa: E402
    GAME_MODES,
    deduplicate_border_names,
    get_country_detail,
    get_data_dir,
    get_db_connection,
    get_powiat_coat_svg,
    get_powiat_detail,
    get_us_state_detail,
    get_voivodeship_detail,
    list_countries,
    list_modes,
    list_powiats,
    list_us_states,
    list_voivodeships,
)
from explore.border_hop import (  # noqa: E402
    BORDER_CANONICAL_ALIASES,
    BorderHopVerifyRequest,
    BorderHopVerifyResponse,
    _get_connected_pairs,
    _get_country_graph,
    _get_daily_border_hop_pair,
    _get_powiat_graph,
    _get_us_state_graph,
    canonicalize_entity_name,
    find_shortest_border_path,
    get_border_hop_challenge,
    get_border_neighbors,
    verify_border_hop,
)

router = APIRouter(prefix="/explore", tags=["explore"])
router.include_router(atlas.router)
router.include_router(border_hop.router)

__all__ = [
    "router",
    "GAME_MODES",
    "BORDER_CANONICAL_ALIASES",
    "BorderHopVerifyRequest",
    "BorderHopVerifyResponse",
    "get_data_dir",
    "get_db_connection",
    "deduplicate_border_names",
    "canonicalize_entity_name",
    "find_shortest_border_path",
    "_get_country_graph",
    "_get_us_state_graph",
    "_get_powiat_graph",
    "_get_connected_pairs",
    "_get_daily_border_hop_pair",
    "list_modes",
    "list_countries",
    "get_country_detail",
    "list_us_states",
    "get_us_state_detail",
    "list_voivodeships",
    "get_voivodeship_detail",
    "list_powiats",
    "get_powiat_coat_svg",
    "get_powiat_detail",
    "get_border_hop_challenge",
    "get_border_neighbors",
    "verify_border_hop",
]
