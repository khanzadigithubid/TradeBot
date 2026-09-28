"""
Backtesting Engine
Runs the signal strategy over historical OHLCV data and simulates trades.
Returns detailed performance metrics without touching real/testnet funds.
"""

import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime
from bot.indicators import (
    generate_ai_signal,
    calculate_ema, calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_atr, calculate_volume_sma, calculate_vwap,
    calculate_stochastic_rsi, calculate_supertrend, calculate_williams_r,
    calculate_obv,
)
import logging

logger = logging.getLogger(__name__)


def run_backtest_reference(
    df: pd.DataFrame,
    config: dict,
    initial_balance: float = 1000.0,
    confidence_threshold: float = 60.0,
    sentiment_lookup=None,
) -> dict:
    """
    Reference implementation: the original per-candle loop, kept as the
    correctness oracle that the fast path in run_backtest() is tested against.

    O(n^2) — generate_ai_signal() is recomputed over a growing window for every
    candle. Fine for tests on a few hundred bars, useless on 17k. Do not use it
    for research; use run_backtest().
    """
    if df.empty or len(df) < 50:
        return {"error": "Not enough candle data (need ≥ 50 candles)"}

    balance      = initial_balance
    trades       = []
    equity_curve = []
    open_trade: Optional[dict] = None

    sl_pct = config.get("STOP_LOSS_PERCENT",   2.0) / 100
    tp_pct = config.get("TAKE_PROFIT_PERCENT", 4.0) / 100
    trade_pct = config.get("TRADE_QUANTITY_PERCENT", 10) / 100
    trailing  = config.get("TRAILING_STOP", False)
    trail_pct = config.get("TRAILING_STOP_PERCENT", 3.0) / 100
    fee_pct     = config.get("BACKTEST_FEE_PERCENT", 0.0) / 100
    slip_pct    = config.get("BACKTEST_SLIPPAGE_PERCENT", 0.0) / 100
    exit_on_signal = config.get("EXIT_ON_SIGNAL", True)

    # Minimum lookback for indicator warmup
    WARMUP = max(
        config.get("EMA_SLOW", 21),
        config.get("MACD_SLOW", 26) + config.get("MACD_SIGNAL", 9),
        config.get("BB_PERIOD", 20),
        config.get("RSI_PERIOD", 14),
    ) + 5

    for i in range(WARMUP, len(df)):
        window  = df.iloc[:i+1]
        candle  = df.iloc[i]
        ts      = candle["timestamp"]
        close   = float(candle["close"])
        high    = float(candle["high"])
        low     = float(candle["low"])

        # ── Check open trade SL/TP on this candle ─────────────────────────────
        if open_trade:
            sl = open_trade["stop_loss"]
            tp = open_trade["take_profit"]
            peak = open_trade.get("peak_price", open_trade["entry_price"])

            # Trailing stop update
            if trailing and high > peak:
                peak = high
                open_trade["peak_price"] = peak
                new_sl = round(peak * (1 - trail_pct), 8)
                if new_sl > sl:
                    open_trade["stop_loss"] = new_sl
                    sl = new_sl

            close_reason = None
            exit_price   = None

            if low <= sl:
                close_reason = "TRAILING_STOP" if trailing and peak > open_trade["entry_price"] else "STOP_LOSS"
                exit_price   = sl     # assume we got filled at SL
            elif high >= tp:
                close_reason = "TAKE_PROFIT"
                exit_price   = tp

            # ── SELL-signal exit (parity with the live engine) ─────────────────
            # The engine flattens a position when the signal flips to SELL at
            # confidence >= 60. Without this the backtest held positions the
            # live bot would have closed, so it never measured the real exit
            # path. Costs the backtest an extra indicator pass, so it is only
            # attempted while a position is open and no stop already fired.
            if close_reason is None and exit_on_signal:
                try:
                    flip = generate_ai_signal(window, config)
                    if flip["action"] == "SELL" and flip["confidence"] >= 60:
                        close_reason = "SIGNAL"
                        exit_price   = close
                except Exception:
                    pass

            if close_reason:
                # Fees and slippage on both legs, always adverse.
                entry_eff = open_trade["entry_price"] * (1 + slip_pct)
                exit_eff  = exit_price * (1 - slip_pct)
                qty       = open_trade["quantity"]
                fees      = (entry_eff + exit_eff) * qty * fee_pct
                pnl     = (exit_eff - entry_eff) * qty - fees
                pnl_pct = ((exit_eff - entry_eff) / entry_eff) * 100
                balance += pnl
                open_trade.update({
                    "status":       "CLOSED",
                    "exit_price":   round(exit_price, 8),
                    "exit_time":    str(ts),
                    "pnl":          round(pnl, 4),
                    "fees":         round(fees, 4),
                    "pnl_percent":  round(pnl_pct, 2),
                    "close_reason": close_reason,
                })
                trades.append(open_trade)
                open_trade = None

        # ── Record equity ──────────────────────────────────────────────────────
        unrealized = 0.0
        if open_trade:
            unrealized = (
                close * (1 - slip_pct) - open_trade["entry_price"] * (1 + slip_pct)
            ) * open_trade["quantity"]
            unrealized -= (close + open_trade["entry_price"]) * open_trade["quantity"] * fee_pct
        equity_curve.append({
            "time":   str(ts),
            "equity": round(balance + unrealized, 4),
        })

        # ── Generate signal & maybe open a trade ──────────────────────────────
        if open_trade is None:
            adjust = 0
            if sentiment_lookup is not None and config.get("SENTIMENT_FILTER", True):
                try:
                    adjust = int(sentiment_lookup(config.get("SYMBOL", "")).get(
                        "score_adjust", 0) or 0)
                except Exception:
                    adjust = 0
            try:
                signal = generate_ai_signal(window, config, sentiment_adjust=adjust)
            except Exception:
                continue

            if signal["action"] == "BUY" and signal["confidence"] >= confidence_threshold:
                qty       = (balance * trade_pct) / close
                entry_sl  = round(close * (1 - sl_pct), 8)
                entry_tp  = round(close * (1 + tp_pct), 8)

                # Use tighter of ATR-based vs %-based SL
                atr_sl = signal.get("stop_loss")
                atr_tp = signal.get("take_profit")
                if atr_sl:
                    entry_sl = min(entry_sl, atr_sl)
                if atr_tp:
                    entry_tp = max(entry_tp, atr_tp)

                open_trade = {
                    "id":          f"bt-{i}",
                    "symbol":      config.get("SYMBOL", "BACKTEST"),
                    "side":        "BUY",
                    "entry_price": close,
                    "quantity":    round(qty, 6),
                    "stop_loss":   entry_sl,
                    "take_profit": entry_tp,
                    "peak_price":  close,
                    "status":      "OPEN",
                    "confidence":  signal["confidence"],
                    "entry_time":  str(ts),
                    "exit_price":  None,
                    "exit_time":   None,
                    "pnl":         None,
                    "pnl_percent": None,
                    "close_reason": None,
                }

    # Close any remaining open trade at last price
    if open_trade:
        last_price = float(df.iloc[-1]["close"])
        entry_eff = open_trade["entry_price"] * (1 + slip_pct)
        exit_eff  = last_price * (1 - slip_pct)
        qty       = open_trade["quantity"]
        fees      = (entry_eff + exit_eff) * qty * fee_pct
        pnl     = (exit_eff - entry_eff) * qty - fees
        pnl_pct = ((exit_eff - entry_eff) / entry_eff) * 100
        balance += pnl
        open_trade.update({
            "status":       "CLOSED",
            "exit_price":   round(last_price, 8),
            "exit_time":    str(df.iloc[-1]["timestamp"]),
            "pnl":          round(pnl, 4),
            "fees":         round(fees, 4),
            "pnl_percent":  round(pnl_pct, 2),
            "close_reason": "END_OF_DATA",
        })
        trades.append(open_trade)

    return {
        "trades":       trades,
        "equity_curve": equity_curve,
        "metrics":      _compute_metrics(trades, equity_curve, initial_balance, balance),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Fast path
# ══════════════════════════════════════════════════════════════════════════════
# Every indicator generate_ai_signal() uses is causal: EWMA recursions, rolling
# windows, a cumulative VWAP, and a forward SuperTrend loop. So computing them
# once over the whole series and reading position i yields the same number as
# recomputing over df.iloc[:i+1] — which turns the O(n^2) reference loop into
# O(n). That equivalence is asserted candle-by-candle in
# tests/test_backtester_equivalence.py rather than assumed here.

class _Features:
    """Indicator series computed once for the whole frame."""

    def __init__(self, df: pd.DataFrame, config: dict):
        c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
        self.p     = c
        self.ema_f = calculate_ema(c, config.get("EMA_FAST", 9))
        self.ema_s = calculate_ema(c, config.get("EMA_SLOW", 21))
        self.rsi   = calculate_rsi(c, config.get("RSI_PERIOD", 14))
        _, _, self.hist = calculate_macd(
            c, config.get("MACD_FAST", 12), config.get("MACD_SLOW", 26),
            config.get("MACD_SIGNAL", 9),
        )
        self.bb_u, _, self.bb_l = calculate_bollinger_bands(
            c, config.get("BB_PERIOD", 20), config.get("BB_STD", 2.0)
        )
        self.atr     = calculate_atr(h, l, c)
        self.vol_sma = calculate_volume_sma(v)
        self.vol     = v
        self.vwap    = calculate_vwap(h, l, c, v)
        self.stoch_k, self.stoch_d = calculate_stochastic_rsi(c)
        _, self.st_dir = calculate_supertrend(h, l, c)
        self.wr   = calculate_williams_r(h, l, c)
        self.obv  = calculate_obv(c, v)
        self.sr_hi = h.rolling(window=20).max()
        self.sr_lo = l.rolling(window=20).min()


def _score_at(f: _Features, i: int, config: dict, sentiment_adjust: int = 0):
    """
    Scoring rules of generate_ai_signal(), vectorised. Must stay in lockstep
    with bot/indicators.py:generate_ai_signal — the equivalence test fails
    loudly if the two drift apart.
    """
    p = f.p.iat[i]
    buy = sell = 0

    if f.ema_f.iat[i] > f.ema_s.iat[i]:
        buy += 25
    else:
        sell += 25

    rsi = f.rsi.iat[i]
    if rsi < config.get("RSI_OVERSOLD", 30):
        buy += 30
    elif rsi > config.get("RSI_OVERBOUGHT", 70):
        sell += 30
    elif 40 < rsi < 60:
        buy += 10

    hist, prev_hist = f.hist.iat[i], f.hist.iat[i - 1]
    if hist > 0 and prev_hist <= 0:
        buy += 25
    elif hist < 0 and prev_hist >= 0:
        sell += 25
    elif hist > 0:
        buy += 10
    else:
        sell += 10

    if p <= f.bb_l.iat[i]:
        buy += 20
    elif p >= f.bb_u.iat[i]:
        sell += 20

    if p > f.vwap.iat[i]:
        buy += 15
    else:
        sell += 15

    k = f.stoch_k.iat[i]
    d = f.stoch_d.iat[i]
    k = 50.0 if pd.isna(k) else k
    d = 50.0 if pd.isna(d) else d
    if k < 20 and k > d:
        buy += 20
    elif k > 80 and k < d:
        sell += 20

    st = f.st_dir.iat[i]
    if not pd.isna(st):
        if st == 1:
            buy += 20
        elif st == -1:
            sell += 20

    wr = f.wr.iat[i]
    if not pd.isna(wr):
        if wr < -80:
            buy += 15
        elif wr > -20:
            sell += 15

    support, resistance = f.sr_lo.iat[i], f.sr_hi.iat[i]
    if not pd.isna(support) and not pd.isna(resistance):
        band = (resistance - support) * 0.05
        if p <= support + band:
            buy += 15
        elif p >= resistance - band:
            sell += 15

    if i >= 4:
        # generate_ai_signal uses obv.iloc[-1] - obv.iloc[-5] on a window of
        # length i+1, so iloc[-5] is position i-4. Off-by-one to get wrong.
        if f.obv.iat[i] - f.obv.iat[i - 4] > 0:
            buy += 10
        else:
            sell += 10

    avol = f.vol_sma.iat[i]
    if not pd.isna(avol) and f.vol.iat[i] > avol * 1.5:
        if buy > sell:
            buy += 15
        else:
            sell += 15

    if sentiment_adjust:
        if sentiment_adjust > 0:
            buy += sentiment_adjust
        else:
            sell += abs(sentiment_adjust)

    total = max(buy + sell, 1)
    if buy > sell and buy >= 50:
        action, confidence = "BUY", min(int((buy / total) * 100), 99)
    elif sell > buy and sell >= 50:
        action, confidence = "SELL", min(int((sell / total) * 100), 99)
    else:
        action, confidence = "HOLD", 50

    sl = tp = None
    if action == "BUY":
        atr = f.atr.iat[i]
        sl = min(round(p - atr * 1.5, 4),
                 round(p * (1 - config.get("STOP_LOSS_PERCENT", 2.0) / 100), 4))
        tp = max(round(p + atr * 3.0, 4),
                 round(p * (1 + config.get("TAKE_PROFIT_PERCENT", 4.0) / 100), 4))
    return action, confidence, sl, tp


def run_backtest(
    df: pd.DataFrame,
    config: dict,
    initial_balance: float = 1000.0,
    confidence_threshold: float = 60.0,
    sentiment_lookup=None,
    start_at: Optional[int] = None,
    stop_at: Optional[int] = None,
) -> dict:
    """
    Simulate the bot strategy on historical OHLCV data.

    Parameters
    ----------
    df                   : OHLCV DataFrame (from BinanceClient.get_klines)
    config               : Same config dict the live engine uses
    initial_balance      : Starting USDT balance for simulation
    confidence_threshold : Min confidence % to enter a trade
    sentiment_lookup     : Optional callable(symbol) -> sentiment dict, used when
                           SENTIMENT_FILTER is on. Historical sentiment is not
                           available, so without this the backtest runs on pure
                           technicals — which is *not* what the live bot trades.
    start_at / stop_at   : Bar range, for splitting a series into walk-forward
                           folds. Indicators are still computed over the whole
                           frame so no fold is starved of warmup history.

    Costs come from config: BACKTEST_FEE_PERCENT (round trip) and
    BACKTEST_SLIPPAGE_PERCENT (per leg). Exits mirror the live engine, including
    the SELL-signal exit, because a backtest that only models stops and targets
    reports a strategy the bot does not actually trade.

    Returns
    -------
    dict with:
        trades            – list of simulated trade dicts
        equity_curve      – list of {time, equity} points for charting
        metrics           – win_rate, total_pnl, sharpe, max_drawdown, etc.
    """
    if df.empty or len(df) < 50:
        return {"error": "Not enough candle data (need ≥ 50 candles)"}

    f = _Features(df, config)
    n = len(df)
    high = df["high"].to_numpy()
    low  = df["low"].to_numpy()
    close = df["close"].to_numpy()
    ts = df["timestamp"]

    sl_pct      = config.get("STOP_LOSS_PERCENT",   2.0) / 100
    tp_pct      = config.get("TAKE_PROFIT_PERCENT", 4.0) / 100
    trade_pct   = config.get("TRADE_QUANTITY_PERCENT", 10) / 100
    trailing    = config.get("TRAILING_STOP", False)
    trail_pct   = config.get("TRAILING_STOP_PERCENT", 3.0) / 100
    fee_pct     = config.get("BACKTEST_FEE_PERCENT", 0.0) / 100
    slip_pct    = config.get("BACKTEST_SLIPPAGE_PERCENT", 0.0) / 100
    exit_on_signal = config.get("EXIT_ON_SIGNAL", True)
    use_sentiment = sentiment_lookup is not None and config.get("SENTIMENT_FILTER", True)

    warmup = max(
        config.get("EMA_SLOW", 21),
        config.get("MACD_SLOW", 26) + config.get("MACD_SIGNAL", 9),
        config.get("BB_PERIOD", 20),
        config.get("RSI_PERIOD", 14),
    ) + 5

    balance = initial_balance
    trades: list = []
    equity_curve: list = []
    open_trade: Optional[dict] = None

    def sentiment_now() -> int:
        if not use_sentiment:
            return 0
        try:
            return int(sentiment_lookup(config.get("SYMBOL", "")).get(
                "score_adjust", 0) or 0)
        except Exception:
            return 0

    def close_out(exit_price: float, reason: str, stamp) -> None:
        nonlocal balance
        entry_eff = open_trade["entry_price"] * (1 + slip_pct)
        exit_eff  = exit_price * (1 - slip_pct)
        qty       = open_trade["quantity"]
        fees      = (entry_eff + exit_eff) * qty * fee_pct
        pnl       = (exit_eff - entry_eff) * qty - fees
        balance  += pnl
        open_trade.update({
            "status":       "CLOSED",
            "exit_price":   round(exit_price, 8),
            "exit_time":    str(stamp),
            "pnl":          round(pnl, 4),
            "fees":         round(fees, 4),
            "pnl_percent":  round((exit_eff - entry_eff) / entry_eff * 100, 2),
            "close_reason": reason,
        })
        trades.append(open_trade)

    lo = warmup if start_at is None else max(warmup, start_at)
    hi = n if stop_at is None else min(n, stop_at)

    for i in range(lo, hi):
        stamp = ts.iloc[i]
        c = float(close[i])

        if open_trade:
            sl = open_trade["stop_loss"]
            tp = open_trade["take_profit"]
            peak = open_trade["peak_price"]

            if trailing and high[i] > peak:
                peak = float(high[i])
                open_trade["peak_price"] = peak
                new_sl = round(peak * (1 - trail_pct), 8)
                if new_sl > sl:
                    open_trade["stop_loss"] = new_sl
                    sl = new_sl

            reason = exit_price = None
            if low[i] <= sl:
                reason = "TRAILING_STOP" if trailing and peak > open_trade["entry_price"] else "STOP_LOSS"
                exit_price = sl
            elif high[i] >= tp:
                reason, exit_price = "TAKE_PROFIT", tp

            if reason is None and exit_on_signal:
                a, conf, _, _ = _score_at(f, i, config, sentiment_now())
                if a == "SELL" and conf >= 60:
                    reason, exit_price = "SIGNAL", c

            if reason:
                close_out(exit_price, reason, stamp)
                open_trade = None

        unrealized = 0.0
        if open_trade:
            unrealized = (
                c * (1 - slip_pct) - open_trade["entry_price"] * (1 + slip_pct)
            ) * open_trade["quantity"]
            unrealized -= (c + open_trade["entry_price"]) * open_trade["quantity"] * fee_pct
        equity_curve.append({"time": str(stamp), "equity": round(balance + unrealized, 4)})

        if open_trade is None:
            action, conf, atr_sl, atr_tp = _score_at(f, i, config, sentiment_now())
            if action == "BUY" and conf >= confidence_threshold:
                qty      = round((balance * trade_pct) / c, 6)
                entry_sl = round(c * (1 - sl_pct), 8)
                entry_tp = round(c * (1 + tp_pct), 8)
                if atr_sl:
                    entry_sl = min(entry_sl, atr_sl)
                if atr_tp:
                    entry_tp = max(entry_tp, atr_tp)
                open_trade = {
                    "id":          f"bt-{i}",
                    "symbol":      config.get("SYMBOL", "BACKTEST"),
                    "side":        "BUY",
                    "entry_price": c,
                    "quantity":    qty,
                    "stop_loss":   entry_sl,
                    "take_profit": entry_tp,
                    "peak_price":  c,
                    "status":      "OPEN",
                    "confidence":  conf,
                    "entry_time":  str(stamp),
                    "exit_price":  None,
                    "exit_time":   None,
                    "pnl":         None,
                    "fees":        None,
                    "pnl_percent": None,
                    "close_reason": None,
                }

    if open_trade:
        close_out(float(close[hi - 1]), "END_OF_DATA", ts.iloc[hi - 1])

    return {
        "trades":       trades,
        "equity_curve": equity_curve,
        "metrics":      _compute_metrics(trades, equity_curve, initial_balance, balance),
    }


def _compute_metrics(trades, equity_curve, initial_balance, final_balance) -> dict:
    closed    = [t for t in trades if t.get("pnl") is not None]
    total     = len(closed)
    if total == 0:
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "win_rate": 0, "total_pnl": 0, "total_pnl_percent": 0,
            "max_drawdown": 0, "max_drawdown_percent": 0,
            "sharpe_ratio": 0, "profit_factor": 0,
            "avg_win": 0, "avg_loss": 0, "best_trade": 0, "worst_trade": 0,
            "initial_balance": initial_balance, "final_balance": round(final_balance, 4),
        }

    wins   = [t for t in closed if (t["pnl"] or 0) > 0]
    losses = [t for t in closed if (t["pnl"] or 0) <= 0]

    pnl_series  = [t["pnl"] for t in closed]
    total_pnl   = sum(pnl_series)
    win_rate    = len(wins) / total * 100

    gross_profit = sum(t["pnl"] for t in wins) if wins else 0
    gross_loss   = abs(sum(t["pnl"] for t in losses)) if losses else 0
    # float("inf") is not valid JSON, so the client silently got a broken payload.
    # Report a capped sentinel when there are no losing trades instead.
    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    elif gross_profit > 0:
        profit_factor = 999.0   # no losing trades — capped, not infinite
    else:
        profit_factor = 0.0

    avg_win  = gross_profit / len(wins)   if wins   else 0
    avg_loss = gross_loss   / len(losses) if losses else 0

    # Max drawdown from equity curve
    equities = [e["equity"] for e in equity_curve] if equity_curve else [initial_balance]
    eq_arr   = np.array(equities)
    peak_arr = np.maximum.accumulate(eq_arr)
    dd_arr   = (peak_arr - eq_arr)
    max_dd   = float(dd_arr.max()) if len(dd_arr) else 0
    max_dd_pct = (max_dd / peak_arr[dd_arr.argmax()] * 100) if max_dd > 0 else 0

    # Sharpe ratio (annualized, daily returns proxy)
    if len(pnl_series) > 1:
        pnl_arr = np.array(pnl_series)
        mean_r  = pnl_arr.mean()
        std_r   = pnl_arr.std()
        sharpe  = round((mean_r / std_r) * np.sqrt(252), 2) if std_r > 0 else 0
    else:
        sharpe = 0

    return {
        "total_trades":        total,
        "winning_trades":      len(wins),
        "losing_trades":       len(losses),
        "win_rate":            round(win_rate, 2),
        "total_pnl":           round(total_pnl, 4),
        "total_pnl_percent":   round((final_balance - initial_balance) / initial_balance * 100, 2),
        "max_drawdown":        round(max_dd, 4),
        "max_drawdown_percent":round(max_dd_pct, 2),
        "sharpe_ratio":        sharpe,
        "profit_factor":       profit_factor,
        "avg_win":             round(avg_win, 4),
        "avg_loss":            round(avg_loss, 4),
        "best_trade":          round(max(pnl_series), 4),
        "worst_trade":         round(min(pnl_series), 4),
        "initial_balance":     initial_balance,
        "final_balance":       round(final_balance, 4),
    }
