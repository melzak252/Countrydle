import pytest

from utils import request_budget


def test_remaining_timeout_returns_configured_timeout_without_deadline():
    assert request_budget.remaining_timeout(None, 12.0) == 12.0
    assert request_budget.remaining_timeout(None) is None


def test_remaining_timeout_uses_smaller_positive_limit(monkeypatch):
    monkeypatch.setattr(request_budget.time, "monotonic", lambda: 10.0)
    assert request_budget.remaining_timeout(14.0, 8.0) == 4.0
    assert request_budget.remaining_timeout(14.0, 2.0) == 2.0


def test_remaining_timeout_raises_when_deadline_is_exhausted(monkeypatch):
    monkeypatch.setattr(request_budget.time, "monotonic", lambda: 10.0)
    with pytest.raises(TimeoutError):
        request_budget.remaining_timeout(10.0)
    with pytest.raises(TimeoutError):
        request_budget.remaining_timeout(9.0, 30.0)


def test_retrieval_does_not_search_after_embedding_exhausts_budget(monkeypatch):
    from qdrant import utils as retrieval

    now = [0.0]
    searches = []
    monkeypatch.setattr(request_budget.time, "monotonic", lambda: now[0])

    def embed(*args, **kwargs):
        now[0] = 5.0
        return [0.1, 0.2]

    monkeypatch.setattr(retrieval, "get_embedding", embed)
    monkeypatch.setattr(retrieval, "search_matches", lambda **kwargs: searches.append(kwargs))
    fragments, vector = retrieval.get_fragments_matching_question_sync(
        "question", "country_id", 1, "countries", deadline=5.0,
    )
    assert fragments == []
    assert vector == []
    assert searches == []
