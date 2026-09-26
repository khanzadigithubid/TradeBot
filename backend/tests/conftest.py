"""
Shared pytest fixtures. Everything here is offline — no network calls.

The exchange is hard-blocked at the client level. Testnet orders are real
orders on Binance's testnet venue, so a test that reached the order path used
to spend testnet funds on every run (several stray BTC positions accumulated
before this was caught).
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Keep tests deterministic and offline-safe.
os.environ.setdefault("TESTNET", "true")
os.environ["PAPER_TRADING"] = "true"
os.environ.pop("LIVE_TRADING_ENABLED", None)
os.environ.pop("API_SECRET", None)


@pytest.fixture(autouse=True, scope="session")
def _block_real_orders():
    """
    Make any real order placement an immediate, loud failure.

    Tests that exercise order routing inject their own fake client, so nothing
    legitimate needs the real methods. A test that reaches them was about to
    spend money on a real venue and must fail instead.
    """
    from bot.binance_client import BinanceClient

    def _forbidden(self, *args, **kwargs):
        raise AssertionError(
            "A test tried to place a real Binance order. Inject a fake client "
            "or set PAPER_TRADING instead."
        )

    for name in ("place_market_buy", "place_market_sell",
                 "place_limit_buy", "place_limit_sell", "place_oco_sell"):
        setattr(BinanceClient, name, _forbidden)

    from bot import trade_manager as tm_mod
    tm_mod.PAPER_TRADING = True
    yield


@pytest.fixture(autouse=True)
def engine_never_places_orders(monkeypatch):
    """Force paper mode on the live engine object for every single test."""
    import main

    monkeypatch.setitem(main.engine.config, "TESTNET", True)
    monkeypatch.setitem(main.engine.config, "PAPER_TRADING", True)


def make_candles(n=300, start=100.0, drift=0.0008, noise=0.004, seed=7):
    """Deterministic synthetic OHLCV frame shaped like Binance klines."""
    rng = np.random.default_rng(seed)
    closes = start * np.exp(np.cumsum(drift + rng.normal(0, noise, n)))
    opens  = np.concatenate([[closes[0]], closes[:-1]])
    highs  = np.maximum(opens, closes) * (1 + rng.uniform(0, 0.002, n))
    lows   = np.minimum(opens, closes) * (1 - rng.uniform(0, 0.002, n))
    volume = rng.uniform(100, 1000, n)
    ts     = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({
        "timestamp": ts,
        "open":   opens,
        "high":   highs,
        "low":    lows,
        "close":  closes,
        "volume": volume,
    })


@pytest.fixture
def candles():
    return make_candles()


@pytest.fixture
def config():
    return {
        "EMA_FAST": 9, "EMA_SLOW": 21,
        "RSI_PERIOD": 14, "RSI_OVERBOUGHT": 70, "RSI_OVERSOLD": 30,
        "MACD_FAST": 12, "MACD_SLOW": 26, "MACD_SIGNAL": 9,
        "BB_PERIOD": 20, "BB_STD": 2.0,
        "STOP_LOSS_PERCENT": 2.0, "TAKE_PROFIT_PERCENT": 4.0,
        "TRADE_QUANTITY_PERCENT": 10,
        "MAX_OPEN_TRADES": 3,
        "TRAILING_STOP": True, "TRAILING_STOP_PERCENT": 1.0,
        "MTF_ENABLED": True, "SENTIMENT_FILTER": True,
    }


class FakeClient:
    """BinanceClient stand-in. No sockets, no order placement."""

    def __init__(self, balance=1000.0, price=100.0, filters=None):
        self.balance   = balance
        self.price     = price
        self.testnet   = True
        self.base_url  = "https://testnet.binance.vision/api"
        self._filters  = filters or {
            "step_size": 0.001, "min_qty": 0.001, "max_qty": 9000.0,
            "min_notional": 10.0, "tick_size": 0.01,
            "qty_precision": 3, "found": True,
        }
        self.orders    = []

    # -- market data
    def get_balance(self, asset="USDT"):
        return self.balance

    def get_ticker_price(self, symbol):
        return self.price

    def get_klines(self, symbol, interval="15m", limit=200):
        return make_candles(min(limit, 300))

    # -- exchange filters
    def get_symbol_filters(self, symbol):
        return self._filters

    def normalize_quantity(self, symbol, quantity, price=0.0):
        from bot.binance_client import BinanceClient
        return BinanceClient.normalize_quantity(self, symbol, quantity, price)

    def normalize_price(self, symbol, price):
        from bot.binance_client import BinanceClient
        return BinanceClient.normalize_price(self, symbol, price)

    # -- orders (record, never send)
    def place_market_buy(self, symbol, quantity):
        self.orders.append(("BUY", symbol, quantity))
        return {"orderId": 1, "status": "FILLED"}

    def place_market_sell(self, symbol, quantity):
        self.orders.append(("SELL", symbol, quantity))
        return {"orderId": 2, "status": "FILLED"}


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """
    Never let the test suite touch the real data/ directory (settings.json holds
    the user's API keys and mode, trades.json holds their history).
    """
    import bot.settings_store as store
    import bot.trade_manager as tm

    monkeypatch.setattr(store, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(tm, "TRADES_FILE", str(tmp_path / "trades.json"))
    return tmp_path


@pytest.fixture
def trade_manager(fake_client, config):
    from bot import trade_manager as tm
    return tm.TradeManager(fake_client, config)
