"""
CORS preflight tests.

The auth middleware rejected OPTIONS /api/settings with a 503 that carried no
Access-Control-Allow-Origin header, so the browser blocked it at the preflight
stage and reported "blocked by CORS policy". The real reason — API_SECRET is
not set — never reached the operator, and there was no way to tell the two
apart from the browser console.

Two things must hold:
  1. a preflight is never auth-rejected, so CORS can answer it
  2. every auth rejection still carries CORS headers, so the browser can read
     the real message (this is middleware ordering, not luck)
"""
import pytest
from fastapi.testclient import TestClient

from main import app

ORIGIN = "https://trade-bot-ten-kappa.vercel.app"
PREFLIGHT = {
    "Origin": ORIGIN,
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "x-api-secret",
}

client = TestClient(app)


def _acao(res):
    return res.headers.get("access-control-allow-origin")


@pytest.fixture
def denied(monkeypatch):
    """No secret and no opt-out: control endpoints are closed."""
    monkeypatch.delenv("API_SECRET", raising=False)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_CONTROL", "false")


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("API_SECRET", "unit-test-secret")
    monkeypatch.delenv("ALLOW_UNAUTHENTICATED_CONTROL", raising=False)


@pytest.mark.parametrize("path", [
    "/api/settings", "/api/bot/start", "/api/bot/stop", "/api/trades/manual",
])
def test_preflight_on_protected_path_is_answered_with_cors(denied, path):
    """
    A preflight carries no secret and changes nothing. If auth answers it, the
    browser sees a headerless response and blocks before the real request.
    """
    res = client.options(path, headers=PREFLIGHT)
    assert _acao(res), f"preflight {path} returned no Access-Control-Allow-Origin"
    assert res.status_code == 200


def test_preflight_is_not_answered_as_a_rejection(denied):
    """A 503/401 to a preflight is the bug; 200 is the fix."""
    res = client.options("/api/settings", headers=PREFLIGHT)
    assert res.status_code == 200
    assert not res.content or b"API_SECRET" not in res.content


def test_rejection_body_reaches_the_browser(denied):
    """
    The whole point: the operator must be able to read *why* it is closed.
    """
    res = client.get("/api/settings", headers={"Origin": ORIGIN})
    assert res.status_code == 503
    assert _acao(res), "rejection lost its CORS header, so the browser hides the reason"
    assert "API_SECRET" in res.json()["detail"]


@pytest.mark.parametrize("headers,expected", [
    ({}, 401),
    ({"X-API-Secret": "wrong"}, 401),
])
def test_bad_secret_is_401_and_still_readable(secret, headers, expected):
    res = client.get("/api/settings", headers={"Origin": ORIGIN, **headers})
    assert res.status_code == expected
    assert _acao(res)
    assert res.json()["detail"]


def test_delete_on_a_trade_is_protected(secret):
    res = client.delete("/api/trades/bt-1", headers={"Origin": ORIGIN})
    assert res.status_code == 401
    assert _acao(res)


def test_read_only_endpoints_stay_public(denied):
    """Monitoring must keep working with no secret at all."""
    for path in ("/api/status", "/api/market/symbols"):
        res = client.get(path, headers={"Origin": ORIGIN})
        assert res.status_code == 200, f"{path} should stay public"
        assert _acao(res)
