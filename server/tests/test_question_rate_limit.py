from types import SimpleNamespace

from utils.question_rate_limit import QuestionAttemptLimiter, client_network_key


def test_default_question_limit_allows_a_fast_quiz():
    limiter = QuestionAttemptLimiter(clock=lambda: 10.0)

    for _ in range(30):
        assert limiter.retry_after("network-a") is None

    assert limiter.retry_after("network-a") == 60


def test_question_attempt_limiter_counts_requests_by_sliding_window_and_network():
    now = [10.0]
    limiter = QuestionAttemptLimiter(max_requests=2, window_seconds=60, clock=lambda: now[0])

    assert limiter.retry_after("network-a") is None
    now[0] = 20.0
    assert limiter.retry_after("network-a") is None
    now[0] = 25.0
    assert limiter.retry_after("network-a") == 45
    assert limiter.retry_after("network-b") is None
    now[0] = 70.0
    assert limiter.retry_after("network-a") is None


def test_client_network_key_normalizes_ipv6_and_does_not_include_raw_ip(monkeypatch):
    from utils import question_rate_limit

    monkeypatch.setattr(question_rate_limit, "TRUST_X_REAL_IP", False)
    first = SimpleNamespace(client=SimpleNamespace(host="2001:db8:1::1"), headers={})
    same_network = SimpleNamespace(client=SimpleNamespace(host="2001:db8:1::ffff"), headers={})
    other_network = SimpleNamespace(client=SimpleNamespace(host="2001:db8:2::1"), headers={})

    first_key = client_network_key(first)
    assert first_key == client_network_key(same_network)
    assert first_key != client_network_key(other_network)
    assert "2001:db8" not in first_key


def test_forwarded_address_is_used_only_when_explicitly_trusted(monkeypatch):
    from utils import question_rate_limit

    request = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.1"),
        headers={"x-real-ip": "198.51.100.2"},
    )
    monkeypatch.setattr(question_rate_limit, "TRUST_X_REAL_IP", False)
    direct_key = client_network_key(request)
    monkeypatch.setattr(question_rate_limit, "TRUST_X_REAL_IP", True)
    forwarded_key = client_network_key(request)

    assert direct_key != forwarded_key
    monkeypatch.setattr(request, "client", SimpleNamespace(host="198.51.100.2"))
    assert forwarded_key == client_network_key(request)
