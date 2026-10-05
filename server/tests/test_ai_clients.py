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


def _success_response():
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP",
        "content": {"parts": [{"text": '{"answer":true}'}]},
    }]})


def test_expired_budget_does_not_issue_provider_request(monkeypatch):
    now = [10.0]
    requests = []
    monkeypatch.setattr(ai_clients.time, "monotonic", lambda: now[0])
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with httpx.Client(transport=httpx.MockTransport(lambda request: requests.append(request) or _success_response())) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        with pytest.raises(TimeoutError):
            ai_clients.gemini_json("system", "question", deadline=9.0)
    assert requests == []


def test_consumed_budget_prevents_paid_retry(monkeypatch):
    now = [0.0]
    requests = []
    monkeypatch.setattr(ai_clients.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(ai_clients.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def respond(request):
        requests.append(request)
        now[0] = 0.5
        return httpx.Response(503, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        with pytest.raises(TimeoutError):
            ai_clients.gemini_json("system", "question", deadline=1.0)
    assert len(requests) == 1


def test_retryable_status_retries_and_succeeds_within_budget(monkeypatch):
    now = [0.0]
    requests = []
    monkeypatch.setattr(ai_clients.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(ai_clients.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, request=request)
        return _success_response()

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        result = ai_clients.gemini_json("system", "question", deadline=10.0)
    assert result["answer"] is True
    assert len(requests) == 2


@pytest.mark.parametrize("failure", ["timeout", "malformed"])
def test_timeout_or_malformed_output_does_not_retry(monkeypatch, failure):
    requests = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def respond(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("provider timed out", request=request)
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": "not-json"}]},
        }]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(ai_clients, "_http_client", client)
        with pytest.raises((httpx.ReadTimeout, RuntimeError)):
            ai_clients.gemini_json("system", "question")
    assert len(requests) == 1


def test_gemini_model_precedence_is_unchanged(monkeypatch):
    monkeypatch.setenv("GEMINI_QUIZ_MODEL", "quiz")
    monkeypatch.setenv("LOCAL_QUESTION_MODEL", "local")
    monkeypatch.setenv("GEMINI_MODEL", "generic")
    assert ai_clients.get_gemini_model() == "quiz"

    monkeypatch.delenv("GEMINI_QUIZ_MODEL")
    assert ai_clients.get_gemini_model() == "local"

    monkeypatch.delenv("LOCAL_QUESTION_MODEL")
    assert ai_clients.get_gemini_model() == "generic"

    monkeypatch.delenv("GEMINI_MODEL")
    assert ai_clients.get_gemini_model() == ai_clients.GEMINI_DEFAULT_MODEL
