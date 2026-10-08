"""Signing and browser-origin contracts, isolated from developer credentials.

The parent process may have loaded .env through tests/conftest.py. Every probe
uses a fresh environment and disables dotenv before importing the real app.
No application lifespan is entered: migrations, schedulers, provider calls and
live database writes are deliberately outside these configuration regressions.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


SERVER_DIR = Path(__file__).resolve().parents[1]
TEST_SIGNING_KEY = "isolated-security-regression-key-907af39aefad484bb6bb598acd46f54e"
APPROVED_ORIGINS = (
    "https://play.countrydle.example",
    "http://localhost:5173",
)
DENIED_ORIGINS = (
    "https://untrusted.countrydle.example",
    "https://play.countrydle.example.attacker.example",
    "https://evil.example",
    "http://localhost:5174",
    "https://internal.example",
    "null",
)
RESULT_PREFIX = "SECURITY_PROBE_RESULT="

# Disable every existing load_dotenv caller, not just app.py's first call. The
# Qdrant constructor's server-version discovery is not needed for these probes.
PROBE_SETUP = """
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
import qdrant_client
_original_qdrant_init = qdrant_client.QdrantClient.__init__
def _offline_qdrant_init(self, *args, **kwargs):
    kwargs['check_compatibility'] = False
    _original_qdrant_init(self, *args, **kwargs)
qdrant_client.QdrantClient.__init__ = _offline_qdrant_init
"""


def run_probe(source, *, secret=TEST_SIGNING_KEY, origins=APPROVED_ORIGINS):
    # Intentionally do not copy os.environ: no inherited signing/provider keys,
    # database URL, origin overrides or dotenv configuration may reach the child.
    environment = {
        "PATH": os.defpath,
        "PYTHONPATH": str(SERVER_DIR),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "DATABASE_URL": "postgresql+asyncpg://security:security@127.0.0.1:1/security_test",
        "ALGORITHM": "HS256",
        "EMAIL_USERNAME": "security@example.com",
        "NOREPLY_EMAIL": "noreply@example.com",
        "EMAIL_PASSWORD": "isolated-test-mail-password",
        "QDRANT_HOST": "127.0.0.1",
        "QDRANT_PORT": "1",
        "CORS_ALLOWED_ORIGINS": ",".join(origins),
    }
    if secret is not None:
        environment["SECRET_KEY"] = secret
    result = subprocess.run(
        [sys.executable, "-c", PROBE_SETUP + textwrap.dedent(source)],
        cwd=SERVER_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # Avoid assertion introspection displaying key material if this fails.
    if secret and secret.strip() and secret in result.stdout + result.stderr:
        pytest.fail("The isolated security probe exposed signing material")
    return result


def probe_result(result):
    if result.returncode != 0:
        # Captured stderr can contain tokens if a regression leaks them. Never
        # dump it into pytest output; the exit code is sufficient for the gate.
        pytest.fail(f"Isolated security probe exited with code {result.returncode}")
    records = [line.removeprefix(RESULT_PREFIX) for line in result.stdout.splitlines()
               if line.startswith(RESULT_PREFIX)]
    if len(records) != 1:
        pytest.fail("Isolated security probe did not return one result")
    return json.loads(records[0])


@pytest.mark.parametrize("secret", [
    pytest.param(None, id="missing"),
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace-only"),
    pytest.param("fallback_countrydle_secret", id="old-public-fallback"),
    pytest.param("your_secret_key", id="env-example-placeholder"),
    pytest.param("change-me", id="common-placeholder"),
    pytest.param("...", id="server-readme-placeholder"),
])
def test_application_startup_rejects_unsafe_signing_configuration(secret):
    result = run_probe("""
        import uvicorn
        config = uvicorn.Config('app:app', log_config=None)
        config.load()
        print('APPLICATION_READY')
    """, secret=secret)
    assert result.returncode != 0, "Unsafe signing configuration allowed app initialization"
    assert "APPLICATION_READY" not in result.stdout
    # This identifies the configuration failure, not a database/import error.
    assert "SECRET_KEY" in result.stdout + result.stderr


TOKEN_PROBE = """
import contextlib
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
import io
import json
import logging
import os
from uuid import UUID

captured = io.StringIO()
handler = logging.StreamHandler(captured)
logging.getLogger().addHandler(handler)
with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
    from app import app
    from fastapi import Request, Response
    from jose import jwt
    from users.utils import set_access_cookie, verify_access_token
    from utils.guest_session import (
        create_guest_game_token, read_guest_game_token,
        get_guest_identity, read_guest_identity,
    )

    key = os.environ['SECRET_KEY']
    email = 'security@example.com'
    expires = datetime.now(UTC) + timedelta(minutes=30)
    def request(cookie=''):
        return Request({'type': 'http', 'method': 'GET', 'scheme': 'https',
                        'path': '/', 'server': ('internal.example', 443),
                        'headers': [(b'cookie', cookie.encode())]})
    def cookie_token(response, name):
        cookies = SimpleCookie()
        cookies.load(response.headers['set-cookie'])
        return cookies[name].value

    # Independent pre-existing signatures must survive validation unchanged.
    old_access = jwt.encode({'sub': email, 'exp': expires}, key, algorithm='HS256')
    old_guest = jwt.encode({'mode': 'countrydle', 'day_id': 9,
                            'guesses_count': 2, 'is_game_over': False,
                            'won': False, 'exp': expires}, key, algorithm='HS256')
    access_response = Response()
    set_access_cookie(access_response, request(), email, remember_me=True)
    access = cookie_token(access_response, 'access_token')
    access_claims = jwt.decode(access, key, algorithms=['HS256'])
    guest = create_guest_game_token('countrydle', 9, 3, True, True)
    guest_claims = jwt.decode(guest, key, algorithms=['HS256'])
    identity_response = Response()
    identity = get_guest_identity(request(), identity_response)
    identity_token = cookie_token(identity_response, 'guest_identity')
    identity_claims = jwt.decode(identity_token, key, algorithms=['HS256'])
    renewed_identity = read_guest_identity(request('guest_identity=' + identity_token))
    results = {
        'existing_auth_accepted': verify_access_token(old_access) == email,
        'existing_guest_accepted': read_guest_game_token(old_guest, 'countrydle', 9)['guesses_count'] == 2,
        'issued_auth_accepted': verify_access_token(access) == email,
        'auth_signature_unchanged': access_claims['sub'] == email and access_claims['remember_me'] is True,
        'issued_guest_accepted': read_guest_game_token(guest, 'countrydle', 9) == {
            'mode': 'countrydle', 'day_id': 9, 'guesses_count': 3,
            'is_game_over': True, 'won': True},
        'guest_signature_unchanged': guest_claims['guesses_count'] == 3 and guest_claims['won'] is True,
        'identity_accepted': str(UUID(identity)) == renewed_identity,
        'identity_signature_unchanged': identity_claims['sub'] == identity and identity_claims['purpose'] == 'guest_identity',
    }
logging.getLogger().removeHandler(handler)
material = (key, old_access, old_guest, access, guest, identity_token)
results['logs_exclude_signing_material'] = not any(value in captured.getvalue() for value in material)
print('SECURITY_PROBE_RESULT=' + json.dumps(results))
"""


@pytest.mark.parametrize("secret", [
    pytest.param(TEST_SIGNING_KEY, id="explicit-key"),
    pytest.param(" " + TEST_SIGNING_KEY + " ", id="preserve-configured-key-bytes"),
])
def test_valid_explicit_key_preserves_existing_and_new_auth_and_guest_tokens(secret):
    outcomes = probe_result(run_probe(TOKEN_PROBE, secret=secret))
    assert outcomes == {
        "existing_auth_accepted": True,
        "existing_guest_accepted": True,
        "issued_auth_accepted": True,
        "auth_signature_unchanged": True,
        "issued_guest_accepted": True,
        "guest_signature_unchanged": True,
        "identity_accepted": True,
        "identity_signature_unchanged": True,
        "logs_exclude_signing_material": True,
    }


BROWSER_PROBE = """
import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID
from app import app
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect
from friend_matches.routes import COOKIE_NAME

# Inputs are public fixture origins, never configuration or signing material.
origins = ['https://play.countrydle.example', 'http://localhost:5173',
           'https://untrusted.countrydle.example',
           'https://play.countrydle.example.attacker.example',
           'https://evil.example', 'http://localhost:5174',
           'https://internal.example', 'null', None]
match_id = str(UUID(int=17))
seat_cookie = COOKIE_NAME + '=' + 'A' * 43

def summary(response):
    return {'status': response.status_code,
            'origin': response.headers.get('access-control-allow-origin'),
            'credentials': response.headers.get('access-control-allow-credentials'),
            'vary': response.headers.get('vary', '')}

async def exercise_http():
    records = {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='https://internal.example') as client:
        for origin in origins:
            headers = {'Origin': origin} if origin is not None else {}
            preflight = await client.options('/users/me', headers={
                **headers, 'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'x-client-authenticated'})
            request = await client.get('/version', headers={**headers, 'Cookie': 'access_token=fixture-cookie'})
            session = await client.post('/friend-matches/session', headers=headers)
            records[origin if origin is not None else '<missing>'] = {
                'preflight': summary(preflight), 'request': summary(request),
                'version_present': isinstance(request.json().get('version'), str),
                'session_status': session.status_code,
                'seat_cookie_issued': COOKIE_NAME in session.cookies,
            }
    return records

records = asyncio.run(exercise_http())
# TestClient itself is not entered as a context manager, so production lifespan
# never runs. Only the authorized snapshot database boundary is isolated.
client = TestClient(app, base_url='https://internal.example')
with patch('friend_matches.routes.service.get_snapshot', AsyncMock(return_value={'status': 'active'})):
    for origin in origins:
        headers = {'Cookie': seat_cookie}
        if origin is not None:
            headers['Origin'] = origin
        try:
            with client.websocket_connect('wss://internal.example/friend-matches/' + match_id + '/ws', headers=headers):
                outcome = 'accepted'
        except WebSocketDisconnect as exc:
            outcome = 'closed:' + str(exc.code)
        records[origin if origin is not None else '<missing>']['websocket'] = outcome
    try:
        with client.websocket_connect('wss://internal.example/friend-matches/' + match_id + '/ws',
                                      headers={'Origin': 'https://play.countrydle.example'}):
            outcome = 'accepted'
    except WebSocketDisconnect as exc:
        outcome = 'closed:' + str(exc.code)
    records['approved_without_seat'] = outcome
client.close()
print('SECURITY_PROBE_RESULT=' + json.dumps(records))
"""


@pytest.fixture(scope="module")
def browser_policy():
    return probe_result(run_probe(BROWSER_PROBE))


@pytest.mark.parametrize("origin", APPROVED_ORIGINS)
def test_configured_origins_allow_credentialed_preflight_and_request(browser_policy, origin):
    record = browser_policy[origin]
    assert record["preflight"]["status"] == 200
    assert record["preflight"]["origin"] == origin
    assert record["preflight"]["credentials"] == "true"
    assert record["request"]["status"] == 200
    assert record["request"]["origin"] == origin
    assert record["request"]["credentials"] == "true"
    assert "origin" in record["request"]["vary"].lower()


@pytest.mark.parametrize("origin", DENIED_ORIGINS)
def test_unapproved_and_same_site_sibling_origins_receive_no_cors_grant(browser_policy, origin):
    record = browser_policy[origin]
    assert record["preflight"]["status"] == 400
    assert record["preflight"]["origin"] is None
    assert record["request"]["origin"] is None
    # CORS does not authenticate or suppress ordinary HTTP route responses.
    assert record["request"]["status"] == 200
    assert record["version_present"] is True


def test_missing_origin_preserves_non_browser_http_behavior(browser_policy):
    record = browser_policy["<missing>"]
    assert record["request"]["status"] == 200
    assert record["version_present"] is True
    assert record["request"]["origin"] is None
    assert record["request"]["credentials"] is None
    # Existing friend mutations/socket admission require an Origin; ordinary
    # non-browser API reads are not given that stricter policy.
    assert record["session_status"] == 403
    assert record["seat_cookie_issued"] is False
    assert record["websocket"] == "closed:1008"


@pytest.mark.parametrize("origin", APPROVED_ORIGINS)
def test_approved_friend_browser_origins_initialize_seat_and_connect_socket(browser_policy, origin):
    record = browser_policy[origin]
    assert record["session_status"] == 200
    assert record["seat_cookie_issued"] is True
    assert record["websocket"] == "accepted"


@pytest.mark.parametrize("origin", DENIED_ORIGINS)
def test_unapproved_friend_origins_cannot_initialize_or_connect_even_with_seat(browser_policy, origin):
    record = browser_policy[origin]
    assert record["session_status"] == 403
    assert record["seat_cookie_issued"] is False
    assert record["websocket"] == "closed:1008"


def test_approved_websocket_origin_does_not_replace_seat_authentication(browser_policy):
    assert browser_policy["approved_without_seat"] == "closed:1008"


def test_empty_allowlist_grants_no_browser_origin_but_keeps_non_browser_reads():
    policy = probe_result(run_probe(BROWSER_PROBE, origins=()))
    for origin in APPROVED_ORIGINS + DENIED_ORIGINS:
        assert policy[origin]["preflight"]["status"] == 400
        assert policy[origin]["preflight"]["origin"] is None
        assert policy[origin]["request"]["origin"] is None
        assert policy[origin]["session_status"] == 403
        assert policy[origin]["websocket"] == "closed:1008"
    assert policy["<missing>"]["request"]["status"] == 200
    assert policy["<missing>"]["version_present"] is True


@pytest.mark.parametrize("scheme,override,expected_secure", [
    ("https", "false", True), ("https", "", True),
    ("http", "false", False), ("http", "true", True),
])
def test_friend_seat_cookie_cannot_downgrade_actual_https(monkeypatch, scheme, override, expected_secure):
    from http.cookies import SimpleCookie
    from starlette.requests import Request
    from starlette.responses import Response
    from friend_matches.routes import COOKIE_NAME, issue_guest

    monkeypatch.setenv("FRIEND_COOKIE_SECURE", override)
    request = Request({"type": "http", "scheme": scheme, "server": ("seat.test", 443),
                       "path": "/friend-matches/session", "headers": []})
    response = Response()
    issue_guest(request, response)
    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    seat = cookies[COOKIE_NAME]
    assert bool(seat["secure"]) is expected_secure
    assert bool(seat["httponly"]) is True
    assert seat["samesite"].lower() == "lax"
