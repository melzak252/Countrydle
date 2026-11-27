from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from db.models.continental import ContinentCode, ContinentalDay, ContinentalState
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.powiatdle import PowiatdleDay, PowiatdleState
from db.models.us_statedle import USStatedleDay, USStatedleState
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleState
from game_logic import (
    CONTINENTAL_CONFIG,
    COUNTRYDLE_CONFIG,
    FLAGDLE_CONFIG,
    POWIATDLE_CONFIG,
    USSTATEDLE_CONFIG,
    WOJEWODZTWDLE_CONFIG,
)

# Optional future model imports (Areas 1-3) guarded so this branch runs standalone.
try:
    from db.models.countydle import CountydleDay, CountydleState  # type: ignore[import-not-found]
except ImportError:
    CountydleDay = None
    CountydleState = None


AdapterKind = Literal["qa_daily", "guess_daily", "heraldry_daily", "quiz_run", "mode_result"]
ModeKind = Literal["qa_daily", "guess_daily", "quiz_run", "score_daily"]


@dataclass(frozen=True)
class ModeStatsSpec:
    mode: str
    adapter: AdapterKind
    mode_kind: ModeKind
    is_daily: bool = True
    max_questions: Optional[int] = None
    max_guesses: Optional[int] = None
    max_score: Optional[int] = None
    state_model: Any = None
    day_model: Any = None
    continent: Any = None
    guest_mode_key: Optional[str] = None
    symbol_mode: Optional[str] = None
    entity_scope: Optional[str] = None
    record_mode: Optional[str] = None


def _build_registry() -> Dict[str, ModeStatsSpec]:
    registry: Dict[str, ModeStatsSpec] = {
        # 8 True/False Daily QA Modes
        "countrydle": ModeStatsSpec(
            mode="countrydle",
            adapter="qa_daily",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=COUNTRYDLE_CONFIG.max_questions,
            max_guesses=COUNTRYDLE_CONFIG.max_guesses,
            state_model=CountrydleState,
            day_model=CountrydleDay,
            guest_mode_key="countrydle",
        ),
        "wojewodztwodle": ModeStatsSpec(
            mode="wojewodztwodle",
            adapter="qa_daily",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=WOJEWODZTWDLE_CONFIG.max_questions,
            max_guesses=WOJEWODZTWDLE_CONFIG.max_guesses,
            state_model=WojewodztwodleState,
            day_model=WojewodztwodleDay,
            guest_mode_key="wojewodztwodle",
        ),
        "powiatdle": ModeStatsSpec(
            mode="powiatdle",
            adapter="qa_daily",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=POWIATDLE_CONFIG.max_questions,
            max_guesses=POWIATDLE_CONFIG.max_guesses,
            state_model=PowiatdleState,
            day_model=PowiatdleDay,
            guest_mode_key="powiatdle",
        ),
        "us_statedle": ModeStatsSpec(
            mode="us_statedle",
            adapter="qa_daily",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=USSTATEDLE_CONFIG.max_questions,
            max_guesses=USSTATEDLE_CONFIG.max_guesses,
            state_model=USStatedleState,
            day_model=USStatedleDay,
            guest_mode_key="us_statedle",
        ),
        # Daily Visual Guess Modes
        "flagdle": ModeStatsSpec(
            mode="flagdle",
            adapter="guess_daily",
            mode_kind="guess_daily",
            is_daily=True,
            max_questions=0,
            max_guesses=FLAGDLE_CONFIG.max_guesses,
            state_model=FlagdleState,
            day_model=FlagdleDay,
            guest_mode_key="flagdle",
        ),
        "heraldry": ModeStatsSpec(
            mode="heraldry",
            adapter="heraldry_daily",
            mode_kind="guess_daily",
            is_daily=True,
            max_guesses=8,
            symbol_mode="coat",
            entity_scope="county",
        ),
        "county_flags": ModeStatsSpec(
            mode="county_flags",
            adapter="heraldry_daily",
            mode_kind="guess_daily",
            is_daily=True,
            max_guesses=8,
            symbol_mode="flag",
            entity_scope="county",
        ),
        # Full-Pool Timed Quizzes (Powiat Coats & Flags)
        "coats_quiz": ModeStatsSpec(
            mode="coats_quiz",
            adapter="quiz_run",
            mode_kind="quiz_run",
            is_daily=False,
            max_score=380,
            symbol_mode="coat",
            entity_scope="county",
        ),
        "county_flags_quiz": ModeStatsSpec(
            mode="county_flags_quiz",
            adapter="quiz_run",
            mode_kind="quiz_run",
            is_daily=False,
            max_score=380,
            symbol_mode="flag",
            entity_scope="county",
        ),
        # Stateless Daily Modes recorded via mode_result_records
        "flag_shades": ModeStatsSpec(
            mode="flag_shades",
            adapter="mode_result",
            mode_kind="guess_daily",
            is_daily=True,
            max_guesses=12,
            record_mode="flag_shades",
        ),
        "border_hop": ModeStatsSpec(
            mode="border_hop",
            adapter="mode_result",
            mode_kind="score_daily",
            is_daily=True,
            record_mode="border_hop",
        ),
        "border_hop:us_states": ModeStatsSpec(
            mode="border_hop:us_states",
            adapter="mode_result",
            mode_kind="score_daily",
            is_daily=True,
            record_mode="border_hop:us_states",
        ),
        # New Area 1-3 Modes (ready adapters)
        "plates_quiz": ModeStatsSpec(
            mode="plates_quiz",
            adapter="quiz_run",
            mode_kind="quiz_run",
            is_daily=False,
            max_score=380,
            symbol_mode="plates",
            entity_scope="county",
        ),
        "map_quiz_london_boroughs": ModeStatsSpec(
            mode="map_quiz_london_boroughs",
            adapter="mode_result",
            mode_kind="quiz_run",
            is_daily=False,
            max_score=33,
            record_mode="map_quiz_london_boroughs",
        ),
        "map_quiz_england_counties": ModeStatsSpec(
            mode="map_quiz_england_counties",
            adapter="mode_result",
            mode_kind="quiz_run",
            is_daily=False,
            max_score=48,
            record_mode="map_quiz_england_counties",
        ),
    }

    # 4 Continental modes
    for code in (
        ContinentCode.EUROPE,
        ContinentCode.ASIA,
        ContinentCode.AFRICA,
        ContinentCode.AMERICAS,
    ):
        key = f"continental:{code.value}"
        registry[key] = ModeStatsSpec(
            mode=key,
            adapter="qa_daily",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=CONTINENTAL_CONFIG.max_questions,
            max_guesses=CONTINENTAL_CONFIG.max_guesses,
            state_model=ContinentalState,
            day_model=ContinentalDay,
            continent=code,
            guest_mode_key=key,
        )

    # Regional symbols daily & quiz modes
    regional_sizes = {
        "voivodeships": 16,
        "london_boroughs": 33,
        "england_counties": 48,
    }
    for scope, pool_size in regional_sizes.items():
        for symbol in ("coat", "flag"):
            daily_key = f"regional_symbols:{scope}:{symbol}"
            registry[daily_key] = ModeStatsSpec(
                mode=daily_key,
                adapter="heraldry_daily",
                mode_kind="guess_daily",
                is_daily=True,
                max_guesses=8,
                symbol_mode=symbol,
                entity_scope=scope,
            )
            quiz_key = f"{daily_key}:quiz"
            registry[quiz_key] = ModeStatsSpec(
                mode=quiz_key,
                adapter="quiz_run",
                mode_kind="quiz_run",
                is_daily=False,
                max_score=pool_size,
                symbol_mode=symbol,
                entity_scope=scope,
            )

    # English Countydle (uses dedicated models once merged, otherwise falls back to mode_result)
    if CountydleDay is not None and CountydleState is not None:
        registry["countydle"] = ModeStatsSpec(
            mode="countydle",
            adapter="qa_daily",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=10,
            max_guesses=3,
            state_model=CountydleState,
            day_model=CountydleDay,
            guest_mode_key="countydle",
        )
    else:
        registry["countydle"] = ModeStatsSpec(
            mode="countydle",
            adapter="mode_result",
            mode_kind="qa_daily",
            is_daily=True,
            max_questions=10,
            max_guesses=3,
            record_mode="countydle",
        )

    return registry


MODE_STATS_REGISTRY: Dict[str, ModeStatsSpec] = _build_registry()

MODE_ALIASES: Dict[str, str] = {
    "europe": "continental:europe",
    "asia": "continental:asia",
    "africa": "continental:africa",
    "americas": "continental:americas",
    "powiat_plates_quiz": "plates_quiz",
    "london_boroughs_quiz": "map_quiz_london_boroughs",
    "historic_counties_quiz": "map_quiz_england_counties",
    "english_countydle": "countydle",
}


def resolve_mode_spec(mode: str) -> Optional[ModeStatsSpec]:
    canonical = MODE_ALIASES.get(mode, mode)
    return MODE_STATS_REGISTRY.get(canonical)
