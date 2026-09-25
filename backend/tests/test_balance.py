"""
Regression tests for balance handling.

The original code did this:

    balance = self.client.get_balance("USDT")
    if balance <= 0:
        balance = 1000.0

BinanceClient._get swallowed every exception and returned {"error": ...}, so a
bad API key, a network failure or a Binance outage all produced a balance of
0.0 — which the code then "fixed" by inventing $1000 and sizing a real order
against money the account never had.

Balance reads now distinguish three states:
  float  — read succeeded (0.0 means a genuine empty account)
  None   — read failed and must never be turned into a number
"""
import pytest

from bot.binance_client import BinanceClient
from bot.trade_manager import TradeManager


# ── get_balance: read failure vs genuine zero ────────────────────────────────

def test_get_balance_returns_none_on_error_payload():
    """A failed /v3/account call must not look like a zero balance."""
    client = BinanceClient("k", "s", testnet=True)
    client.get_account_info = lambda: {"error": "HTTP 401 Unauthorized"}

    assert client.get_balance("USDT") is None


def test_get_balance_returns_none_when_account_info_raises():
    client = BinanceClient("k", "s", testnet=True)

    def boom():
        raise RuntimeError("network down")

    client.get_account_info = boom
    assert client.get_balance("USDT") is None


def test_get_balance_returns_zero_for_genuinely_empty_account():
    """Zero is real data and must stay distinguishable from a failure."""
    client = BinanceClient("k", "s", testnet=True)
    client.get_account_info = lambda: {"balances": [{"asset": "USDT", "free": "0.0"}]}

    assert client.get_balance("USDT") == 0.0


def test_get_balance_returns_actual_free_balance():
    client = BinanceClient("k", "s", testnet=True)
    client.get_account_info = lambda: {
        "balances": [
            {"asset": "BTC", "free": "0.5"},
            {"asset": "USDT", "free": "250.75"},
        ]
    }

    assert client.get_balance("USDT") == 250.75


# ── get_trade_quantity: must fail closed ────────────────────────────────────

def _manager(balance):
    tm = TradeManager.__new__(TradeManager)
    tm.client = type("C", (), {"get_balance": lambda self, a="USDT": balance})()
    tm.config = {"TRADE_QUANTITY_PERCENT": 10}
    return tm


def test_unreadable_balance_refuses_to_size_a_trade():
    qty, err = _manager(None).get_trade_quantity("BTCUSDT", 100.0)

    assert qty == 0.0
    assert err and "could not be read" in err


def test_zero_balance_refuses_to_size_a_trade():
    qty, err = _manager(0.0).get_trade_quantity("BTCUSDT", 100.0)

    assert qty == 0.0
    assert err and "no funds" in err


def test_never_invents_a_1000_balance():
    """The exact regression: a failed read must not become $1000."""
    for broken in (None, 0.0, 0):
        qty, err = _manager(broken).get_trade_quantity("BTCUSDT", 100.0)
        assert qty == 0.0, f"invented a size from balance={broken!r}"
        assert err


def test_real_balance_sizes_a_position():
    qty, err = _manager(1000.0).get_trade_quantity("BTCUSDT", 100.0)

    assert err is None
    assert qty == 1.0  # 10% of 1000 at price 100


def test_invalid_price_is_rejected():
    qty, err = _manager(1000.0).get_trade_quantity("BTCUSDT", 0.0)

    assert qty == 0.0
    assert "price" in err


# ── execute_buy: an unreadable balance must not place an order ───────────────

def test_execute_buy_places_nothing_when_balance_unreadable(monkeypatch):
    tm = TradeManager.__new__(TradeManager)
    placed = []

    tm.client = type(
        "C",
        (),
        {
            "get_balance": lambda self, a="USDT": None,
            "normalize_quantity": lambda self, s, q, p=0.0: (q, None),
            "normalize_price": lambda self, s, p: p,
            "place_market_buy": lambda self, s, q: placed.append((s, q)),
        },
    )()
    tm.config = {"TRADE_QUANTITY_PERCENT": 10, "MAX_OPEN_TRADES": 3, "TESTNET": True}
    tm.trades = []
    tm._notified = {}

    result = tm.execute_buy("BTCUSDT", {"price": 100.0}, force=True)

    assert result is None
    assert placed == [], "an order was placed with an unreadable balance"
