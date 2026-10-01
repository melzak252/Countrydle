from __future__ import annotations

import hashlib
import hmac
import ipaddress
import math
import os
import time
from collections import OrderedDict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request

from utils.guest_session import SECRET_KEY


QUESTION_LIMIT = 30
QUESTION_WINDOW_SECONDS = 60
MAX_TRACKED_CLIENTS = 10_000
TRUST_X_REAL_IP = os.getenv("QUESTION_RATE_LIMIT_TRUST_X_REAL_IP", "false").lower() in {
    "1", "true", "yes",
}


def client_network_key(request: Request) -> str:
    """Hash a normalized client network; never retain or log the raw address."""
    address_text = request.client.host if request.client else "unknown"
    if TRUST_X_REAL_IP:
        forwarded_ip = request.headers.get("x-real-ip")
        if forwarded_ip:
            address_text = forwarded_ip.strip()

    try:
        address = ipaddress.ip_address(address_text.split("%", 1)[0])
        prefix = 32 if address.version == 4 else 64
        network = ipaddress.ip_network(f"{address}/{prefix}", strict=False).with_prefixlen
    except ValueError:
        network = "unknown"

    return hmac.new(
        SECRET_KEY.encode("utf-8"), network.encode("utf-8"), hashlib.sha256,
    ).hexdigest()


class QuestionAttemptLimiter:
    """Process-local sliding-window limit shared by every question endpoint."""

    def __init__(
        self,
        max_requests: int = QUESTION_LIMIT,
        window_seconds: int = QUESTION_WINDOW_SECONDS,
        max_clients: int = MAX_TRACKED_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.clock = clock
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()

    def retry_after(self, client_key: str) -> int | None:
        now = self.clock()
        requests = self._requests.get(client_key)
        if requests is not None:
            self._discard_expired(requests, now)
            if not requests:
                del self._requests[client_key]
                requests = None
            else:
                self._requests.move_to_end(client_key)

        if requests is None:
            if len(self._requests) >= self.max_clients:
                self._discard_expired_clients(now)
            if len(self._requests) >= self.max_clients:
                return self.window_seconds
            requests = deque()
            self._requests[client_key] = requests

        if len(requests) >= self.max_requests:
            return max(1, math.ceil(requests[0] + self.window_seconds - now))

        requests.append(now)
        return None

    def clear(self) -> None:
        self._requests.clear()

    def _discard_expired(self, requests: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while requests and requests[0] <= cutoff:
            requests.popleft()

    def _discard_expired_clients(self, now: float) -> None:
        for key, requests in list(self._requests.items()):
            self._discard_expired(requests, now)
            if not requests:
                del self._requests[key]


question_attempt_limiter = QuestionAttemptLimiter()


async def enforce_question_attempt_limit(request: Request) -> None:
    retry_after = question_attempt_limiter.retry_after(client_network_key(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many question attempts. Please wait before asking again.",
            headers={"Retry-After": str(retry_after)},
        )
