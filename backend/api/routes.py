"""
FastAPI Routes — REST API Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from bot.engine import engine
from bot.binance_client import BinanceClient
from bot import config as cfg

router = APIRouter()


# ─── Request Models ────────────────────────────────────────────────────────────

class BotStartRequest(BaseModel):
    symbol:   Optional[str]  = None
    interval: Optional[str]  = None
    multi_symbol: Optional[bool] = None
    active_symbols: Optional[List[str]] = None

class SettingsUpdate(BaseModel):
    api_key:                Optional[str]   = None
    secret_key:             Optional[str]   = None
    testnet:                Optional[bool]  = None
    symbol:                 Optional[str]   = None
    interval:               Optional[str]   = None
    trade_quantity_percent: Optional[float] = None
    max_open_trades:        Optional[int]   = None
    stop_loss_percent:      Optional[float] = None
    take_profit_percent:    Optional[float] = None
    trailing_stop:          Optional[bool]  = None
    trailing_stop_percent:  Optional[float] = None
    ema_fast:               Optional[int]   = None
    ema_slow:               Optional[int]   = None
    rsi_period:             Optional[int]   = None
    rsi_overbought:         Optional[float] = None
    rsi_oversold:           Optional[float] = None
    telegram_bot_token:     Optional[str]   = None
    telegram_chat_id:       Optional[str]   = None
    email_sender:           Optional[str]   = None
    email_app_password:     Optional[str]   = None
    email_receiver:         Optional[str]   = None
    multi_symbol_mode:      Optional[bool]  = None
    active_symbols:         Optional[List[str]] = None

class ManualTradeRequest(BaseModel):
    symbol:   str
    side:     str              # BUY or SELL
    quantity: Optional[float] = None

class BacktestRequest(BaseModel):
    symbol:               str   = "BTCUSDT"
    interval:             str   = "15m"
    limit:                int   = 500
    initial_balance:      float = 1000.0
    confidence_threshold: float = 60.0


# ─── Bot Control ───────────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    return engine.get_status()

@router.post("/bot/start")
async def start_bot(req: BotStartRequest):
    if engine.running:
        raise HTTPException(400, "Bot is already running")
    if req.symbol:
        engine.current_symbol = req.symbol
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
    return {
        "testnet":                engine.config.get("TESTNET", False),
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
        "multi_symbol_mode":      engine.config.get("MULTI_SYMBOL_MODE", False),
        "active_symbols":         engine.active_symbols,
        "supported_pairs":        cfg.SUPPORTED_PAIRS,
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
    if settings.multi_symbol_mode      is not None: update["MULTI_SYMBOL_MODE"]      = settings.multi_symbol_mode
    if settings.active_symbols         is not None:
        engine.active_symbols = settings.active_symbols
        update["ACTIVE_SYMBOLS"] = settings.active_symbols

    if update:
        engine.update_config(update)
    return {"message": "Settings updated"}

@router.post("/settings/test-connection")
def test_connection(settings: SettingsUpdate):
    client = BinanceClient(
        api_key    = settings.api_key    or "",
        secret_key = settings.secret_key or "",
        testnet    = settings.testnet if settings.testnet is not None else True,
    )
    if client.test_connection():
        balance = client.get_balance("USDT")
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
    """Send a test email"""
    result = engine.email_notifier.test_email()
    if result:
        return {"success": True, "message": "Test email sent — check your inbox"}
    return {"success": False, "message": "Email not configured or send failed. Check credentials."}


# ─── Market Data ───────────────────────────────────────────────────────────────

@router.get("/market/{symbol}/price")
def get_price(symbol: str):
    price = engine.client.get_ticker_price(symbol.upper())
    if price is None:
        raise HTTPException(404, "Symbol not found")
    return {"symbol": symbol.upper(), "price": price}

@router.get("/market/{symbol}/stats")
def get_market_stats(symbol: str):
    return engine.client.get_24h_stats(symbol.upper())

@router.get("/market/{symbol}/candles")
def get_candles(symbol: str, interval: str = "15m", limit: int = 100):
    df = engine.client.get_klines(symbol.upper(), interval, limit)
    if df.empty:
        return []
    return df[["timestamp", "open", "high", "low", "close", "volume"]].to_dict(orient="records")

@router.get("/market/{symbol}/signal")
def get_signal(symbol: str):
    from bot.indicators import generate_ai_signal
    df = engine.client.get_klines(symbol.upper(), engine.interval, 200)
    if df.empty:
        return {
            "action": "HOLD", "confidence": 50, "price": 0,
            "rsi": 50, "ema_fast": 0, "ema_slow": 0,
            "macd": 0, "macd_signal": 0,
            "bb_upper": 0, "bb_lower": 0,
            "stop_loss": None, "take_profit": None,
            "signals": ["Waiting for market data..."],
            "buy_score": 0, "sell_score": 0,
            "symbol": symbol.upper()
        }
    signal = generate_ai_signal(df, engine.config)
    signal["symbol"] = symbol.upper()
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
    df = engine.client.get_klines(symbol.upper(), interval, limit)
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
    stats["usdt_balance"] = engine.client.get_balance("USDT")
    return stats

@router.post("/trades/manual")
async def manual_trade(req: ManualTradeRequest):
    symbol = req.symbol.upper()
    price  = engine.client.get_ticker_price(symbol)
    if not price:
        raise HTTPException(404, "Could not get price")

    if req.side.upper() == "BUY":
        from bot.indicators import generate_ai_signal
        df     = engine.client.get_klines(symbol, engine.interval, 200)
        signal = generate_ai_signal(df, engine.config)
        signal["price"] = price
        trade  = engine.trade_manager.execute_buy(symbol, signal)
        if trade:
            return {"message": "Buy placed", "trade": trade}
        raise HTTPException(400, "Could not execute buy")

    elif req.side.upper() == "SELL":
        open_trades = [t for t in engine.trade_manager.get_open_trades() if t["symbol"] == symbol]
        if not open_trades:
            raise HTTPException(404, "No open trades for this symbol")
        results = []
        for t in open_trades:
            r = engine.trade_manager.execute_sell(t["id"], price, "MANUAL")
            if r:
                results.append(r)
        return {"message": f"Closed {len(results)} trade(s)", "trades": results}

    raise HTTPException(400, "Invalid side — use BUY or SELL")

@router.delete("/trades/{trade_id}")
def close_trade(trade_id: str):
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
