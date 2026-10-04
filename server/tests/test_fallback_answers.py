from datetime import datetime, timezone

import pytest


@pytest.fixture
def fallback(monkeypatch):
    from collections import deque
    from types import SimpleNamespace
    from utils import fallback_answers

    seconds = [0.0]
    utc = [datetime(2026, 10, 4, tzinfo=timezone.utc)]
    monkeypatch.setattr(fallback_answers, "_cache", fallback_answers._AnswerCache(
        capacity=2, ttl=300, clock=lambda: seconds[0],
    ))
    monkeypatch.setattr(fallback_answers, "datetime", SimpleNamespace(now=lambda tz: utc[0]))
    monkeypatch.setenv("GEMINI_QUIZ_MODEL", "test-model-a")
    responses = deque()
    calls = []

    def provider(*args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("evidence") is not None:
            kwargs["evidence"].update(provider="gemini", usage={"input_tokens": 100})
        return responses.popleft()

    monkeypatch.setattr(fallback_answers, "gemini_json", provider)
    arguments = {
        "entity_name": "Poland", "original_question": "Did it host the event?",
        "question": "Did the country host the event?",
        "context": "Poland hosted the event in 2001.", "cache_scope": ("countrydle", 31),
    }

    def answer(value):
        return {"answer": value, "explanation": (
            "The country hosted the event." if value is True else
            "The country did not host the event." if value is False else "The date is undetermined."
        )}

    def get(**changes):
        return fallback_answers.get_answer(
            "Stable game rules.", "Exact question data.", **(arguments | changes),
        )

    return SimpleNamespace(module=fallback_answers, responses=responses, calls=calls,
                           seconds=seconds, utc=utc, arguments=arguments, answer=answer, get=get)


@pytest.mark.parametrize("value", [True, False])
def test_identical_evidence_reuses_both_booleans_without_rebilling_or_mutable_result_sharing(fallback, value):
    fallback.responses.extend([fallback.answer(value), fallback.answer(not value)])
    evidence = {}
    first = fallback.get(evidence=evidence)
    first["answer"] = not value
    second = fallback.get(evidence=evidence)
    assert second["answer"] is value
    assert len(fallback.calls) == 1
    assert evidence["provider"] == "answer_cache"
    assert evidence["cache_hit"] is True
    assert "usage" not in evidence


@pytest.mark.parametrize("changes", [
    {"cache_scope": ("countrydle", 32)},
    {"cache_scope": ("us_statedle", 31)},
    {"entity_name": "Japan"},
    {"context": "Poland did not host the event."},
    {"original_question": "Did it NOT host the event?"},
    {"question": "Does the official name contain 'é'?"},
])
def test_changed_target_mode_evidence_or_exact_meaning_cannot_reuse_prior_answer(fallback, changes):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])
    assert fallback.get()["answer"] is True
    assert fallback.get(**changes)["answer"] is False
    assert len(fallback.calls) == 2


def test_model_revision_and_midnight_invalidate_reuse(fallback, monkeypatch):
    from datetime import timedelta
    fallback.responses.extend([fallback.answer(True), fallback.answer(False), fallback.answer(True)])
    assert fallback.get()["answer"] is True
    monkeypatch.setenv("GEMINI_QUIZ_MODEL", "test-model-b")
    assert fallback.get()["answer"] is False
    fallback.utc[0] += timedelta(days=1)
    assert fallback.get()["answer"] is True
    assert len(fallback.calls) == 3


@pytest.mark.parametrize("changes", [{"context": ""}, {"cache_scope": None}, {"request_timeout": 30}])
def test_missing_context_or_diagnostic_call_does_not_reuse_answer(fallback, changes):
    fallback.responses.extend([fallback.answer(False), fallback.answer(True)])
    assert fallback.get(**changes)["answer"] is False
    assert fallback.get(**changes)["answer"] is True
    assert len(fallback.calls) == 2


def test_abstention_and_malformed_provider_result_do_not_poison_later_answer(fallback):
    fallback.responses.extend([
        fallback.answer(None), {"answer": "false", "explanation": "Incorrect wire type."},
        fallback.answer(True),
    ])
    assert fallback.get()["answer"] is None
    with pytest.raises(ValueError):
        fallback.get()
    assert fallback.get()["answer"] is True
    assert len(fallback.calls) == 3


def test_expiry_and_capacity_eviction_require_a_fresh_answer(fallback):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False),
                               fallback.answer(True), fallback.answer(False), fallback.answer(True)])
    assert fallback.get()["answer"] is True
    fallback.seconds[0] = 300
    assert fallback.get()["answer"] is False
    fallback.get(cache_scope=("countrydle", 32))
    fallback.get(cache_scope=("countrydle", 33))
    assert fallback.get()["answer"] is True
    assert len(fallback.calls) == 5


def test_reported_answer_is_evicted_and_not_reused_during_quarantine(fallback):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False), fallback.answer(True)])
    assert fallback.get()["answer"] is True
    fallback.module.invalidate_reported_answer(
        mode="continental", entity_name="Poland",
        original_question=fallback.arguments["original_question"],
        question=fallback.arguments["question"], context=fallback.arguments["context"],
        game_date=fallback.utc[0].date(),
    )
    assert fallback.get()["answer"] is False
    assert fallback.get()["answer"] is True
    assert len(fallback.calls) == 3


def test_quoted_character_identity_is_not_accent_folded(fallback):
    accented = "Does the official name contain the character 'é'?"
    plain = "Does the official name contain the character 'e'?"
    fallback.responses.extend([fallback.answer(False), fallback.answer(True)])
    assert fallback.get(original_question=accented, question=accented)["answer"] is False
    assert fallback.get(original_question=plain, question=plain)["answer"] is True


def test_prompt_policy_revision_requires_new_generation(fallback):
    fallback.responses.extend([fallback.answer(True), fallback.answer(False)])
    assert fallback.get()["answer"] is True
    changed = fallback.module.get_answer(
        "Revised game rules.", "Exact question data.", **fallback.arguments,
    )
    assert changed["answer"] is False


def test_generation_racing_a_report_cannot_repopulate_the_cache(fallback, monkeypatch):
    def disputed_provider(*args, **kwargs):
        fallback.module.invalidate_reported_answer(
            mode="countrydle", entity_name="Poland",
            original_question=fallback.arguments["original_question"],
            question=fallback.arguments["question"], context=fallback.arguments["context"],
            game_date=fallback.utc[0].date(),
        )
        fallback.seconds[0] = 2
        return fallback.answer(True)

    monkeypatch.setattr(fallback.module, "gemini_json", disputed_provider)
    assert fallback.get()["answer"] is True
    # The report's quarantine expired, but an incorrect late insertion would not.
    fallback.seconds[0] = 301
    monkeypatch.setattr(fallback.module, "gemini_json", lambda *args, **kwargs: fallback.answer(False))
    assert fallback.get()["answer"] is False
