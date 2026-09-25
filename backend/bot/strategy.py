"""
Unified Signal Builder
Single entry point for signal generation, shared by the live engine, the REST
API, manual trades and the backtester.

Before this module existed each caller wired `generate_ai_signal` up slightly
differently, so the signal shown on the dashboard was frequently NOT the signal
that triggered the trade (the live path passed MTF data, the API path did not).
Everything now goes through `compute_signal`.
"""

import logging
from typing import Optional

from bot.indicators import generate_ai_signal
from bot.market_data import get_klines

logger = logging.getLogger(__name__)


def _mtf_enabled(config: dict) -> bool:
    return bool(config.get("MTF_ENABLED", True))


def _sentiment_enabled(config: dict) -> bool:
    return bool(config.get("SENTIMENT_FILTER", True))


def get_sentiment(symbol: str, config: dict) -> dict:
    """Fetch combined sentiment, or {} when disabled/unavailable."""
    if not _sentiment_enabled(config):
        return {}
    try:
        from bot.sentiment import get_combined_sentiment
        return get_combined_sentiment(symbol)
    except Exception as e:
        logger.debug(f"[{symbol}] sentiment unavailable: {e}")
        return {}


def compute_signal(
    symbol: str,
    config: dict,
    interval: str = "15m",
    limit: int = 200,
    df: Optional[object] = None,
    use_mtf: Optional[bool] = None,
    use_sentiment: Optional[bool] = None,
) -> Optional[dict]:
    """
    Build the canonical signal dict for `symbol`.

    Returns None when there is no usable candle data, so callers can decide
    how to surface the failure. Includes:
      action, confidence, scores, SL/TP, indicators, mtf, sentiment
    """
    symbol = symbol.upper()

    if df is None:
        try:
            df = get_klines(symbol, interval, limit)
        except Exception as e:
            logger.warning(f"[{symbol}] klines failed: {e}")
            return None

    if df is None or getattr(df, "empty", True):
        return None

    # Multi-timeframe context
    df_1h = df_4h = None
    if _mtf_enabled(config) if use_mtf is None else use_mtf:
        try:
            df_1h = get_klines(symbol, "1h", 100)
            df_4h = get_klines(symbol, "4h", 100)
        except Exception as e:
            logger.debug(f"[{symbol}] MTF data unavailable: {e}")

    # Sentiment — applied to the scores before the decision is made
    want_sentiment = _sentiment_enabled(config) if use_sentiment is None else use_sentiment
    sentiment = get_sentiment(symbol, config) if want_sentiment else {}
    adjust = int(sentiment.get("score_adjust", 0) or 0) if sentiment else 0

    signal = generate_ai_signal(
        df, config, df_1h, df_4h, sentiment_adjust=adjust
    )
    signal["symbol"]          = symbol
    signal["interval"]        = interval
    signal["sentiment"]       = sentiment
    signal["mtf_enabled"]     = df_1h is not None or df_4h is not None
    signal["sentiment_active"] = bool(sentiment)

    return signal


def sentiment_blocks_buy(sentiment: dict, config: dict) -> bool:
    """
    Hard gate: refuse new BUYs on Extreme Greed when the filter is on.
    This is the only sentiment rule that gates execution outright.
    """
    if not sentiment or not _sentiment_enabled(config):
        return False
    return sentiment.get("fear_greed", {}).get("signal") == "EXTREME_GREED"
