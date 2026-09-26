"""Thread-safe bounded in-memory LRU cache for Gemini question execution plans."""

from __future__ import annotations

import re
import threading
import unicodedata
from collections import OrderedDict
from typing import Any


def strip_accents(text: str) -> str:
    """Remove combining diacritics and normalize Polish characters."""
    text = text.replace("ł", "l").replace("Ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize_question_key(mode: str, question: str) -> tuple[str, str]:
    """Normalize game mode and question text into a canonical cache key."""
    norm_mode = mode.strip().lower()
    cleaned = re.sub(r"\s+", " ", question.strip()).casefold()
    cleaned = cleaned.rstrip("?.,! ")
    cleaned = strip_accents(cleaned)
    return (norm_mode, cleaned)


class PlanCache:
    """Thread-safe LRU cache for question execution plans."""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: OrderedDict[tuple[str, str, str], Any] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, mode: str, question: str, *, version: str) -> Any | None:
        key = (version, *normalize_question_key(mode, question))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, mode: str, question: str, plan: Any, *, version: str) -> None:
        # Only validated provider responses reach the cache; failures never do.
        key = (version, *normalize_question_key(mode, question))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = plan
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            total = self._hits + self._misses
            hit_ratio = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_ratio_percent": round(hit_ratio, 1),
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0


# Global shared singleton cache instance
plan_cache = PlanCache(max_size=10000)
