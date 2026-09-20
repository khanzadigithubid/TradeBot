"""
Crypto Sentiment Analysis
- Fear & Greed Index (alternative.me)
- CryptoPanic news headlines
"""

import requests
import logging

logger = logging.getLogger(__name__)


def get_fear_greed_index() -> dict:
    """
    Get Crypto Fear & Greed Index
    Returns value 0-100 and classification
    """
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()["data"][0]
            value       = int(data["value"])
            category    = data["value_classification"]
            return {
                "value":    value,
                "category": category,
                "signal":   _fng_signal(value),
            }
    except Exception as e:
        logger.warning(f"Fear & Greed API failed: {e}")
    return {"value": 50, "category": "Neutral", "signal": "NEUTRAL"}


def _fng_signal(value: int) -> str:
    if value <= 25:   return "EXTREME_FEAR"    # Good BUY opportunity
    if value <= 45:   return "FEAR"            # Lean BUY
    if value <= 55:   return "NEUTRAL"
    if value <= 75:   return "GREED"           # Lean SELL
    return "EXTREME_GREED"                      # Good SELL opportunity


def get_news_sentiment(symbol: str = "BTC") -> dict:
    """
    Get recent crypto news sentiment
    Uses CryptoPanic public API (no key needed)
    """
    coin = symbol.replace("USDT", "").upper()
    try:
        r = requests.get(
            f"https://cryptopanic.com/api/free/v1/posts/?auth_token=free&currencies={coin}&kind=news&filter=hot",
            timeout=8,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])[:10]
            positive = sum(1 for n in results if n.get("votes", {}).get("positive", 0) >
                                                  n.get("votes", {}).get("negative", 0))
            negative = len(results) - positive
            sentiment = "POSITIVE" if positive > negative else "NEGATIVE" if negative > positive else "NEUTRAL"
            headlines = [n.get("title", "") for n in results[:3]]
            return {
                "sentiment": sentiment,
                "positive":  positive,
                "negative":  negative,
                "headlines": headlines,
            }
    except Exception as e:
        logger.warning(f"News sentiment failed: {e}")
    return {"sentiment": "NEUTRAL", "positive": 0, "negative": 0, "headlines": []}


def get_combined_sentiment(symbol: str = "BTCUSDT") -> dict:
    """Combined sentiment score from Fear/Greed + News"""
    fng  = get_fear_greed_index()
    news = get_news_sentiment(symbol)

    # Sentiment bonus/penalty for signal scoring
    score_adjust = 0
    if fng["signal"] in ("EXTREME_FEAR", "FEAR"):
        score_adjust += 15   # Good time to buy
    elif fng["signal"] in ("EXTREME_GREED", "GREED"):
        score_adjust -= 15   # Good time to sell

    if news["sentiment"] == "POSITIVE":
        score_adjust += 10
    elif news["sentiment"] == "NEGATIVE":
        score_adjust -= 10

    return {
        "fear_greed":     fng,
        "news":           news,
        "score_adjust":   score_adjust,
        "overall":        "BULLISH" if score_adjust > 0 else "BEARISH" if score_adjust < 0 else "NEUTRAL",
    }
