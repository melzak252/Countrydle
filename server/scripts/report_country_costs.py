"""Print measured Countrydle Gemini planner/fallback cost for completed UTC days."""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta
import importlib.util
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import create_async_engine

_METRICS_SPEC = importlib.util.spec_from_file_location(
    "_countrydle_cost_metrics", SERVER_DIR / "utils" / "country_cost_metrics.py"
)
if _METRICS_SPEC is None or _METRICS_SPEC.loader is None:
    raise ImportError("Could not load Countrydle aggregate metrics module")
_METRICS_MODULE = importlib.util.module_from_spec(_METRICS_SPEC)
_METRICS_SPEC.loader.exec_module(_METRICS_MODULE)
aggregate_daily_metrics = _METRICS_MODULE.aggregate_daily_metrics
build_cost_report = _METRICS_MODULE.build_cost_report
metrics_started_at = _METRICS_MODULE.metrics_started_at


async def completed_games_by_day(database_url: str, start: date, end: date) -> dict[str, int]:
    os.environ.setdefault("DATABASE_URL", database_url)
    from db.models.countrydle import CountrydleDay, CountrydleState
    from db.models.guest_participation import GuestParticipation
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            states = await connection.execute(
                select(CountrydleDay.date, func.count(func.distinct(CountrydleState.user_id)))
                .join(CountrydleState, CountrydleState.day_id == CountrydleDay.id)
                .where(CountrydleState.is_game_over.is_(True), CountrydleState.user_id.is_not(None), CountrydleDay.date >= start, CountrydleDay.date <= end)
                .group_by(CountrydleDay.date)
            )
            # Only unlinked browser identities are counted here; linked play is
            # represented by its CountrydleState, so the same game is not doubled.
            guests = await connection.execute(
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
    finally:
        await engine.dispose()

def apply_measurement_coverage(report: dict, started_at: str | None) -> date | None:
    started_date = (
        datetime.fromisoformat(started_at).astimezone(UTC).date()
        if started_at else None
    )
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="completed UTC days to include (default: 7)")
    load_dotenv()
    args = parser.parse_args(argv)
    if args.days < 1 or args.days > 366:
        parser.error("--days must be between 1 and 366")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required to read completed-game denominators", file=sys.stderr)
        return 2

    end = datetime.now(UTC).date() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    try:
        rows = aggregate_daily_metrics(start, end)
        completed = asyncio.run(completed_games_by_day(database_url, start, end))
        for offset in range(args.days):
            completed.setdefault((start + timedelta(days=offset)).isoformat(), 0)
        report = build_cost_report(rows, completed)
        started_at = metrics_started_at()
    except Exception as exc:
        print(f"Could not build Countrydle cost report ({type(exc).__name__}); check DATABASE_URL and metrics storage", file=sys.stderr)
        return 1

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
        "denominator_note": (
            "Completed games are won or lost Countrydle daily states plus unlinked guest participations "
            "(won or at least 3 guesses); linked guests are counted only through their state. "
            "Per-1000 rates use completed games, not all requests."
        ),
        "scope_note": "Gemini planner and fallback generation only; embeddings, retrieval, hosting, and other modes are excluded.",
        "pricing_note": (
            "Only Gemini 2.5 Flash-Lite is priced (USD per million tokens: input $0.10, cached input $0.01, "
            "output $0.40). Output usage is total_tokens minus input_tokens, including hidden reasoning once. "
            "Missing cached-input counts widen input-cost bounds; missing usage or unknown models make cost incomplete. "
            "No-data days have null cost, and startup-day per-1000 rates are omitted because coverage is partial."
        ),
    })
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
