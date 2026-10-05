from concurrent.futures import ThreadPoolExecutor
from datetime import date

from utils.country_cost_metrics import (
    aggregate_daily_metrics,
    append_metrics,
    build_cost_report,
)

from scripts.report_country_costs import apply_measurement_coverage


def test_metrics_aggregate_atomically_across_reopen_and_threads(tmp_path):
    database = tmp_path / "country-cost.sqlite3"

    def append_one(_):
        append_metrics(
            {"day": "2026-10-03", "model": "gemini-2.5-flash-lite", "stage": "planner",
             "new_planner_calls": 1, "input_tokens": 100, "output_tokens": 20},
            database_path=database,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append_one, range(32)))

    rows = aggregate_daily_metrics(date(2026, 10, 3), database_path=database)
    assert len(rows) == 1
    assert rows[0]["new_planner_calls"] == 32
    assert rows[0]["input_tokens"] == 3200
    assert rows[0]["output_tokens"] == 640


def test_report_prices_flash_lite_bounds_and_completed_game_denominator():
    rows = [
        {"day": "2026-10-03", "model": "none", "stage": "route", "requests": 6},
        {"day": "2026-10-03", "model": "gemini-2.5-flash-lite", "stage": "planner",
         "input_tokens": 1000, "cached_input_tokens": None, "total_tokens": 1400,
         "unknown_usage_calls": 0, "new_planner_calls": 2},
        {"day": "2026-10-03", "model": "unpriced", "stage": "fallback",
         "input_tokens": 0, "cached_input_tokens": 0, "total_tokens": 0,
         "unknown_usage_calls": 1, "fallback_model_calls": 1},
    ]
    report = build_cost_report(rows, {"2026-10-03": 500})
    day = report["days"][0]

    assert day["completed_games"] == 500
    assert day["new_planner_calls"] == 2
    assert day["new_planner_rate_per_1000_games"] == 4
    assert day["new_planner_share_of_requests"] == round(2 / 6, 4)
    assert day["cost_status"] == "incomplete"
    assert day["priced_models"]["gemini-2.5-flash-lite"]["cost_lower_usd"] < day["priced_models"]["gemini-2.5-flash-lite"]["cost_upper_usd"]
    assert day["priced_models"]["gemini-2.5-flash-lite"]["cost_bounded"] is True
    assert day["unpriced_models"] == ["unpriced"]
    assert day["unpriced_model_usage"]["unpriced"]["unknown_usage_calls"] == 1
    assert day["cost_lower_per_1000_games_usd"] is None

def test_cost_prices_cached_input_at_flash_lite_rate_and_leaves_no_data_null():
    report = build_cost_report(
        [{"day": "2026-10-03", "model": "gemini-2.5-flash-lite", "stage": "planner",
          "input_tokens": 1000, "cached_input_tokens": 100, "total_tokens": 1000,
          "unknown_usage_calls": 0}],
        {"2026-10-03": 1000, "2026-10-04": 0},
    )
    measured, empty = report["days"]

    assert measured["cost_lower_usd"] == measured["cost_upper_usd"] == 0.000091
    assert empty["cost_status"] == "no_data"
    assert empty["cost_lower_usd"] is None
    assert empty["cost_upper_per_1000_games_usd"] is None
    assert empty["new_planner_rate_per_1000_games"] is None

def test_partial_startup_day_does_not_publish_full_day_rates():
    report = build_cost_report(
        [{"day": "2026-10-03", "model": "none", "stage": "route", "requests": 3}],
        {"2026-10-03": 300, "2026-10-04": 400},
    )

    apply_measurement_coverage(report, "2026-10-03T12:00:00+00:00")
    startup, full_day = report["days"]

    assert startup["measurement_coverage"] == "partial_startup_day"
    assert startup["new_planner_rate_per_1000_games"] is None
    assert startup["cost_lower_per_1000_games_usd"] is None
    assert full_day["measurement_coverage"] == "after_measurement_start"
