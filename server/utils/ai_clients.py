"""Process-local, thread-safe provider connection pools; async callers offload SDK work."""
import json
import os
import threading
import time
from typing import Any
import httpx
from openai import OpenAI
from .request_budget import remaining_timeout

_lock = threading.Lock()
_http_client: httpx.Client | None = None
_openai_client: OpenAI | None = None


def get_http_client() -> httpx.Client:
    global _http_client
    with _lock:
        if _http_client is None:
            _http_client = httpx.Client()
        return _http_client


def get_openai_client(*, request_timeout: float | None = None) -> OpenAI:
    global _openai_client
    with _lock:
        if _openai_client is None:
            _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        client = _openai_client
    return client.with_options(timeout=request_timeout, max_retries=0) if request_timeout is not None else client

def close_ai_clients() -> None:
    global _http_client, _openai_client
    with _lock:
        http_client, openai_client = _http_client, _openai_client
        _http_client = _openai_client = None
    if http_client is not None:
        http_client.close()
    if openai_client is not None:
        openai_client.close()


def generate_gemini_json(
    prompt: str, *, model: str, api_key: str, max_output_tokens: int,
    timeout: float, evidence: dict | None = None, response_schema: dict | None = None,
    thinking_budget: int | None = None,
) -> dict[str, Any]:
    generation = {"temperature": 0, "maxOutputTokens": max_output_tokens, "responseMimeType": "application/json"}
    if response_schema is not None:
        generation["responseJsonSchema"] = response_schema
    if thinking_budget is not None:
        generation["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    response = get_http_client().post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if evidence is not None:
        evidence.update(model_version=data.get("modelVersion"), response_id=data.get("responseId"))
        usage = data.get("usageMetadata") or {}
        evidence["usage"] = {
            public: usage[wire] for public, wire in (
                ("input_tokens", "promptTokenCount"), ("output_tokens", "candidatesTokenCount"),
                ("thought_tokens", "thoughtsTokenCount"), ("cached_input_tokens", "cachedContentTokenCount"),
                ("total_tokens", "totalTokenCount"),
            ) if type(usage.get(wire)) is int and usage[wire] >= 0
        }
    candidates = data.get("candidates") or []
    if not candidates or candidates[0].get("finishReason", "STOP") != "STOP":
        raise RuntimeError("Gemini returned no complete answer")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part["text"] for part in parts if isinstance(part.get("text"), str) and not part.get("thought"))
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Gemini returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini returned JSON that is not an object")
    return parsed

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"

FALLBACK_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string", "minLength": 1},
        "answer": {"type": ["boolean", "null"]},
    },
    "required": ["answer", "explanation"],
    "additionalProperties": False,
}


def get_gemini_model() -> str:
    """Return the configured Gemini model using the established precedence."""
    return (
        os.getenv("GEMINI_QUIZ_MODEL")
        or os.getenv("LOCAL_QUESTION_MODEL")
        or os.getenv("GEMINI_MODEL")
        or GEMINI_DEFAULT_MODEL
    )

DEFAULT_REQUEST_TIMEOUT = float(os.getenv("GEMINI_REQUEST_TIMEOUT", "15.0"))


def gemini_json(
    system_prompt: str, user_prompt: str, max_output_tokens: int = 1024, *,
    evidence: dict | None = None, request_timeout: float = DEFAULT_REQUEST_TIMEOUT, max_attempts: int = 3,
    response_schema: dict | None = None, thinking_budget: int | None = None,
    model: str | None = None, deadline: float | None = None,
) -> dict:
    """Call Gemini through the shared connection pool, retaining fallback retry policy."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    model = get_gemini_model() if model is None else model
    if evidence is not None:
        evidence["provider_attempts"] = 0
    prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
    retryable_statuses = {429, 500, 502, 503, 504}
    for attempt in range(max_attempts):
        timeout = remaining_timeout(deadline, request_timeout)
        if evidence is not None:
            evidence["provider_attempts"] = attempt + 1
        try:
            parsed = generate_gemini_json(
                prompt, model=model, api_key=api_key, max_output_tokens=max_output_tokens,
                timeout=timeout, evidence=evidence, response_schema=response_schema,
                thinking_budget=thinking_budget if model.startswith("gemini-2.5") else None,
            )
            remaining_timeout(deadline)
            break
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in retryable_statuses or attempt == max_attempts - 1:
                raise RuntimeError(f"Gemini HTTP error {status}") from exc
            backoff = 2**attempt
            remaining = remaining_timeout(deadline)
            time.sleep(min(backoff, remaining) if remaining is not None else backoff)
    else:
        raise RuntimeError("Gemini request failed")
    if evidence is not None:
        evidence.update(
            provider="gemini", model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0, max_output_tokens=max_output_tokens,
        )

    return parsed
