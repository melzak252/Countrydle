"""UTC clock and rollover boundaries for daily puzzles."""

from datetime import date, datetime, time, timedelta, timezone


def utc_now() -> datetime:
    """Return the current instant as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_today() -> date:
    """Return today's puzzle date in UTC."""
    return utc_now().date()


def next_utc_midnight(now: datetime) -> datetime:
    """Return the first UTC midnight strictly after an aware instant."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    tomorrow = now.astimezone(timezone.utc).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)
