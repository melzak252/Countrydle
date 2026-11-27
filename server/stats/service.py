from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.dashboard_stats import (
    DashboardLeaderboardEntry,
    DashboardLeaderboardResponse,
    LeaderboardPeriod,
    ModeStatsSummaryResponse,
    PlayerSummary,
)
from stats.adapters import (
    _PlayRow,
    _dedupe_plays,
    _fetch_summary_rows,
    _is_test_username,
    _month_bounds,
    _non_test_user_filters,
    _utc_date,
)
from stats.distributions import (
    _border_hop_bucket,
    _build_distributions,
    _compute_summary_metrics,
    _performance_key,
    _quiz_score_band,
    _select_player_row,
)
from stats.leaderboards import _build_leaderboard_response, _compute_ranked_entries
from stats.recording import record_mode_result
from stats.registry import ModeStatsSpec


async def get_mode_leaderboard(
    session: AsyncSession,
    spec: ModeStatsSpec,
    *,
    period: LeaderboardPeriod = "daily",
    target_date: Optional[date] = None,
    limit: int = 25,
    offset: int = 0,
    current_user_id: Optional[int] = None,
) -> DashboardLeaderboardResponse:
    effective_date = target_date or datetime.now(timezone.utc).date()
    all_entries = await _compute_ranked_entries(
        session, spec, period, effective_date, current_user_id=current_user_id
    )
    return _build_leaderboard_response(
        spec, period, effective_date, all_entries, limit, offset, current_user_id
    )


async def get_mode_summary(
    session: AsyncSession,
    spec: ModeStatsSpec,
    *,
    target_date: Optional[date] = None,
    period: LeaderboardPeriod = "daily",
    limit: int = 10,
    current_user_id: Optional[int] = None,
    guest_id: Optional[str] = None,
) -> ModeStatsSummaryResponse:
    effective_date = target_date or datetime.now(timezone.utc).date()

    today_rows, dist_rows = await _fetch_summary_rows(session, spec, effective_date)
    dist_completed = [r for r in dist_rows if r.completed]
    player_row = _select_player_row(spec, today_rows, dist_rows, current_user_id, guest_id)
    metrics = _compute_summary_metrics(spec, today_rows, dist_rows, player_row)
    distributions = _build_distributions(spec, dist_completed, player_row)

    period_entries: Dict[LeaderboardPeriod, List[DashboardLeaderboardEntry]] = {}
    periods_to_compute: List[LeaderboardPeriod] = [period]
    if current_user_id is not None:
        for p in ("daily", "monthly", "all_time"):
            if p not in periods_to_compute:
                periods_to_compute.append(p)  # type: ignore[arg-type]

    for p in periods_to_compute:
        period_entries[p] = await _compute_ranked_entries(
            session, spec, p, effective_date, current_user_id=current_user_id
        )

    def _find_rank(p: LeaderboardPeriod) -> Optional[int]:
        if current_user_id is None or p not in period_entries:
            return None
        match = next((e for e in period_entries[p] if e.user_id == current_user_id), None)
        return match.rank if match is not None else None

    player_summary = PlayerSummary(
        played=player_row is not None,
        completed=bool(player_row.completed) if player_row is not None else False,
        won=bool(player_row.won) if player_row is not None else False,
        is_guest=(current_user_id is None and player_row is not None),
        points=player_row.points if player_row is not None else None,
        questions_used=player_row.questions_used if player_row is not None else None,
        guesses_used=player_row.guesses_used if player_row is not None else None,
        score=player_row.score if player_row is not None else None,
        max_score=player_row.max_score if player_row is not None else spec.max_score,
        elapsed_seconds=(
            round(player_row.elapsed_seconds, 2)
            if (player_row is not None and player_row.elapsed_seconds is not None)
            else None
        ),
        percentile=metrics.percentile,
        daily_rank=_find_rank("daily"),
        monthly_rank=_find_rank("monthly"),
        all_time_rank=_find_rank("all_time"),
    )

    leaderboard = _build_leaderboard_response(
        spec,
        period,
        effective_date,
        period_entries[period],
        limit=limit,
        offset=0,
        current_user_id=current_user_id,
    )

    return ModeStatsSummaryResponse(
        mode=spec.mode,
        mode_kind=spec.mode_kind,
        is_daily=spec.is_daily,
        date=effective_date.isoformat(),
        played_today=metrics.played_today,
        completed_today=metrics.completed_today,
        winners_today=metrics.winners_today,
        win_rate_pct=metrics.win_rate_pct,
        avg_questions_won=metrics.avg_questions_won,
        avg_guesses_won=metrics.avg_guesses_won,
        avg_score=metrics.avg_score,
        avg_elapsed_seconds=metrics.avg_elapsed_seconds,
        distributions=distributions,
        player=player_summary,
        leaderboard=leaderboard,
    )


__all__ = [
    "record_mode_result",
    "get_mode_leaderboard",
    "get_mode_summary",
    "_PlayRow",
    "_month_bounds",
    "_utc_date",
    "_non_test_user_filters",
    "_is_test_username",
    "_dedupe_plays",
    "_fetch_summary_rows",
    "_performance_key",
    "_quiz_score_band",
    "_border_hop_bucket",
    "_build_distributions",
    "_select_player_row",
    "_compute_ranked_entries",
    "_build_leaderboard_response",
]
