"""
Backtester correctness tests.

The fast path in bot/backtester.py replaced an O(n^2) reference loop. Any such
rewrite is only trustworthy if it is *proved* equivalent, because a backtester
that quietly diverges from the live strategy is worse than no backtester: it
reports numbers for a system nobody is running. These tests pin that down
candle-by-candle rather than trusting the argument in the module docstring.
"""
import numpy as np
import pandas as pd
import pytest

from bot.backtester import run_backtest, run_backtest_reference, _score_at, _Features
from bot.indicators import generate_ai_signal

BASE = {
    "SYMBOL": "BTCUSDT", "EMA_FAST": 9, "EMA_SLOW": 21, "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70, "RSI_OVERSOLD": 30, "MACD_FAST": 12, "MACD_SLOW": 26,
    "MACD_SIGNAL": 9, "BB_PERIOD": 20, "BB_STD": 2.0, "STOP_LOSS_PERCENT": 2.0,
    "TAKE_PROFIT_PERCENT": 4.0, "TRADE_QUANTITY_PERCENT": 10,
    "TRAILING_STOP": False, "TRAILING_STOP_PERCENT": 3.0,
    "BACKTEST_FEE_PERCENT": 0.0, "BACKTEST_SLIPPAGE_PERCENT": 0.0,
    "EXIT_ON_SIGNAL": False,
}


def synth(n=420, seed=7):
    """Deterministic random-walk OHLCV — no network, no cached data.

    Kept small on purpose: run_backtest_reference() is O(n^2) with a Python
    loop inside calculate_supertrend(), so the reference side dominates test
    runtime. 420 bars is still well past warmup and yields enough trades to
    catch a divergence.
    """
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.004, n).cumsum()
    close = 70_000 * np.exp(steps)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min"),
        "open":   close,
        "high":   close * (1 + np.abs(rng.normal(0, 0.0012, n))),
        "low":    close * (1 - np.abs(rng.normal(0, 0.0012, n))),
        "close":  close,
        "volume": np.abs(rng.normal(140, 40, n)),
    })


@pytest.fixture(scope="module")
def df():
    return synth()


# ── signal parity ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("start", [200, 300, 380])
def test_vectorised_score_matches_generate_ai_signal(df, start):
    """The scoring rewrite must agree with the live signal generator exactly."""
    f = _Features(df, BASE)
    for i in range(start, min(start + 25, len(df))):
        ref = generate_ai_signal(df.iloc[: i + 1], BASE)
        action, conf, sl, tp = _score_at(f, i, BASE)
        assert action == ref["action"], f"action diverged at i={i}"
        assert conf == ref["confidence"], f"confidence diverged at i={i}"
        if ref["action"] == "BUY":
            assert sl == ref["stop_loss"], f"stop diverged at i={i}"
            assert tp == ref["take_profit"], f"target diverged at i={i}"


def test_vectorised_score_handles_sentiment(df):
    """Sentiment is applied before the decision, so it can flip the action."""
    f = _Features(df, BASE)
    for i in (200, 300):
        ref = generate_ai_signal(df.iloc[: i + 1], BASE, sentiment_adjust=20)
        action, conf, _, _ = _score_at(f, i, BASE, sentiment_adjust=20)
        assert (action, conf) == (ref["action"], ref["confidence"])


# ── simulation parity ─────────────────────────────────────────────────────────
def _compare(ref, got, label):
    rt, gt = ref["trades"], got["trades"]
    assert len(rt) == len(gt), f"{label}: {len(rt)} reference trades vs {len(gt)}"
    for r, g in zip(rt, gt):
        assert abs(r["entry_price"] - g["entry_price"]) < 1e-6, f"{label}: entry"
        assert abs(r["quantity"] - g["quantity"]) < 1e-6, f"{label}: quantity"
        assert abs(r["stop_loss"] - g["stop_loss"]) < 1e-6, f"{label}: stop"
        assert abs(r["take_profit"] - g["take_profit"]) < 1e-6, f"{label}: target"
        assert abs(r["exit_price"] - g["exit_price"]) < 1e-6, f"{label}: exit"
        assert abs(r["pnl"] - g["pnl"]) < 1e-4, f"{label}: pnl"
        assert r["close_reason"] == g["close_reason"], f"{label}: reason"
    re_ = [e["equity"] for e in ref["equity_curve"]]
    ge_ = [e["equity"] for e in got["equity_curve"]]
    assert len(re_) == len(ge_), f"{label}: equity length"
    for a, b in zip(re_, ge_):
        assert abs(a - b) < 1e-3, f"{label}: equity curve"
    assert abs(ref["metrics"]["final_balance"] - got["metrics"]["final_balance"]) < 1e-4


@pytest.mark.parametrize("over", [
    {},
    {"TRAILING_STOP": True, "TRAILING_STOP_PERCENT": 1.0},
    {"STOP_LOSS_PERCENT": 1.0, "TAKE_PROFIT_PERCENT": 8.0},
    {"BACKTEST_FEE_PERCENT": 0.10, "BACKTEST_SLIPPAGE_PERCENT": 0.02},
    {"EXIT_ON_SIGNAL": True},
])
def test_fast_path_matches_reference(df, over):
    """Trade-for-trade equality, including costs and the signal exit."""
    conf = dict(BASE, **over)
    _compare(
        run_backtest_reference(df, conf, 1000.0, 60.0),
        run_backtest(df, conf, 1000.0, 60.0),
        str(over),
    )


def test_reference_and_fast_agree_with_costs_and_trailing(df):
    """The full-cost, trailing-on case is the one people actually run."""
    conf = dict(BASE, TRAILING_STOP=True, TRAILING_STOP_PERCENT=1.0,
                BACKTEST_FEE_PERCENT=0.10, BACKTEST_SLIPPAGE_PERCENT=0.02)
    _compare(
        run_backtest_reference(df, conf, 1000.0, 60.0),
        run_backtest(df, conf, 1000.0, 60.0),
        "full-cost",
    )


# ── no lookahead ──────────────────────────────────────────────────────────────
def test_futuristic_candles_cannot_change_past_signals(df):
    """Rewriting the candles after i must not alter the signal at i."""
    f_before = _Features(df, BASE)
    before = [_score_at(f_before, i, BASE)[:2] for i in (150, 250, 350)]

    tampered = df.copy()
    tampered.loc[351:, ["open", "high", "low", "close", "volume"]] *= 1.5
    f_after = _Features(tampered, BASE)
    after = [_score_at(f_after, i, BASE)[:2] for i in (150, 250, 350)]

    assert before == after


def test_futuristic_candles_cannot_change_past_trades(df):
    """Trade history up to a bar must survive a rewrite of everything after."""
    conf = dict(BASE, EXIT_ON_SIGNAL=True,
                BACKTEST_FEE_PERCENT=0.10, BACKTEST_SLIPPAGE_PERCENT=0.02)
    cut = 320
    base = run_backtest(df, conf, 1000.0, 60.0, stop_at=cut)

    tampered = df.copy()
    tampered.loc[cut:, ["open", "high", "low", "close", "volume"]] *= 0.6
    after = run_backtest(tampered, conf, 1000.0, 60.0, stop_at=cut)

    assert [t["entry_time"] for t in base["trades"]] == \
           [t["entry_time"] for t in after["trades"]]
    assert [t["close_reason"] for t in base["trades"]] == \
           [t["close_reason"] for t in after["trades"]]
    assert abs(base["metrics"]["final_balance"]
               - after["metrics"]["final_balance"]) < 1e-6


# ── cost and parity behaviour ─────────────────────────────────────────────────
def test_costs_reduce_pnl_for_a_strategy_that_trades(df):
    """Fees must never flatter a high-turnover strategy."""
    free = run_backtest(df, dict(BASE, BACKTEST_FEE_PERCENT=0.0,
                                 BACKTEST_SLIPPAGE_PERCENT=0.0), 1000.0, 60.0)
    costed = run_backtest(df, dict(BASE, BACKTEST_FEE_PERCENT=0.10,
                                   BACKTEST_SLIPPAGE_PERCENT=0.02), 1000.0, 60.0)
    assert costed["metrics"]["final_balance"] < free["metrics"]["final_balance"]
    assert sum(t["fees"] for t in costed["trades"]) > 0


def test_signal_exit_closes_positions_before_stop_or_target(df):
    """The live engine flattens on a SELL signal; the backtest must too."""
    conf = dict(BASE, EXIT_ON_SIGNAL=True)
    out = run_backtest(df, conf, 1000.0, 60.0)
    assert any(t["close_reason"] == "SIGNAL" for t in out["trades"]), \
        "no SELL-signal exits: the backtest does not match the engine"
    assert all(t["close_reason"] in
               {"STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP", "SIGNAL", "END_OF_DATA"}
               for t in out["trades"])


def test_split_ranges_do_not_leak_a_position_across_the_boundary(df):
    """A fold must close out rather than hand an open trade to the next fold."""
    cut = 300
    out = run_backtest(df, BASE, 1000.0, 60.0, start_at=60, stop_at=cut)
    assert all(t["status"] == "CLOSED" for t in out["trades"])
    assert all(t["close_reason"] is not None for t in out["trades"])


def test_rejects_short_frames():
    out = run_backtest(synth(40), BASE)
    assert "error" in out
