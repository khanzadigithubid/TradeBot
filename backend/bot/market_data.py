"""
Market Data Provider
Uses multiple free APIs as fallback when Binance is blocked.
Order: Binance → Binance mirrors → CoinGecko → Stooq
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

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

BINANCE_BASES = [
    "https://api.binance.com/api/v3",
    "https://api1.binance.com/api/v3",
    "https://api2.binance.com/api/v3",
    "https://api3.binance.com/api/v3",
    "https://api4.binance.com/api/v3",
]


def _try_binance(endpoint: str, params: dict):
    for base in BINANCE_BASES:
        try:
            r = requests.get(f"{base}/{endpoint}", params=params, timeout=8)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None


def get_price(symbol: str) -> float | None:
    # Binance
    data = _try_binance("ticker/price", {"symbol": symbol.upper()})
    if data and "price" in data:
        return float(data["price"])

    # CoinGecko
    cg_id = COINGECKO_IDS.get(symbol.upper())
    if cg_id:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"},
                timeout=10,
            )
            if r.status_code == 200:
                return float(r.json()[cg_id]["usd"])
        except Exception:
            pass

    # Kraken fallback
    kraken_pairs = {
        "BTCUSDT": "XBTUSD", "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD", "XRPUSDT": "XRPUSD",
        "ADAUSDT": "ADAUSD", "DOGEUSDT": "XDGUSD",
    }
    kraken_pair = kraken_pairs.get(symbol.upper())
    if kraken_pair:
        try:
            r = requests.get(
                f"https://api.kraken.com/0/public/Ticker?pair={kraken_pair}",
                timeout=8,
            )
            if r.status_code == 200:
                result = r.json().get("result", {})
                for key, val in result.items():
                    return float(val["c"][0])
        except Exception:
            pass

    return None


def get_24h_stats(symbol: str) -> dict:
    # Binance
    data = _try_binance("ticker/24hr", {"symbol": symbol.upper()})
    if data and "lastPrice" in data:
        return data

    # CoinGecko
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
                price  = md.get("current_price", {}).get("usd", 0)
                change = md.get("price_change_percentage_24h", 0)
                return {
                    "symbol": symbol,
                    "lastPrice": str(price),
                    "priceChangePercent": str(round(change, 2)),
                    "volume": str(md.get("total_volume", {}).get("usd", 0)),
                    "highPrice": str(md.get("high_24h", {}).get("usd", price)),
                    "lowPrice":  str(md.get("low_24h",  {}).get("usd", price)),
                }
        except Exception:
            pass

    return {"symbol": symbol, "lastPrice": "0", "priceChangePercent": "0", "volume": "0"}


def get_klines(symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
    # Binance
    data = _try_binance("klines", {"symbol": symbol.upper(), "interval": interval, "limit": limit})
    if data and isinstance(data, list) and len(data) > 0:
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df

    # Kraken OHLC fallback
    kraken_pairs = {
        "BTCUSDT": "XBTUSD", "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD", "XRPUSDT": "XRPUSD",
        "ADAUSDT": "ADAUSD", "DOGEUSDT": "XDGUSD",
        "BNBUSDT": "BNBUSD", "AVAXUSDT": "AVAXUSD",
    }
    interval_map = {
        "1m": 1, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "4h": 240, "1d": 1440,
    }
    kraken_pair = kraken_pairs.get(symbol.upper())
    kraken_interval = interval_map.get(interval, 15)

    if kraken_pair:
        try:
            r = requests.get(
                f"https://api.kraken.com/0/public/OHLC",
                params={"pair": kraken_pair, "interval": kraken_interval},
                timeout=12,
            )
            if r.status_code == 200:
                result = r.json().get("result", {})
                for key, rows in result.items():
                    if key == "last":
                        continue
                    df = pd.DataFrame(rows, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
                    ])
                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)
                    return df.tail(limit).reset_index(drop=True)
        except Exception as e:
            logger.warning(f"Kraken OHLC failed: {e}")

    # CoinGecko OHLC fallback
    cg_id = COINGECKO_IDS.get(symbol.upper())
    if cg_id:
        try:
            days = min(max(limit // 4, 7), 90)
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
                return df.tail(limit).reset_index(drop=True)
        except Exception as e:
            logger.warning(f"CoinGecko OHLC failed: {e}")

    return pd.DataFrame()
