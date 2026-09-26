"""Thread-safe bounded LRU with persistent SQLite storage for question plans."""

from __future__ import annotations

import importlib
import json
import re
import sqlite3
import threading
import unicodedata
from collections.abc import Iterator
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[2]


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
    """Thread-safe LRU backed by a SQLite table for durable plan reuse."""

    def __init__(self, max_size: int = 10000, db_path: str | Path | None = None):
        self.max_size = max_size
        self.db_path = Path(db_path) if db_path is not None else ROOT_DIR / "data" / "plan_cache.sqlite"
        self._cache: OrderedDict[tuple[str, str, str], Any] = OrderedDict()
        self._lock = threading.RLock()
        self._loaded_versions: set[str] = set()
        self._hits = 0
        self._misses = 0
        self._initialize_database()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS plan_cache (
                    version TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    improved_question TEXT,
                    explanation TEXT,
                    valid INTEGER,
                    supported INTEGER,
                    fallback_reason TEXT,
                    created_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (version, mode, question_key)
                )
            """)

    @staticmethod
    def _serialize(plan: Any) -> tuple[str, str | None, str | None, int | None, int | None, str | None]:
        if is_dataclass(plan) and not isinstance(plan, type):
            data = {field.name: getattr(plan, field.name) for field in fields(plan)}
            descriptor = {"module": type(plan).__module__, "class": type(plan).__qualname__, "data": data}
            improved = getattr(plan, "improved_question", None)
            explanation = getattr(plan, "explanation", None)
            valid = getattr(plan, "valid", None)
            supported = getattr(plan, "supported", None)
            fallback_reason = getattr(plan, "fallback_reason", None)
        else:
            descriptor = {"module": None, "class": None, "data": plan}
            improved = explanation = fallback_reason = valid = supported = None
        return (
            json.dumps(descriptor, ensure_ascii=False, separators=(",", ":")),
            improved,
            explanation,
            int(valid) if valid is not None else None,
            int(supported) if supported is not None else None,
            fallback_reason,
        )

    @staticmethod
    def _deserialize(plan_json: str) -> Any:
        descriptor = json.loads(plan_json)
        module_name = descriptor["module"]
        class_name = descriptor["class"]
        data = descriptor["data"]
        if not module_name or not class_name:
            return data
        # Cached classes are the two planner result models used by this application.
        if module_name not in {"local_kb_question", "countrydle.local_planner"}:
            return data
        target: Any = importlib.import_module(module_name)
        for component in class_name.split("."):
            target = getattr(target, component)
        return target(**data)

    def _load_version(self, version: str) -> None:
        if version in self._loaded_versions:
            return
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT mode, question_key, plan_json FROM plan_cache WHERE version = ? ORDER BY created_at ASC",
                (version,),
            ).fetchall()
        for mode, question_key, plan_json in rows:
            self._cache[(version, mode, question_key)] = self._deserialize(plan_json)
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)
        self._loaded_versions.add(version)

    def get(self, mode: str, question: str, *, version: str) -> Any | None:
        key = (version, *normalize_question_key(mode, question))
        with self._lock:
            self._load_version(version)
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT plan_json FROM plan_cache WHERE version = ? AND mode = ? AND question_key = ?",
                    key,
                ).fetchone()
            if row is not None:
                plan = self._deserialize(row[0])
                self._cache[key] = plan
                self._cache.move_to_end(key)
                if len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)
                self._hits += 1
                return plan
            self._misses += 1
            return None

    def set(self, mode: str, question: str, plan: Any, *, version: str) -> None:
        # Only validated provider responses reach the cache; failures never do.
        key = (version, *normalize_question_key(mode, question))
        plan_json, improved, explanation, valid, supported, fallback_reason = self._serialize(plan)
        with self._lock:
            self._load_version(version)
            self._cache[key] = plan
            self._cache.move_to_end(key)
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO plan_cache (
                        version, mode, question_key, plan_json, improved_question, explanation,
                        valid, supported, fallback_reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(version, mode, question_key) DO UPDATE SET
                        plan_json=excluded.plan_json,
                        improved_question=excluded.improved_question,
                        explanation=excluded.explanation,
                        valid=excluded.valid,
                        supported=excluded.supported,
                        fallback_reason=excluded.fallback_reason,
                        created_at=excluded.created_at""",
                    (*key, plan_json, improved, explanation, valid, supported, fallback_reason,
                     datetime.now(timezone.utc).isoformat()),
                )
            self._loaded_versions.add(version)

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
        """Clear cached plans from both memory and persistent storage."""
        with self._lock:
            self._cache.clear()
            self._loaded_versions.clear()
            with self._connect() as connection:
                connection.execute("DELETE FROM plan_cache")
            self._hits = 0
            self._misses = 0


# Global shared singleton cache instance
plan_cache = PlanCache(max_size=10000)
