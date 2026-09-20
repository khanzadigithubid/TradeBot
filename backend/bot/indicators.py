"""
Technical Indicators - Advanced Signal Generation
EMA, RSI, MACD, Bollinger Bands, VWAP, Stochastic RSI,
Support/Resistance, Multi-Timeframe Analysis
"""

import numpy as np
import pandas as pd
from typing import Tuple


# ── Basic Indicators ───────────────────────────────────────────────────────────

def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta    = prices.diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast    = calculate_ema(prices, fast)
    ema_slow    = calculate_ema(prices, slow)
    macd_line   = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices: pd.Series, period=20, std_dev=2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = prices.rolling(window=period).mean()
    std    = prices.rolling(window=period).std()
    return middle + (std * std_dev), middle, middle - (std * std_dev)


def calculate_volume_sma(volume: pd.Series, period=20) -> pd.Series:
    return volume.rolling(window=period).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low  - close.shift())
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# ── Advanced Indicators ────────────────────────────────────────────────────────

def calculate_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Volume Weighted Average Price"""
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    return vwap


def calculate_stochastic_rsi(prices: pd.Series, rsi_period=14, stoch_period=14,
                              smooth_k=3, smooth_d=3) -> Tuple[pd.Series, pd.Series]:
    """Stochastic RSI — more sensitive than regular RSI"""
    rsi        = calculate_rsi(prices, rsi_period)
    rsi_min    = rsi.rolling(window=stoch_period).min()
    rsi_max    = rsi.rolling(window=stoch_period).max()
    stoch_rsi  = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
    k          = stoch_rsi.rolling(window=smooth_k).mean()
    d          = k.rolling(window=smooth_d).mean()
    return k, d


def calculate_support_resistance(high: pd.Series, low: pd.Series,
                                  close: pd.Series, lookback=20) -> Tuple[float, float]:
    """Key support and resistance levels using recent swing highs/lows"""
    recent_high = high.rolling(window=lookback).max().iloc[-1]
    recent_low  = low.rolling(window=lookback).min().iloc[-1]
    return float(recent_support := recent_low), float(recent_high)


def calculate_supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                          period=10, multiplier=3.0) -> Tuple[pd.Series, pd.Series]:
    """SuperTrend indicator — trend direction filter"""
    atr    = calculate_atr(high, low, close, period)
    hl2    = (high + low) / 2
    upper  = hl2 + multiplier * atr
    lower  = hl2 - multiplier * atr

    supertrend = pd.Series(index=close.index, dtype=float)
    direction  = pd.Series(index=close.index, dtype=float)

    for i in range(1, len(close)):
        if close.iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1   # Bullish
        elif close.iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1  # Bearish
        else:
            direction.iloc[i] = direction.iloc[i - 1] if i > 0 else 1

        supertrend.iloc[i] = lower.iloc[i] if direction.iloc[i] == 1 else upper.iloc[i]

    return supertrend, direction


def calculate_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    """Williams %R — overbought/oversold"""
    highest_high = high.rolling(window=period).max()
    lowest_low   = low.rolling(window=period).min()
    wr = ((highest_high - close) / (highest_high - lowest_low + 1e-10)) * -100
    return wr


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume — volume momentum"""
    obv = pd.Series(index=close.index, dtype=float)
    obv.iloc[0] = 0
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i - 1]
    return obv


# ── Multi-Timeframe Signal Scoring ─────────────────────────────────────────────

def generate_mtf_score(df_fast: pd.DataFrame, df_medium: pd.DataFrame,
                        df_slow: pd.DataFrame, config: dict) -> dict:
    """
    Multi-Timeframe analysis:
    df_fast   = 15m candles
    df_medium = 1h  candles
    df_slow   = 4h  candles
    Returns combined score and trend direction
    """
    scores = {}
    for name, df in [("15m", df_fast), ("1h", df_medium), ("4h", df_slow)]:
        if df is None or df.empty or len(df) < 30:
            scores[name] = {"bull": 0, "bear": 0, "trend": "NEUTRAL"}
            continue
        close = df["close"]
        ema_f = calculate_ema(close, config.get("EMA_FAST", 9)).iloc[-1]
        ema_s = calculate_ema(close, config.get("EMA_SLOW", 21)).iloc[-1]
        rsi   = calculate_rsi(close, config.get("RSI_PERIOD", 14)).iloc[-1]
        _, _, hist = calculate_macd(close)
        macd_hist = hist.iloc[-1]

        bull = 0
        bear = 0
        if ema_f > ema_s:           bull += 1
        else:                        bear += 1
        if rsi < 40:                 bull += 1
        elif rsi > 60:               bear += 1
        if macd_hist > 0:            bull += 1
        else:                        bear += 1

        trend = "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL"
        scores[name] = {"bull": bull, "bear": bear, "trend": trend}

    # Combined MTF score
    total_bull = sum(s["bull"] for s in scores.values())
    total_bear = sum(s["bear"] for s in scores.values())

    return {
        "timeframes":  scores,
        "total_bull":  total_bull,
        "total_bear":  total_bear,
        "mtf_trend":   "BULLISH" if total_bull > total_bear else "BEARISH" if total_bear > total_bull else "NEUTRAL",
        "alignment":   total_bull == 9 or total_bear == 9,  # All 3 TFs agree
    }


# ── Main Signal Generator ──────────────────────────────────────────────────────

def generate_ai_signal(df: pd.DataFrame, config: dict,
                        df_1h: pd.DataFrame = None,
                        df_4h: pd.DataFrame = None) -> dict:
    """
    Advanced AI Signal Generator
    Combines: EMA, RSI, MACD, BB, VWAP, Stoch RSI, S/R, SuperTrend,
              Williams %R, OBV, Volume + Multi-Timeframe analysis
    """
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]

    # ── Calculate all indicators ───────────────────────────────────────────────
    ema_fast   = calculate_ema(close, config.get("EMA_FAST", 9))
    ema_slow   = calculate_ema(close, config.get("EMA_SLOW", 21))
    rsi        = calculate_rsi(close, config.get("RSI_PERIOD", 14))
    macd_line, signal_line, histogram = calculate_macd(
        close, config.get("MACD_FAST", 12),
        config.get("MACD_SLOW", 26), config.get("MACD_SIGNAL", 9)
    )
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(
        close, config.get("BB_PERIOD", 20), config.get("BB_STD", 2.0)
    )
    atr      = calculate_atr(high, low, close)
    vol_sma  = calculate_volume_sma(volume)
    vwap     = calculate_vwap(high, low, close, volume)
    stoch_k, stoch_d = calculate_stochastic_rsi(close)
    support, resistance = calculate_support_resistance(high, low, close)
    _, supertrend_dir = calculate_supertrend(high, low, close)
    wr       = calculate_williams_r(high, low, close)
    obv      = calculate_obv(close, volume)

    # ── Get latest values ──────────────────────────────────────────────────────
    p             = close.iloc[-1]
    cur_rsi       = rsi.iloc[-1]
    cur_ema_fast  = ema_fast.iloc[-1]
    cur_ema_slow  = ema_slow.iloc[-1]
    cur_macd      = macd_line.iloc[-1]
    cur_signal    = signal_line.iloc[-1]
    cur_hist      = histogram.iloc[-1]
    prev_hist     = histogram.iloc[-2]
    cur_bb_upper  = bb_upper.iloc[-1]
    cur_bb_lower  = bb_lower.iloc[-1]
    cur_vol       = volume.iloc[-1]
    avg_vol       = vol_sma.iloc[-1]
    cur_vwap      = vwap.iloc[-1]
    cur_stoch_k   = stoch_k.iloc[-1] if not pd.isna(stoch_k.iloc[-1]) else 50
    cur_stoch_d   = stoch_d.iloc[-1] if not pd.isna(stoch_d.iloc[-1]) else 50
    cur_st_dir    = supertrend_dir.iloc[-1] if not pd.isna(supertrend_dir.iloc[-1]) else 0
    cur_wr        = wr.iloc[-1] if not pd.isna(wr.iloc[-1]) else -50
    cur_atr       = atr.iloc[-1]
    obv_slope     = obv.iloc[-1] - obv.iloc[-5] if len(obv) > 5 else 0

    # ── Scoring system ─────────────────────────────────────────────────────────
    buy_score  = 0
    sell_score = 0
    signals    = []

    # 1. EMA Crossover (25 pts)
    if cur_ema_fast > cur_ema_slow:
        buy_score += 25; signals.append("EMA Bullish")
    else:
        sell_score += 25; signals.append("EMA Bearish")

    # 2. RSI (30 pts)
    rsi_ob = config.get("RSI_OVERBOUGHT", 70)
    rsi_os = config.get("RSI_OVERSOLD", 30)
    if cur_rsi < rsi_os:
        buy_score += 30; signals.append(f"RSI Oversold ({cur_rsi:.1f})")
    elif cur_rsi > rsi_ob:
        sell_score += 30; signals.append(f"RSI Overbought ({cur_rsi:.1f})")
    elif 40 < cur_rsi < 60:
        buy_score += 10; signals.append(f"RSI Neutral ({cur_rsi:.1f})")

    # 3. MACD (25 pts)
    if cur_hist > 0 and prev_hist <= 0:
        buy_score += 25; signals.append("MACD Bullish Crossover")
    elif cur_hist < 0 and prev_hist >= 0:
        sell_score += 25; signals.append("MACD Bearish Crossover")
    elif cur_hist > 0:
        buy_score += 10; signals.append("MACD Positive")
    else:
        sell_score += 10; signals.append("MACD Negative")

    # 4. Bollinger Bands (20 pts)
    if p <= cur_bb_lower:
        buy_score += 20; signals.append("Price at BB Lower (Oversold)")
    elif p >= cur_bb_upper:
        sell_score += 20; signals.append("Price at BB Upper (Overbought)")

    # 5. VWAP (15 pts) — NEW
    if p > cur_vwap:
        buy_score += 15; signals.append(f"Price above VWAP (${cur_vwap:.2f})")
    else:
        sell_score += 15; signals.append(f"Price below VWAP (${cur_vwap:.2f})")

    # 6. Stochastic RSI (20 pts) — NEW
    if cur_stoch_k < 20 and cur_stoch_k > cur_stoch_d:
        buy_score += 20; signals.append(f"Stoch RSI Oversold Crossup ({cur_stoch_k:.1f})")
    elif cur_stoch_k > 80 and cur_stoch_k < cur_stoch_d:
        sell_score += 20; signals.append(f"Stoch RSI Overbought Crossdown ({cur_stoch_k:.1f})")

    # 7. SuperTrend (20 pts) — NEW
    if cur_st_dir == 1:
        buy_score += 20; signals.append("SuperTrend Bullish")
    elif cur_st_dir == -1:
        sell_score += 20; signals.append("SuperTrend Bearish")

    # 8. Williams %R (15 pts) — NEW
    if cur_wr < -80:
        buy_score += 15; signals.append(f"Williams %R Oversold ({cur_wr:.1f})")
    elif cur_wr > -20:
        sell_score += 15; signals.append(f"Williams %R Overbought ({cur_wr:.1f})")

    # 9. Support/Resistance (15 pts) — NEW
    sr_range = (resistance - support) * 0.05
    if p <= support + sr_range:
        buy_score += 15; signals.append(f"Near Support (${support:.2f})")
    elif p >= resistance - sr_range:
        sell_score += 15; signals.append(f"Near Resistance (${resistance:.2f})")

    # 10. OBV Momentum (10 pts) — NEW
    if obv_slope > 0:
        buy_score += 10; signals.append("OBV Bullish Momentum")
    else:
        sell_score += 10; signals.append("OBV Bearish Momentum")

    # 11. Volume Confirmation (15 pts)
    if cur_vol > avg_vol * 1.5:
        if buy_score > sell_score:
            buy_score += 15; signals.append("High Volume — Bullish Confirmed")
        else:
            sell_score += 15; signals.append("High Volume — Bearish Confirmed")

    # 12. Multi-Timeframe Analysis (30 pts) — NEW
    mtf = None
    if df_1h is not None or df_4h is not None:
        mtf = generate_mtf_score(df, df_1h, df_4h, config)
        if mtf["mtf_trend"] == "BULLISH":
            buy_score += 30
            signals.append(f"MTF Bullish ({mtf['total_bull']}/9 timeframes)")
        elif mtf["mtf_trend"] == "BEARISH":
            sell_score += 30
            signals.append(f"MTF Bearish ({mtf['total_bear']}/9 timeframes)")

    # ── Final Decision ─────────────────────────────────────────────────────────
    total_score = max(buy_score + sell_score, 1)

    if buy_score > sell_score and buy_score >= 50:
        action     = "BUY"
        confidence = min(int((buy_score / total_score) * 100), 99)
    elif sell_score > buy_score and sell_score >= 50:
        action     = "SELL"
        confidence = min(int((sell_score / total_score) * 100), 99)
    else:
        action     = "HOLD"
        confidence = 50

    # ── SL/TP using ATR ────────────────────────────────────────────────────────
    sl_pct = config.get("STOP_LOSS_PERCENT", 2.0) / 100
    tp_pct = config.get("TAKE_PROFIT_PERCENT", 4.0) / 100
    atr_mult = 1.5

    stop_loss_price   = None
    take_profit_price = None

    if action == "BUY":
        atr_sl = round(p - cur_atr * atr_mult, 4)
        pct_sl = round(p * (1 - sl_pct), 4)
        stop_loss_price   = min(atr_sl, pct_sl)
        atr_tp = round(p + cur_atr * atr_mult * 2, 4)
        pct_tp = round(p * (1 + tp_pct), 4)
        take_profit_price = max(atr_tp, pct_tp)
    elif action == "SELL":
        stop_loss_price   = round(p + cur_atr * atr_mult, 4)
        take_profit_price = round(p - cur_atr * atr_mult * 2, 4)

    return {
        "action":       action,
        "confidence":   confidence,
        "price":        float(p),
        "rsi":          round(float(cur_rsi), 2),
        "ema_fast":     round(float(cur_ema_fast), 4),
        "ema_slow":     round(float(cur_ema_slow), 4),
        "macd":         round(float(cur_macd), 4),
        "macd_signal":  round(float(cur_signal), 4),
        "bb_upper":     round(float(cur_bb_upper), 4),
        "bb_lower":     round(float(cur_bb_lower), 4),
        "vwap":         round(float(cur_vwap), 4),
        "stoch_k":      round(float(cur_stoch_k), 2),
        "stoch_d":      round(float(cur_stoch_d), 2),
        "williams_r":   round(float(cur_wr), 2),
        "support":      round(float(support), 4),
        "resistance":   round(float(resistance), 4),
        "supertrend":   "BULLISH" if cur_st_dir == 1 else "BEARISH" if cur_st_dir == -1 else "NEUTRAL",
        "stop_loss":    stop_loss_price,
        "take_profit":  take_profit_price,
        "signals":      signals,
        "buy_score":    buy_score,
        "sell_score":   sell_score,
        "mtf":          mtf,
    }
