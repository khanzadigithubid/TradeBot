"""
FastAPI Routes — REST API Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from bot.engine import engine
from bot.binance_client import BinanceClient
from bot.strategy import compute_signal, sentiment_blocks_buy
from bot.safety import assert_live_allowed, LiveTradingBlocked, describe_mode
from bot import config as cfg

router = APIRouter()


# ─── Request Models ────────────────────────────────────────────────────────────

_SYMBOL_MAX_LEN = 20
_INTERVALS      = ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d")


def _validate_symbol(v: str) -> str:
    """Normalise to uppercase and reject junk before it reaches the exchange."""
    v = v.strip().upper()
    if not v:
        raise ValueError("symbol cannot be empty")
    if len(v) > _SYMBOL_MAX_LEN:
        raise ValueError(f"symbol too long (max {_SYMBOL_MAX_LEN})")
    if not v.isalnum():
        raise ValueError("symbol may only contain letters and digits")
    return v


def _validate_interval(v: str) -> str:
    v = v.strip().lower()
    if v not in _INTERVALS:
        raise ValueError(f"interval must be one of {list(_INTERVALS)}")
    return v


def _symbol_param(v: str) -> str:
    """
    Path/query-parameter variant of _validate_symbol.

    A bare ValueError inside a path parameter is NOT converted by FastAPI into a
    4xx response — it escapes as a 500. These wrappers turn bad input into a
    clean 400 instead of a crash.
    """
    try:
        return _validate_symbol(v)
    except ValueError as e:
        raise HTTPException(400, str(e))


def _interval_param(v: str) -> str:
    try:
        return _validate_interval(v)
    except ValueError as e:
        raise HTTPException(400, str(e))


class BotStartRequest(BaseModel):
    symbol:   Optional[str]  = None
    interval: Optional[str]  = None
    multi_symbol: Optional[bool] = None
    active_symbols: Optional[List[str]] = None

    _sym = field_validator("symbol")(classmethod(lambda cls, v: _validate_symbol(v) if v else v))
    _int = field_validator("interval")(classmethod(lambda cls, v: _validate_interval(v) if v else v))
    _act = field_validator("active_symbols")(classmethod(
        lambda cls, v: [_validate_symbol(s) for s in v] if v else v
    ))


class SettingsUpdate(BaseModel):
    # A misspelled setting is far more dangerous than a rejected request: it
    # used to be silently ignored, leaving the bot running the old value.
    model_config = ConfigDict(extra="forbid")

    api_key:                Optional[str]   = Field(default=None, max_length=128)
    secret_key:             Optional[str]   = Field(default=None, max_length=128)
    testnet:                Optional[bool]  = None
    symbol:                 Optional[str]   = Field(default=None, max_length=_SYMBOL_MAX_LEN)
    interval:               Optional[str]   = None
    trade_quantity_percent: Optional[float] = Field(default=None, ge=0.1, le=100)
    max_open_trades:        Optional[int]   = Field(default=None, ge=1, le=50)
    stop_loss_percent:      Optional[float] = Field(default=None, gt=0, le=50)
    take_profit_percent:    Optional[float] = Field(default=None, gt=0, le=500)
    trailing_stop:          Optional[bool]  = None
    trailing_stop_percent:  Optional[float] = Field(default=None, gt=0, le=50)
    ema_fast:               Optional[int]   = Field(default=None, ge=2, le=200)
    ema_slow:               Optional[int]   = Field(default=None, ge=3, le=400)
    rsi_period:             Optional[int]   = Field(default=None, ge=2, le=100)
    rsi_overbought:         Optional[float] = Field(default=None, ge=50, le=100)
    rsi_oversold:           Optional[float] = Field(default=None, ge=0, le=50)
    telegram_bot_token:     Optional[str]   = Field(default=None, max_length=128)
    telegram_chat_id:       Optional[str]   = Field(default=None, max_length=64)
    email_sender:           Optional[str]   = Field(default=None, max_length=254)
    email_app_password:     Optional[str]   = Field(default=None, max_length=128)
    email_receiver:         Optional[str]   = Field(default=None, max_length=254)
    multi_symbol_mode:      Optional[bool]  = None
    active_symbols:         Optional[List[str]] = None
    discord_webhook_url:    Optional[str]   = Field(default=None, max_length=512)
    daily_loss_limit_percent: Optional[float] = Field(default=None, ge=0, le=100)
    sentiment_filter:       Optional[bool]  = None
    mtf_enabled:            Optional[bool]  = None

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v):
        return _validate_symbol(v) if v else v

    @field_validator("interval")
    @classmethod
    def _int(cls, v):
        return _validate_interval(v) if v else v

    @field_validator("active_symbols")
    @classmethod
    def _act(cls, v):
        return [_validate_symbol(s) for s in v] if v else v


class ManualTradeRequest(BaseModel):
    symbol:   str
    side:     str
    quantity: Optional[float] = Field(default=None, gt=0)

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v):
        return _validate_symbol(v)

    @field_validator("side")
    @classmethod
    def _side(cls, v):
        v = v.strip().upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        return v


class BacktestRequest(BaseModel):
    symbol:               str   = "BTCUSDT"
    interval:             str   = "15m"
    limit:                int   = Field(default=500, ge=50, le=1000)
    initial_balance:      float = Field(default=1000.0, gt=0, le=1e9)
    confidence_threshold: float = Field(default=60.0, ge=0, le=100)

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v):
        return _validate_symbol(v)

    @field_validator("interval")
    @classmethod
    def _int(cls, v):
        return _validate_interval(v)


# ─── Bot Control ───────────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    return engine.get_status()

@router.post("/bot/start")
async def start_bot(req: BotStartRequest = BotStartRequest()):
    if engine.running:
        raise HTTPException(400, "Bot is already running")

    # ── Safety interlock: refuse to start in live mode without opt-in ───────
    mode = describe_mode(engine.config.get("TESTNET", True))
    if not mode["live_allowed"]:
        raise HTTPException(
            403,
            "Live trading is disabled. Switch to Testnet, or set "
            "LIVE_TRADING_ENABLED=true on the server to allow real orders.",
        )

    if req.symbol:
        sym = _validate_symbol(req.symbol)
        # A watchlist pair is only guaranteed to be monitorable. Refuse here,
        # with a clear reason, rather than letting the bot start and then fail
        # on the first order.
        if not _tradeable(sym):
            raise HTTPException(
                400,
                f"{sym} is on the watchlist for price monitoring but is not a "
                f"pair this bot trades. Add it to CRYPTO_PAIRS in "
                f"backend/bot/config.py to trade it.",
            )
        engine.current_symbol = sym
    if req.interval:
        engine.interval = req.interval
    if req.multi_symbol is not None:
        engine.config["MULTI_SYMBOL_MODE"] = req.multi_symbol
    if req.active_symbols:
        engine.active_symbols = req.active_symbols

    import asyncio
    asyncio.create_task(engine.start())
    return {"message": "Bot started", "symbols": engine._resolve_symbols()}

@router.post("/bot/stop")
def stop_bot():
    if not engine.running:
        raise HTTPException(400, "Bot is not running")
    engine.stop()
    return {"message": "Bot stopped"}


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings():
    from bot.config import CRYPTO_PAIRS, FOREX_PAIRS
    mode = describe_mode(engine.config.get("TESTNET", True))
    return {
        "testnet":                engine.config.get("TESTNET", False),
        # What the bot will actually trade with right now. A stored live config
        # that cannot be authorised reads as testnet here.
        "effective_testnet":      engine.config.get("TESTNET", True) or not mode["live_allowed"],
        "symbol":                 engine.current_symbol,
        "interval":               engine.interval,
        "trade_quantity_percent": engine.config.get("TRADE_QUANTITY_PERCENT", 10),
        "max_open_trades":        engine.config.get("MAX_OPEN_TRADES", 3),
        "stop_loss_percent":      engine.config.get("STOP_LOSS_PERCENT", 2.0),
        "take_profit_percent":    engine.config.get("TAKE_PROFIT_PERCENT", 4.0),
        "trailing_stop":          engine.config.get("TRAILING_STOP", True),
        "trailing_stop_percent":  engine.config.get("TRAILING_STOP_PERCENT", 1.0),
        "ema_fast":               engine.config.get("EMA_FAST", 9),
        "ema_slow":               engine.config.get("EMA_SLOW", 21),
        "rsi_period":             engine.config.get("RSI_PERIOD", 14),
        "rsi_overbought":         engine.config.get("RSI_OVERBOUGHT", 70),
        "rsi_oversold":           engine.config.get("RSI_OVERSOLD", 30),
        "telegram_configured":    bool(engine.config.get("TELEGRAM_BOT_TOKEN")),
        "email_configured":       bool(engine.config.get("EMAIL_SENDER") and engine.config.get("EMAIL_APP_PASSWORD")),
        "resend_configured":      bool(engine.config.get("RESEND_API_KEY")),
        "discord_configured":     bool(engine.config.get("DISCORD_WEBHOOK_URL")),
        "daily_loss_limit":       engine.config.get("DAILY_LOSS_LIMIT_PERCENT", 5.0),
        "sentiment_filter":       engine.config.get("SENTIMENT_FILTER", True),
        "mtf_enabled":            engine.config.get("MTF_ENABLED", True),
        "multi_symbol_mode":      engine.config.get("MULTI_SYMBOL_MODE", False),
        "active_symbols":         engine.active_symbols,
        "safety":                 mode,
        "price_stream_url":       engine.price_stream.base,
        # Separated lists for frontend grouping
        "crypto_pairs":           CRYPTO_PAIRS,
        "forex_pairs":            FOREX_PAIRS,
        "supported_pairs":        CRYPTO_PAIRS + FOREX_PAIRS,
        "supported_intervals":    ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
    }

@router.post("/settings")
def update_settings(settings: SettingsUpdate):
    update = {}
    if settings.api_key                is not None: update["BINANCE_API_KEY"]        = settings.api_key
    if settings.secret_key             is not None: update["BINANCE_SECRET_KEY"]     = settings.secret_key
    if settings.testnet                is not None: update["TESTNET"]                = settings.testnet
    if settings.symbol                 is not None:
        engine.current_symbol = settings.symbol
        update["SYMBOL"] = settings.symbol
    if settings.interval               is not None:
        engine.interval = settings.interval
        update["INTERVAL"] = settings.interval
    if settings.trade_quantity_percent is not None: update["TRADE_QUANTITY_PERCENT"] = settings.trade_quantity_percent
    if settings.max_open_trades        is not None: update["MAX_OPEN_TRADES"]        = settings.max_open_trades
    if settings.stop_loss_percent      is not None: update["STOP_LOSS_PERCENT"]      = settings.stop_loss_percent
    if settings.take_profit_percent    is not None: update["TAKE_PROFIT_PERCENT"]    = settings.take_profit_percent
    if settings.trailing_stop          is not None: update["TRAILING_STOP"]          = settings.trailing_stop
    if settings.trailing_stop_percent  is not None: update["TRAILING_STOP_PERCENT"]  = settings.trailing_stop_percent
    if settings.ema_fast               is not None: update["EMA_FAST"]               = settings.ema_fast
    if settings.ema_slow               is not None: update["EMA_SLOW"]               = settings.ema_slow
    if settings.rsi_period             is not None: update["RSI_PERIOD"]             = settings.rsi_period
    if settings.rsi_overbought         is not None: update["RSI_OVERBOUGHT"]         = settings.rsi_overbought
    if settings.rsi_oversold           is not None: update["RSI_OVERSOLD"]           = settings.rsi_oversold
    if settings.telegram_bot_token     is not None: update["TELEGRAM_BOT_TOKEN"]     = settings.telegram_bot_token
    if settings.telegram_chat_id       is not None: update["TELEGRAM_CHAT_ID"]       = settings.telegram_chat_id
    if settings.email_sender           is not None: update["EMAIL_SENDER"]           = settings.email_sender
    if settings.email_app_password     is not None: update["EMAIL_APP_PASSWORD"]     = settings.email_app_password
    if settings.email_receiver         is not None: update["EMAIL_RECEIVER"]         = settings.email_receiver
    if settings.multi_symbol_mode      is not None: update["MULTI_SYMBOL_MODE"]          = settings.multi_symbol_mode
    if settings.active_symbols         is not None:
        engine.active_symbols = settings.active_symbols
        update["ACTIVE_SYMBOLS"] = settings.active_symbols
    if settings.discord_webhook_url      is not None: update["DISCORD_WEBHOOK_URL"]       = settings.discord_webhook_url
    if settings.daily_loss_limit_percent is not None: update["DAILY_LOSS_LIMIT_PERCENT"]  = settings.daily_loss_limit_percent
    if settings.sentiment_filter         is not None: update["SENTIMENT_FILTER"]          = settings.sentiment_filter
    if settings.mtf_enabled              is not None: update["MTF_ENABLED"]               = settings.mtf_enabled

    if update:
        requested_live = update.get("TESTNET") is False
        engine.update_config(update)

        # A refused live switch is surfaced as an error, not a silent downgrade,
        # so the UI can tell the user their request was rejected.
        if requested_live and engine.config.get("TESTNET", True):
            raise HTTPException(
                403,
                "Live trading is disabled. Switch to Testnet, or set "
                "LIVE_TRADING_ENABLED=true on the server to allow real orders.",
            )

    mode = describe_mode(engine.config.get("TESTNET", True))
    # Report the *effective* mode — a rejected live switch is reported as testnet.
    return {
        "message": "Settings updated",
        "testnet": engine.config.get("TESTNET", True),
        # What the bot will actually trade with right now.
        "effective_testnet": engine.config.get("TESTNET", True) or not mode["live_allowed"],
        "safety":  mode,
    }

@router.post("/settings/test-connection")
def test_connection(settings: SettingsUpdate):
    client = BinanceClient(
        api_key    = settings.api_key    or "",
        secret_key = settings.secret_key or "",
        testnet    = settings.testnet if settings.testnet is not None else True,
    )
    if client.test_connection():
        balance = client.get_balance("USDT")
        if balance is None:
            return {
                "connected": True,
                "usdt_balance": None,
                "error": "Connected to Binance, but the USDT balance could not be read. Check the key's permissions.",
            }
        return {"connected": True, "usdt_balance": balance}
    return {"connected": False, "error": "Could not connect to Binance"}

@router.post("/settings/test-telegram")
def test_telegram():
    """Send a test Telegram message"""
    result = engine.notifier.send("✅ <b>Telegram connected!</b> Your trading bot notifications are working.")
    if result:
        return {"success": True, "message": "Test message sent"}
    return {"success": False, "message": "Telegram not configured or send failed"}

@router.post("/settings/test-email")
def test_email():
    """Send a test email via Gmail SMTP"""
    result = engine.email_notifier.test_email()
    if result:
        return {"success": True, "message": "Test email sent — check your inbox"}
    return {"success": False, "message": "Email not configured or send failed."}

@router.post("/settings/test-resend")
def test_resend():
    """Send a test email via Resend API"""
    result = engine.resend_notifier.test_email()
    if result:
        return {"success": True, "message": "Resend test email sent — check your inbox"}
    return {"success": False, "message": "Resend not configured or send failed."}

@router.post("/settings/test-discord")
def test_discord():
    """Send a test Discord message"""
    result = engine.discord_notifier.test_discord()
    if result:
        return {"success": True, "message": "Discord test message sent!"}
    return {"success": False, "message": "Discord webhook not configured."}

@router.get("/market/sentiment")
def get_sentiment(symbol: str = "BTCUSDT"):
    """Get Fear & Greed index + news sentiment"""
    from bot.sentiment import get_combined_sentiment
    return get_combined_sentiment(_symbol_param(symbol))

@router.get("/market/fear-greed")
def get_fear_greed():
    """Get Fear & Greed Index"""
    from bot.sentiment import get_fear_greed_index
    return get_fear_greed_index()


# ─── Watchlist ────────────────────────────────────────────────────────────────

def _tradeable(symbol: str) -> bool:
    """
    Whether the bot can actually trade this pair.

    Being on the watchlist only means "show me its price". Trading needs the
    pair to be in the configured set AND to exist on the venue, so this is
    checked rather than assumed from the watchlist itself.
    """
    return symbol in cfg.SUPPORTED_PAIRS


@router.get("/watchlist")
def get_watchlist():
    """
    The dashboard sidebar list, annotated with whether each pair is tradeable.

    The client is told up front so a monitoring-only pair cannot be mistaken
    for one the bot will trade.
    """
    from bot.watchlist_store import load_watchlist
    return {
        "symbols":   load_watchlist(),
        "tradeable": [s for s in load_watchlist() if _tradeable(s)],
    }


class WatchlistAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("symbol")
    @classmethod
    def _check(cls, v):
        return _validate_symbol(v)


@router.post("/watchlist")
def add_to_watchlist(body: WatchlistAdd):
    """
    Add a pair to the watchlist.

    Verified against the exchange's 24h ticker so a typo is reported here
    instead of showing up as a permanently blank row in the sidebar.
    """
    from bot.market_data import get_24h_stats
    from bot.watchlist_store import add_symbol, load_watchlist

    sym = _validate_symbol(body.symbol)
    try:
        stats = get_24h_stats(sym)
        last  = float(stats.get("lastPrice", 0) or 0)
    except Exception:
        raise HTTPException(404, f"{sym} was not found on the exchange")

    if not last or last <= 0:
        raise HTTPException(404, f"{sym} has no price on the exchange")

    try:
        symbols = add_symbol(sym)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"symbols": symbols, "added": sym, "tradeable": _tradeable(sym)}


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(symbol: str):
    from bot.watchlist_store import remove_symbol
    try:
        symbols = remove_symbol(_symbol_param(symbol))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"symbols": symbols, "removed": symbol}


# ─── Market Data ───────────────────────────────────────────────────────────────

@router.get("/market/prices")
def get_bulk_prices(symbols: str = "BTCUSDT,ETHUSDT,BNBUSDT"):
    """
    Get prices + 24h change for multiple symbols in one call.
    Usage: /api/market/prices?symbols=BTCUSDT,ETHUSDT,BNBUSDT
    """
    from bot.market_data import get_price, get_24h_stats
    result = {}
    for sym in symbols.split(","):
        sym = sym.strip()
        if not sym:
            continue
        try:
            sym = _symbol_param(sym)
        except HTTPException:
            continue                      # skip junk symbols, keep the rest
        try:
            stats = get_24h_stats(sym)
            result[sym] = {
                "price":  float(stats.get("lastPrice", 0) or 0),
                "change": float(stats.get("priceChangePercent", 0) or 0),
            }
        except Exception:
            price = get_price(sym)
            result[sym] = {"price": price or 0, "change": 0}
    return result


@router.get("/market/{symbol}/price")
def get_price(symbol: str):
    from bot.market_data import get_price as _get_price
    sym = _symbol_param(symbol)
    price = _get_price(sym)
    if price is None:
        raise HTTPException(404, "Symbol not found")
    return {"symbol": sym, "price": price}

@router.get("/market/{symbol}/stats")
def get_market_stats(symbol: str):
    return engine.client.get_24h_stats(_symbol_param(symbol))

@router.get("/market/{symbol}/candles")
def get_candles(symbol: str, interval: str = "15m", limit: int = 100):
    sym  = _symbol_param(symbol)
    tf   = _interval_param(interval)
    limit = max(1, min(limit, 1000))
    df = engine.client.get_klines(sym, tf, limit)
    if df.empty:
        return []
    return df[["timestamp", "open", "high", "low", "close", "volume"]].to_dict(orient="records")

@router.get("/market/{symbol}/signal")
def get_signal(symbol: str):
    """
    Canonical signal for `symbol` — the same function the live engine calls, so
    what the dashboard shows is what the bot actually trades on.

    A fresh engine signal is preferred (it already has MTF + sentiment); it is
    recomputed only when the engine has nothing cached for this symbol.
    """
    sym = _symbol_param(symbol)

    # last_signal is None until the first engine cycle completes.
    cached = (engine.last_signal or {}).get(sym)
    if cached:
        return cached

    signal = compute_signal(sym, engine.config, interval=engine.interval, limit=200)
    if signal is None:
        return {
            "action": "HOLD", "confidence": 50, "price": 0,
            "rsi": 50, "ema_fast": 0, "ema_slow": 0,
            "macd": 0, "macd_signal": 0,
            "bb_upper": 0, "bb_lower": 0,
            "stop_loss": None, "take_profit": None,
            "signals": ["Waiting for market data..."],
            "buy_score": 0, "sell_score": 0,
            "symbol": sym,
        }
    return signal

@router.get("/market/{symbol}/indicators")
def get_indicators(symbol: str, interval: str = "15m", limit: int = 200):
    """
    Returns full indicator series for chart overlays:
    RSI, MACD line/signal/histogram, EMA fast/slow, Bollinger Bands
    """
    from bot.indicators import (
        calculate_ema, calculate_rsi, calculate_macd,
        calculate_bollinger_bands,
    )
    df = engine.client.get_klines(
        _symbol_param(symbol), _interval_param(interval), max(1, min(limit, 1000))
    )
    if df.empty:
        raise HTTPException(404, "No data")

    close = df["close"]
    times = df["timestamp"].astype(str).tolist()

    ema_f = calculate_ema(close, engine.config.get("EMA_FAST", 9))
    ema_s = calculate_ema(close, engine.config.get("EMA_SLOW", 21))
    rsi   = calculate_rsi(close, engine.config.get("RSI_PERIOD", 14))
    macd_line, sig_line, hist = calculate_macd(
        close,
        engine.config.get("MACD_FAST", 12),
        engine.config.get("MACD_SLOW", 26),
        engine.config.get("MACD_SIGNAL", 9),
    )
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(
        close,
        engine.config.get("BB_PERIOD", 20),
        engine.config.get("BB_STD", 2.0),
    )

    def s(series): return [round(float(v), 6) if not __import__("math").isnan(v) else None for v in series]

    return {
        "times":      times,
        "ema_fast":   s(ema_f),
        "ema_slow":   s(ema_s),
        "rsi":        s(rsi),
        "macd":       s(macd_line),
        "macd_signal":s(sig_line),
        "macd_hist":  s(hist),
        "bb_upper":   s(bb_upper),
        "bb_middle":  s(bb_mid),
        "bb_lower":   s(bb_lower),
    }


# ─── Trades ────────────────────────────────────────────────────────────────────

@router.get("/trades/open")
def get_open_trades():
    return engine.trade_manager.get_open_trades()

@router.get("/trades/history")
def get_trade_history(limit: int = 100):
    return engine.trade_manager.get_trade_history(limit)

@router.get("/trades/stats")
def get_trade_stats():
    stats = engine.trade_manager.get_stats()
    balance = engine.client.get_balance("USDT")
    stats["usdt_balance"] = balance if balance is not None else 0.0
    stats["balance_ok"] = balance is not None
    return stats

@router.post("/trades/manual")
async def manual_trade(req: ManualTradeRequest):
    symbol = req.symbol
    side   = req.side

    # ── Safety interlock: never place a real order without opt-in ──────────
    try:
        assert_live_allowed(
            engine.config.get("TESTNET", True),
            context=f"manual {side} {symbol}",
        )
    except LiveTradingBlocked as e:
        raise HTTPException(403, str(e))

    price  = engine.client.get_ticker_price(symbol)
    if not price:
        raise HTTPException(404, "Could not get price for this symbol")

    if side == "BUY":
        # Max open trades check
        open_count = len([t for t in engine.trade_manager.get_open_trades()])
        max_trades = engine.config.get("MAX_OPEN_TRADES", 3)
        if open_count >= max_trades:
            raise HTTPException(400, f"Max open trades limit reached ({open_count}/{max_trades}). Close a trade first or increase Max Trades in Settings.")

        # Already open for this symbol?
        already = [t for t in engine.trade_manager.get_open_trades() if t["symbol"] == symbol]
        if already:
            raise HTTPException(400, f"Already have an open trade for {symbol}. Close it first before buying again.")

        # Balance check — only for real money. Testnet uses simulated funds.
        if not engine.config.get("TESTNET", True):
            balance = engine.client.get_balance("USDT")
            if balance is None:
                raise HTTPException(400, "Could not read your USDT balance from Binance. Check the API key and network.")
            if balance <= 0:
                raise HTTPException(400, "USDT balance is 0 — deposit funds before placing a live trade.")

        signal = compute_signal(
            symbol, engine.config, interval=engine.interval, limit=200
        )
        if signal is None:
            raise HTTPException(404, f"No candle data for {symbol}")

        signal["price"]      = price
        signal["action"]     = "BUY"
        signal["confidence"] = 99   # Manual override — skip confidence check
        signal["forced"]     = True
        trade = engine.trade_manager.execute_buy(
            symbol, signal, force=True, quantity=req.quantity
        )
        if trade:
            return {"message": f"Buy placed for {symbol}", "trade": trade}
        raise HTTPException(400, f"Buy failed for {symbol}. Check Binance keys, balance, and that the order size meets Binance's minimum notional.")

    else:  # SELL
        open_trades = [t for t in engine.trade_manager.get_open_trades() if t["symbol"] == symbol]
        if not open_trades:
            raise HTTPException(404, f"No open trades for {symbol}. Nothing to sell.")
        results = []
        for t in open_trades:
            r = engine.trade_manager.execute_sell(t["id"], price, "MANUAL")
            if r:
                results.append(r)
        if not results:
            raise HTTPException(400, f"Could not close trades for {symbol}.")
        return {"message": f"Closed {len(results)} trade(s) for {symbol}", "trades": results}


@router.delete("/trades/{trade_id}")
def close_trade(trade_id: str):
    # ── Safety interlock ───────────────────────────────────────────────────
    try:
        assert_live_allowed(
            engine.config.get("TESTNET", True),
            context=f"close trade {trade_id[:8]}",
        )
    except LiveTradingBlocked as e:
        raise HTTPException(403, str(e))

    price = None
    for t in engine.trade_manager.get_open_trades():
        if t["id"] == trade_id:
            price = engine.client.get_ticker_price(t["symbol"])
            break
    if not price:
        raise HTTPException(404, "Trade not found or already closed")
    result = engine.trade_manager.execute_sell(trade_id, price, "MANUAL_CLOSE")
    if result:
        return {"message": "Trade closed", "trade": result}
    raise HTTPException(400, "Could not close trade")



# ─── Backtesting ───────────────────────────────────────────────────────────────

@router.post("/backtest")
def run_backtest(req: BacktestRequest):
    """
    Run a strategy backtest on historical data.
    Returns trades list, equity curve, and performance metrics.
    """
    from bot.backtester import run_backtest as _backtest

    df = engine.client.get_klines(req.symbol.upper(), req.interval, req.limit)
    if df.empty:
        raise HTTPException(404, f"No data for {req.symbol}")

    bt_config = dict(engine.config)
    bt_config["SYMBOL"] = req.symbol.upper()

    result = _backtest(
        df,
        bt_config,
        initial_balance      = req.initial_balance,
        confidence_threshold = req.confidence_threshold,
    )

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


# ─── Analytics ────────────────────────────────────────────────────────────────

@router.get("/analytics")
def get_analytics():
    """
    Returns data for the Analytics page:
    - Cumulative P&L curve
    - Drawdown series
    - Win/loss by symbol breakdown
    - Monthly performance
    """
    trades = engine.trade_manager.get_trade_history(limit=1000)
    if not trades:
        return {
            "equity_curve":    [],
            "drawdown_series": [],
            "by_symbol":       {},
            "monthly":         {},
            "sharpe":          0,
        }

    import numpy as np

    # Sort oldest-first
    closed = sorted(trades, key=lambda t: t.get("exit_time", ""))

    # Cumulative P&L
    cumulative = 0.0
    equity_curve = []
    for t in closed:
        cumulative += t.get("pnl") or 0
        equity_curve.append({"time": t.get("exit_time"), "pnl": round(cumulative, 4)})

    # Drawdown
    pnl_arr   = np.array([e["pnl"] for e in equity_curve])
    peak_arr  = np.maximum.accumulate(pnl_arr)
    dd_arr    = pnl_arr - peak_arr
    drawdown_series = [
        {"time": equity_curve[i]["time"], "drawdown": round(float(dd_arr[i]), 4)}
        for i in range(len(dd_arr))
    ]

    # By symbol
    by_symbol: dict = {}
    for t in closed:
        sym = t.get("symbol", "?")
        if sym not in by_symbol:
            by_symbol[sym] = {"wins": 0, "losses": 0, "pnl": 0.0}
        pnl = t.get("pnl") or 0
        by_symbol[sym]["pnl"] = round(by_symbol[sym]["pnl"] + pnl, 4)
        if pnl > 0:
            by_symbol[sym]["wins"] += 1
        else:
            by_symbol[sym]["losses"] += 1

    # Monthly P&L
    monthly: dict = {}
    for t in closed:
        et = t.get("exit_time", "")
        if et and len(et) >= 7:
            key = et[:7]  # "YYYY-MM"
            monthly[key] = round(monthly.get(key, 0.0) + (t.get("pnl") or 0), 4)

    # Sharpe (annualized, per-trade returns)
    pnl_vals = np.array([t.get("pnl") or 0 for t in closed])
    sharpe = 0.0
    if len(pnl_vals) > 1 and pnl_vals.std() > 0:
        sharpe = round(float(pnl_vals.mean() / pnl_vals.std() * np.sqrt(252)), 2)

    return {
        "equity_curve":    equity_curve,
        "drawdown_series": drawdown_series,
        "by_symbol":       by_symbol,
        "monthly":         monthly,
        "sharpe":          sharpe,
    }
