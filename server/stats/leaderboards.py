from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun
from db.models.mode_result import ModeResultRecord
from db.models.user import User
from schemas.dashboard_stats import (
    DashboardLeaderboardEntry,
    DashboardLeaderboardResponse,
    LeaderboardPeriod,
)
from stats.adapters import _month_bounds, _non_test_user_filters, _utc_date
from stats.registry import ModeStatsSpec


async def _rank_qa_or_guess_daily(
    session: AsyncSession,
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    month_start: date,
    next_month: date,
    current_user_id: Optional[int],
) -> List[DashboardLeaderboardEntry]:
    state_model = spec.state_model
    day_model = spec.day_model
    filters = [
        state_model.user_id.is_not(None),
        state_model.is_game_over.is_(True),
        or_(state_model.questions_asked > 0, state_model.guesses_made > 0),
        *_non_test_user_filters(),
    ]
    if spec.continent is not None:
        filters.append(day_model.continent == spec.continent)
    if period == "daily":
        filters.append(day_model.date == target_date)
    elif period == "monthly":
        filters.extend((day_model.date >= month_start, day_model.date < next_month))

    stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            day_model.id.label("day_id"),
            state_model.points,
            state_model.won,
            state_model.questions_asked,
            state_model.guesses_made,
        )
        .join(state_model, User.id == state_model.user_id)
        .join(day_model, state_model.day_id == day_model.id)
        .where(and_(*filters))
    )
    raw_rows = (await session.execute(stmt)).all()

    per_user_day: Dict[Tuple[int, int], Tuple[str, int, int, int, int]] = {}
    for r in raw_rows:
        key = (r.user_id, r.day_id)
        pts = int(r.points or 0)
        win = 1 if r.won else 0
        q_used = int(r.questions_asked or 0)
        g_used = int(r.guesses_made or 0)
        prev = per_user_day.get(key)
        if prev is None or (pts, win, g_used) > (prev[1], prev[2], prev[4]):
            per_user_day[key] = (r.username, pts, win, q_used, g_used)

    agg: Dict[int, dict] = {}
    for (uid, _day_id), (uname, pts, win, q_used, g_used) in per_user_day.items():
        entry = agg.setdefault(
            uid,
            {
                "user_id": uid,
                "username": uname,
                "points": 0,
                "wins": 0,
                "games_played": 0,
                "questions_used": None,
                "guesses_used": None,
            },
        )
        entry["points"] += pts
        entry["wins"] += win
        entry["games_played"] += 1
        if period == "daily":
            entry["questions_used"] = q_used if spec.adapter == "qa_daily" else None
            entry["guesses_used"] = g_used

    sorted_items = sorted(agg.values(), key=lambda e: (-e["points"], -e["wins"], e["user_id"]))
    return [
        DashboardLeaderboardEntry(
            rank=idx + 1,
            user_id=item["user_id"],
            username=item["username"],
            points=item["points"],
            wins=item["wins"],
            games_played=item["games_played"],
            average_points=round(item["points"] / item["games_played"], 2),
            questions_used=item["questions_used"],
            guesses_used=item["guesses_used"],
            is_current_user=(current_user_id is not None and item["user_id"] == current_user_id),
        )
        for idx, item in enumerate(sorted_items)
    ]


async def _rank_heraldry_daily(
    session: AsyncSession,
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    month_start: date,
    next_month: date,
    current_user_id: Optional[int],
) -> List[DashboardLeaderboardEntry]:
    filters = [
        HeraldryDailySession.user_id.is_not(None),
        HeraldryDailySession.completed_at.is_not(None),
        HeraldryDailySession.symbol_mode == spec.symbol_mode,
        HeraldryDailySession.entity_scope == spec.entity_scope,
        *_non_test_user_filters(),
    ]
    if period == "daily":
        filters.append(HeraldryDailySession.date == target_date)
    elif period == "monthly":
        filters.extend((HeraldryDailySession.date >= month_start, HeraldryDailySession.date < next_month))

    stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            HeraldryDailySession.guesses,
            HeraldryDailySession.points,
            HeraldryDailySession.won,
            HeraldryDailySession.started_at,
            HeraldryDailySession.completed_at,
        )
        .join(HeraldryDailySession, User.id == HeraldryDailySession.user_id)
        .where(and_(*filters))
    )
    raw_rows = (await session.execute(stmt)).all()

    agg: Dict[int, dict] = {}
    for r in raw_rows:
        g_len = len(r.guesses or [])
        if g_len == 0:
            continue
        entry = agg.setdefault(
            r.user_id,
            {
                "user_id": r.user_id,
                "username": r.username,
                "points": 0,
                "wins": 0,
                "games_played": 0,
                "guesses_used": None,
                "best_elapsed": None,
            },
        )
        entry["points"] += int(r.points or 0)
        entry["wins"] += 1 if r.won else 0
        entry["games_played"] += 1
        if period == "daily":
            entry["guesses_used"] = g_len
            if r.started_at is not None and r.completed_at is not None:
                entry["best_elapsed"] = round(max(0.0, (r.completed_at - r.started_at).total_seconds()), 2)

    sorted_items = sorted(agg.values(), key=lambda e: (-e["points"], -e["wins"], e["user_id"]))
    return [
        DashboardLeaderboardEntry(
            rank=idx + 1,
            user_id=item["user_id"],
            username=item["username"],
            points=item["points"],
            wins=item["wins"],
            games_played=item["games_played"],
            average_points=round(item["points"] / item["games_played"], 2),
            guesses_used=item["guesses_used"],
            best_elapsed_seconds=item["best_elapsed"],
            is_current_user=(current_user_id is not None and item["user_id"] == current_user_id),
        )
        for idx, item in enumerate(sorted_items)
    ]


async def _rank_quiz_run(
    session: AsyncSession,
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    month_start: date,
    next_month: date,
    current_user_id: Optional[int],
) -> List[DashboardLeaderboardEntry]:
    stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            QuizRun.status,
            QuizRun.solved_count,
            QuizRun.elapsed_seconds,
            QuizRun.started_at,
        )
        .join(QuizRun, User.id == QuizRun.user_id)
        .where(
            QuizRun.user_id.is_not(None),
            QuizRun.symbol_mode == spec.symbol_mode,
            QuizRun.entity_scope == spec.entity_scope,
            QuizRun.status.in_(("completed", "given_up")),
            *_non_test_user_filters(),
        )
    )
    raw_rows = (await session.execute(stmt)).all()

    agg: Dict[int, dict] = {}
    for r in raw_rows:
        run_date = _utc_date(r.started_at)
        if period == "daily" and run_date != target_date:
            continue
        if period == "monthly" and (run_date is None or not (month_start <= run_date < next_month)):
            continue
        score = int(r.solved_count or 0)
        elapsed = float(r.elapsed_seconds) if r.elapsed_seconds is not None else None
        entry = agg.setdefault(
            r.user_id,
            {
                "user_id": r.user_id,
                "username": r.username,
                "best_score": -1,
                "best_elapsed": None,
                "total_score": 0,
                "wins": 0,
                "games_played": 0,
            },
        )
        entry["total_score"] += score
        entry["games_played"] += 1
        if r.status == "completed":
            entry["wins"] += 1
        if score > entry["best_score"]:
            entry["best_score"] = score
            entry["best_elapsed"] = elapsed
        elif score == entry["best_score"] and elapsed is not None:
            if entry["best_elapsed"] is None or elapsed < entry["best_elapsed"]:
                entry["best_elapsed"] = elapsed

    sorted_items = sorted(
        agg.values(),
        key=lambda e: (
            -e["best_score"],
            e["best_elapsed"] if e["best_elapsed"] is not None else 1e12,
            -e["wins"],
            e["user_id"],
        ),
    )
    return [
        DashboardLeaderboardEntry(
            rank=idx + 1,
            user_id=item["user_id"],
            username=item["username"],
            points=item["best_score"],
            wins=item["wins"],
            games_played=item["games_played"],
            average_points=round(item["total_score"] / item["games_played"], 2),
            best_score=item["best_score"],
            best_elapsed_seconds=round(item["best_elapsed"], 2) if item["best_elapsed"] is not None else None,
            is_current_user=(current_user_id is not None and item["user_id"] == current_user_id),
        )
        for idx, item in enumerate(sorted_items)
    ]


async def _rank_mode_result(
    session: AsyncSession,
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    month_start: date,
    next_month: date,
    current_user_id: Optional[int],
) -> List[DashboardLeaderboardEntry]:
    record_mode = spec.record_mode or spec.mode
    stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            ModeResultRecord.date,
            ModeResultRecord.completed,
            ModeResultRecord.won,
            ModeResultRecord.points,
            ModeResultRecord.questions_used,
            ModeResultRecord.guesses_used,
            ModeResultRecord.score,
            ModeResultRecord.elapsed_seconds,
            ModeResultRecord.completed_at,
        )
        .join(ModeResultRecord, User.id == ModeResultRecord.user_id)
        .where(
            ModeResultRecord.user_id.is_not(None),
            ModeResultRecord.mode == record_mode,
            ModeResultRecord.completed.is_(True),
            *_non_test_user_filters(),
        )
    )
    raw_rows = (await session.execute(stmt)).all()

    agg: Dict[int, dict] = {}
    for r in raw_rows:
        rec_date = r.date or _utc_date(r.completed_at)
        if period == "daily" and rec_date != target_date:
            continue
        if period == "monthly" and (rec_date is None or not (month_start <= rec_date < next_month)):
            continue

        entry = agg.setdefault(
            r.user_id,
            {
                "user_id": r.user_id,
                "username": r.username,
                "points": 0,
                "wins": 0,
                "games_played": 0,
                "best_score": None,
                "best_elapsed": None,
                "questions_used": None,
                "guesses_used": None,
            },
        )
        entry["points"] += int(r.points or 0)
        entry["wins"] += 1 if r.won else 0
        entry["games_played"] += 1

        if r.score is not None:
            if entry["best_score"] is None or (
                r.score > entry["best_score"] if spec.mode_kind == "quiz_run" else r.score < entry["best_score"]
            ):
                entry["best_score"] = r.score
                if r.elapsed_seconds is not None:
                    entry["best_elapsed"] = float(r.elapsed_seconds)
        if r.elapsed_seconds is not None and entry["best_elapsed"] is None:
            entry["best_elapsed"] = float(r.elapsed_seconds)

        if period == "daily":
            entry["questions_used"] = r.questions_used
            entry["guesses_used"] = r.guesses_used

    if spec.mode_kind == "quiz_run":
        sorted_items = sorted(
            agg.values(),
            key=lambda e: (
                -(e["best_score"] if e["best_score"] is not None else e["points"]),
                e["best_elapsed"] if e["best_elapsed"] is not None else 1e12,
                -e["wins"],
                e["user_id"],
            ),
        )
    else:
        sorted_items = sorted(agg.values(), key=lambda e: (-e["points"], -e["wins"], e["user_id"]))

    return [
        DashboardLeaderboardEntry(
            rank=idx + 1,
            user_id=item["user_id"],
            username=item["username"],
            points=(
                item["best_score"]
                if (spec.mode_kind == "quiz_run" and item["best_score"] is not None)
                else item["points"]
            ),
            wins=item["wins"],
            games_played=item["games_played"],
            average_points=round(item["points"] / item["games_played"], 2),
            best_score=item["best_score"],
            best_elapsed_seconds=round(item["best_elapsed"], 2) if item["best_elapsed"] is not None else None,
            questions_used=item["questions_used"],
            guesses_used=item["guesses_used"],
            is_current_user=(current_user_id is not None and item["user_id"] == current_user_id),
        )
        for idx, item in enumerate(sorted_items)
    ]


async def _compute_ranked_entries(
    session: AsyncSession,
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    current_user_id: Optional[int] = None,
) -> List[DashboardLeaderboardEntry]:
    month_start, next_month = _month_bounds(target_date)
    if spec.adapter in ("qa_daily", "guess_daily"):
        return await _rank_qa_or_guess_daily(session, spec, period, target_date, month_start, next_month, current_user_id)
    if spec.adapter == "heraldry_daily":
        return await _rank_heraldry_daily(session, spec, period, target_date, month_start, next_month, current_user_id)
    if spec.adapter == "quiz_run":
        return await _rank_quiz_run(session, spec, period, target_date, month_start, next_month, current_user_id)
    return await _rank_mode_result(session, spec, period, target_date, month_start, next_month, current_user_id)


def _build_leaderboard_response(
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    all_entries: List[DashboardLeaderboardEntry],
    limit: int,
    offset: int,
    current_user_id: Optional[int],
) -> DashboardLeaderboardResponse:
    page_entries = all_entries[offset : offset + limit]
    current_user_entry = None
    if current_user_id is not None:
        in_page = any(e.user_id == current_user_id for e in page_entries)
        if not in_page:
            current_user_entry = next((e for e in all_entries if e.user_id == current_user_id), None)
    return DashboardLeaderboardResponse(
        mode=spec.mode,
        period=period,
        date=target_date.isoformat(),
        total_ranked=len(all_entries),
        entries=page_entries,
        current_user_entry=current_user_entry,
    )
