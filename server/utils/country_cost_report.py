"""Shared Countrydle cost-report assembly for the CLI and admin API."""
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.country_cost_metrics import aggregate_daily_metrics, build_cost_report, metrics_started_at

DENOMINATOR_NOTE = (
    "Completed games are won or lost Countrydle daily states plus unlinked guest participations "
    "(won or at least 3 guesses); linked guests are counted only through their state. "
    "Per-1000 rates use completed games, not all requests."
)
SCOPE_NOTE = "Gemini planner and fallback generation only; embeddings, retrieval, hosting, and other modes are excluded."
PRICING_NOTE = (
    "Only Gemini 2.5 Flash-Lite is priced (USD per million tokens: input $0.10, cached input $0.01, "
    "output $0.40). Output usage is total_tokens minus input_tokens, including hidden reasoning once. "
    "Missing cached-input counts widen input-cost bounds; missing usage or unknown models make cost incomplete. "
    "No-data days have null cost, and startup-day per-1000 rates are omitted because coverage is partial."
)


async def completed_games_by_day(session: AsyncSession, start: date, end: date) -> dict[str, int]:
    from db.models.countrydle import CountrydleDay, CountrydleState
    from db.models.guest_participation import GuestParticipation
    states = await session.execute(
        select(CountrydleDay.date, func.count(func.distinct(CountrydleState.user_id)))
        .join(CountrydleState, CountrydleState.day_id == CountrydleDay.id)
        .where(
            CountrydleState.is_game_over.is_(True),
            CountrydleState.user_id.is_not(None),
            CountrydleDay.date >= start,
            CountrydleDay.date <= end,
        )
        .group_by(CountrydleDay.date)
    )
    # Linked guests are represented by their state and must not be counted twice.
    guests = await session.execute(
        select(CountrydleDay.date, func.count(GuestParticipation.id))
        .join(CountrydleDay, CountrydleDay.id == GuestParticipation.day_id)
        .where(
            GuestParticipation.mode == "countrydle",
            GuestParticipation.user_id.is_(None),
            or_(GuestParticipation.won.is_(True), GuestParticipation.guesses_made >= 3),
            CountrydleDay.date >= start,
            CountrydleDay.date <= end,
        )
        .group_by(CountrydleDay.date)
    )
    totals: dict[str, int] = {}
    for game_day, count in states:
        totals[game_day.isoformat()] = int(count)
    for game_day, count in guests:
        key = game_day.isoformat()
        totals[key] = totals.get(key, 0) + int(count)
    return totals


def apply_measurement_coverage(report: dict[str, Any], started_at: str | None) -> date | None:
    started_date = datetime.fromisoformat(started_at).astimezone(UTC).date() if started_at else None
    for daily in report["days"]:
        observed_day = date.fromisoformat(daily["day"])
        if started_date is None or observed_day < started_date:
            daily["measurement_coverage"] = "none"
            daily["cost_status"] = "not_measured"
            daily["cost_lower_usd"] = None
            daily["cost_upper_usd"] = None
            daily["cost_lower_per_1000_games_usd"] = None
            daily["cost_upper_per_1000_games_usd"] = None
            daily["new_planner_rate_per_1000_games"] = None
            daily["new_planner_share_of_requests"] = None
            daily["new_planner_share_of_planner_requests"] = None
        elif observed_day == started_date:
            daily["measurement_coverage"] = "partial_startup_day"
            daily["new_planner_rate_per_1000_games"] = None
            daily["new_planner_share_of_requests"] = None
            daily["new_planner_share_of_planner_requests"] = None
            daily["cost_lower_per_1000_games_usd"] = None
            daily["cost_upper_per_1000_games_usd"] = None
            if daily["cost_status"] != "no_data":
                daily["cost_status"] = "incomplete_coverage"
        else:
            daily["measurement_coverage"] = "after_measurement_start"
    return started_date


async def build_country_cost_report_for_period(
    session: AsyncSession, start: date, end: date
) -> dict[str, Any]:
    """Build one report using the caller's async database session."""
    rows, started_at = await asyncio.gather(
        asyncio.to_thread(aggregate_daily_metrics, start, end),
        asyncio.to_thread(metrics_started_at),
    )
    completed = await completed_games_by_day(session, start, end)
    day_count = (end - start).days + 1
    for offset in range(day_count):
        completed.setdefault((start + timedelta(days=offset)).isoformat(), 0)
    report = build_cost_report(rows, completed)
    started_date = apply_measurement_coverage(report, started_at)
    if started_at:
        coverage_note = (
            f"Measurement store began {started_at}; days before {started_date.isoformat()} have no measured coverage. "
            "Request counts include requests that reached the Countrydle handler; dependency, body-validation, "
            "and rate-limiter rejections happen before it and are excluded."
        )
    else:
        coverage_note = (
            "No measurement store exists yet, so the window has no measured coverage. Request counts include "
            "requests that reached the Countrydle handler; dependency, body-validation, and rate-limiter "
            "rejections happen before it and are excluded."
        )
    report.update({
        "period_utc": {"start": start.isoformat(), "end": end.isoformat()},
        "metrics_started_at_utc": started_at,
        "coverage_note": coverage_note,
        "denominator_note": DENOMINATOR_NOTE,
        "scope_note": SCOPE_NOTE,
        "pricing_note": PRICING_NOTE,
    })
    return report


async def build_country_cost_report(session: AsyncSession, days: int = 7) -> dict[str, Any]:
    """Build a report for the requested number of completed UTC days."""
    end = datetime.now(UTC).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return await build_country_cost_report_for_period(session, start, end)
