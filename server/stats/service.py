from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.guest_participation import GuestParticipation
from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun
from db.models.mode_result import ModeResultRecord
from db.models.user import User
from schemas.dashboard_stats import (
    DashboardLeaderboardEntry,
    DashboardLeaderboardResponse,
    DistributionBucket,
    LeaderboardPeriod,
    ModeDistributions,
    ModeStatsSummaryResponse,
    PlayerSummary,
)
from stats.registry import ModeStatsSpec


@dataclass
class _PlayRow:
    identity: str
    user_id: Optional[int]
    guest_id: Optional[str]
    completed: bool
    won: bool
    points: Optional[int] = None
    questions_used: Optional[int] = None
    guesses_used: Optional[int] = None
    score: Optional[int] = None
    max_score: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    played_date: Optional[date] = None


def _month_bounds(target_date: date) -> Tuple[date, date]:
    first_day = target_date.replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_month = first_day.replace(month=first_day.month + 1)
    return first_day, next_month


def _utc_date(dt: Optional[datetime]) -> Optional[date]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).date()
    return dt.date()


def _non_test_user_filters():
    return (
        User.username.not_like("test_%"),
        User.username.not_like("pytest_%"),
        User.username.not_like("guess_c_%"),
        User.username.not_like("ask_q_%"),
    )


def _is_test_username(username: Optional[str]) -> bool:
    if not username:
        return True
    lowered = username.lower()
    return (
        lowered.startswith("test_")
        or lowered.startswith("pytest_")
        or lowered.startswith("guess_c_")
        or lowered.startswith("ask_q_")
    )


async def record_mode_result(
    session: AsyncSession,
    *,
    mode: str,
    record_date: Optional[date],
    user_id: Optional[int],
    guest_id: Optional[str],
    completed: bool = True,
    won: bool = False,
    points: int = 0,
    questions_used: Optional[int] = None,
    guesses_used: Optional[int] = None,
    score: Optional[int] = None,
    max_score: Optional[int] = None,
    elapsed_seconds: Optional[float] = None,
    completed_at: Optional[datetime] = None,
) -> Optional[ModeResultRecord]:
    """Persist a mode completion into mode_result_records (idempotent for daily modes)."""
    if user_id is None and not guest_id:
        return None

    now = completed_at or datetime.now(timezone.utc)
    effective_guest_id = None if user_id is not None else guest_id

    if record_date is not None:
        if user_id is not None:
            owner_clause = ModeResultRecord.user_id == user_id
        else:
            owner_clause = and_(
                ModeResultRecord.user_id.is_(None),
                ModeResultRecord.guest_id == effective_guest_id,
            )

        existing = (
            await session.execute(
                select(ModeResultRecord).where(
                    ModeResultRecord.mode == mode,
                    ModeResultRecord.date == record_date,
                    owner_clause,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            if existing.completed:
                return existing
            existing.completed = completed
            existing.won = won
            existing.points = points
            existing.questions_used = questions_used
            existing.guesses_used = guesses_used
            existing.score = score
            existing.max_score = max_score
            existing.elapsed_seconds = elapsed_seconds
            existing.completed_at = now
            await session.commit()
            return existing

    record = ModeResultRecord(
        id=str(uuid4()),
        mode=mode,
        date=record_date,
        user_id=user_id,
        guest_id=effective_guest_id,
        completed=completed,
        won=won,
        points=points,
        questions_used=questions_used,
        guesses_used=guesses_used,
        score=score,
        max_score=max_score,
        elapsed_seconds=elapsed_seconds,
        completed_at=now,
    )
    session.add(record)
    await session.commit()
    return record


def _dedupe_plays(rows: List[_PlayRow]) -> List[_PlayRow]:
    by_identity: Dict[str, _PlayRow] = {}
    for row in rows:
        existing = by_identity.get(row.identity)
        if existing is None:
            by_identity[row.identity] = row
            continue
        new_key = (
            1 if row.completed else 0,
            1 if row.won else 0,
            row.points if row.points is not None else -1,
            row.guesses_used if row.guesses_used is not None else -1,
            row.questions_used if row.questions_used is not None else -1,
        )
        old_key = (
            1 if existing.completed else 0,
            1 if existing.won else 0,
            existing.points if existing.points is not None else -1,
            existing.guesses_used if existing.guesses_used is not None else -1,
            existing.questions_used if existing.questions_used is not None else -1,
        )
        if new_key > old_key:
            by_identity[row.identity] = row
    return list(by_identity.values())


async def _fetch_summary_rows(
    session: AsyncSession,
    spec: ModeStatsSpec,
    target_date: date,
) -> Tuple[List[_PlayRow], List[_PlayRow]]:
    """Return (today_rows, distribution_rows) for the given mode spec and date."""
    if spec.adapter in ("qa_daily", "guess_daily"):
        state_model = spec.state_model
        day_model = spec.day_model
        day_filters = [day_model.date == target_date]
        if spec.continent is not None:
            day_filters.append(day_model.continent == spec.continent)

        auth_stmt = (
            select(
                state_model.user_id,
                state_model.questions_asked,
                state_model.guesses_made,
                state_model.is_game_over,
                state_model.won,
                state_model.points,
            )
            .join(day_model, day_model.id == state_model.day_id)
            .where(
                state_model.user_id.is_not(None),
                or_(state_model.questions_asked > 0, state_model.guesses_made > 0),
                *day_filters,
            )
        )
        auth_rows = (await session.execute(auth_stmt)).all()

        guest_stmt = (
            select(
                GuestParticipation.guest_id,
                GuestParticipation.questions_asked,
                GuestParticipation.guesses_made,
                GuestParticipation.won,
            )
            .join(day_model, day_model.id == GuestParticipation.day_id)
            .where(
                GuestParticipation.mode == spec.guest_mode_key,
                GuestParticipation.user_id.is_(None),
                or_(
                    GuestParticipation.questions_asked > 0,
                    GuestParticipation.guesses_made > 0,
                ),
                *day_filters,
            )
        )
        guest_rows = (await session.execute(guest_stmt)).all()

        plays: List[_PlayRow] = []
        for r in auth_rows:
            plays.append(
                _PlayRow(
                    identity=f"user:{r.user_id}",
                    user_id=r.user_id,
                    guest_id=None,
                    completed=bool(r.is_game_over),
                    won=bool(r.won),
                    points=int(r.points or 0),
                    questions_used=int(r.questions_asked or 0) if spec.adapter == "qa_daily" else None,
                    guesses_used=int(r.guesses_made or 0),
                    played_date=target_date,
                )
            )
        for r in guest_rows:
            g_used = int(r.guesses_made or 0)
            is_won = bool(r.won)
            is_completed = is_won or (spec.max_guesses is not None and g_used >= spec.max_guesses)
            plays.append(
                _PlayRow(
                    identity=f"guest:{r.guest_id}",
                    user_id=None,
                    guest_id=r.guest_id,
                    completed=is_completed,
                    won=is_won,
                    points=None,
                    questions_used=int(r.questions_asked or 0) if spec.adapter == "qa_daily" else None,
                    guesses_used=g_used,
                    played_date=target_date,
                )
            )
        deduped = _dedupe_plays(plays)
        return deduped, deduped

    if spec.adapter == "heraldry_daily":
        stmt = select(HeraldryDailySession).where(
            HeraldryDailySession.date == target_date,
            HeraldryDailySession.symbol_mode == spec.symbol_mode,
            HeraldryDailySession.entity_scope == spec.entity_scope,
        )
        sessions = (await session.execute(stmt)).scalars().all()
        plays = []
        for s in sessions:
            guesses_len = len(s.guesses or [])
            if guesses_len == 0:
                continue
            identity = f"user:{s.user_id}" if s.user_id is not None else f"guest:{s.guest_id}"
            elapsed = None
            if s.started_at is not None and s.completed_at is not None:
                elapsed = max(0.0, (s.completed_at - s.started_at).total_seconds())
            plays.append(
                _PlayRow(
                    identity=identity,
                    user_id=s.user_id,
                    guest_id=None if s.user_id is not None else s.guest_id,
                    completed=s.completed_at is not None,
                    won=bool(s.won),
                    points=int(s.points or 0) if s.points is not None else None,
                    guesses_used=guesses_len,
                    elapsed_seconds=elapsed,
                    played_date=s.date,
                )
            )
        deduped = _dedupe_plays(plays)
        return deduped, deduped

    if spec.adapter == "quiz_run":
        stmt = select(QuizRun).where(
            QuizRun.symbol_mode == spec.symbol_mode,
            QuizRun.entity_scope == spec.entity_scope,
        )
        runs = (await session.execute(stmt)).scalars().all()
        all_rows: List[_PlayRow] = []
        today_rows: List[_PlayRow] = []
        for run in runs:
            identity = f"user:{run.user_id}" if run.user_id is not None else f"guest:{run.guest_id}"
            run_date = _utc_date(run.started_at)
            is_completed = run.status in ("completed", "given_up")
            is_won = run.status == "completed"
            row = _PlayRow(
                identity=identity,
                user_id=run.user_id,
                guest_id=None if run.user_id is not None else run.guest_id,
                completed=is_completed,
                won=is_won,
                points=int(run.solved_count or 0),
                score=int(run.solved_count or 0),
                max_score=spec.max_score,
                elapsed_seconds=float(run.elapsed_seconds) if run.elapsed_seconds is not None else None,
                played_date=run_date,
            )
            all_rows.append(row)
            if run_date == target_date:
                today_rows.append(row)
        return today_rows, all_rows

    # adapter == "mode_result"
    record_mode = spec.record_mode or spec.mode
    stmt = select(ModeResultRecord).where(ModeResultRecord.mode == record_mode)
    if spec.is_daily:
        stmt = stmt.where(ModeResultRecord.date == target_date)
    records = (await session.execute(stmt)).scalars().all()

    all_rows = []
    today_rows = []
    for rec in records:
        identity = f"user:{rec.user_id}" if rec.user_id is not None else f"guest:{rec.guest_id}"
        rec_date = rec.date or _utc_date(rec.completed_at)
        row = _PlayRow(
            identity=identity,
            user_id=rec.user_id,
            guest_id=None if rec.user_id is not None else rec.guest_id,
            completed=bool(rec.completed),
            won=bool(rec.won),
            points=int(rec.points or 0),
            questions_used=rec.questions_used,
            guesses_used=rec.guesses_used,
            score=rec.score,
            max_score=rec.max_score if rec.max_score is not None else spec.max_score,
            elapsed_seconds=float(rec.elapsed_seconds) if rec.elapsed_seconds is not None else None,
            played_date=rec_date,
        )
        all_rows.append(row)
        if rec_date == target_date:
            today_rows.append(row)

    if spec.is_daily:
        deduped = _dedupe_plays(today_rows)
        return deduped, deduped
    return today_rows, all_rows


def _performance_key(spec: ModeStatsSpec, row: _PlayRow) -> tuple:
    """Higher tuple means better performance for percentile comparison."""
    if spec.mode_kind == "qa_daily":
        return (
            1 if row.won else 0,
            -(row.questions_used if row.questions_used is not None else 9999),
            -(row.guesses_used if row.guesses_used is not None else 9999),
            row.points if row.points is not None else 0,
        )
    if spec.mode_kind == "guess_daily":
        return (
            1 if row.won else 0,
            -(row.guesses_used if row.guesses_used is not None else 9999),
            row.points if row.points is not None else 0,
        )
    if spec.mode_kind == "score_daily":
        if row.score is not None and row.max_score is not None:
            delta = row.score - row.max_score
        else:
            delta = row.score if row.score is not None else 9999
        return (
            1 if row.won else 0,
            -delta,
            row.points if row.points is not None else 0,
        )
    # quiz_run
    return (
        row.score if row.score is not None else 0,
        -(row.elapsed_seconds if row.elapsed_seconds is not None else 1e12),
    )


def _quiz_score_band(score: int, max_score: int) -> str:
    if max_score <= 0:
        return "0-20%"
    if score >= max_score:
        return "100%"
    pct = (score / max_score) * 100.0
    if pct <= 20.0:
        return "0-20%"
    if pct <= 40.0:
        return "21-40%"
    if pct <= 60.0:
        return "41-60%"
    if pct <= 80.0:
        return "61-80%"
    return "81-99%"


def _border_hop_bucket(row: _PlayRow) -> str:
    if row.score is not None and row.max_score is not None:
        delta = max(0, row.score - row.max_score)
        if delta == 0:
            return "Optimal"
        if delta == 1:
            return "+1 hop"
        if delta == 2:
            return "+2 hops"
        return "+3+ hops"
    if row.score is not None:
        return str(row.score)
    return "X"


def _build_distributions(
    spec: ModeStatsSpec,
    completed_rows: List[_PlayRow],
    player_row: Optional[_PlayRow],
) -> ModeDistributions:
    total = len(completed_rows)
    player_completed = player_row if (player_row is not None and player_row.completed) else None

    questions_buckets: Optional[List[DistributionBucket]] = None
    guesses_buckets: Optional[List[DistributionBucket]] = None
    score_buckets: Optional[List[DistributionBucket]] = None

    if spec.mode_kind == "qa_daily" and spec.max_questions is not None:
        labels = [str(i) for i in range(0, spec.max_questions + 1)] + ["X"]
        counts = {label: 0 for label in labels}
        for r in completed_rows:
            if r.won and r.questions_used is not None:
                lbl = str(min(max(0, r.questions_used), spec.max_questions))
            else:
                lbl = "X"
            counts[lbl] = counts.get(lbl, 0) + 1
        player_lbl = None
        if player_completed is not None:
            if player_completed.won and player_completed.questions_used is not None:
                player_lbl = str(min(max(0, player_completed.questions_used), spec.max_questions))
            else:
                player_lbl = "X"
        questions_buckets = [
            DistributionBucket(
                label=lbl,
                count=counts[lbl],
                pct=round((counts[lbl] / total) * 100.0, 1) if total > 0 else 0.0,
                is_player=(lbl == player_lbl),
            )
            for lbl in labels
        ]

    if spec.mode_kind in ("qa_daily", "guess_daily") and spec.max_guesses is not None:
        labels = [str(i) for i in range(1, spec.max_guesses + 1)] + ["X"]
        counts = {label: 0 for label in labels}
        for r in completed_rows:
            if r.won and r.guesses_used is not None:
                lbl = str(min(max(1, r.guesses_used), spec.max_guesses))
            else:
                lbl = "X"
            counts[lbl] = counts.get(lbl, 0) + 1
        player_lbl = None
        if player_completed is not None:
            if player_completed.won and player_completed.guesses_used is not None:
                player_lbl = str(min(max(1, player_completed.guesses_used), spec.max_guesses))
            else:
                player_lbl = "X"
        guesses_buckets = [
            DistributionBucket(
                label=lbl,
                count=counts[lbl],
                pct=round((counts[lbl] / total) * 100.0, 1) if total > 0 else 0.0,
                is_player=(lbl == player_lbl),
            )
            for lbl in labels
        ]

    if spec.mode_kind == "quiz_run":
        labels = ["0-20%", "21-40%", "41-60%", "61-80%", "81-99%", "100%"]
        counts = {label: 0 for label in labels}
        for r in completed_rows:
            max_s = r.max_score or spec.max_score or 100
            lbl = _quiz_score_band(r.score or 0, max_s)
            counts[lbl] += 1
        player_lbl = None
        if player_completed is not None:
            max_s = player_completed.max_score or spec.max_score or 100
            player_lbl = _quiz_score_band(player_completed.score or 0, max_s)
        score_buckets = [
            DistributionBucket(
                label=lbl,
                count=counts[lbl],
                pct=round((counts[lbl] / total) * 100.0, 1) if total > 0 else 0.0,
                is_player=(lbl == player_lbl),
            )
            for lbl in labels
        ]
    elif spec.mode_kind == "score_daily":
        labels = ["Optimal", "+1 hop", "+2 hops", "+3+ hops"]
        counts = {label: 0 for label in labels}
        for r in completed_rows:
            lbl = _border_hop_bucket(r)
            if lbl not in counts:
                counts[lbl] = 0
                labels.append(lbl)
            counts[lbl] += 1
        player_lbl = _border_hop_bucket(player_completed) if player_completed is not None else None
        score_buckets = [
            DistributionBucket(
                label=lbl,
                count=counts[lbl],
                pct=round((counts[lbl] / total) * 100.0, 1) if total > 0 else 0.0,
                is_player=(lbl == player_lbl),
            )
            for lbl in labels
        ]

    return ModeDistributions(
        questions=questions_buckets,
        guesses=guesses_buckets,
        score=score_buckets,
    )


def _select_player_row(
    spec: ModeStatsSpec,
    today_rows: List[_PlayRow],
    dist_rows: List[_PlayRow],
    user_id: Optional[int],
    guest_id: Optional[str],
) -> Optional[_PlayRow]:
    identities: List[str] = []
    if user_id is not None:
        identities.append(f"user:{user_id}")
    if guest_id:
        identities.append(f"guest:{guest_id}")
    if not identities:
        return None

    def _find_best(pool: List[_PlayRow]) -> Optional[_PlayRow]:
        matches = [r for r in pool if r.identity in identities]
        if not matches:
            return None
        if spec.is_daily:
            # Prefer user row over guest row if both somehow exist
            matches.sort(key=lambda r: (1 if r.user_id is not None else 0, 1 if r.completed else 0), reverse=True)
            return matches[0]
        completed_matches = [r for r in matches if r.completed]
        candidates = completed_matches or matches
        candidates.sort(key=lambda r: _performance_key(spec, r), reverse=True)
        return candidates[0]

    today_match = _find_best(today_rows)
    if today_match is not None or spec.is_daily:
        return today_match
    return _find_best(dist_rows)


async def _compute_ranked_entries(
    session: AsyncSession,
    spec: ModeStatsSpec,
    period: LeaderboardPeriod,
    target_date: date,
    current_user_id: Optional[int] = None,
) -> List[DashboardLeaderboardEntry]:
    month_start, next_month = _month_bounds(target_date)

    if spec.adapter in ("qa_daily", "guess_daily"):
        state_model = spec.state_model
        day_model = spec.day_model
        filters = [
            state_model.user_id.is_not(None),
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

        # Deduplicate per (user_id, day_id)
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

        sorted_items = sorted(
            agg.values(),
            key=lambda e: (-e["points"], -e["wins"], e["user_id"]),
        )
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

    if spec.adapter == "heraldry_daily":
        filters = [
            HeraldryDailySession.user_id.is_not(None),
            HeraldryDailySession.symbol_mode == spec.symbol_mode,
            HeraldryDailySession.entity_scope == spec.entity_scope,
            *_non_test_user_filters(),
        ]
        if period == "daily":
            filters.append(HeraldryDailySession.date == target_date)
        elif period == "monthly":
            filters.extend(
                (HeraldryDailySession.date >= month_start, HeraldryDailySession.date < next_month)
            )

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
        agg = {}
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
                    entry["best_elapsed"] = round(
                        max(0.0, (r.completed_at - r.started_at).total_seconds()), 2
                    )

        sorted_items = sorted(
            agg.values(),
            key=lambda e: (-e["points"], -e["wins"], e["user_id"]),
        )
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

    if spec.adapter == "quiz_run":
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
        agg = {}
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
                best_elapsed_seconds=(
                    round(item["best_elapsed"], 2) if item["best_elapsed"] is not None else None
                ),
                is_current_user=(current_user_id is not None and item["user_id"] == current_user_id),
            )
            for idx, item in enumerate(sorted_items)
        ]

    # adapter == "mode_result"
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

    agg = {}
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
        pts = int(r.points or 0)
        entry["points"] += pts
        entry["wins"] += 1 if r.won else 0
        entry["games_played"] += 1

        if r.score is not None:
            if entry["best_score"] is None or (
                r.score > entry["best_score"]
                if spec.mode_kind == "quiz_run"
                else r.score < entry["best_score"]
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
        sorted_items = sorted(
            agg.values(),
            key=lambda e: (-e["points"], -e["wins"], e["user_id"]),
        )

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
            best_elapsed_seconds=(
                round(item["best_elapsed"], 2) if item["best_elapsed"] is not None else None
            ),
            questions_used=item["questions_used"],
            guesses_used=item["guesses_used"],
            is_current_user=(current_user_id is not None and item["user_id"] == current_user_id),
        )
        for idx, item in enumerate(sorted_items)
    ]


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
            current_user_entry = next(
                (e for e in all_entries if e.user_id == current_user_id),
                None,
            )
    return DashboardLeaderboardResponse(
        mode=spec.mode,
        period=period,
        date=target_date.isoformat(),
        total_ranked=len(all_entries),
        entries=page_entries,
        current_user_entry=current_user_entry,
    )


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

    played_today = len({r.identity for r in today_rows})
    today_completed = [r for r in today_rows if r.completed]
    completed_today = len(today_completed)
    winners_today = sum(1 for r in today_completed if r.won)
    win_rate_pct = (
        round((winners_today / completed_today) * 100.0, 1) if completed_today > 0 else 0.0
    )

    dist_completed = [r for r in dist_rows if r.completed]
    dist_won = [r for r in dist_completed if r.won]

    q_vals = [r.questions_used for r in dist_won if r.questions_used is not None]
    avg_questions_won = round(sum(q_vals) / len(q_vals), 2) if q_vals else None

    g_vals = [r.guesses_used for r in dist_won if r.guesses_used is not None]
    avg_guesses_won = round(sum(g_vals) / len(g_vals), 2) if g_vals else None

    score_vals = [r.score for r in dist_completed if r.score is not None]
    avg_score = round(sum(score_vals) / len(score_vals), 2) if score_vals else None

    elapsed_vals = [r.elapsed_seconds for r in dist_completed if r.elapsed_seconds is not None]
    avg_elapsed_seconds = (
        round(sum(elapsed_vals) / len(elapsed_vals), 2) if elapsed_vals else None
    )

    player_row = _select_player_row(spec, today_rows, dist_rows, current_user_id, guest_id)
    distributions = _build_distributions(spec, dist_completed, player_row)

    percentile: Optional[float] = None
    if player_row is not None and player_row.completed and dist_completed:
        player_perf = _performance_key(spec, player_row)
        worse_or_equal = sum(
            1 for r in dist_completed if _performance_key(spec, r) <= player_perf
        )
        percentile = round(min(100.0, max(0.0, (worse_or_equal / len(dist_completed)) * 100.0)), 1)

    # Compute leaderboards & player ranks across periods
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
        max_score=(
            player_row.max_score if player_row is not None else spec.max_score
        ),
        elapsed_seconds=(
            round(player_row.elapsed_seconds, 2)
            if (player_row is not None and player_row.elapsed_seconds is not None)
            else None
        ),
        percentile=percentile,
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
        played_today=played_today,
        completed_today=completed_today,
        winners_today=winners_today,
        win_rate_pct=win_rate_pct,
        avg_questions_won=avg_questions_won,
        avg_guesses_won=avg_guesses_won,
        avg_score=avg_score,
        avg_elapsed_seconds=avg_elapsed_seconds,
        distributions=distributions,
        player=player_summary,
        leaderboard=leaderboard,
    )
