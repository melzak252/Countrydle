"""Print measured Countrydle Gemini planner/fallback cost for completed UTC days."""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from utils.country_cost_report import build_country_cost_report_for_period


async def _report(database_url: str, start, end) -> dict:
    engine = create_async_engine(database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await build_country_cost_report_for_period(session, start, end)
    finally:
        await engine.dispose()


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
        report = asyncio.run(_report(database_url, start, end))
    except Exception as exc:
        print(f"Could not build Countrydle cost report ({type(exc).__name__}); check DATABASE_URL and metrics storage", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
