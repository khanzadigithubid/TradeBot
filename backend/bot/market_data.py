"""
Market Data Provider
Uses multiple free APIs as fallback when Binance is blocked.
Crypto:  Binance → Binance mirrors → CoinGecko → Kraken
Forex:   Binance (forex tokens) → ExchangeRate-API → frankfurter.app
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
    "LINKUSDT":  "chainlink",
    "UNIUSDT":   "uniswap",
    "LTCUSDT":   "litecoin",
    "ATOMUSDT":  "cosmos",
    "NEARUSDT":  "near",
    "APTUSDT":   "aptos",
    "ARBUSDT":   "arbitrum",
    "OPUSDT":    "optimism",
    "INJUSDT":   "injective-protocol",
    "SUIUSDT":   "sui",
    "TRXUSDT":   "tron",
    "XLMUSDT":   "stellar",
    "VETUSDT":   "vechain",
    "FILUSDT":   "filecoin",
    "ICPUSDT":   "internet-computer",
}

# Forex symbol → base currency (vs USD)
FOREX_SYMBOLS = {
    "EURUSDT":  "EUR",
    "GBPUSDT":  "GBP",
    "JPYUSDT":  "JPY",
    "AUDUSTDT": "AUD",
    "CADUSTDT": "CAD",
    "CHFUSDT":  "CHF",
}

BINANCE_BASES = [
    "https://api.binance.com/api/v3",
    "https://api1.binance.com/api/v3",
    "https://api2.binance.com/api/v3",
    "https://api3.binance.com/api/v3",
    "https://api4.binance.com/api/v3",
]

def _is_forex(symbol: str) -> bool:
    return symbol.upper() in FOREX_SYMBOLS

def _try_binance(endpoint: str, params: dict):
    for base in BINANCE_BASES:
        try:
            r = requests.get(f"{base}/{endpoint}", params=params, timeout=8)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None


# ── Forex Price ────────────────────────────────────────────────────────────────

def _get_forex_price(symbol: str) -> float | None:
    """Get forex price using multiple free APIs as fallback"""
    base_currency = FOREX_SYMBOLS.get(symbol.upper())
    if not base_currency:
        return None

    # 1. frankfurter.app (free, no key needed)
    try:
        r = requests.get(
            f"https://api.frankfurter.app/latest",
            params={"from": base_currency, "to": "USD"},
            timeout=8,
        )
        if r.status_code == 200:
            rate = r.json().get("rates", {}).get("USD")
            if rate:
                return float(rate)
    except Exception as e:
        logger.debug(f"Frankfurter failed for {symbol}: {e}")

    # 2. ExchangeRate-API (free tier, no key needed)
    try:
        r = requests.get(
            f"https://open.er-api.com/v6/latest/{base_currency}",
            timeout=8,
        )
        if r.status_code == 200:
            rate = r.json().get("rates", {}).get("USD")
            if rate:
                return float(rate)
    except Exception as e:
        logger.debug(f"ExchangeRate-API failed for {symbol}: {e}")

    # 3. Fixer.io free alternative — exchangerate.host
    try:
        r = requests.get(
            f"https://api.exchangerate.host/latest",
            params={"base": base_currency, "symbols": "USD"},
            timeout=8,
        )
        if r.status_code == 200:
            rate = r.json().get("rates", {}).get("USD")
            if rate:
                return float(rate)
    except Exception as e:
        logger.debug(f"exchangerate.host failed for {symbol}: {e}")

    # 4. Hardcoded approximate fallback (last resort)
    fallback_rates = {
        "EUR": 1.10, "GBP": 1.27, "JPY": 0.0067,
        "AUD": 0.65, "CAD": 0.74, "CHF": 1.12,
    }
    if base_currency in fallback_rates:
        logger.warning(f"Using hardcoded fallback rate for {symbol}")
        return fallback_rates[base_currency]

    return None


def _get_forex_klines(symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
    """
    Generate OHLCV candles for forex from multiple free APIs.
    """
    base_currency = FOREX_SYMBOLS.get(symbol.upper())
    if not base_currency:
        return pd.DataFrame()

    end_date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    # 1. frankfurter.app
    try:
        r = requests.get(
            f"https://api.frankfurter.app/{start_date}..{end_date}",
            params={"from": base_currency, "to": "USD"},
            timeout=10,
        )
        if r.status_code == 200:
            raw = r.json().get("rates", {})
            if raw:
                return _build_forex_df(raw, limit)
    except Exception as e:
        logger.debug(f"Frankfurter klines failed for {symbol}: {e}")

    # 2. exchangerate.host
    try:
        r = requests.get(
            f"https://api.exchangerate.host/timeseries",
            params={
                "base": base_currency,
                "symbols": "USD",
                "start_date": start_date,
                "end_date": end_date,
            },
            timeout=10,
        )
        if r.status_code == 200:
            raw = r.json().get("rates", {})
            if raw:
                return _build_forex_df(
                    {d: {"USD": v.get("USD", 0)} for d, v in raw.items()},
                    limit
                )
    except Exception as e:
        logger.debug(f"exchangerate.host timeseries failed: {e}")

    # 3. Synthetic data from current price (last resort)
    price = _get_forex_price(symbol)
    if price:
        logger.warning(f"Using synthetic forex data for {symbol}")
        rows = []
        for i in range(min(limit, 90)):
            day = datetime.now(timezone.utc) - timedelta(days=i)
            rows.append({
                "timestamp": pd.Timestamp(day.strftime("%Y-%m-%d")),
                "open":   price,
                "high":   price * 1.002,
                "low":    price * 0.998,
                "close":  price,
                "volume": 1000000.0,
            })
        df = pd.DataFrame(rows[::-1])
        return df.tail(limit).reset_index(drop=True)

    return pd.DataFrame()


def _build_forex_df(raw: dict, limit: int) -> pd.DataFrame:
    """Build OHLCV DataFrame from date→rates dict"""
    rows = []
    for date_str, rate_dict in sorted(raw.items()):
        price = float(rate_dict.get("USD", 0))
        if price > 0:
            rows.append({
                "timestamp": pd.Timestamp(date_str),
                "open":   price,
                "high":   price * 1.002,
                "low":    price * 0.998,
                "close":  price,
                "volume": 1000000.0,
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.tail(limit).reset_index(drop=True)


# ── Public Functions ───────────────────────────────────────────────────────────

def get_price(symbol: str) -> float | None:
    sym = symbol.upper()

    # Forex
    if _is_forex(sym):
        return _get_forex_price(sym)

    # Binance
    data = _try_binance("ticker/price", {"symbol": sym})
    if data and "price" in data:
        return float(data["price"])

    # CoinGecko
    cg_id = COINGECKO_IDS.get(sym)
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
        "LTCUSDT": "LTCUSD", "LINKUSDT": "LINKUSD",
        "DOTUSDT": "DOTUSD", "ATOMUSDT": "ATOMUSD",
        "UNIUSDT": "UNIUSD", "XLMUSDT":  "XLMUSD",
    }
    kraken_pair = kraken_pairs.get(sym)
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
    sym = symbol.upper()

    # Forex — generate stats from current price
    if _is_forex(sym):
        price = _get_forex_price(sym)
        if price:
            return {
                "symbol":             sym,
                "lastPrice":          str(price),
                "priceChangePercent": "0.00",
                "volume":             "0",
                "highPrice":          str(round(price * 1.005, 6)),
                "lowPrice":           str(round(price * 0.995, 6)),
            }
        return {"symbol": sym, "lastPrice": "0", "priceChangePercent": "0", "volume": "0"}

    # Binance
    data = _try_binance("ticker/24hr", {"symbol": sym})
    if data and "lastPrice" in data:
        return data

    # CoinGecko
    cg_id = COINGECKO_IDS.get(sym)
    if cg_id:
        try:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}",
                params={"localization": "false", "tickers": "false", "community_data": "false"},
                timeout=10,
            )
            if r.status_code == 200:
                d  = r.json()
                md = d.get("market_data", {})
                price  = md.get("current_price", {}).get("usd", 0)
                change = md.get("price_change_percentage_24h", 0)
                return {
                    "symbol":             sym,
                    "lastPrice":          str(price),
                    "priceChangePercent": str(round(change, 2)),
                    "volume":             str(md.get("total_volume", {}).get("usd", 0)),
                    "highPrice":          str(md.get("high_24h", {}).get("usd", price)),
                    "lowPrice":           str(md.get("low_24h",  {}).get("usd", price)),
                }
        except Exception:
            pass

    return {"symbol": sym, "lastPrice": "0", "priceChangePercent": "0", "volume": "0"}


def get_klines(symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
    sym = symbol.upper()

    # Forex — use daily data from frankfurter
    if _is_forex(sym):
        return _get_forex_klines(sym, interval, limit)

    # Binance
    data = _try_binance("klines", {"symbol": sym, "interval": interval, "limit": limit})
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
        "BTCUSDT":  "XBTUSD",  "ETHUSDT":  "ETHUSD",
        "SOLUSDT":  "SOLUSD",  "XRPUSDT":  "XRPUSD",
        "ADAUSDT":  "ADAUSD",  "DOGEUSDT": "XDGUSD",
        "BNBUSDT":  "BNBUSD",  "AVAXUSDT": "AVAXUSD",
        "LTCUSDT":  "LTCUSD",  "LINKUSDT": "LINKUSD",
        "DOTUSDT":  "DOTUSD",  "ATOMUSDT": "ATOMUSD",
        "UNIUSDT":  "UNIUSD",  "XLMUSDT":  "XLMUSD",
        "NEARUSDT": "NEARUSD", "TRXUSDT":  "TRXUSD",
    }
    interval_map = {
        "1m": 1, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "4h": 240, "1d": 1440,
    }
    kraken_pair     = kraken_pairs.get(sym)
    kraken_interval = interval_map.get(interval, 15)

    if kraken_pair:
        try:
            r = requests.get(
                "https://api.kraken.com/0/public/OHLC",
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
    cg_id = COINGECKO_IDS.get(sym)
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
                df  = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['volume']    = 0.0
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = df[col].astype(float)
                return df.tail(limit).reset_index(drop=True)
        except Exception as e:
            logger.warning(f"CoinGecko OHLC failed: {e}")

    return pd.DataFrame()
