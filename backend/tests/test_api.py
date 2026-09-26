"""Tests for the API surface: validation, auth, live interlock, signals."""

import os

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    """
    Import main with startup disabled so the live engine never boots in tests.
    """
    monkeypatch.setenv("TESTNET", "true")
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    monkeypatch.delenv("API_SECRET", raising=False)

    import api.auth as auth

    import main
    main.app.router.on_startup = []      # do not start the trading engine

    # Start from a known state; never depend on the developer's real settings.
    monkeypatch.setitem(main.engine.config, "TESTNET", True)
    monkeypatch.setattr(main.engine, "last_signal", {})

    return TestClient(main.app)


# ── Symbol / interval validation ───────────────────────────────────────────────

def test_bad_symbol_rejected(client):
    r = client.get("/api/market/; DROP TABLE users/candles")
    assert r.status_code in (400, 404, 422)


@pytest.mark.parametrize(
    "symbol", ["../etc/passwd", "a" * 40, "", "BTC%20USDT", "bt%20c", "BTC-USDT"]
)
def test_unsafe_symbols_rejected(client, symbol):
    r = client.get(f"/api/market/{symbol}/candles")
    assert r.status_code in (400, 404, 422), f"{symbol!r} was not rejected"


def test_bad_interval_rejected(client):
    r = client.get("/api/market/BTCUSDT/candles?interval=1y")
    assert r.status_code in (400, 422), "junk interval reached the exchange"


def test_bad_interval_on_backtest_rejected(client):
    r = client.post("/api/backtest", json={"symbol": "BTCUSDT", "interval": "1y"})
    assert r.status_code in (400, 422)


def test_bad_interval_on_start_rejected(client):
    r = client.post("/api/bot/start", json={"interval": "1y"})
    assert r.status_code in (400, 422)


def test_manual_trade_rejects_bad_symbol(client):
    r = client.post("/api/trades/manual", json={"symbol": "bad symbol!", "side": "BUY"})
    assert r.status_code in (400, 422)


def test_manual_trade_rejects_bad_side(client):
    r = client.post("/api/trades/manual", json={"symbol": "BTCUSDT", "side": "HODL"})
    assert r.status_code in (400, 422)


def test_manual_trade_rejects_negative_quantity(client):
    r = client.post("/api/trades/manual",
                    json={"symbol": "BTCUSDT", "side": "BUY", "quantity": -5})
    assert r.status_code in (400, 422)


def test_settings_reject_out_of_range_values(client):
    bad_values = [
        {"trade_quantity_percent": 0},
        {"trade_quantity_percent": 101},
        {"trade_quantity_percent": -5},
        {"stop_loss_percent": -1},
        {"stop_loss_percent": 0},
        {"max_open_trades": 0},
        {"max_open_trades": 999},
        {"ema_fast": 1},
        {"ema_fast": 5000},
        {"take_profit_percent": 0},
        {"trailing_stop_percent": 0},
        {"rsi_period": 0},
        {"interval": "1y"},
        {"symbol": "not a symbol!"},
    ]
    for patch in bad_values:
        r = client.post("/api/settings", json=patch)
        assert r.status_code == 422, f"{patch} was accepted"


def test_settings_reject_unknown_keys(client):
    """A typo must not be silently ignored."""
    r = client.post("/api/settings", json={"trailing_stopp": True})
    assert r.status_code == 422


def test_settings_accept_valid_patch(client):
    r = client.post("/api/settings", json={"trade_quantity_percent": 12.5,
                                           "max_open_trades": 4})
    assert r.status_code == 200
    assert r.json()["effective_testnet"] is True, "must never report an unauthorised live mode"
    client.post("/api/settings", json={"trade_quantity_percent": 10,
                                       "max_open_trades": 3})   # restore


# ── Safety interlock over HTTP ────────────────────────────────────────────────

def test_settings_refuses_live_without_opt_in(client):
    r = client.post("/api/settings", json={"testnet": False})
    assert r.status_code == 403
    assert "LIVE_TRADING_ENABLED" in r.text
    # The stored config must have been downgraded, so a restart cannot go live.
    body = client.get("/api/settings").json()
    assert body["testnet"] is True
    assert body["effective_testnet"] is True


def test_settings_reports_effective_mode(client, monkeypatch):
    import main
    body = client.get("/api/settings").json()
    assert "safety" in body and "testnet" in body and "effective_testnet" in body
    assert body["effective_testnet"] is True

    # A stored live config that cannot be authorised must read as testnet.
    monkeypatch.setitem(main.engine.config, "TESTNET", False)
    body = client.get("/api/settings").json()
    assert body["testnet"] is False, "stored preference should be reported as-is"
    assert body["safety"]["live_allowed"] is False
    assert body["effective_testnet"] is True, "but the bot is not actually live"


def test_manual_buy_blocked_in_live_mode(client, monkeypatch):
    import main
    monkeypatch.setitem(main.engine.config, "TESTNET", False)
    try:
        r = client.post("/api/trades/manual", json={"symbol": "BTCUSDT", "side": "BUY"})
        assert r.status_code == 403
        assert "LIVE_TRADING_ENABLED" in r.text
    finally:
        main.engine.config["TESTNET"] = True


def test_bot_start_blocked_in_live_mode(client, monkeypatch):
    import main
    monkeypatch.setitem(main.engine.config, "TESTNET", False)
    try:
        r = client.post("/api/bot/start", json={})
        assert r.status_code == 403
    finally:
        main.engine.config["TESTNET"] = True


def test_bot_start_accepts_bare_post(client):
    """The frontend must not need to invent a body to start the bot."""
    r = client.post("/api/bot/start")
    assert r.status_code != 422, "bare POST /bot/start was rejected by validation"


def test_close_trade_blocked_in_live_mode(client, monkeypatch):
    import main
    monkeypatch.setitem(main.engine.config, "TESTNET", False)
    try:
        r = client.request("DELETE", "/api/trades/does-not-exist")
        assert r.status_code == 403
    finally:
        main.engine.config["TESTNET"] = True


# ── Auth ───────────────────────────────────────────────────────────────────────

def test_auth_is_closed_by_default_without_a_secret(client, monkeypatch):
    """
    Was "disabled by default", i.e. an unset API_SECRET left every control
    endpoint open to anyone who could reach the host. It now closes them
    instead; see test_deployment_hardening.py for the full matrix. The suite
    opts out via ALLOW_UNAUTHENTICATED_CONTROL in conftest, which is why the
    read still succeeds here.
    """
    import api.auth as auth
    monkeypatch.delenv("API_SECRET", raising=False)
    assert auth.auth_enabled() is False
    assert auth.control_access_mode() in ("denied", "open")
    assert client.get("/api/settings").status_code == 200


def test_auth_blocks_protected_paths_without_secret(client, monkeypatch):
    import api.auth as auth
    monkeypatch.setenv("API_SECRET", "s3cr3t-value")
    assert auth.auth_enabled() is True

    r = client.get("/api/settings")
    assert r.status_code == 401, "unauthenticated call must be a clean 401, not a 500"

    r = client.get("/api/settings", headers={"X-API-Secret": "wrong"})
    assert r.status_code == 401

    r = client.get("/api/settings", headers={"X-API-Secret": "s3cr3t-value"})
    assert r.status_code == 200


def test_auth_leaves_public_paths_open(client, monkeypatch):
    import api.auth as auth
    monkeypatch.setenv("API_SECRET", "s3cr3t-value")
    for path in ("/api/status", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 200, f"{path} should stay public"


def test_auth_leaves_market_data_public(client, monkeypatch):
    import api.auth as auth
    monkeypatch.setenv("API_SECRET", "s3cr3t-value")
    # charts must keep working without the secret
    r = client.get("/api/market/BTCUSDT/signal")
    assert r.status_code != 401


def test_auth_protects_trade_endpoints(client, monkeypatch):
    import api.auth as auth
    monkeypatch.setenv("API_SECRET", "s3cr3t-value")

    assert client.post("/api/trades/manual",
                       json={"symbol": "BTCUSDT", "side": "BUY"}).status_code == 401
    assert client.post("/api/bot/start", json={}).status_code == 401
    assert client.post("/api/settings",
                       json={"trade_quantity_percent": 12}).status_code == 401
    assert client.request("DELETE", "/api/trades/abc").status_code == 401


def test_auth_comparison_is_constant_time():
    import hmac
    import api.auth as auth
    # the implementation must use hmac.compare_digest, not ==
    assert hmac.compare_digest("abcdef", "abcdef") is True
    assert hmac.compare_digest("abcdef", "abcdeg") is False
    src = open(auth.__file__, encoding="utf-8").read()
    assert "compare_digest" in src, "secret comparison must be constant-time"


# ── Signal endpoint consistency ───────────────────────────────────────────────

def test_signal_endpoint_survives_none_cache(client, monkeypatch):
    """
    engine.last_signal is None until the first cycle. The endpoint used to raise
    AttributeError -> 500.
    """
    import main
    from tests.conftest import make_candles
    monkeypatch.setattr(main.engine, "last_signal", None)
    import bot.strategy as strategy
    monkeypatch.setattr(strategy, "get_klines", lambda *a, **k: make_candles(drift=0.0012, seed=3))
    monkeypatch.setattr(strategy, "get_sentiment", lambda s, c: {})

    r = client.get("/api/market/BTCUSDT/signal")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action"] in ("BUY", "SELL", "HOLD")
    assert 0 <= body["confidence"] <= 99


def test_signal_endpoint_uses_engine_cache(client, monkeypatch):
    import main
    cached = {"symbol": "BTCUSDT", "action": "HOLD", "confidence": 55, "price": 1.0}
    monkeypatch.setattr(main.engine, "last_signal", {"BTCUSDT": cached})
    r = client.get("/api/market/BTCUSDT/signal")
    assert r.status_code == 200
    assert r.json()["confidence"] == 55


def test_signal_endpoint_normalises_symbol(client, monkeypatch):
    from tests.conftest import make_candles
    import main
    monkeypatch.setattr(main.engine, "last_signal", None)
    import bot.strategy as strategy
    monkeypatch.setattr(strategy, "get_klines", lambda *a, **k: make_candles(drift=0.0012, seed=3))
    monkeypatch.setattr(strategy, "get_sentiment", lambda s, c: {})
    r = client.get("/api/market/btcusdt/signal")
    assert r.status_code == 200
    assert r.json()["symbol"] == "BTCUSDT"
