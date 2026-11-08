"""Deterministic deduction analysis using the local Countrydle playable fact catalog.

Illustrates narrowing candidate pools and compares target countries with recorded
common wrong guesses using actual catalog relations.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from country_eligibility import is_country_eligible
from countrydle.local_answering import canonical_country_name, expand_geographic_areas
from schemas.blog import (
    CandidateFunnelStep,
    DeductionAnalysis,
    WrongGuessComparison,
    WrongGuessStat,
)
from utils.water_hierarchy import is_marine_water_body

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent  # server
DATA_DIR = BASE_DIR / "data" if (BASE_DIR / "data").exists() else BASE_DIR.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "country_facts.sqlite"

DEFAULT_PROVENANCE = "Current stored Countrydle country catalog facts (country_facts.sqlite)"
DEFAULT_DISCLAIMER = (
    "Illustrative deduction model based on present catalog facts; "
    "this is not a recorded single-player walkthrough."
)


@dataclass(frozen=True)
class CatalogCountry:
    id: int
    name: str
    official_name: Optional[str]
    cca2: Optional[str]
    cca3: Optional[str]
    region: Optional[str]
    subregion: Optional[str]
    capital: Optional[str]
    population: Optional[int]
    area_km2: Optional[float]
    continents: tuple[str, ...]
    subregions: tuple[str, ...]
    borders: tuple[str, ...]
    water_bodies: tuple[str, ...]
    # marine_status: "coastal" (has >=1 open-sea marine body),
    #                "inland_only" (has water bodies, but all are inland/endorheic like Caspian Sea),
    #                "unknown" (no water records in catalog; not assumed landlocked)
    marine_status: str
    is_eligible: bool


def _resolve_facts_db(source: Optional[Union[str, Path, sqlite3.Connection]] = None) -> Optional[sqlite3.Connection]:
    if isinstance(source, sqlite3.Connection):
        return source
    if source is not None:
        p = Path(source)
        if p.exists():
            return sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
        return None

    if DEFAULT_DB_PATH.exists():
        return sqlite3.connect(f"{DEFAULT_DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    return None


def _load_catalog(conn: sqlite3.Connection) -> Dict[int, CatalogCountry]:
    """Bulk-load all catalog countries and relations in one pass to avoid N+1 queries.

    Schema errors are not masked; relations are query-aligned with evaluator standards.
    """
    conn.row_factory = sqlite3.Row

    # 1. Base country rows
    country_rows = conn.execute(
        "SELECT id, app_country_name, official_name, cca2, cca3, region, subregion, capital, population, area_km2 "
        "FROM countries"
    ).fetchall()
    if not country_rows:
        return {}

    # 2. Continents (ordered deterministically)
    continent_map: Dict[int, List[str]] = {}
    for r in conn.execute("SELECT country_id, continent FROM country_continents ORDER BY continent ASC").fetchall():
        continent_map.setdefault(r[0], []).append(r[1])

    # 3. Subregions (aligned with evaluator: country_subregions + expand_geographic_areas)
    subregion_map: Dict[int, Set[str]] = {}
    for r in conn.execute("SELECT country_id, subregion_name FROM country_subregions").fetchall():
        subregion_map.setdefault(r[0], set()).add(r[1])

    # Map from canonical key to canonical app_country_name display
    canonical_to_app: Dict[str, str] = {
        canonical_country_name(r["app_country_name"]): r["app_country_name"]
        for r in country_rows
    }

    # 4. Borders (deduplicated and mapped to canonical app_country_name)
    border_map: Dict[int, Set[str]] = {}
    for r in conn.execute("SELECT country_id, border_country_name FROM country_borders").fetchall():
        raw_b = r[1]
        canon_b = canonical_country_name(raw_b)
        app_b = canonical_to_app.get(canon_b, raw_b)
        border_map.setdefault(r[0], set()).add(app_b)
    # 5. Water access
    water_map: Dict[int, List[str]] = {}
    for r in conn.execute("SELECT country_id, water_body FROM country_water_access ORDER BY water_body ASC").fetchall():
        water_map.setdefault(r[0], []).append(r[1])

    catalog: Dict[int, CatalogCountry] = {}
    for r in country_rows:
        cid = r["id"]
        cname = r["app_country_name"]
        raw_conts = continent_map.get(cid) or []
        waters = tuple(water_map.get(cid) or [])
        raw_subs = subregion_map.get(cid) or set()
        expanded_subs = expand_geographic_areas(raw_subs) if raw_subs else set()

        if waters:
            if any(is_marine_water_body(w) for w in waters):
                marine_status = "coastal"
            else:
                marine_status = "inland_only"
        else:
            marine_status = "unknown"

        eligible = is_country_eligible(cname, "countrydle")

        catalog[cid] = CatalogCountry(
            id=cid,
            name=cname,
            official_name=r["official_name"],
            cca2=r["cca2"],
            cca3=r["cca3"],
            region=r["region"],
            subregion=r["subregion"],
            capital=r["capital"],
            population=r["population"],
            area_km2=r["area_km2"],
            continents=tuple(sorted(set(raw_conts))),
            subregions=tuple(sorted(expanded_subs)),
            borders=tuple(sorted(border_map.get(cid) or set())),
            water_bodies=waters,
            marine_status=marine_status,
            is_eligible=eligible,
        )

    return catalog


def compute_candidate_funnel(
    catalog_or_source: Union[Dict[int, CatalogCountry], str, Path, sqlite3.Connection],
    target_name: str,
) -> List[CandidateFunnelStep]:
    """Compute step-by-step candidate pool reduction from catalog facts without fabricated uniqueness.

    Unknown and unrecorded candidate relations are conservatively retained at each filter step.
    """
    if isinstance(catalog_or_source, dict):
        catalog = catalog_or_source
        owns_conn, conn = False, None
    else:
        owns_conn = not isinstance(catalog_or_source, sqlite3.Connection)
        conn = _resolve_facts_db(catalog_or_source)
        if not conn:
            return []
        try:
            catalog = _load_catalog(conn)
        finally:
            if owns_conn and conn:
                conn.close()

    if not catalog:
        return []

    target_canon = canonical_country_name(target_name.strip())
    target = next((c for c in catalog.values() if canonical_country_name(c.name) == target_canon), None)
    if not target:
        return []

    # Initial pool: all eligible playable countries in Countrydle (195 playable nations)
    playable_pool = {cid: c for cid, c in catalog.items() if c.is_eligible}
    if not playable_pool or target.id not in playable_pool:
        return []

    steps: List[CandidateFunnelStep] = []
    current_pool = playable_pool

    # Step 0: Playable Country Catalog baseline
    steps.append(CandidateFunnelStep(
        criterion="Playable Country Catalog",
        explanation="Initial set of all recognized playable countries in the Countrydle mode.",
        remaining_count=len(current_pool),
        sample_candidates=sorted([c.name for c in current_pool.values() if c.id != target.id])[:4],
    ))

    # Step 1: Continent filter (retains countries with unknown/empty continents)
    if target.continents:
        target_continent = target.continents[0]
        narrowed = {
            cid: c for cid, c in current_pool.items()
            if target_continent in c.continents or not c.continents
        }
        if narrowed and target.id in narrowed:
            current_pool = narrowed
            steps.append(CandidateFunnelStep(
                criterion=f"Continent: {target_continent}",
                explanation=f"Filtering for playable nations situated in {target_continent} (retaining unclassified candidates).",
                remaining_count=len(current_pool),
                sample_candidates=sorted([c.name for c in current_pool.values() if c.id != target.id])[:4],
            ))

    # Step 2: Maritime access / Inland Water / Unknown
    # Retains countries with unknown water records
    if target.marine_status == "coastal":
        marine_waters = [w for w in target.water_bodies if is_marine_water_body(w)]
        water_sample = f" ({', '.join(sorted(marine_waters)[:2])})" if marine_waters else ""
        narrowed = {
            cid: c for cid, c in current_pool.items()
            if c.marine_status == "coastal" or c.marine_status == "unknown"
        }
        if narrowed and target.id in narrowed:
            current_pool = narrowed
            steps.append(CandidateFunnelStep(
                criterion=f"Maritime Access: Coastal{water_sample}",
                explanation="Eliminating nations known to have solely inland waters or no open-sea marine coastline (retaining unverified candidates).",
                remaining_count=len(current_pool),
                sample_candidates=sorted([c.name for c in current_pool.values() if c.id != target.id])[:4],
            ))
    elif target.marine_status == "inland_only":
        inland_sample = [w for w in target.water_bodies if not is_marine_water_body(w)]
        water_sample = f" ({', '.join(sorted(inland_sample)[:2])})" if inland_sample else ""
        narrowed = {
            cid: c for cid, c in current_pool.items()
            if c.marine_status in ("inland_only", "unknown")
        }
        if narrowed and target.id in narrowed:
            current_pool = narrowed
            steps.append(CandidateFunnelStep(
                criterion=f"Maritime Access: Inland Water Only{water_sample}",
                explanation="Filtering for nations bordering inland endorheic water bodies without direct open-sea marine access (retaining unverified candidates).",
                remaining_count=len(current_pool),
                sample_candidates=sorted([c.name for c in current_pool.values() if c.id != target.id])[:4],
            ))

    # Step 3: Subregion (retains countries with unknown/empty subregions)
    if target.subregions and len(current_pool) > 1:
        # Pick the most specific subregion that narrows the pool
        best_sub = None
        best_sub_narrowed: Dict[int, CatalogCountry] = {}
        for sub in sorted(target.subregions):
            cand_pool = {
                cid: c for cid, c in current_pool.items()
                if sub in c.subregions or not c.subregions
            }
            if 0 < len(cand_pool) < len(current_pool) and target.id in cand_pool:
                if not best_sub_narrowed or len(cand_pool) < len(best_sub_narrowed):
                    best_sub = sub
                    best_sub_narrowed = cand_pool

        if best_sub and best_sub_narrowed:
            current_pool = best_sub_narrowed
            steps.append(CandidateFunnelStep(
                criterion=f"Subregion: {best_sub}",
                explanation=f"Narrowing candidates to the {best_sub} area (retaining unclassified candidates).",
                remaining_count=len(current_pool),
                sample_candidates=sorted([c.name for c in current_pool.values() if c.id != target.id])[:4],
            ))

    # Step 4: Neighboring Border Feature (retains countries with unrecorded borders)
    if len(current_pool) > 1 and target.borders:
        best_neighbor = None
        best_narrowed: Dict[int, CatalogCountry] = {}
        for neighbor in sorted(target.borders):
            cand_pool = {
                cid: c for cid, c in current_pool.items()
                if any(canonical_country_name(b) == canonical_country_name(neighbor) for b in c.borders) or not c.borders
            }
            if 0 < len(cand_pool) < len(current_pool) and target.id in cand_pool:
                if not best_narrowed or len(cand_pool) < len(best_narrowed):
                    best_neighbor = neighbor
                    best_narrowed = cand_pool

        if best_neighbor and best_narrowed:
            current_pool = best_narrowed
            steps.append(CandidateFunnelStep(
                criterion=f"Border Neighbor: Shares land border with {best_neighbor}",
                explanation=f"Filtering candidates that border {best_neighbor} (retaining unrecorded border candidates).",
                remaining_count=len(current_pool),
                sample_candidates=sorted([c.name for c in current_pool.values() if c.id != target.id])[:4],
            ))

    # Final outcome: TRUTHFUL report of remaining pool (NEVER force remaining_count=1 if pool > 1)
    if len(current_pool) == 1:
        steps.append(CandidateFunnelStep(
            criterion=f"Target: {target.name}",
            explanation=f"Identified solution: {target.name} uniquely satisfies all catalog traits.",
            remaining_count=1,
            sample_candidates=[target.name],
        ))
    elif len(current_pool) > 1:
        remaining_names = sorted(c.name for c in current_pool.values())
        steps.append(CandidateFunnelStep(
            criterion=f"Remaining Candidates ({len(current_pool)})",
            explanation=(
                f"Catalog traits narrow candidate pool to {len(current_pool)} candidates: "
                f"{', '.join(remaining_names)}."
            ),
            remaining_count=len(current_pool),
            sample_candidates=remaining_names[:4],
        ))

    return steps


def compute_wrong_guess_comparisons(
    catalog_or_source: Union[Dict[int, CatalogCountry], str, Path, sqlite3.Connection],
    target_name: str,
    wrong_guesses: List[WrongGuessStat],
) -> List[WrongGuessComparison]:
    """Compare target country with recorded common wrong guesses using catalog facts."""
    if not wrong_guesses:
        return []

    if isinstance(catalog_or_source, dict):
        catalog = catalog_or_source
        owns_conn, conn = False, None
    else:
        owns_conn = not isinstance(catalog_or_source, sqlite3.Connection)
        conn = _resolve_facts_db(catalog_or_source)
        if not conn:
            return []
        try:
            catalog = _load_catalog(conn)
        finally:
            if owns_conn and conn:
                conn.close()

    if not catalog:
        return []

    target_canon = canonical_country_name(target_name.strip())
    target = next((c for c in catalog.values() if canonical_country_name(c.name) == target_canon), None)
    target_name_clean = target.name if target else target_name

    comparisons: List[WrongGuessComparison] = []
    for pf in wrong_guesses:
        guess_str = pf.guess.strip()
        guess_canon = canonical_country_name(guess_str)
        guess_rec = next((c for c in catalog.values() if canonical_country_name(c.name) == guess_canon), None)

        if not guess_rec:
            # Entity not recognized in catalog
            comparisons.append(WrongGuessComparison(
                guess=guess_str,
                count=pf.count,
                shared_traits=[],
                differences=[
                    f"'{guess_str}' is an unknown entity not found in catalog facts."
                ],
                guess_facts={
                    "capital": "Unknown",
                    "continent": "Unknown",
                    "region": "Unknown",
                    "coastline": "Unknown",
                    "borders": "Unknown",
                },
                target_facts=_format_catalog_country_facts(target) if target else {},
            ))
            continue

        shared_traits: List[str] = []
        differences: List[str] = []

        # 1. Continent / Subregion
        t_cont = target.continents[0] if (target and target.continents) else None
        g_cont = guess_rec.continents[0] if guess_rec.continents else None
        if t_cont and g_cont and t_cont == g_cont:
            shared_traits.append(f"Both situated in {t_cont}")

        # Check overlapping subregions
        common_subs = set(target.subregions).intersection(set(guess_rec.subregions)) if target else set()
        if common_subs:
            shared_traits.append(f"Both located within {sorted(common_subs)[0]}")

        # 2. Maritime access
        if target:
            if target.marine_status == guess_rec.marine_status and target.marine_status != "unknown":
                if target.marine_status == "coastal":
                    shared_traits.append("Both have direct maritime coastline to open oceans")
                elif target.marine_status == "inland_only":
                    shared_traits.append("Both border inland endorheic water bodies")
            elif target.marine_status != "unknown" and guess_rec.marine_status != "unknown":
                t_desc = "coastal" if target.marine_status == "coastal" else "inland/landlocked"
                g_desc = "coastal" if guess_rec.marine_status == "coastal" else "inland/landlocked"
                differences.append(f"Marine coastline: {target_name_clean} is {t_desc}, whereas {guess_rec.name} is {g_desc}")

        # 3. Direct borders & common neighbors (preserving canonical country name casing)
        t_borders = target.borders if target else ()
        g_borders = guess_rec.borders
        t_canon = canonical_country_name(target_name_clean) if target else ""
        g_canon = canonical_country_name(guess_rec.name)
        if any(canonical_country_name(b) == g_canon for b in t_borders) or any(canonical_country_name(b) == t_canon for b in g_borders):
            shared_traits.append("Direct neighbors sharing a land border")

        # Find common border neighbors preserving canonical casing from catalog
        t_border_canon = {canonical_country_name(b): b for b in t_borders}
        g_border_canon = {canonical_country_name(b): b for b in g_borders}
        common_keys = sorted(set(t_border_canon.keys()).intersection(set(g_border_canon.keys())))
        if common_keys:
            display_common = [t_border_canon[k] for k in common_keys[:3]]
            shared_traits.append(f"Both border {', '.join(display_common)}")
        comparisons.append(WrongGuessComparison(
            guess=guess_rec.name,
            count=pf.count,
            shared_traits=shared_traits,
            differences=differences,
            guess_facts=_format_catalog_country_facts(guess_rec),
            target_facts=_format_catalog_country_facts(target) if target else {},
        ))

    return comparisons


def _format_catalog_country_facts(record: CatalogCountry) -> Dict[str, Optional[str]]:
    continents = ", ".join(record.continents) if record.continents else "Unrecorded in catalog"
    if record.marine_status == "coastal":
        marine_waters = [w for w in record.water_bodies if is_marine_water_body(w)]
        coastline = f"Coastal ({', '.join(marine_waters)})" if marine_waters else "Coastal"
    elif record.marine_status == "inland_only":
        coastline = f"Inland water only ({', '.join(record.water_bodies)})"
    else:
        coastline = "Unrecorded in catalog"

    sub_display = record.region or (record.subregions[0] if record.subregions else "N/A")

    return {
        "capital": record.capital or "N/A",
        "continent": continents,
        "region": sub_display,
        "coastline": coastline,
        "borders": ", ".join(sorted(record.borders)) if record.borders else "None",
    }


def get_deduction_analysis(
    db_source: Optional[Union[str, Path, sqlite3.Connection]],
    target_name: str,
    wrong_guesses: List[WrongGuessStat],
    *,
    is_past_day: bool,
) -> DeductionAnalysis:
    """Build dynamic present-catalog deduction analysis for past-day recaps."""
    if not is_past_day:
        return DeductionAnalysis(has_analysis=False)

    conn = _resolve_facts_db(db_source)
    if not conn:
        return DeductionAnalysis(has_analysis=False)

    owns_conn = not isinstance(db_source, sqlite3.Connection)
    try:
        catalog = _load_catalog(conn)
    finally:
        if owns_conn and conn:
            conn.close()

    funnel = compute_candidate_funnel(catalog, target_name)
    comparisons = compute_wrong_guess_comparisons(catalog, target_name, wrong_guesses)

    has_data = len(funnel) > 0 or len(comparisons) > 0
    return DeductionAnalysis(
        has_analysis=has_data,
        catalog_provenance=DEFAULT_PROVENANCE,
        disclaimer=DEFAULT_DISCLAIMER,
        candidate_funnel=funnel,
        wrong_guess_comparisons=comparisons,
    )
