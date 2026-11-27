"""Flagdle FastAPI router facade mounting gameplay, questions/sync, and Flag Shades."""

from __future__ import annotations

import logging
import os  # noqa: F401 - re-exported for test monkeypatching
import urllib.request  # noqa: F401 - re-exported for test monkeypatching

from fastapi import APIRouter

from countrydle.local_answering import execute_local_plan  # noqa: F401
from countrydle.local_planner import analyze_question_for_local_plan  # noqa: F401
from db.repositories.flagdle import (  # noqa: F401
    FlagdleDayRepository,
    FlagdleGuessRepository,
    FlagdleQuestionRepository,
    FlagdleStateRepository,
)
from flagdle import gameplay, questions_sync, shades
from flagdle.gameplay import (  # noqa: F401
    get_countries,
    get_end_state,
    get_flag_asset,
    get_history,
    get_leaderboard,
    get_state,
    make_guess,
    reveal_country,
)
from flagdle.questions_sync import (  # noqa: F401
    ask_flag_question,
    sync_guest_data,
)
from flagdle.shades import (  # noqa: F401
    FLAG_SVG_CACHE_DIR,
    _get_or_fetch_flag_svg,
    get_shades_challenge,
    get_shades_flag_asset,
    make_shades_guess,
)
from flagdle.utils import (  # noqa: F401
    FACTS_DB_PATH,
    UNMASK_ORDER,
    evaluate_flag_clues,
    generate_asset_token,
    generate_shades_token,
    get_country_iso2,
    normalize_svg_for_grid,
    verify_asset_token,
    verify_shades_token,
)
from schemas.flagdle import (  # noqa: F401
    FlagdleQuestionDisplay,
    FlagdleStateResponse,
)
from utils.guest_session import (  # noqa: F401
    get_guest_question_history,
    link_guest_participation,
    record_guest_action,
)

logger = logging.getLogger("countrydle.flagdle")

router = APIRouter(prefix="/flagdle", tags=["flagdle"])
router.include_router(gameplay.router)
router.include_router(questions_sync.router)
router.include_router(shades.router)
