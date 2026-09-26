"""
Signed-request robustness.

Binance rejects a request with -1021 when the signed timestamp falls outside
recvWindow, and the default window is only 5 seconds. A machine running even a
few seconds behind the exchange therefore loses orders and balance reads
intermittently — a failure that looks random and only shows up in production.

Measured on this machine: the local clock sat 4.4s behind Binance, which was
enough to fail roughly 1 request in 8.
"""
import time

import pytest

from bot.binance_client import BinanceClient, RECV_WINDOW_MS


class _Resp:
    def __init__(self, payload=None, status=200, text=""):
        self._payload = payload or {}
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise _HttpErr(self.status_code, self.text)

    def json(self):
        return self._payload


class _HttpErr(Exception):
    def __init__(self, status, text):
        super().__init__(f"{status} Client Error")
        self.response = _Resp(status=status, text=text)


# ── recvWindow ───────────────────────────────────────────────────────────────

def test_signed_requests_carry_a_recv_window():
    client = BinanceClient("k", "s", testnet=True)
    client._server_time_offset_ms = lambda: 0

    signed = client._sign({})
    assert "recvWindow" in signed, "a signed request without recvWindow uses the 5s default"
    assert signed["recvWindow"] == RECV_WINDOW_MS
    assert RECV_WINDOW_MS >= 30_000, "5s is too tight for a drifting clock"


def test_signing_does_not_mutate_the_callers_params():
    """
    The retry path signs the original values again, so _sign must not bake a
    timestamp/signature into the dict the caller still holds.
    """
    client = BinanceClient("k", "s", testnet=True)
    client._server_time_offset_ms = lambda: 0

    original = {"symbol": "BTCUSDT"}
    client._sign(original)

    assert "signature" not in original, "the caller's params were signed in place"
    assert "timestamp" not in original
    assert "recvWindow" not in original


def test_a_resign_uses_the_current_offset():
    """
    HMAC is deterministic, so re-signing the same values at the same
    millisecond gives the same hex. What must change on a retry is the offset
    used to build the timestamp — that is what actually repairs a -1021.
    """
    client = BinanceClient("k", "s", testnet=True)

    client._server_time_offset_ms = lambda: 4_000
    drifted = client._sign({"symbol": "BTCUSDT"})

    client._server_time_offset_ms = lambda: 0
    corrected = client._sign({"symbol": "BTCUSDT"})

    assert corrected["timestamp"] < drifted["timestamp"], "the offset was not applied"
    assert corrected["signature"] != drifted["signature"]


# ── clock offset ─────────────────────────────────────────────────────────────

def test_clock_offset_is_measured_against_the_exchange(monkeypatch):
    client = BinanceClient("k", "s", testnet=True)
    monkeypatch.setattr(client, "_get", lambda ep: {"serverTime": int(time.time() * 1000) + 4_000})

    offset = client._server_time_offset_ms()

    assert offset == pytest.approx(4_000, abs=250), "a 4s drift must be detected"
    assert offset > 0, "Binance is ahead, so signatures must be pushed forward"


def test_clock_offset_is_measured_once_and_cached(monkeypatch):
    client = BinanceClient("k", "s", testnet=True)
    calls = []

    def fake_get(ep):
        calls.append(ep)
        return {"serverTime": int(time.time() * 1000)}

    monkeypatch.setattr(client, "_get", fake_get)
    client._server_time_offset_ms()
    client._server_time_offset_ms()
    client._server_time_offset_ms()

    assert calls == ["/v3/time"], "server time must not be re-fetched per request"


def test_offset_survives_a_server_time_failure(monkeypatch):
    client = BinanceClient("k", "s", testnet=True)

    def boom(ep):
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_get", boom)
    assert client._server_time_offset_ms() == 0, "must still sign when time sync fails"


def test_signature_uses_the_corrected_timestamp(monkeypatch):
    client = BinanceClient("k", "s", testnet=True)
    monkeypatch.setattr(client, "_get", lambda ep: {"serverTime": int(time.time() * 1000) + 30_000})
    client._server_time_offset_ms = lambda: 30_000

    signed = client._sign({})

    assert signed["timestamp"] - int(time.time() * 1000) == pytest.approx(30_000, abs=2000)


# ── error reporting ──────────────────────────────────────────────────────────

def test_binance_error_body_is_preserved(monkeypatch):
    """str(HTTPError) is only "400 Client Error" and hides the real reason."""
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    monkeypatch.setattr(
        mod.requests, "get",
        lambda *a, **kw: _Resp(status=400, text='{"code":-2010,"msg":"Account has insufficient balance"}'),
    )

    out = client._get("/v3/account", signed=True)

    assert "-2010" in out["error"]
    assert "insufficient balance" in out["error"]


def test_a_rejected_timestamp_resyncs_and_retries_once(monkeypatch):
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    sent = []
    offsets = iter([4_000, 0])          # first sign is wrong, the resync fixes it
    client._server_time_offset_ms = lambda: next(offsets)

    def flaky(url, *a, **kw):
        sent.append(dict(kw.get("params") or {}))
        if len(sent) == 1:
            return _Resp(status=400, text='{"code":-1021,"msg":"Timestamp outside recvWindow"}')
        return _Resp({"balances": [{"asset": "USDT", "free": "5"}]})

    monkeypatch.setattr(mod.requests, "get", flaky)

    out = client._get("/v3/account", signed=True)

    assert "error" not in out, "a recoverable clock error must not surface as a failure"
    assert len(sent) == 2, "exactly one retry"
    assert client._clock_offset is None or client._clock_offset == 0, \
        "the cached offset must be discarded so it is re-measured"

    # The retry must be signed against the corrected offset, not the rejected one.
    assert sent[0]["signature"] != sent[1]["signature"], "the retry reused the rejected signature"
    assert sent[1]["timestamp"] < sent[0]["timestamp"], "the retry did not apply the corrected clock"


def test_retry_happens_only_once(monkeypatch):
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    seen = []

    def always_stale(url, *a, **kw):
        if "/v3/time" in url:
            return _Resp({"serverTime": int(time.time() * 1000)})
        seen.append(1)
        return _Resp(status=400, text='{"code":-1021,"msg":"Timestamp outside recvWindow"}')

    monkeypatch.setattr(mod.requests, "get", always_stale)

    out = client._get("/v3/account", signed=True)

    assert "-1021" in out["error"]
    assert len(seen) == 2, "must not retry forever"


def test_a_real_rejection_is_not_retried(monkeypatch):
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    seen = []

    def rejected(url, *a, **kw):
        if "/v3/time" in url:
            return _Resp({"serverTime": int(time.time() * 1000)})
        seen.append(1)
        return _Resp(status=400, text='{"code":-2010,"msg":"insufficient balance"}')

    monkeypatch.setattr(mod.requests, "get", rejected)

    out = client._get("/v3/order", signed=True)

    assert "-2010" in out["error"]
    assert len(seen) == 1, "only clock errors are retried"


def test_order_rejection_never_reaches_the_exchange_twice(monkeypatch):
    """A real rejection must not be resubmitted, or it could double an order."""
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    posts = []

    def rejected(url, *a, **kw):
        if "/v3/time" in url:
            return _Resp({"serverTime": int(time.time() * 1000)})
        posts.append(1)
        return _Resp(status=400, text='{"code":-2010,"msg":"insufficient balance"}')

    monkeypatch.setattr(mod.requests, "post", rejected)

    # _post directly: place_market_buy is hard-blocked for the whole test session.
    out = client._post("/v3/order", {"symbol": "BTCUSDT", "side": "BUY"})

    assert "-2010" in out["error"]
    assert len(posts) == 1, "an order must never be submitted twice"


def test_a_clock_error_on_an_order_is_retried_exactly_once(monkeypatch):
    """
    -1021 is raised by Binance's request validation before an order is ever
    matched, so resubmitting the same signed request cannot create a second
    order. The retry is therefore safe, and bounded to one attempt.
    """
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    posts = []
    offsets = iter([4_000, 0])
    client._server_time_offset_ms = lambda: next(offsets)

    def first_stale(url, *a, **kw):
        posts.append(dict(kw.get("params") or {}))
        if len(posts) == 1:
            return _Resp(status=400, text='{"code":-1021,"msg":"Timestamp outside recvWindow"}')
        return _Resp({"orderId": 7, "status": "FILLED", "executedQty": "0.001"})

    monkeypatch.setattr(mod.requests, "post", first_stale)

    out = client._post("/v3/order", {"symbol": "BTCUSDT", "side": "BUY"})

    assert out.get("orderId") == 7, "a stale timestamp should not lose the order"
    assert len(posts) == 2

    # The order must be retried with a fresh signature, not the rejected one.
    assert posts[0]["side"] == posts[1]["side"] == "BUY", "the retry lost the order parameters"
    assert posts[0]["signature"] != posts[1]["signature"], "the retry reused the rejected signature"


# ── other signed verbs ───────────────────────────────────────────────────────

def test_cancel_order_is_signed(monkeypatch):
    """A cancel sent unsigned is rejected by Binance and leaves the order live."""
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)
    seen = {}

    def fake_delete(url, *a, **kw):
        seen.update(kw.get("params") or {})
        return _Resp({"orderId": 5, "status": "CANCELED"})

    monkeypatch.setattr(mod.requests, "delete", fake_delete)

    out = client._delete("/v3/order", {"symbol": "BTCUSDT", "orderId": 5})

    assert "error" not in out
    assert seen.get("signature"), "cancel was not signed"
    assert seen.get("timestamp")


def test_cancel_order_reports_the_real_rejection_reason(monkeypatch):
    import bot.binance_client as mod

    client = BinanceClient("k", "s", testnet=True)

    def rejected(url, *a, **kw):
        if "/v3/time" in url:
            return _Resp({"serverTime": int(time.time() * 1000)})
        return _Resp(status=400, text='{"code":-2011,"msg":"Unknown order sent"}')

    monkeypatch.setattr(mod.requests, "delete", rejected)

    out = client._delete("/v3/order", {"symbol": "BTCUSDT", "orderId": 5})

    assert "-2011" in out["error"], "str(HTTPError) hides the reason a cancel failed"
