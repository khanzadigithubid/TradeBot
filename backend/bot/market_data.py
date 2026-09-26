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
    "AUDUSDT": "AUD",
    "CADUSDT": "CAD",
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

    # 4. No live rate available. Returning None means the synthetic-candle
    #    fallback is skipped too — a hardcoded rate is off by several percent
    #    (EURUSD is ~1.14, not 1.10) and would produce a confidently wrong
    #    signal out of a number that never came from a market.
    logger.error(
        f"No live FX rate available for {symbol} — refusing to synthesise "
        f"candles from a stale rate. Forex trading disabled for this symbol."
    )
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
                daily = _build_forex_df(raw, limit)
                out   = _resample_forex_df(daily, interval)
                if out is not None and not out.empty:
                    return out.tail(limit).reset_index(drop=True)
    except Exception as e:
        logger.debug(f"Frankfurter klines failed for {symbol}: {e}")

    # 2. exchangerate.host
    try:
        r = requests.get(
            "https://api.exchangerate.host/timeseries",
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
                daily = _build_forex_df(
                    {d: {"USD": v.get("USD", 0)} for d, v in raw.items()},
                    limit
                )
                out = _resample_forex_df(daily, interval)
                if out is not None and not out.empty:
                    return out.tail(limit).reset_index(drop=True)
    except Exception as e:
        logger.debug(f"exchangerate.host timeseries failed for {symbol}: {e}")

    # 3. Synthetic data from current price (last resort)
    price = _get_forex_price(symbol)
    if price:
        logger.warning(
            f"Using synthetic forex data for {symbol} @ {interval} — indicators unreliable"
        )
        rows = []
        step = _FOREX_RESAMPLE.get(interval) or "1D"
        now  = datetime.now(timezone.utc)
        for i in range(limit, 0, -1):
            ts = now - timedelta(**{_STEP_UNIT[step]: i * _STEP_COUNT[step]})
            rows.append({
                "timestamp": ts,
                "open":   price,
                "high":   price * 1.002,
                "low":    price * 0.998,
                "close":  price,
                "volume": 1000000.0,
            })
        return pd.DataFrame(rows)

    return pd.DataFrame()


_STEP_UNIT = {
    "1min": "minutes", "5min": "minutes", "15min": "minutes",
    "30min": "minutes", "1h": "hours", "4h": "hours",
    "W": "weeks", "ME": "days", "1D": "days",
}
_STEP_COUNT = {
    "1min": 1, "5min": 5, "15min": 15, "30min": 30,
    "1h": 1, "4h": 4, "W": 1, "ME": 30, "1D": 1,
}



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
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.tail(limit).reset_index(drop=True)


# Free forex APIs only publish one rate per day, so sub-daily intervals have to
# be resampled from that daily series instead of silently returning daily
# candles labelled "1h" (which made 1h/4h forex signals meaningless).
_FOREX_RESAMPLE = {
    "1d": None, "1w": "W", "1M": "ME",
    "4h": "4h", "1h": "1h", "30m": "30min",
    "15m": "15min", "5m": "5min", "3m": "3min", "1m": "1min",
}


def _resample_forex_df(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """
    Upsample the daily forex series to `interval`. Intraday bars are
    interpolated from the daily closes, so they are indicative rather than
    true tick data — the UI labels these as approximate.
    """
    if df is None or df.empty:
        return df

    rule = _FOREX_RESAMPLE.get(interval, "1h")
    if rule is None:
        return df

    d = df.copy()
    d = d.set_index("timestamp").sort_index()

    if rule in ("W", "ME"):
        agg = {"open": "first", "high": "max", "low": "min",
               "close": "last", "volume": "sum"}
        out = d.resample(rule).agg(agg).dropna(subset=["close"])
        return out.reset_index()

    # Intraday: linearly interpolate between daily closes, then resample.
    target = rule
    full_idx = pd.date_range(
        start=d.index.min(), end=d.index.max(), freq=target, tz="UTC"
    )
    if len(full_idx) == 0:
        return df

    close_interp = d["close"].reindex(
        d.index.union(full_idx)
    ).interpolate(method="time").reindex(full_idx)

    out = pd.DataFrame({
        "timestamp": full_idx,
        "open":   close_interp.values,
        "high":   close_interp.values * 1.0008,
        "low":    close_interp.values * 0.9992,
        "close":  close_interp.values,
        "volume": 1000000.0 / max(1, len(full_idx) // max(1, len(d))),
    }).dropna(subset=["close"])

    return out.tail(1000).reset_index(drop=True)


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


def search_symbols(query: str, quote: str = "USDT", limit: int = 25) -> list:
    """
    Symbols the exchange actually lists, matching a free-text query.

    The watchlist add box searches this instead of accepting raw text: it is
    what makes a typo impossible rather than merely reported. Results carry
    live 24h price and change so the dropdown can show them before the pair is
    added.

    Matching is on the base asset, so "pe" finds PEPE, and "pepe" finds it
    ahead of unrelated pairs. The forex pairs are folded in because they are
    not on the Binance exchangeInfo feed.
    """
    q = (query or "").strip().upper()
    if len(q) < 2:
        return []

    out, seen = [], set()

    for sym in FOREX_SYMBOLS:
        base = FOREX_SYMBOLS[sym]
        if q in base or q in sym:
            out.append({"symbol": sym, "price": None, "change": None, "source": "forex"})
            seen.add(sym)

    for sym in _listed_usdt_symbols():
        if sym in seen:
            continue
        base = sym[:-len(quote)]
        if q not in base and q not in sym:
            continue
        out.append({"symbol": sym, "price": None, "change": None, "source": "binance"})
        seen.add(sym)
        if len(out) >= limit * 2:
            break

    # Prices come last, and only for the rows actually returned, so this stays
    # a handful of ticker calls rather than the whole market.
    for row in out[:limit * 2]:
        try:
            stats = get_24h_stats(row["symbol"])
            row["price"]  = float(stats.get("lastPrice", 0) or 0) or None
            row["change"] = float(stats.get("priceChangePercent", 0) or 0)
        except Exception:
            pass

    # "BTC" has to mean BTCUSDT, not WBTCUSDT. Exact base first, then prefix
    # matches, then anything else that merely contains the query.
    def rank(row):
        sym = row["symbol"]
        base = sym[:-len(quote)] if sym.endswith(quote) else sym
        if base == q:
            return (0, base)
        if base.startswith(q):
            return (1, base)
        return (2, base)

    out.sort(key=rank)
    return out[:limit]


_LISTED_CACHE: dict = {"at": 0.0, "symbols": ()}
_LISTED_TTL = 600.0


def _listed_usdt_symbols() -> tuple:
    """
    USDT spot symbols currently in TRADING status, cached briefly.

    exchangeInfo is a large payload and the tradable set changes slowly, so it
    is refetched at most every _LISTED_TTL seconds. A failure returns the last
    good list rather than an empty one, which would break the dropdown.
    """
    import time as _time
    now = _time.time()
    if now - _LISTED_CACHE["at"] < _LISTED_TTL and _LISTED_CACHE["symbols"]:
        return _LISTED_CACHE["symbols"]

    try:
        data = _try_binance("exchangeInfo", {"permissions": "SPOT"})
        syms = tuple(sorted({
            s["symbol"] for s in data.get("symbols", [])
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
        }))
        if syms:
            _LISTED_CACHE.update(at=now, symbols=syms)
            return syms
    except Exception:
        pass

    return _LISTED_CACHE["symbols"]


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
