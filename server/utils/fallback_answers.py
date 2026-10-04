"""Short-lived reuse of server-generated answers to identical target/evidence inputs."""
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import threading
import time
from typing import Callable

from utils.ai_clients import FALLBACK_ANSWER_SCHEMA, gemini_json, get_gemini_model
from utils.request_budget import remaining_timeout


# No text folding: negation, spelling, quantities and quoted literals are meaningful.
_Signature = tuple[str, str, str, str | None, bytes, str]
_Key = tuple[_Signature, int, str, bytes, bytes]


@dataclass(frozen=True)
class _Entry:
    expires_at: float
    answer: bool
    explanation: str


class _AnswerCache:
    def __init__(self, *, capacity: int = 256, ttl: float = 300,
                 clock: Callable[[], float] = time.monotonic):
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock
        self._entries: OrderedDict[_Key, _Entry] = OrderedDict()
        self._blocked: OrderedDict[_Signature, float] = OrderedDict()
        self._epoch = 0
        self._lock = threading.Lock()

    def _is_blocked(self, signature: _Signature, now: float) -> bool:
        expiry = self._blocked.get(signature)
        if expiry is None:
            return False
        if expiry <= now:
            del self._blocked[signature]
            return False
        return True

    def get(self, key: _Key) -> tuple[_Entry | None, int]:
        with self._lock:
            now = self.clock()
            if self._is_blocked(key[0], now):
                return None, self._epoch
            entry = self._entries.get(key)
            if entry is not None:
                if entry.expires_at <= now:
                    del self._entries[key]
                    entry = None
                else:
                    self._entries.move_to_end(key)
            return entry, self._epoch

    def put(self, key: _Key, answer: bool, explanation: str, epoch: int) -> None:
        with self._lock:
            now = self.clock()
            # A report racing this generation must win over its late result.
            if epoch != self._epoch or self._is_blocked(key[0], now):
                return
            self._entries[key] = _Entry(now + self.ttl, answer, explanation)
            self._entries.move_to_end(key)
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)

    def invalidate(self, signature: _Signature) -> None:
        with self._lock:
            self._epoch += 1
            for key in [key for key in self._entries if key[0] == signature]:
                del self._entries[key]
            self._blocked[signature] = self.clock() + self.ttl
            self._blocked.move_to_end(signature)
            while len(self._blocked) > self.capacity:
                self._blocked.popitem(last=False)


_cache = _AnswerCache()


def _signature(mode: str, entity_name: str, original_question: str,
               question: str | None, context: str, game_date: str) -> _Signature:
    # Continental uses the same country facts and answer policy.
    mode = "countrydle" if mode == "continental" else mode
    return (mode, entity_name, original_question, question,
            sha256(context.encode("utf-8")).digest(), game_date)


def invalidate_reported_answer(*, mode: str, entity_name: str,
                               original_question: str, question: str | None,
                               context: str | None, game_date: date | str) -> None:
    """Evict/quarantine server-owned report inputs; never trust client diagnostics."""
    if not context:
        return
    day = game_date.isoformat() if isinstance(game_date, date) else game_date
    _cache.invalidate(_signature(mode, entity_name, original_question, question, context, day))


def get_answer(system_prompt: str, question_prompt: str, *, entity_name: str,
               original_question: str, question: str | None, context: str,
               cache_scope: tuple[str, int] | None = None, evidence: dict | None = None,
               request_timeout: float | None = None, deadline: float | None = None) -> dict:
    """Generate one strict answer or reuse the same exact current evidence.

    Retrieval precedes this lookup. Scope-less and explicit-timeout diagnostic
    calls always generate; empty-context general knowledge and nulls never cache.
    No player record, ownership, token or private context is stored in the result.
    """
    timeout = 60 if request_timeout is None else request_timeout
    if deadline is None:
        deadline = time.monotonic() + timeout
    remaining_timeout(deadline, timeout)
    model = get_gemini_model()
    key = None
    epoch = 0
    if cache_scope is not None and context and request_timeout is None:
        signature = _signature(cache_scope[0], entity_name, original_question, question,
                               context, datetime.now(timezone.utc).date().isoformat())
        key = (signature, cache_scope[1], model,
               sha256(system_prompt.encode("utf-8")).digest(),
               sha256(question_prompt.encode("utf-8")).digest())
        cached, epoch = _cache.get(key)
        if cached is not None:
            remaining_timeout(deadline, timeout)
            if evidence is not None:
                for field in ("usage", "response_id", "model_version", "messages",
                              "temperature", "max_output_tokens", "attempts"):
                    evidence.pop(field, None)
                evidence.update(provider="answer_cache", model=model, cache_hit=True,
                                provider_attempts=0)
            # The caller may sanitize/mutate its own dict; the cached entry is immutable.
            return {"answer": cached.answer, "explanation": cached.explanation}
    if evidence is not None:
        evidence["cache_hit"] = False
    result = gemini_json(
        system_prompt, question_prompt, model=model, max_output_tokens=2048,
        evidence=evidence, request_timeout=timeout,
        max_attempts=3 if request_timeout is None else 1,
        response_schema=FALLBACK_ANSWER_SCHEMA, thinking_budget=1024, deadline=deadline,
    )
    remaining_timeout(deadline, timeout)
    if not isinstance(result, dict):
        raise ValueError("Gemini answer must be a JSON object")
    if "answer" not in result:
        raise ValueError("Gemini answer is missing the answer field")
    answer = result["answer"]
    if answer is not None and type(answer) is not bool:
        raise ValueError("Gemini answer must be true, false, or null")
    if result.keys() - {"answer", "explanation"}:
        raise ValueError("Gemini answer contains unexpected fields")
    explanation = result.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Gemini answer must include a non-empty explanation")
    if key is not None and answer is not None:
        _cache.put(key, answer, explanation, epoch)
    return result
