"""Game eligibility is independent of canonical geography and historical facts."""
from datetime import date

from fastapi import HTTPException


def excluded_country_names(mode: str | None = None) -> tuple[str, ...]:
    return ("Israel", "Azerbaijan") if mode == "europe" else ("Israel",)


def is_country_eligible(name: str, mode: str | None = None) -> bool:
    normalized = name.strip().casefold()
    if normalized in {"israel", "state of israel"}:
        return False
    return mode != "europe" or normalized not in {"azerbaijan", "republic of azerbaijan"}


def require_eligible_target(day, mode: str | None = None):
    """Keep history readable, but never play a disabled pre-generated target."""
    if day is not None and day.date >= date.today() and not is_country_eligible(day.country.name, mode):
        raise HTTPException(status_code=503, detail="This game's target is no longer eligible.")
    return day
