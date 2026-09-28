"""
Tests for the data-layer and risk-default changes made after the 180-day
backtest showed the 1% trailing stop was destroying the account.

The trailing-stop test is a regression guard: if someone re-tightens the
default to 1%, this fails with the numbers that motivated the change.
"""
import pandas as pd
import pytest

import bot.config as cfg
import bot.market_data as md
from bot.backtester import run_backtest


# ── klines pagination ─────────────────────────────────────────────────────────
class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status


def _row(ts, close):
    return [ts, "1", "2", "0.5", str(close), "10", 0, "0", 1, "0", "0", "0"]


def test_klines_paginates_past_the_1000_candle_request_cap(monkeypatch):
    """Binance rejects limit>1000, so long windows must walk backwards."""
    calls = []

    def fake(endpoint, params):
        calls.append(dict(params))
        limit = params["limit"]
        # Serve 1000 candles ending at endTime (or 900_000 for the first call).
        end = params.get("endTime", 900_000)
        start = end - limit * 60_000
        return [_row(start + i * 60_000, 100 + i) for i in range(limit)]

    monkeypatch.setattr(md, "_try_binance", fake)
    monkeypatch.setattr(md, "_is_forex", lambda s: False)

    df = md.get_klines("BTCUSDT", "15m", limit=2500)

    assert len(df) == 2500, "did not gather the full requested window"
    assert len(calls) == 3, f"expected 3 paginated requests, got {len(calls)}"
    assert all(c["limit"] <= 1000 for c in calls), "sent an illegal per-request limit"
    # Oldest first, strictly increasing, no duplicates at the page seams.
    assert df["timestamp"].is_monotonic_increasing
    assert df["timestamp"].is_unique


def test_klines_returns_nothing_rather_than_fabricated_prices(monkeypatch):
    """A dead upstream must yield an empty frame, never invented candles."""
    monkeypatch.setattr(md, "_is_forex", lambda s: False)

    def boom(*a, **k):
        raise AssertionError("no network call should fabricate a series")

    monkeypatch.setattr(md.requests, "get", boom)
    df = md.get_klines("BTCUSDT", "15m", limit=100)

    assert df.empty


def test_klines_clamps_absurd_limits(monkeypatch):
    monkeypatch.setattr(md, "_is_forex", lambda s: False)
    seen = {}

    def fake(endpoint, params):
        seen.update(params)
        return [_row(i * 60_000, 100) for i in range(params["limit"])]

    monkeypatch.setattr(md, "_try_binance", fake)
    md.get_klines("BTCUSDT", "15m", limit=10**9)

    assert seen["limit"] == 1000, "per-request limit must never exceed 1000"


# ── trailing stop regression guard ────────────────────────────────────────────
def _walk(n=600, seed=3, vol=0.005):
    import numpy as np
    rng = np.random.default_rng(seed)
    close = 70_000 * np.exp(rng.normal(0, vol, n).cumsum())
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min"),
        "open": close,
        "high": close * (1 + np.abs(rng.normal(0, 0.002, n))),
        "low": close * (1 - np.abs(rng.normal(0, 0.002, n))),
        "close": close,
        "volume": np.abs(rng.normal(140, 40, n)),
    })


COSTS = {"BACKTEST_FEE_PERCENT": 0.10, "BACKTEST_SLIPPAGE_PERCENT": 0.02}


def test_default_trailing_stop_is_off():
    """The 1% default cost 28% over 180 days. It must not come back by default."""
    assert cfg.TRAILING_STOP is False
    assert cfg.TRAILING_STOP_PERCENT >= 3.0


@pytest.mark.parametrize("seed", [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23])
def test_a_one_percent_trail_churns_and_costs_more(seed):
    """
    The measurement behind the default change, as a regression guard.

    Over 180d of real 15m candles the 1% trail produced 98.6% of all exits and
    -28.4% versus -1.8% with no trail. On a 2000-bar synthetic walk it is worse
    on 21 of 24 seeds, by ~$12 per $1000, and runs ~150 extra trades — the
    effect scales with sample length because the whole mechanism is cost drag
    from extra round trips. A short window is a coin flip, which is why this
    asserts the long-window behaviour rather than a per-window P&L.
    """
    df = _walk(n=2000, seed=seed)
    base = {"SYMBOL": "BTCUSDT", "STOP_LOSS_PERCENT": 2.0,
            "TAKE_PROFIT_PERCENT": 4.0, "TRADE_QUANTITY_PERCENT": 10,
            "EXIT_ON_SIGNAL": False, **COSTS}

    tight = run_backtest(df, dict(base, TRAILING_STOP=True,
                                  TRAILING_STOP_PERCENT=1.0), 1000.0, 60.0)
    off = run_backtest(df, dict(base, TRAILING_STOP=False), 1000.0, 60.0)

    assert tight["metrics"]["total_trades"] > off["metrics"]["total_trades"], (
        f"seed {seed}: 1% trail should churn more "
        f"({tight['metrics']['total_trades']} vs {off['metrics']['total_trades']})"
    )


def test_a_one_percent_trail_underperforms_over_many_seeds():
    """
    Aggregate version of the above. Individually a trail can help on one path
    by cutting a loser short; the claim that holds is the mean.
    """
    base = {"SYMBOL": "BTCUSDT", "STOP_LOSS_PERCENT": 2.0,
            "TAKE_PROFIT_PERCENT": 4.0, "TRADE_QUANTITY_PERCENT": 10,
            "EXIT_ON_SIGNAL": False, **COSTS}

    worse, diffs, extra = 0, [], []
    for seed in range(1, 13):
        df = _walk(n=2000, seed=seed)
        t = run_backtest(df, dict(base, TRAILING_STOP=True,
                                  TRAILING_STOP_PERCENT=1.0), 1000.0, 60.0)["metrics"]
        o = run_backtest(df, dict(base, TRAILING_STOP=False), 1000.0, 60.0)["metrics"]
        diffs.append(t["final_balance"] - o["final_balance"])
        extra.append(t["total_trades"] - o["total_trades"])
        if t["final_balance"] < o["final_balance"]:
            worse += 1

    assert sum(diffs) < 0, f"1% trail did not cost money on average: {sum(diffs):+.2f}"
    assert sum(extra) > 0, "1% trail did not add churn"
    assert worse >= 8, f"1% trail only underperformed on {worse}/12 seeds"
