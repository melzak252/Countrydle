"""Report aggregate product evidence from existing PostgreSQL gameplay records.

No application imports, schema setup, tracking calls, or writes. See
 docs/product-evidence.md for definitions and limitations.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, time
import json
import os
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


# Existing model table families; identifiers never come from command-line input.
MODES = ("countrydle", "powiatdle", "wojewodztwodle", "us_statedle", "continental", "flagdle")


def fraction(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


async def aggregate(connection, sql: str, parameters: dict) -> dict:
    return dict((await connection.execute(text(sql), parameters)).mappings().one())


async def build_report(connection, start: date, end: date, observed_until: date) -> dict:
    """Read aggregates only; caller must establish a read-only snapshot transaction."""
    parameters = {
        "start": start, "end": end, "observed_until": observed_until,
        "start_at": datetime.combine(start, time(), UTC),
        "end_at": datetime.combine(end, time(), UTC),
        "cutoff_at": datetime.combine(observed_until, time(), UTC),
        # Interpret naive timestamps as UTC; historical writer timezones are unverified.
        "start_naive": datetime.combine(start, time()),
        "end_naive": datetime.combine(end, time()),
        "cutoff_naive": datetime.combine(observed_until, time()),
    }
    report = {
        "window": {"start_inclusive": str(start), "end_exclusive": str(end),
                   "observed_until_exclusive": str(observed_until), "timezone": "UTC"},
        "snapshot_generated_at": datetime.now(UTC).isoformat(),
        "unknown": {
            "true_first_game_completion": "No first-visit/start cohort or exposure denominator; earliest retained puzzle activity is not first-game conversion.",
            "visitor_return_rate": "No visitor cohort, consent/exposure data or durable cross-device guest identity.",
            "guest_terminal_completion": "Historical guest participation records do not consistently establish losses or completion times.",
            "consent_sample_coverage": "Analytics deployment, consent choices, blockers and visitor coverage are not in these tables.",
            "question_report_timestamp_timezone": "Timezone-less question/report timestamps are interpreted as UTC; historical writer timezones are unverified, so UTC alignment is conditional.",
            "flag_question_report_coverage": "New Flag question persistence does not reconstruct historical coverage or establish a reviewed report-control surface; excluded from question/report cohort rates.",
        },
        "daily_modes": {},
        "caveats": [
            "Retained records only; deletion, guest-to-account sync and missing history bias cohorts.",
            "Daily dates identify puzzles, not actual visit/action/completion timestamps.",
            "Daily completion and ownership are current snapshot values, not historical as-of reconstructions.",
            "Continental aggregates all continents; guest linked rows are not additive to account activity.",
            "Null ownership may mean guest or deleted account; report rates are not verified answer-error rates.",
            "Duel cleanup removes older completed records; creation cohorts are survivor-biased.",
            "No baseline observations or feature priority are claimed until an authorized report is run.",
        ],
    }
    account_activity = []
    for mode in MODES:
        params = {**parameters, "mode": mode, "guest_mode": "continental:%" if mode == "continental" else mode}
        # Deduplicate legacy states by logical account/puzzle key before counting.
        activity = f"""
            SELECT s.user_id, d.date AS puzzle_date,
                   bool_or(s.is_game_over) AS completed
            FROM {mode}_states s JOIN {mode}_days d ON d.id = s.day_id
            WHERE s.user_id IS NOT NULL AND (s.questions_asked > 0 OR s.guesses_made > 0)
            GROUP BY s.user_id, d.id, d.date
        """
        account_activity.append(activity)
        account = await aggregate(connection, f"""
            WITH activity AS ({activity})
            SELECT count(*) AS active_games,
                   count(*) FILTER (WHERE completed) AS completed_games,
                   count(DISTINCT user_id) AS active_accounts
            FROM activity WHERE puzzle_date >= :start AND puzzle_date < :end
        """, params)
        guests = await aggregate(connection, f"""
            SELECT count(*) FILTER (WHERE g.user_id IS NULL) AS unlinked_active_games,
                   count(*) FILTER (WHERE g.user_id IS NULL AND g.won) AS unlinked_won_games,
                   count(*) FILTER (WHERE g.user_id IS NOT NULL) AS linked_active_games
            FROM guest_participations g JOIN {mode}_days d ON d.id = g.day_id
            WHERE g.mode LIKE :guest_mode AND d.date >= :start AND d.date < :end
              AND (g.questions_asked > 0 OR g.guesses_made > 0)
        """, params)
        entry = {
            "account_activity": account,
            "account_active_game_completion_snapshot": fraction(account["completed_games"], account["active_games"]),
            "guest_activity": guests,
            "guest_terminal_completion": None,
        }
        if mode != "flagdle":
            # Population is question ownership at query time, not reporter identity.
            questions = await aggregate(connection, f"""
                SELECT count(*) AS persisted_questions,
                       count(*) FILTER (WHERE q.asked_at IS NULL) AS missing_asked_at,
                       count(*) FILTER (WHERE q.asked_at >= :start_naive AND q.asked_at < :end_naive) AS questions_in_window
                FROM {mode}_questions q
            """, params)
            entry["question_coverage"] = questions
            rates = (await connection.execute(text(f"""
                SELECT CASE WHEN q.user_id IS NOT NULL THEN 'account'
                            ELSE 'unattributed_or_guest' END AS population,
                       count(*) AS persisted_questions,
                       count(*) FILTER (WHERE q.valid AND q.answer IS NOT NULL) AS answered_questions,
                       count(*) FILTER (WHERE reported) AS reported_questions,
                       count(*) FILTER (WHERE reported AND q.valid AND q.answer IS NOT NULL) AS reported_answers
                FROM {mode}_questions q
                CROSS JOIN LATERAL (
                    SELECT EXISTS (
                        SELECT 1 FROM answer_reports r
                        WHERE r.mode = :mode AND r.question_id = q.id AND r.created_at < :cutoff_naive
                    ) AS reported
                ) r
                WHERE q.asked_at >= :start_naive AND q.asked_at < :end_naive
                GROUP BY population ORDER BY population
            """), params)).mappings().all()
            entry["question_cohort_report_rates"] = {
                row["population"]: {
                    "persisted_questions": row["persisted_questions"],
                    "reported_questions": row["reported_questions"],
                    "answered_question_report_rate": fraction(row["reported_answers"], row["answered_questions"]),
                } for row in rates
            }
        report["daily_modes"][mode] = entry

    # This is explicitly an earliest-retained-activity proxy, never visitor retention.
    union = " UNION ALL ".join(account_activity)
    cohorts = await aggregate(connection, f"""
        WITH activity AS ({union}),
        first_seen AS (
            SELECT user_id, min(puzzle_date) AS first_date FROM activity
            WHERE puzzle_date < :observed_until GROUP BY user_id
        ), cohort AS (
            SELECT f.*,
                   EXISTS (SELECT 1 FROM activity a WHERE a.user_id = f.user_id
                           AND a.puzzle_date = f.first_date AND a.completed) AS completed_first_date,
                   EXISTS (SELECT 1 FROM activity a WHERE a.user_id = f.user_id
                           AND a.puzzle_date > f.first_date AND a.puzzle_date <= f.first_date + 7
                           AND a.puzzle_date < :observed_until) AS returned
            FROM first_seen f WHERE first_date >= :start AND first_date < :end
        )
        SELECT count(*) AS observed_first_date_accounts,
               count(*) FILTER (WHERE completed_first_date) AS completed_on_first_puzzle_date,
               count(*) FILTER (WHERE first_date + 7 < :observed_until) AS mature_accounts,
               count(*) FILTER (WHERE first_date + 7 < :observed_until AND returned) AS returned_mature_accounts
        FROM cohort
    """, parameters)
    report["account_retained_activity_proxies"] = {
        "first_puzzle_date_any_game_completion_snapshot": fraction(
            cohorts["completed_on_first_puzzle_date"], cohorts["observed_first_date_accounts"]),
        "one_to_seven_puzzle_day_return": fraction(
            cohorts["returned_mature_accounts"], cohorts["mature_accounts"]),
        "immature_accounts_excluded_from_return": cohorts["observed_first_date_accounts"] - cohorts["mature_accounts"],
    }
    report["report_submission_volume"] = await aggregate(connection, """
        SELECT count(*) AS reports,
               count(*) FILTER (WHERE reporter_id IS NOT NULL) AS account_attributed_reports,
               count(*) FILTER (WHERE reporter_id IS NULL) AS guest_or_deleted_account_reports
        FROM answer_reports WHERE created_at >= :start_naive AND created_at < :end_naive
    """, parameters)
    # A match is classified by its retained seats, not by a transient login event.
    duel_rows = (await connection.execute(text("""
        WITH cohort AS (
            SELECT m.*,
                   CASE WHEN count(s.id) = 0 THEN 'unknown_no_seats'
                        WHEN count(s.user_id) = count(s.id) THEN 'account_only'
                        WHEN count(s.user_id) = 0 THEN 'guest_or_deleted_account_only'
                        ELSE 'mixed' END AS population
            FROM friend_matches m LEFT JOIN friend_seats s ON s.match_id = m.id
            WHERE m.created_at >= :start_at AND m.created_at < :end_at
            GROUP BY m.id
        )
        SELECT population, count(*) AS created_matches,
               count(*) FILTER (WHERE created_at + interval '7 days' <= :cutoff_at) AS mature_matches,
               count(*) FILTER (WHERE created_at + interval '7 days' <= :cutoff_at
                                AND finished_at >= created_at AND finished_at < created_at + interval '7 days'
                                AND status = 'finished' AND result IN ('solved', 'draw', 'forfeit')) AS completed_matches,
               count(*) FILTER (WHERE result = 'cancelled') AS cancelled_snapshot,
               count(*) FILTER (WHERE result = 'interrupted') AS interrupted_snapshot,
               count(*) FILTER (WHERE status = 'finished' AND finished_at IS NULL) AS missing_finish_time
        FROM cohort GROUP BY population ORDER BY population
    """), parameters)).mappings().all()
    report["retained_duel_creation_cohort"] = {
        row["population"]: {
            "created_matches": row["created_matches"],
            "seven_day_completion": fraction(row["completed_matches"], row["mature_matches"]),
            "immature_matches_excluded": row["created_matches"] - row["mature_matches"],
            "cancelled_snapshot": row["cancelled_snapshot"],
            "interrupted_snapshot": row["interrupted_snapshot"],
            "missing_finish_time": row["missing_finish_time"],
        } for row in duel_rows
    }
    return report


async def run(database_url: str, start: date, end: date, observed_until: date) -> dict:
    engine = create_async_engine(database_url, isolation_level="REPEATABLE READ")
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                await connection.execute(text("SET LOCAL statement_timeout = '60s'"))
                await connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
                return await build_report(connection, start, end, observed_until)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="inclusive UTC date")
    parser.add_argument("--end", type=date.fromisoformat, required=True, help="exclusive UTC date")
    parser.add_argument("--observed-until", type=date.fromisoformat, default=datetime.now(UTC).date(),
                        help="exclusive observation cutoff; defaults to current UTC date")
    args = parser.parse_args(argv)
    if not args.start < args.end <= args.observed_until <= datetime.now(UTC).date():
        parser.error("require start < end <= observed-until <= current UTC date")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("explicit DATABASE_URL is required; .env files are not loaded")
    try:
        if make_url(database_url).drivername != "postgresql+asyncpg":
            parser.error("DATABASE_URL must use postgresql+asyncpg")
        report = asyncio.run(run(database_url, args.start, args.end, args.observed_until))
    except Exception as exc:
        print(f"Product aggregate report failed ({type(exc).__name__}); check schema and read-only access", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
