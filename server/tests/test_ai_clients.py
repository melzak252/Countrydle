"""Never treat a blocked/truncated provider result as a resolved answer."""
import httpx
import pytest

from utils import ai_clients


@pytest.mark.parametrize("payload", [
    {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": '{"answer":true}'}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"answer":'}]}}]},
])
def test_unfinished_generation_is_an_error_even_if_json_is_parseable(monkeypatch, payload):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        with pytest.raises(RuntimeError):
            ai_clients.generate_gemini_json(
                "Test question", model="test-model", api_key="test-key", max_output_tokens=1024, timeout=30,
            )


def test_thought_parts_are_not_interpreted_as_the_final_answer(monkeypatch):
    payload = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"thought": True, "text": '{"answer":true}'},
        {"text": '{"answer":false}'},
    ]}}]}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        result = ai_clients.generate_gemini_json(
            "Test question", model="test-model", api_key="test-key", max_output_tokens=1024, timeout=30,
        )
    assert result["answer"] is False
