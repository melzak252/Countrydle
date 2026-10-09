"""Small durable aggregate store for Countrydle question cost measurements."""
from __future__ import annotations

from datetime import UTC, date, datetime
import os
from pathlib import Path
import sqlite3
from typing import Mapping

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR if (APP_DIR / "data").is_dir() else APP_DIR.parent
DEFAULT_DATABASE_PATH = DATA_DIR / "data" / "countrydle_cost_metrics.sqlite3"
COUNTERS = (
    "requests", "answered", "invalid", "quota_failures", "provider_failures",
    "template_answers", "plan_cache_hits", "new_planner_calls", "fallback_cache_hits",
    "fallback_model_calls", "retries", "failed_attempts", "input_tokens",
    "cached_input_tokens", "cached_input_unknown_tokens", "output_tokens", "thought_tokens",
    "total_tokens", "unknown_usage_calls",
)
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "thought_tokens", "total_tokens")
MODEL_FLASH_LITE = "gemini-2.5-flash-lite"


def _database_path(path: str | Path | None = None) -> Path:
    return Path(path or os.getenv("COUNTRYDLE_COST_METRICS_DB", DEFAULT_DATABASE_PATH))


def _connect(path: str | Path | None, started_at: str | None = None) -> sqlite3.Connection:
    target = _database_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=10, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS daily_metrics ("
        "day TEXT NOT NULL, model TEXT NOT NULL, stage TEXT NOT NULL, "
        + ", ".join(f"{column} INTEGER NOT NULL DEFAULT 0" for column in COUNTERS)
        + ", PRIMARY KEY(day, model, stage))"
    )
    connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute(
        "INSERT OR IGNORE INTO metadata(key, value) VALUES ('started_at', ?)",
        (started_at or datetime.now(UTC).isoformat(),),
    )
    return connection


def _integer(value) -> int:
    return int(value) if isinstance(value, (int, float)) and value >= 0 else 0


def _model_bucket(model: object) -> str:
    normalized = "".join(character for character in str(model or "").lower() if character.isalnum())
    if normalized in {"gemini25flashlite", "gemini25flashlite001", "modelsgemini25flashlite", "modelsgemini25flashlite001"}:
        return MODEL_FLASH_LITE
    return "unpriced"

def append_metrics(event: Mapping, *, database_path: str | Path | None = None) -> None:
    """Atomically add whitelisted counters; never accept caller payloads or identities."""
    day = date.fromisoformat(str(event["day"])).isoformat()
    stage = str(event.get("stage", "route"))
    if stage not in {"route", "planner", "fallback", "template", "local"}:
        stage = "route"
    model = _model_bucket(event.get("model")) if stage in {"planner", "fallback"} else "none"
    counters = {name: _integer(event.get(name, 0)) for name in COUNTERS}
    if counters["cached_input_tokens"] > counters["input_tokens"]:
        counters["cached_input_tokens"] = counters["input_tokens"]
    names = ", ".join(COUNTERS)
    placeholders = ", ".join("?" for _ in range(3 + len(COUNTERS)))
    updates = ", ".join(f"{name}=daily_metrics.{name}+excluded.{name}" for name in COUNTERS)
    connection = _connect(database_path, event.get("started_at"))
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            f"INSERT INTO daily_metrics(day, model, stage, {names}) VALUES ({placeholders}) "
            f"ON CONFLICT(day, model, stage) DO UPDATE SET {updates}",
            (day, model, stage, *(counters[name] for name in COUNTERS)),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def aggregate_daily_metrics(start: date, end: date | None = None, *, database_path: str | Path | None = None) -> list[dict]:
    target = _database_path(database_path)
    if not target.exists():
        return []
    connection = sqlite3.connect(target, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        query = "SELECT day, model, stage, " + ", ".join(COUNTERS) + " FROM daily_metrics WHERE day >= ?"
        parameters: tuple = (start.isoformat(),)
        if end is not None:
            query += " AND day <= ?"
            parameters += (end.isoformat(),)
        query += " ORDER BY day, stage, model"
        cursor = connection.execute(query, parameters)
        return [dict(zip((column[0] for column in cursor.description), row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def metrics_started_at(*, database_path: str | Path | None = None) -> str | None:
    target = _database_path(database_path)
    if not target.exists():
        return None
    connection = sqlite3.connect(target, timeout=10)
    try:
        row = connection.execute("SELECT value FROM metadata WHERE key='started_at'").fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def build_cost_report(rows: list[Mapping], completed_games: Mapping[str, int]) -> dict:
    """Summarize measured provider cost and state the games denominator explicitly."""
    by_day: dict[str, list[Mapping]] = {}
    for row in rows:
        by_day.setdefault(str(row["day"]), []).append(row)
    days = []
    for day in sorted(set(by_day) | set(completed_games)):
        day_rows = by_day.get(day, [])
        model_totals: dict[str, dict] = {}
        stage_totals: dict[str, dict[str, dict]] = {}
        total_known_lower = total_known_upper = 0.0
        total_usage_unknown = False
        cached_usage_unknown = False
        new_planner_calls = planner_cache_hits = planner_requests = 0
        route_counts = {name: 0 for name in ("requests", "answered", "invalid", "quota_failures", "provider_failures", "template_answers", "fallback_cache_hits", "fallback_model_calls", "retries", "failed_attempts")}
        for row in day_rows:
            for key in route_counts:
                route_counts[key] += int(row.get(key, 0) or 0)
            if row.get("stage") == "planner":
                planner_requests += int(row.get("new_planner_calls", 0) or 0) + int(row.get("plan_cache_hits", 0) or 0)
                new_planner_calls += int(row.get("new_planner_calls", 0) or 0)
                planner_cache_hits += int(row.get("plan_cache_hits", 0) or 0)
            if row.get("stage") not in {"planner", "fallback"}:
                continue
            model = str(row.get("model", "unpriced"))
            stage_entry = stage_totals.setdefault(str(row["stage"]), {}).setdefault(
                model,
                {name: 0 for name in (*TOKEN_FIELDS, "cached_input_unknown_tokens", "unknown_usage_calls",
                                      "new_planner_calls", "plan_cache_hits", "fallback_cache_hits",
                                      "fallback_model_calls", "retries", "failed_attempts")},
            )
            for name in (*TOKEN_FIELDS, "cached_input_unknown_tokens", "unknown_usage_calls",
                         "new_planner_calls", "plan_cache_hits", "fallback_cache_hits",
                         "fallback_model_calls", "retries", "failed_attempts"):
                stage_entry[name] += int(row.get(name, 0) or 0)
            entry = model_totals.setdefault(model, {"input_tokens": 0, "cached_input_tokens": 0, "cached_input_unknown_tokens": 0, "output_tokens": 0, "thought_tokens": 0, "total_tokens": 0, "unknown_usage_calls": 0, "cost_lower_usd": 0.0, "cost_upper_usd": 0.0, "cost_incomplete": False, "cost_bounded": False})
            for key in TOKEN_FIELDS:
                if row.get(key) is not None:
                    entry[key] += int(row.get(key, 0) or 0)
            entry["unknown_usage_calls"] += int(row.get("unknown_usage_calls", 0) or 0)
            entry["cached_input_unknown_tokens"] += int(row.get("cached_input_unknown_tokens", 0) or 0)
            if row.get("unknown_usage_calls", 0):
                entry["cost_incomplete"] = True
            if model != MODEL_FLASH_LITE:
                continue
            input_tokens = row.get("input_tokens")
            total_tokens = row.get("total_tokens")
            cached_tokens = row.get("cached_input_tokens")
            if input_tokens is None or total_tokens is None:
                entry["cost_incomplete"] = total_usage_unknown = True
                continue
            if row.get("unknown_usage_calls", 0):
                entry["cost_incomplete"] = total_usage_unknown = True
            input_tokens, total_tokens = int(input_tokens), int(total_tokens)
            billable_output = max(0, total_tokens - input_tokens)
            known_cached = int(cached_tokens or 0)
            unknown_cached = row.get("cached_input_unknown_tokens")
            if unknown_cached is None and cached_tokens is None:
                unknown_cached = input_tokens
            if unknown_cached:
                cached_usage_unknown = True
                entry["cost_bounded"] = True
            unknown_cached = int(unknown_cached or 0)
            lower_cached = min(input_tokens, known_cached + unknown_cached)
            upper_cached = min(input_tokens, known_cached)
            lower = (max(0, input_tokens - lower_cached) * .10 + lower_cached * .01 + billable_output * .40) / 1_000_000
            upper = (max(0, input_tokens - upper_cached) * .10 + upper_cached * .01 + billable_output * .40) / 1_000_000
            entry["cost_lower_usd"] += lower
            entry["cost_upper_usd"] += upper
            total_known_lower += lower
            total_known_upper += upper
        games = int(completed_games.get(day, 0))
        priced = {name: value for name, value in model_totals.items() if name == MODEL_FLASH_LITE}
        unpriced = sorted(name for name in model_totals if name != MODEL_FLASH_LITE)
        unpriced_usage = {name: value for name, value in model_totals.items() if name != MODEL_FLASH_LITE}
        days.append({
            "day": day, "completed_games": games, **route_counts,
            "new_planner_calls": new_planner_calls, "planner_cache_hits": planner_cache_hits,
            "new_planner_rate_per_1000_games": round(new_planner_calls * 1000 / games, 4) if day_rows and games else None,
            "new_planner_share_of_requests": round(new_planner_calls / route_counts["requests"], 4) if route_counts["requests"] else None,
            "new_planner_share_of_planner_requests": round(new_planner_calls / planner_requests, 4) if planner_requests else None,
            "stage_usage": stage_totals,
            "priced_models": priced, "unpriced_models": unpriced, "unpriced_model_usage": unpriced_usage,
            "cost_lower_usd": round(total_known_lower, 8) if day_rows else None,
            "cost_upper_usd": round(total_known_upper, 8) if day_rows else None,
            "cost_lower_per_1000_games_usd": round(total_known_lower * 1000 / games, 8) if day_rows and games and not total_usage_unknown and not unpriced else None,
            "cost_upper_per_1000_games_usd": round(total_known_upper * 1000 / games, 8) if day_rows and games and not total_usage_unknown and not unpriced else None,
            "cost_status": (
                "no_data" if not day_rows
                else "incomplete" if total_usage_unknown or unpriced
                else "bounded" if cached_usage_unknown
                else "complete"
            ),
        })
    return {"days": days}
