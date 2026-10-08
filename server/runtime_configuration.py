"""Validated signing and exact browser-origin configuration for this process."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Match the existing nearest-file dotenv precedence without searching outside
# this checkout. Explicit process environment always takes precedence.
_SERVER_DIR = Path(__file__).resolve().parent
for _dotenv_path in (_SERVER_DIR / ".env", _SERVER_DIR.parent / ".env"):
    if _dotenv_path.is_file():
        load_dotenv(dotenv_path=_dotenv_path, override=False)
        break

_PUBLIC_SIGNING_KEYS = frozenset({
    "fallback_countrydle_secret",
    "your_secret_key",
    "change-me",
    "...",
})

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or not SECRET_KEY.strip() or SECRET_KEY.strip().lower() in _PUBLIC_SIGNING_KEYS:
    raise RuntimeError("SECRET_KEY must be explicitly configured with a private signing key, not a public placeholder.")

# Validation must not normalize valid key bytes: existing signatures and
# sessions depend on retaining the exact configured value.
ALGORITHM = os.getenv("ALGORITHM", "HS256")
CORS_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)
if any(origin in {"*", "null"} for origin in CORS_ALLOWED_ORIGINS):
    raise RuntimeError("CORS_ALLOWED_ORIGINS must contain exact browser origins, not wildcard or null origins.")
