"""Helpers for spending bounded work against an absolute monotonic deadline."""
import time


def remaining_timeout(deadline: float | None, configured: float | None = None) -> float | None:
    """Return the configured timeout bounded by the deadline's remaining time."""
    if deadline is None:
        return configured

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Request deadline has expired")
    if configured is not None and configured > 0:
        return min(configured, remaining)
    return remaining
