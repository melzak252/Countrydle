"""Process-local, thread-safe provider connection pools; async callers offload SDK work."""
import json
import os
import threading
from typing import Any

import httpx
from openai import OpenAI

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
