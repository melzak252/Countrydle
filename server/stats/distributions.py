from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from schemas.dashboard_stats import DistributionBucket, ModeDistributions
from stats.adapters import _PlayRow
from stats.registry import ModeStatsSpec


@dataclass
class SummaryMetrics:
    played_today: int
    completed_today: int
    winners_today: int
    win_rate_pct: float
    avg_questions_won: Optional[float]
    avg_guesses_won: Optional[float]
    avg_score: Optional[float]
    avg_elapsed_seconds: Optional[float]
    percentile: Optional[float]


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


def _to_buckets(
    labels: List[str],
    counts: Dict[str, int],
    total: int,
    player_lbl: Optional[str],
) -> List[DistributionBucket]:
    return [
        DistributionBucket(
            label=lbl,
            count=counts[lbl],
            pct=round((counts[lbl] / total) * 100.0, 1) if total > 0 else 0.0,
            is_player=(lbl == player_lbl),
        )
        for lbl in labels
    ]


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
            lbl = (
                str(min(max(0, r.questions_used), spec.max_questions))
                if (r.won and r.questions_used is not None)
                else "X"
            )
            counts[lbl] = counts.get(lbl, 0) + 1
        player_lbl = None
        if player_completed is not None:
            player_lbl = (
                str(min(max(0, player_completed.questions_used), spec.max_questions))
                if (player_completed.won and player_completed.questions_used is not None)
                else "X"
            )
        questions_buckets = _to_buckets(labels, counts, total, player_lbl)

    if spec.mode_kind in ("qa_daily", "guess_daily") and spec.max_guesses is not None:
        labels = [str(i) for i in range(1, spec.max_guesses + 1)] + ["X"]
        counts = {label: 0 for label in labels}
        for r in completed_rows:
            lbl = (
                str(min(max(1, r.guesses_used), spec.max_guesses))
                if (r.won and r.guesses_used is not None)
                else "X"
            )
            counts[lbl] = counts.get(lbl, 0) + 1
        player_lbl = None
        if player_completed is not None:
            player_lbl = (
                str(min(max(1, player_completed.guesses_used), spec.max_guesses))
                if (player_completed.won and player_completed.guesses_used is not None)
                else "X"
            )
        guesses_buckets = _to_buckets(labels, counts, total, player_lbl)

    if spec.mode_kind == "quiz_run":
        if spec.max_score is not None and spec.max_score <= 12:
            labels = [str(i) for i in range(0, spec.max_score + 1)]
            counts = {label: 0 for label in labels}
            for r in completed_rows:
                clamped = min(max(0, int(r.score or 0)), spec.max_score)
                counts[str(clamped)] += 1
            player_lbl = (
                str(min(max(0, int(player_completed.score or 0)), spec.max_score))
                if player_completed is not None
                else None
            )
        else:
            labels = ["0-20%", "21-40%", "41-60%", "61-80%", "81-99%", "100%"]
            counts = {label: 0 for label in labels}
            for r in completed_rows:
                max_s = r.max_score or spec.max_score or 100
                counts[_quiz_score_band(r.score or 0, max_s)] += 1
            player_lbl = None
            if player_completed is not None:
                max_s = player_completed.max_score or spec.max_score or 100
                player_lbl = _quiz_score_band(player_completed.score or 0, max_s)
        score_buckets = _to_buckets(labels, counts, total, player_lbl)
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
        score_buckets = _to_buckets(labels, counts, total, player_lbl)

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


def _compute_summary_metrics(
    spec: ModeStatsSpec,
    today_rows: List[_PlayRow],
    dist_rows: List[_PlayRow],
    player_row: Optional[_PlayRow],
) -> SummaryMetrics:
    today_completed = [r for r in today_rows if r.completed]
    played_today = len({r.identity for r in today_completed})
    completed_today = len(today_completed)
    winners_today = sum(1 for r in today_completed if r.won)
    win_rate_pct = round((winners_today / completed_today) * 100.0, 1) if completed_today > 0 else 0.0

    dist_completed = [r for r in dist_rows if r.completed]
    dist_won = [r for r in dist_completed if r.won]

    q_vals = [r.questions_used for r in dist_won if r.questions_used is not None]
    avg_questions_won = round(sum(q_vals) / len(q_vals), 2) if q_vals else None

    g_vals = [r.guesses_used for r in dist_won if r.guesses_used is not None]
    avg_guesses_won = round(sum(g_vals) / len(g_vals), 2) if g_vals else None

    score_vals = [r.score for r in dist_completed if r.score is not None]
    avg_score = round(sum(score_vals) / len(score_vals), 2) if score_vals else None

    elapsed_vals = [r.elapsed_seconds for r in dist_completed if r.elapsed_seconds is not None]
    avg_elapsed_seconds = round(sum(elapsed_vals) / len(elapsed_vals), 2) if elapsed_vals else None

    percentile: Optional[float] = None
    if player_row is not None and player_row.completed and dist_completed:
        player_perf = _performance_key(spec, player_row)
        worse_or_equal = sum(1 for r in dist_completed if _performance_key(spec, r) <= player_perf)
        percentile = round(min(100.0, max(0.0, (worse_or_equal / len(dist_completed)) * 100.0)), 1)

    return SummaryMetrics(
        played_today=played_today,
        completed_today=completed_today,
        winners_today=winners_today,
        win_rate_pct=win_rate_pct,
        avg_questions_won=avg_questions_won,
        avg_guesses_won=avg_guesses_won,
        avg_score=avg_score,
        avg_elapsed_seconds=avg_elapsed_seconds,
        percentile=percentile,
    )
