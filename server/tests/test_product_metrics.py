"""Real private PostgreSQL aggregates; no app/provider imports or player-data reads."""
import json
import os
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from scripts import product_metrics

pytestmark = [pytest.mark.real_database, pytest.mark.anyio]


async def seed_metrics(connection, cutoff):
    """Seed explicit observation/maturity boundaries into an owned empty schema."""
    start, end = cutoff - timedelta(days=11), cutoff - timedelta(days=6)
    for mode in product_metrics.MODES:
        await connection.execute(text(f"CREATE TABLE {mode}_days (id INTEGER PRIMARY KEY, date DATE)"))
        await connection.execute(text(f"""CREATE TABLE {mode}_states (
            id SERIAL PRIMARY KEY, user_id INTEGER, day_id INTEGER,
            questions_asked INTEGER, guesses_made INTEGER, is_game_over BOOLEAN)"""))
        if mode != "flagdle":
            await connection.execute(text(f"""CREATE TABLE {mode}_questions (
                id INTEGER PRIMARY KEY, user_id INTEGER, valid BOOLEAN, answer BOOLEAN,
                asked_at TIMESTAMP, original_question TEXT)"""))
    await connection.execute(text("""CREATE TABLE guest_participations (
        id SERIAL PRIMARY KEY, mode TEXT, day_id INTEGER, user_id INTEGER,
        questions_asked INTEGER, guesses_made INTEGER, won BOOLEAN)"""))
    await connection.execute(text("""CREATE TABLE answer_reports (
        id SERIAL PRIMARY KEY, mode TEXT, question_id INTEGER,
        reporter_id INTEGER, created_at TIMESTAMP, comment TEXT)"""))
    await connection.execute(text("""CREATE TABLE friend_matches (
        id INTEGER PRIMARY KEY, created_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
        status TEXT, result TEXT)"""))
    await connection.execute(text("CREATE TABLE friend_seats (id SERIAL PRIMARY KEY, match_id INTEGER, user_id INTEGER)"))
    days = [start, start + timedelta(days=1), start + timedelta(days=4),
            start - timedelta(days=3), start + timedelta(days=3),
            start + timedelta(days=7), start + timedelta(days=9)]
    await connection.execute(text("INSERT INTO countrydle_days VALUES (:id, :date)"),
                             [{"id": index, "date": day} for index, day in enumerate(days, 1)])
    states = [(1, 1, True), (1, 1, False), (2, 2, False), (3, 3, True),
              (4, 4, True), (4, 5, True), (1, 6, False), (2, 7, False)]
    await connection.execute(text("""INSERT INTO countrydle_states
        (user_id, day_id, questions_asked, guesses_made, is_game_over)
        VALUES (:user, :day, 0, 1, :completed)"""),
        [{"user": user, "day": day, "completed": completed} for user, day, completed in states])
    await connection.execute(text("INSERT INTO countrydle_states VALUES (DEFAULT, 5, 1, 0, 0, TRUE)"))
    await connection.execute(text("INSERT INTO flagdle_days VALUES (1, :date)"), {"date": days[1]})
    await connection.execute(text("INSERT INTO flagdle_states VALUES (DEFAULT, 2, 1, 0, 1, FALSE)"))
    await connection.execute(text("""INSERT INTO guest_participations
        (mode, day_id, user_id, questions_asked, guesses_made, won) VALUES
        ('countrydle', 1, NULL, 0, 1, FALSE), ('countrydle', 2, NULL, 0, 1, TRUE),
        ('countrydle', 3, 3, 1, 0, FALSE)"""))
    naive = lambda day: datetime.combine(day, time())
    question_rows = [(1, 1, True, False, naive(start)), (2, 1, True, True, naive(start)),
                     (3, None, True, False, naive(start)), (4, None, False, None, naive(start)),
                     (5, 1, True, None, naive(start)), (6, 1, True, True, None),
                     (7, 1, True, True, naive(start - timedelta(days=1))),
                     (8, 1, True, True, naive(end))]
    await connection.execute(text("""INSERT INTO countrydle_questions VALUES
        (:id, :user, :valid, :answer, :asked, 'PRIVATE_QUESTION_CANARY')"""),
        [{"id": id_, "user": user, "valid": valid, "answer": answer, "asked": asked}
         for id_, user, valid, answer, asked in question_rows])
    await connection.execute(text("INSERT INTO us_statedle_questions VALUES (1, 1, TRUE, FALSE, :asked, 'PRIVATE_QUESTION_CANARY')"),
                             {"asked": naive(start)})
    reports = [(1, 1, start + timedelta(days=1)), (1, 1, start + timedelta(days=1)),
               (3, None, start + timedelta(days=2)), (4, None, start + timedelta(days=3)),
               (7, 1, start + timedelta(days=1)), (8, 1, end), (2, 1, cutoff)]
    await connection.execute(text("""INSERT INTO answer_reports
        (mode, question_id, reporter_id, created_at, comment)
        VALUES ('countrydle', :question, :reporter, :created, 'PRIVATE_REPORT_CANARY')"""),
        [{"question": question, "reporter": reporter, "created": naive(created)}
         for question, reporter, created in reports])
    at = lambda day: datetime.combine(day, time(), UTC)
    duels = [
        (1, at(start), at(start + timedelta(days=1)), "finished", "solved", [1, 2]),
        (2, at(start), at(start + timedelta(days=7)), "finished", "draw", [1, 2]),
        (3, at(start + timedelta(days=1)), at(start + timedelta(days=2)), "finished", "forfeit", [1, 2]),
        (4, at(start + timedelta(days=1)), at(start + timedelta(days=2)), "finished", "interrupted", [1, 2]),
        (5, at(start + timedelta(days=4)), at(start + timedelta(days=5)), "finished", "cancelled", [1, 2]),
        (6, at(start + timedelta(days=4)) + timedelta(hours=1), at(start + timedelta(days=4)) + timedelta(hours=3), "finished", "solved", [1, 2]),
        (7, at(start + timedelta(days=1)), None, "finished", "solved", [1, 2]),
        (8, at(start + timedelta(days=2)), at(start + timedelta(days=3)), "finished", "solved", [None, None]),
        (9, at(start + timedelta(days=4)), at(start + timedelta(days=5)), "finished", "draw", [1, None]),
        (10, at(start + timedelta(days=1)), None, "waiting", None, []),
        (11, at(start) - timedelta(seconds=1), at(start), "finished", "solved", [1, 2]),
        (12, at(end), at(end) + timedelta(hours=1), "finished", "solved", [1, 2]),
    ]
    for id_, created, finished, status, result, seats in duels:
        await connection.execute(text("INSERT INTO friend_matches VALUES (:id, :created, :finished, :status, :result)"),
                                 {"id": id_, "created": created, "finished": finished, "status": status, "result": result})
        for user in seats:
            await connection.execute(text("INSERT INTO friend_seats VALUES (DEFAULT, :match, :user)"),
                                     {"match": id_, "user": user})
    return start, end


@pytest.fixture
async def metrics_snapshot():
    configured = os.getenv("QUESTION_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("Set QUESTION_TEST_DATABASE_URL to explicit disposable PostgreSQL")
    target = make_url(configured)
    if target.get_backend_name() != "postgresql" or target.host not in {"127.0.0.1", "localhost", "::1"} or not (
        target.database == "hardening" or (target.database or "").endswith(("_test", "_tests", "_e2e"))
    ):
        pytest.fail("Metrics fixtures require a named disposable loopback database, never DATABASE_URL")
    schema = "product_metrics_test_" + uuid4().hex
    bootstrap = create_async_engine(configured)
    engine = None
    try:
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(configured, isolation_level="REPEATABLE READ",
                                     connect_args={"server_settings": {"search_path": schema, "timezone": "UTC"}})
        cutoff = datetime.now(UTC).date()
        async with engine.begin() as connection:
            start, end = await seed_metrics(connection, cutoff)
        yield engine, start, end, cutoff
    finally:
        if engine is not None:
            await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await bootstrap.dispose()


async def test_retained_aggregate_cohorts_respect_ownership_boundaries_missingness_and_privacy(metrics_snapshot):
    engine, start, end, cutoff = metrics_snapshot
    async with engine.begin() as connection:
        await connection.execute(text("SET TRANSACTION READ ONLY"))
        report = await product_metrics.build_report(connection, start, end, cutoff)
    daily = report["daily_modes"]
    assert daily["countrydle"]["account_active_game_completion_snapshot"] == {"numerator": 3, "denominator": 4, "rate": 0.75}
    assert daily["countrydle"]["guest_activity"] == {"unlinked_active_games": 2, "unlinked_won_games": 1, "linked_active_games": 1}
    assert daily["countrydle"]["guest_terminal_completion"] is None
    proxy = report["account_retained_activity_proxies"]
    assert proxy["first_puzzle_date_any_game_completion_snapshot"]["numerator"] == 2
    assert proxy["first_puzzle_date_any_game_completion_snapshot"]["denominator"] == 3
    assert proxy["one_to_seven_puzzle_day_return"] == {"numerator": 1, "denominator": 2, "rate": 0.5}
    assert proxy["immature_accounts_excluded_from_return"] == 1
    questions = daily["countrydle"]["question_cohort_report_rates"]
    assert questions["account"]["answered_question_report_rate"] == {"numerator": 1, "denominator": 2, "rate": 0.5}
    assert questions["unattributed_or_guest"]["answered_question_report_rate"] == {"numerator": 1, "denominator": 1, "rate": 1.0}
    assert daily["countrydle"]["question_coverage"] == {"persisted_questions": 8, "missing_asked_at": 1, "questions_in_window": 5}
    assert daily["us_statedle"]["question_cohort_report_rates"]["account"]["answered_question_report_rate"] == {"numerator": 0, "denominator": 1, "rate": 0.0}
    assert report["report_submission_volume"] == {"reports": 5, "account_attributed_reports": 3, "guest_or_deleted_account_reports": 2}
    duels = report["retained_duel_creation_cohort"]
    assert duels["account_only"]["seven_day_completion"]["numerator"] == 2
    assert duels["account_only"]["seven_day_completion"]["denominator"] == 6
    assert duels["account_only"]["immature_matches_excluded"] == 1
    assert (duels["account_only"]["cancelled_snapshot"], duels["account_only"]["interrupted_snapshot"], duels["account_only"]["missing_finish_time"]) == (1, 1, 1)
    assert duels["mixed"]["seven_day_completion"]["rate"] == 1.0
    assert duels["guest_or_deleted_account_only"]["seven_day_completion"]["rate"] == 1.0
    assert duels["unknown_no_seats"]["seven_day_completion"]["rate"] == 0.0
    assert daily["powiatdle"]["account_active_game_completion_snapshot"]["rate"] is None
    assert "question_cohort_report_rates" not in daily["flagdle"]
    serialized = json.dumps(report)
    for forbidden in ("PRIVATE_QUESTION_CANARY", "PRIVATE_REPORT_CANARY", '"user_id"', '"reporter_id"', '"question_id"', '"match_id"'):
        assert forbidden not in serialized
