"""Game eligibility is independent of canonical geography and historical facts."""
from datetime import date

from daily_clock import utc_today

from fastapi import HTTPException


def excluded_country_names(mode: str | None = None) -> tuple[str, ...]:
    if mode == "europe":
        return ("Israel", "Azerbaijan", "Kazakhstan", "Georgia")
    if mode == "asia":
        return ("Israel", "Egypt")
    return ("Israel",)


def is_country_eligible(name: str, mode: str | None = None) -> bool:
    normalized = name.strip().casefold()
    if normalized in {"israel", "state of israel"}:
        return False
    if mode == "europe":
        return normalized not in {"azerbaijan", "republic of azerbaijan", "kazakhstan", "georgia"}
    if mode == "asia":
        return normalized not in {"egypt", "arab republic of egypt"}
    return True


def require_eligible_target(day, mode: str | None = None, *, today: date | None = None):
    """Keep history readable, but never play a disabled pre-generated target."""
    current_date = today if today is not None else utc_today()
    if day is not None and day.date >= current_date and not is_country_eligible(day.country.name, mode):
        raise HTTPException(status_code=503, detail="This game's target is no longer eligible.")
    return day
