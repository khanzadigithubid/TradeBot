"""
Deployment hardening: what happens on a host that cannot trade, and what a
public deployment is allowed to do.

The Render logs that prompted this showed a dashboard that looked healthy while
being unable to reach the exchange account at all (Binance geo-blocks the
datacenter range), with every control endpoint open to the internet because
API_SECRET was unset, and the bot resuming trading unattended on each restart.
Each of those is a failure mode a passing test suite does not catch, so they
are pinned here.
"""
import pytest
from fastapi.testclient import TestClient


# ── control access mode ───────────────────────────────────────────────────────

@pytest.fixture
def no_auth_env(monkeypatch):
    """Neutral auth environment; the test chooses the mode."""
    monkeypatch.delenv("API_SECRET", raising=False)
    monkeypatch.delenv("ALLOW_UNAUTHENTICATED_CONTROL", raising=False)


def test_control_access_is_denied_without_a_secret(no_auth_env):
    """
    The regression that mattered: an unset API_SECRET used to leave /api/settings,
    /api/bot/* and /api/trades/manual open, so anyone who could reach the host
    could overwrite the Binance key and rewrite every strategy parameter.
    """
    import api.auth as auth

    assert auth.control_access_mode() == "denied"
    assert auth.auth_enabled() is False


def test_denied_control_endpoints_answer_503_with_instructions(no_auth_env):
    """
    503, not 401: nothing is being asked for, the endpoint is administratively
    closed. The body has to say how to reopen it, otherwise the operator is
    left guessing why the Settings page broke.
    """
    import main

    client = TestClient(main.app)
    for method, path, payload in (
        ("get",    "/api/settings",              None),
        ("post",   "/api/settings",              {}),
        ("post",   "/api/bot/start",             {}),
        ("post",   "/api/bot/stop",              None),
        ("post",   "/api/trades/manual",         {"symbol": "BTCUSDT", "side": "BUY"}),
        ("delete", "/api/trades/1",              None),
    ):
        kwargs = {"json": payload} if payload is not None else {}
        r = getattr(client, method)(path, **kwargs)
        assert r.status_code == 503, f"{method.upper()} {path} must be closed"
        detail = r.json()["detail"]
        assert "API_SECRET" in detail, "the error must name the env var to set"


def test_monitoring_stays_available_when_control_is_closed(no_auth_env):
    """
    Closing the control endpoints must not take the dashboard down with them —
    that is the whole point of the public read-only mode.
    """
    import main

    client = TestClient(main.app)
    for path in ("/api/status", "/api/market/BTCUSDT/signal", "/health", "/api/watchlist"):
        assert client.get(path).status_code == 200, f"{path} must stay readable"
    assert client.get("/").status_code == 200


def test_secret_reopens_control_endpoints(monkeypatch):
    import api.auth as auth

    monkeypatch.setenv("API_SECRET", "s3cr3t-value")
    monkeypatch.delenv("ALLOW_UNAUTHENTICATED_CONTROL", raising=False)
    assert auth.control_access_mode() == "secret"

    import main
    client = TestClient(main.app)
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/settings", headers={"X-API-Secret": "wrong"}).status_code == 401
    assert client.get("/api/settings", headers={"X-API-Secret": "s3cr3t-value"}).status_code == 200


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_local_development_opt_out_reopens_control_endpoints(no_auth_env, monkeypatch, value):
    import api.auth as auth

    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_CONTROL", value)
    assert auth.unauthenticated_control_allowed() is True
    assert auth.control_access_mode() == "open"

    import main
    assert TestClient(main.app).get("/api/settings").status_code == 200


def test_a_secret_wins_over_the_development_opt_out(monkeypatch):
    """Both set must not silently downgrade to the open path."""
    import api.auth as auth

    monkeypatch.setenv("API_SECRET", "s3cr3t-value")
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_CONTROL", "true")
    assert auth.control_access_mode() == "secret"


def test_control_access_is_reported_in_status(no_auth_env):
    """The UI has to be able to tell the user why its buttons are dead."""
    import main

    body = TestClient(main.app).get("/api/status").json()
    assert body["control_access"] == "denied"
    assert body["exchange"]["reachable"] is True


# ── exchange reachability ─────────────────────────────────────────────────────

def test_geo_block_is_not_reported_as_a_generic_failure():
    """
    Binance's regional block arrives as HTTP 451/403 with a `msg` naming the
    terms page. It was previously indistinguishable from any other error, so a
    host that can never trade logged the same "Balance read failed" every
    cycle with no hint that retrying was pointless.
    """
    from bot.binance_client import classify_binance_error

    geo = ('{"code": 0, "msg": "Service unavailable from a restricted location '
           "according to 'b. Eligibility' in https://www.binance.com/en/terms.\"}")
    assert classify_binance_error(geo) == "geo_restricted"
    assert classify_binance_error('{"code": -1021, "msg": "outside recvWindow"}') == "clock_skew"
    assert classify_binance_error('{"code": -2015, "msg": "Invalid API-key"}') == "auth_rejected"
    assert classify_binance_error('{"code": -1003, "msg": "Too many requests"}') == "rate_limited"
    assert classify_binance_error("HTTPSConnectionPool read timed out") == "network"
    assert classify_binance_error('{"code": -2014, "msg": "Unknown order"}') == "bad_request"
    assert classify_binance_error("") == "unknown"


def test_geo_block_help_tells_the_operator_what_to_do():
    from bot.binance_client import BINANCE_ERROR_HELP

    assert "region" in BINANCE_ERROR_HELP["geo_restricted"]


def test_unreachable_exchange_is_reported_once_not_every_cycle(caplog):
    """
    A blocked host fails on every candle. The old code reprinted the whole error
    stack each time, which is what buried the one line that mattered.
    """
    from bot.binance_client import BinanceClient

    client = BinanceClient("k", "s", testnet=True)
    geo = ('{"code": 0, "msg": "Service unavailable from a restricted location"}')

    with caplog.at_level("ERROR", logger="bot.binance_client"):
        for _ in range(5):
            client._mark_unreachable("GET", "/v3/account", geo)

    geo_lines = [r for r in caplog.records if "geo_restricted" in r.getMessage()]
    assert len(geo_lines) == 1, f"logged {len(geo_lines)} times, expected 1"

    assert client.exchange_health["reachable"] is False
    assert client.exchange_health["reason"] == "geo_restricted"
    assert client.exchange_health["help"]


def test_recovery_clears_the_exchange_health():
    from bot.binance_client import BinanceClient

    client = BinanceClient("k", "s", testnet=True)
    client._mark_unreachable("GET", "/v3/account", '{"msg": "restricted location"}')
    assert client.exchange_health["reachable"] is False

    client._mark_reachable()
    assert client.exchange_health == {
        "reachable": True, "reason": None, "detail": None, "help": None, "since": None,
    }


def test_health_reports_degraded_when_the_exchange_is_unreachable(no_auth_env):
    import main

    client = TestClient(main.app)
    assert client.get("/health").json()["status"] == "healthy"

    main.engine.client._mark_unreachable(
        "GET", "/v3/account", '{"msg": "Service unavailable from a restricted location"}'
    )
    body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["exchange_ok"] is False
    assert body["exchange_error"] == "geo_restricted"


# ── health probes ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/", "/health", "/ping"])
def test_head_probe_is_answered(path):
    """
    Render's liveness check sends HEAD. FastAPI's @app.get does not register it
    (unlike Starlette's plain Route), so every health check got a 405.
    """
    import main

    assert TestClient(main.app).request("HEAD", path).status_code == 200
    assert TestClient(main.app).get(path).status_code == 200


# ── auto-start ────────────────────────────────────────────────────────────────

def test_auto_start_is_off_unless_asked(monkeypatch):
    from bot.safety import should_auto_start

    monkeypatch.delenv("AUTO_START", raising=False)
    allowed, reason = should_auto_start(testnet_flag=True)
    assert allowed is False
    assert "AUTO_START" in reason


@pytest.mark.parametrize("value", ["true", "1", "yes", "on"])
def test_auto_start_runs_in_testnet_when_opted_in(monkeypatch, value):
    from bot.safety import should_auto_start

    monkeypatch.setenv("AUTO_START", value)
    assert should_auto_start(testnet_flag=True)[0] is True


def test_auto_start_never_arms_live_money(monkeypatch):
    """
    Every deploy and restart used to resume trading on its own. Even with
    AUTO_START set, a live config must wait for a deliberate start.
    """
    from bot.safety import should_auto_start

    monkeypatch.setenv("AUTO_START", "true")
    allowed, reason = should_auto_start(testnet_flag=False)
    assert allowed is False
    assert "live" in reason.lower()


def test_live_still_requires_its_own_opt_in(monkeypatch):
    """AUTO_START must not double as permission to trade real money."""
    from bot.safety import assert_live_allowed, LiveTradingBlocked, live_opt_in

    monkeypatch.setenv("AUTO_START", "true")
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    assert live_opt_in() is False
    with pytest.raises(LiveTradingBlocked):
        assert_live_allowed(testnet_flag=False, context="auto-start")


# ── honesty of the log wording ────────────────────────────────────────────────

def test_logs_do_not_call_testnet_orders_simulated():
    """
    The banner read "TESTNET — simulated orders". Testnet orders are real
    orders on Binance's testnet venue, and the wording is what makes an
    operator assume paper mode.
    """
    import main

    src = open(main.__file__, encoding="utf-8").read()
    assert "simulated orders" not in src
    assert "testnet venue" in src


def test_unreadable_balance_log_matches_what_the_ui_shows():
    """
    engine.py logged "reporting 0 in UI" while the broadcast set balance_ok:false
    and the dashboard rendered "Unavailable". The log claimed a zero balance.
    """
    import bot.engine as engine_mod

    src = open(engine_mod.__file__, encoding="utf-8").read()
    assert "reporting 0 in UI" not in src
    assert "Unavailable" in src
