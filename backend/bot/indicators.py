"""
Technical Indicators - AI Signal Generation
EMA, RSI, MACD, Bollinger Bands
"""

import numpy as np
import pandas as pd
from typing import Tuple


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return prices.ewm(span=period, adjust=False).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD - Moving Average Convergence Divergence"""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands"""
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume Simple Moving Average"""
    return volume.rolling(window=period).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range - Volatility measure"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def generate_ai_signal(df: pd.DataFrame, config: dict) -> dict:
    """
    AI Signal Generator
    Combines multiple indicators to generate BUY/SELL/HOLD signal
    Returns signal with confidence score
    """
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # Calculate all indicators
    ema_fast = calculate_ema(close, config.get('EMA_FAST', 9))
    ema_slow = calculate_ema(close, config.get('EMA_SLOW', 21))
    rsi = calculate_rsi(close, config.get('RSI_PERIOD', 14))
    macd_line, signal_line, histogram = calculate_macd(
        close,
        config.get('MACD_FAST', 12),
        config.get('MACD_SLOW', 26),
        config.get('MACD_SIGNAL', 9)
    )
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(
        close,
        config.get('BB_PERIOD', 20),
        config.get('BB_STD', 2.0)
    )
    atr = calculate_atr(high, low, close)
    vol_sma = calculate_volume_sma(volume)

    # Get latest values
    current_price = close.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_ema_fast = ema_fast.iloc[-1]
    current_ema_slow = ema_slow.iloc[-1]
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_hist = histogram.iloc[-1]
    prev_hist = histogram.iloc[-2]
    current_bb_upper = bb_upper.iloc[-1]
    current_bb_lower = bb_lower.iloc[-1]
    current_vol = volume.iloc[-1]
    avg_vol = vol_sma.iloc[-1]
    current_atr = atr.iloc[-1]

    # Signal scoring system (AI Logic)
    buy_score = 0
    sell_score = 0
    signals = []

    # --- EMA Crossover ---
    if current_ema_fast > current_ema_slow:
        buy_score += 25
        signals.append("EMA Bullish")
    else:
        sell_score += 25
        signals.append("EMA Bearish")

    # --- RSI ---
    if current_rsi < config.get('RSI_OVERSOLD', 30):
        buy_score += 30
        signals.append(f"RSI Oversold ({current_rsi:.1f})")
    elif current_rsi > config.get('RSI_OVERBOUGHT', 70):
        sell_score += 30
        signals.append(f"RSI Overbought ({current_rsi:.1f})")
    elif 40 < current_rsi < 60:
        buy_score += 10
        signals.append(f"RSI Neutral ({current_rsi:.1f})")

    # --- MACD ---
    if current_hist > 0 and prev_hist <= 0:
        buy_score += 25
        signals.append("MACD Bullish Crossover")
    elif current_hist < 0 and prev_hist >= 0:
        sell_score += 25
        signals.append("MACD Bearish Crossover")
    elif current_hist > 0:
        buy_score += 10
        signals.append("MACD Positive")
    else:
        sell_score += 10
        signals.append("MACD Negative")

    # --- Bollinger Bands ---
    if current_price <= current_bb_lower:
        buy_score += 20
        signals.append("Price at BB Lower (Oversold)")
    elif current_price >= current_bb_upper:
        sell_score += 20
        signals.append("Price at BB Upper (Overbought)")

    # --- Volume Confirmation ---
    if current_vol > avg_vol * 1.5:
        if buy_score > sell_score:
            buy_score += 15
            signals.append("High Volume - Bullish Confirmed")
        else:
            sell_score += 15
            signals.append("High Volume - Bearish Confirmed")

    # --- Final Decision ---
    total_score = buy_score + sell_score
    if total_score == 0:
        total_score = 1

    if buy_score > sell_score and buy_score >= 50:
        action = "BUY"
        confidence = min(int((buy_score / total_score) * 100), 99)
    elif sell_score > buy_score and sell_score >= 50:
        action = "SELL"
        confidence = min(int((sell_score / total_score) * 100), 99)
    else:
        action = "HOLD"
        confidence = 50

    # Stop Loss & Take Profit calculation using ATR
    atr_multiplier = 1.5
    stop_loss_price = None
    take_profit_price = None

    if action == "BUY":
        stop_loss_price = round(current_price - (current_atr * atr_multiplier), 4)
        take_profit_price = round(current_price + (current_atr * atr_multiplier * 2), 4)
    elif action == "SELL":
        stop_loss_price = round(current_price + (current_atr * atr_multiplier), 4)
        take_profit_price = round(current_price - (current_atr * atr_multiplier * 2), 4)

    return {
        "action": action,
        "confidence": confidence,
        "price": float(current_price),
        "rsi": round(float(current_rsi), 2),
        "ema_fast": round(float(current_ema_fast), 4),
        "ema_slow": round(float(current_ema_slow), 4),
        "macd": round(float(current_macd), 4),
        "macd_signal": round(float(current_signal), 4),
        "bb_upper": round(float(current_bb_upper), 4),
        "bb_lower": round(float(current_bb_lower), 4),
        "stop_loss": stop_loss_price,
        "take_profit": take_profit_price,
        "signals": signals,
        "buy_score": buy_score,
        "sell_score": sell_score,
    }
