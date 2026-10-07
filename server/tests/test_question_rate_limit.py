import importlib
import ipaddress

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

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

    monkeypatch.setattr(question_rate_limit, "TRUSTED_PROXIES", ())
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
    monkeypatch.setattr(question_rate_limit, "TRUSTED_PROXIES", ())
    direct_key = client_network_key(request)
    monkeypatch.setattr(question_rate_limit, "TRUSTED_PROXIES", (ipaddress.ip_network("203.0.113.1/32"),))
    forwarded_key = client_network_key(request)

    assert direct_key != forwarded_key
    monkeypatch.setattr(request, "client", SimpleNamespace(host="198.51.100.2"))
    assert forwarded_key == client_network_key(request)


@pytest.fixture
def network_http(monkeypatch, request):
    """Configure the real env parser and exercise the actual HTTP dependency."""
    from utils import question_rate_limit

    original_limiter = question_rate_limit.question_attempt_limiter
    now = [10.0]
    with monkeypatch.context() as configuration:
        configuration.setenv("QUESTION_RATE_LIMIT_TRUSTED_PROXIES", request.param)
        # The removed global switch must not grant trust to arbitrary peers.
        configuration.setenv("QUESTION_RATE_LIMIT_TRUST_X_REAL_IP", "true")
        importlib.reload(question_rate_limit)
        configuration.setattr(
            question_rate_limit,
            "question_attempt_limiter",
            question_rate_limit.QuestionAttemptLimiter(clock=lambda: now[0]),
        )
        application = FastAPI()

        @application.post("/question", dependencies=[Depends(question_rate_limit.enforce_question_attempt_limit)])
        async def question():
            return {"accepted": True}

        async def send(peer, headers=None):
            transport = ASGITransport(app=application, client=(peer, 12345))
            async with AsyncClient(transport=transport, base_url="http://quota.test") as client:
                return await client.post("/question", headers=headers or {})

        try:
            yield SimpleNamespace(send=send, now=now, trusted_proxies=request.param)
        finally:
            configuration.undo()
            importlib.reload(question_rate_limit)
            question_rate_limit.question_attempt_limiter = original_limiter


@pytest.mark.anyio
@pytest.mark.parametrize(
    "network_http,peer",
    [
        ("", "203.0.113.8"),
        ("10.0.0.0/8", "203.0.113.8"),
        ("10.0.0.0/8,2001:db8:feed::/48", "2001:db8:beef::1"),
        ("10.0.0.1/32", "10.0.0.2"),
        ("2001:db8:feed::1/128", "2001:db8:feed::2"),
    ],
    indirect=["network_http"],
)
async def test_untrusted_peer_cannot_split_its_quota_with_any_forwarding_headers(network_http, peer):
    def forged_headers(index):
        address = f"198.51.100.{index + 1}"
        return (
            {},
            {"X-Real-IP": address},
            {"X-Forwarded-For": address},
            {"Forwarded": f"for={address}"},
            {"X-Real-IP": address, "X-Forwarded-For": "192.0.2.1"},
            {"X-Real-IP": address, "Forwarded": "for=192.0.2.1"},
            {"X-Real-IP": address, "X-Forwarded-For": "192.0.2.1", "Forwarded": "for=192.0.2.2"},
        )[index % 7]

    for index in range(30):
        assert (await network_http.send(peer, forged_headers(index))).status_code == 200

    rejected = await network_http.send(peer, forged_headers(30))
    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "60"
    assert (await network_http.send("192.0.2.99", {"X-Real-IP": "198.51.100.1"})).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    "network_http,peer,second_proxy",
    [
        ("10.0.0.0/8", "10.1.2.3", "10.9.8.7"),
        ("2001:db8:feed::/48", "2001:db8:feed:1::1", "2001:db8:feed:2::2"),
        ("10.1.2.3/32", "10.1.2.3", "10.1.2.3"),
        ("2001:db8:feed::1/128", "2001:0db8:feed:0000::1", "2001:db8:feed::1"),
    ],
    indirect=["network_http"],
)
async def test_trusted_proxy_isolates_real_clients_and_proxy_changes_do_not_reset_quota(
    network_http, peer, second_proxy,
):
    first = {"X-Real-IP": "198.51.100.1", "X-Forwarded-For": "192.0.2.1", "Forwarded": "for=192.0.2.2"}
    second = {"X-Real-IP": "198.51.100.2", "X-Forwarded-For": "198.51.100.1"}
    for _ in range(30):
        assert (await network_http.send(peer, first)).status_code == 200
    assert (await network_http.send(second_proxy, first)).status_code == 429

    for _ in range(30):
        assert (await network_http.send(peer, second)).status_code == 200
    assert (await network_http.send(second_proxy, second)).status_code == 429


@pytest.mark.anyio
@pytest.mark.parametrize("network_http", ["10.0.0.0/8", "2001:db8:feed::/48"], indirect=True)
async def test_missing_or_malformed_real_ip_falls_back_to_actual_peer_not_other_headers(network_http):
    trust_ipv4 = network_http.trusted_proxies == "10.0.0.0/8"
    peer = "10.1.2.3" if trust_ipv4 else "2001:db8:feed:1::1"
    other_peer = "10.1.2.4" if trust_ipv4 else "2001:db8:feed:2::1"
    for _ in range(30):
        assert (await network_http.send(peer)).status_code == 200

    invalid_values = [None, "", "   ", "unknown", "999.1.2.3", "198.51.100.1:80", "198.51.100.1, 198.51.100.2"]
    for value in invalid_values:
        headers = {"X-Forwarded-For": "198.51.100.2", "Forwarded": "for=198.51.100.3"}
        if value is not None:
            headers["X-Real-IP"] = value
        rejected = await network_http.send(peer, headers)
        assert rejected.status_code == 429, value
        assert rejected.headers["Retry-After"] == "60"
        assert (await network_http.send(other_peer, headers)).status_code == 200, value


@pytest.mark.anyio
@pytest.mark.parametrize(
    "network_http,trusted",
    [("", False), ("10.0.0.0/8", True)],
    indirect=["network_http"],
)
async def test_ipv6_spellings_and_hosts_in_one_64_share_quota_but_other_networks_do_not(network_http, trusted):
    addresses = [
        "2001:db8:1::1",
        "2001:0db8:0001:0000:0000:0000:0000:ffff",
        "2001:db8:1::1234",
    ]

    async def send(address):
        return await network_http.send("10.1.2.3", {"X-Real-IP": address}) if trusted else await network_http.send(address)

    for index in range(30):
        assert (await send(addresses[index % len(addresses)])).status_code == 200
    assert (await send("2001:db8:1::abcd")).status_code == 429
    assert (await send("2001:db8:2::1")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("network_http", [""], indirect=True)
async def test_http_network_quota_keeps_the_existing_60_second_sliding_window(network_http):
    for _ in range(30):
        assert (await network_http.send("203.0.113.8")).status_code == 200
    network_http.now[0] = 25.0
    rejected = await network_http.send("203.0.113.8", {"X-Real-IP": "198.51.100.1"})
    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "45"
    network_http.now[0] = 70.0
    assert (await network_http.send("203.0.113.8")).status_code == 200
