"""
Market Data Provider
Uses CoinGecko (free, no API key) as fallback when Binance is blocked.
Falls back to Binance if CoinGecko fails.
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# CoinGecko symbol mapping
COINGECKO_IDS = {
    "BTCUSDT":   "bitcoin",
    "ETHUSDT":   "ethereum",
    "BNBUSDT":   "binancecoin",
    "SOLUSDT":   "solana",
    "XRPUSDT":   "ripple",
    "ADAUSDT":   "cardano",
    "DOGEUSDT":  "dogecoin",
    "AVAXUSDT":  "avalanche-2",
    "DOTUSDT":   "polkadot",
    "MATICUSDT": "matic-network",
}

BINANCE_URLS = [
    "https://api.binance.com/api/v3",
    "https://api1.binance.com/api/v3",
    "https://api2.binance.com/api/v3",
    "https://api3.binance.com/api/v3",
]


def get_price(symbol: str) -> float | None:
    """Get current price — tries Binance first, then CoinGecko"""
    # Try Binance
    for base in BINANCE_URLS:
        try:
            r = requests.get(f"{base}/ticker/price", params={"symbol": symbol}, timeout=6)
            if r.status_code == 200:
                return float(r.json()["price"])
        except Exception:
            continue

    # CoinGecko fallback
    cg_id = COINGECKO_IDS.get(symbol.upper())
    if cg_id:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"},
                timeout=8,
            )
            if r.status_code == 200:
                data = r.json()
                return float(data[cg_id]["usd"])
        except Exception:
            pass
    return None


def get_24h_stats(symbol: str) -> dict:
    """Get 24h stats — tries Binance first, then CoinGecko"""
    for base in BINANCE_URLS:
        try:
            r = requests.get(f"{base}/ticker/24hr", params={"symbol": symbol}, timeout=6)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue

    # CoinGecko fallback
    cg_id = COINGECKO_IDS.get(symbol.upper())
    if cg_id:
        try:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}",
                params={"localization": "false", "tickers": "false", "community_data": "false"},
                timeout=10,
            )
            if r.status_code == 200:
                d = r.json()
                md = d.get("market_data", {})
                price = md.get("current_price", {}).get("usd", 0)
                change = md.get("price_change_percentage_24h", 0)
                volume = md.get("total_volume", {}).get("usd", 0)
                return {
                    "symbol": symbol,
                    "lastPrice": str(price),
                    "priceChangePercent": str(round(change, 2)),
                    "volume": str(volume),
                    "highPrice": str(md.get("high_24h", {}).get("usd", price)),
                    "lowPrice":  str(md.get("low_24h",  {}).get("usd", price)),
                }
        except Exception:
            pass
    return {"symbol": symbol, "lastPrice": "0", "priceChangePercent": "0", "volume": "0"}


def get_klines(symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
    """Get OHLCV candles — tries Binance first, then CoinGecko"""
    for base in BINANCE_URLS:
        try:
            r = requests.get(f"{base}/klines",
                             params={"symbol": symbol, "interval": interval, "limit": limit},
                             timeout=10)
            if r.status_code == 200 and isinstance(r.json(), list):
                data = r.json()
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades',
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                return df
        except Exception:
            continue

    # CoinGecko fallback — daily only (no minute/hour candles on free tier)
    cg_id = COINGECKO_IDS.get(symbol.upper())
    if cg_id:
        try:
            days = min(limit, 90)
            r = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc",
                params={"vs_currency": "usd", "days": days},
                timeout=12,
            )
            if r.status_code == 200:
                raw = r.json()
                df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['volume'] = 0.0
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = df[col].astype(float)
                return df
        except Exception:
            pass

    return pd.DataFrame()
