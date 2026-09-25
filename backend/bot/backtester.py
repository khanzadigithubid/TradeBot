"""
Backtesting Engine
Runs the signal strategy over historical OHLCV data and simulates trades.
Returns detailed performance metrics without touching real/testnet funds.
"""

import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime
from bot.indicators import generate_ai_signal
import logging

logger = logging.getLogger(__name__)


def run_backtest(
    df: pd.DataFrame,
    config: dict,
    initial_balance: float = 1000.0,
    confidence_threshold: float = 60.0,
    sentiment_lookup=None,
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

    Returns
    -------
    dict with:
        trades            – list of simulated trade dicts
        equity_curve      – list of {time, equity} points for charting
        metrics           – win_rate, total_pnl, sharpe, max_drawdown, etc.
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
    trailing  = config.get("TRAILING_STOP", True)
    trail_pct = config.get("TRAILING_STOP_PERCENT", 1.0) / 100

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

            if close_reason:
                pnl     = (exit_price - open_trade["entry_price"]) * open_trade["quantity"]
                pnl_pct = ((exit_price - open_trade["entry_price"]) / open_trade["entry_price"]) * 100
                balance += pnl
                open_trade.update({
                    "status":       "CLOSED",
                    "exit_price":   round(exit_price, 8),
                    "exit_time":    str(ts),
                    "pnl":          round(pnl, 4),
                    "pnl_percent":  round(pnl_pct, 2),
                    "close_reason": close_reason,
                })
                trades.append(open_trade)
                open_trade = None

        # ── Record equity ──────────────────────────────────────────────────────
        unrealized = 0.0
        if open_trade:
            unrealized = (close - open_trade["entry_price"]) * open_trade["quantity"]
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
        pnl     = (last_price - open_trade["entry_price"]) * open_trade["quantity"]
        pnl_pct = ((last_price - open_trade["entry_price"]) / open_trade["entry_price"]) * 100
        balance += pnl
        open_trade.update({
            "status":       "CLOSED",
            "exit_price":   round(last_price, 8),
            "exit_time":    str(df.iloc[-1]["timestamp"]),
            "pnl":          round(pnl, 4),
            "pnl_percent":  round(pnl_pct, 2),
            "close_reason": "END_OF_DATA",
        })
        trades.append(open_trade)

    metrics = _compute_metrics(trades, equity_curve, initial_balance, balance)

    return {
        "trades":       trades,
        "equity_curve": equity_curve,
        "metrics":      metrics,
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
