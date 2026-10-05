"""Strict synchronous answer generation; durable reuse belongs to the async runner."""
import os
import time

FALLBACK_REQUEST_TIMEOUT = float(os.getenv("FALLBACK_REQUEST_TIMEOUT", "15.0"))

from utils.ai_clients import FALLBACK_ANSWER_SCHEMA, gemini_json, get_gemini_model
from utils.request_budget import remaining_timeout


def get_answer(system_prompt: str, question_prompt: str, *,
               evidence: dict | None = None, request_timeout: float | None = None,
               deadline: float | None = None, model: str | None = None) -> dict:
    """Generate one answer without retaining player data or a worker-local cache."""
    timeout = FALLBACK_REQUEST_TIMEOUT if request_timeout is None else request_timeout
    if deadline is None:
        deadline = time.monotonic() + timeout
    remaining_timeout(deadline, timeout)
    if evidence is not None:
        evidence["cache_hit"] = False
    result = gemini_json(
        system_prompt, question_prompt, model=get_gemini_model() if model is None else model,
        max_output_tokens=2048, evidence=evidence, request_timeout=timeout,
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
    return result
