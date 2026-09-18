"""
FastAPI Routes - REST API Endpoints
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
    symbol: Optional[str] = None
    interval: Optional[str] = None

class SettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    testnet: Optional[bool] = None
    symbol: Optional[str] = None
    interval: Optional[str] = None
    trade_quantity_percent: Optional[float] = None
    max_open_trades: Optional[int] = None
    stop_loss_percent: Optional[float] = None
    take_profit_percent: Optional[float] = None
    ema_fast: Optional[int] = None
    ema_slow: Optional[int] = None
    rsi_period: Optional[int] = None
    rsi_overbought: Optional[float] = None
    rsi_oversold: Optional[float] = None

class ManualTradeRequest(BaseModel):
    symbol: str
    side: str   # BUY or SELL
    quantity: Optional[float] = None


# ─── Bot Control ───────────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    """Get current bot status"""
    return engine.get_status()


@router.post("/bot/start")
async def start_bot(req: BotStartRequest):
    """Start the trading bot"""
    if engine.running:
        raise HTTPException(status_code=400, detail="Bot is already running")

    if req.symbol:
        engine.current_symbol = req.symbol
    if req.interval:
        engine.interval = req.interval

    import asyncio
    asyncio.create_task(engine.start())
    return {"message": "Bot started successfully", "symbol": engine.current_symbol}


@router.post("/bot/stop")
def stop_bot():
    """Stop the trading bot"""
    if not engine.running:
        raise HTTPException(status_code=400, detail="Bot is not running")
    engine.stop()
    return {"message": "Bot stopped successfully"}


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings():
    """Get current settings — API keys never exposed"""
    return {
        "testnet": engine.config.get("TESTNET", False),
        "symbol": engine.current_symbol,
        "interval": engine.interval,
        "trade_quantity_percent": engine.config.get("TRADE_QUANTITY_PERCENT", 10),
        "max_open_trades": engine.config.get("MAX_OPEN_TRADES", 3),
        "stop_loss_percent": engine.config.get("STOP_LOSS_PERCENT", 2.0),
        "take_profit_percent": engine.config.get("TAKE_PROFIT_PERCENT", 4.0),
        "ema_fast": engine.config.get("EMA_FAST", 9),
        "ema_slow": engine.config.get("EMA_SLOW", 21),
        "rsi_period": engine.config.get("RSI_PERIOD", 14),
        "rsi_overbought": engine.config.get("RSI_OVERBOUGHT", 70),
        "rsi_oversold": engine.config.get("RSI_OVERSOLD", 30),
        "supported_pairs": cfg.SUPPORTED_PAIRS,
        "supported_intervals": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
    }


@router.post("/settings")
def update_settings(settings: SettingsUpdate):
    """Update bot settings"""
    update = {}
    if settings.api_key is not None:
        update["BINANCE_API_KEY"] = settings.api_key
    if settings.secret_key is not None:
        update["BINANCE_SECRET_KEY"] = settings.secret_key
    if settings.testnet is not None:
        update["TESTNET"] = settings.testnet
    if settings.symbol is not None:
        engine.current_symbol = settings.symbol
        update["SYMBOL"] = settings.symbol
    if settings.interval is not None:
        engine.interval = settings.interval
        update["INTERVAL"] = settings.interval
    if settings.trade_quantity_percent is not None:
        update["TRADE_QUANTITY_PERCENT"] = settings.trade_quantity_percent
    if settings.max_open_trades is not None:
        update["MAX_OPEN_TRADES"] = settings.max_open_trades
    if settings.stop_loss_percent is not None:
        update["STOP_LOSS_PERCENT"] = settings.stop_loss_percent
    if settings.take_profit_percent is not None:
        update["TAKE_PROFIT_PERCENT"] = settings.take_profit_percent
    if settings.ema_fast is not None:
        update["EMA_FAST"] = settings.ema_fast
    if settings.ema_slow is not None:
        update["EMA_SLOW"] = settings.ema_slow
    if settings.rsi_period is not None:
        update["RSI_PERIOD"] = settings.rsi_period
    if settings.rsi_overbought is not None:
        update["RSI_OVERBOUGHT"] = settings.rsi_overbought
    if settings.rsi_oversold is not None:
        update["RSI_OVERSOLD"] = settings.rsi_oversold

    if update:
        engine.update_config(update)

    return {"message": "Settings updated successfully"}


@router.post("/settings/test-connection")
def test_connection(settings: SettingsUpdate):
    """Test Binance API connection"""
    client = BinanceClient(
        api_key=settings.api_key or "",
        secret_key=settings.secret_key or "",
        testnet=settings.testnet if settings.testnet is not None else True
    )
    connected = client.test_connection()
    if connected:
        balance = client.get_balance("USDT")
        return {"connected": True, "usdt_balance": balance}
    return {"connected": False, "error": "Could not connect to Binance"}


# ─── Market Data ───────────────────────────────────────────────────────────────

@router.get("/market/{symbol}/price")
def get_price(symbol: str):
    """Get current price for a symbol"""
    price = engine.client.get_ticker_price(symbol.upper())
    if price is None:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return {"symbol": symbol.upper(), "price": price}


@router.get("/market/{symbol}/stats")
def get_market_stats(symbol: str):
    """Get 24h market statistics"""
    stats = engine.client.get_24h_stats(symbol.upper())
    return stats


@router.get("/market/{symbol}/candles")
def get_candles(symbol: str, interval: str = "15m", limit: int = 100):
    """Get OHLCV candle data"""
    df = engine.client.get_klines(symbol.upper(), interval, limit)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available")
    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].to_dict(orient='records')


@router.get("/market/{symbol}/signal")
def get_signal(symbol: str):
    """Get current AI signal for a symbol"""
    from bot.indicators import generate_ai_signal
    df = engine.client.get_klines(symbol.upper(), engine.interval, 200)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available")
    signal = generate_ai_signal(df, engine.config)
    signal["symbol"] = symbol.upper()
    return signal


# ─── Trades ────────────────────────────────────────────────────────────────────

@router.get("/trades/open")
def get_open_trades():
    """Get all open trades"""
    return engine.trade_manager.get_open_trades()


@router.get("/trades/history")
def get_trade_history(limit: int = 50):
    """Get closed trade history"""
    return engine.trade_manager.get_trade_history(limit)


@router.get("/trades/stats")
def get_trade_stats():
    """Get performance statistics"""
    stats = engine.trade_manager.get_stats()
    balance = engine.client.get_balance("USDT")
    stats["usdt_balance"] = balance
    return stats


@router.post("/trades/manual")
async def manual_trade(req: ManualTradeRequest):
    """Execute a manual trade"""
    symbol = req.symbol.upper()
    price = engine.client.get_ticker_price(symbol)
    if not price:
        raise HTTPException(status_code=404, detail="Could not get price")

    if req.side.upper() == "BUY":
        from bot.indicators import generate_ai_signal
        df = engine.client.get_klines(symbol, engine.interval, 200)
        signal = generate_ai_signal(df, engine.config)
        signal["price"] = price
        trade = engine.trade_manager.execute_buy(symbol, signal)
        if trade:
            return {"message": "Buy order placed", "trade": trade}
        raise HTTPException(status_code=400, detail="Could not execute buy")

    elif req.side.upper() == "SELL":
        open_trades = [
            t for t in engine.trade_manager.get_open_trades()
            if t["symbol"] == symbol
        ]
        if not open_trades:
            raise HTTPException(status_code=404, detail="No open trades for this symbol")
        results = []
        for trade in open_trades:
            result = engine.trade_manager.execute_sell(trade["id"], price, "MANUAL")
            if result:
                results.append(result)
        return {"message": f"Closed {len(results)} trade(s)", "trades": results}

    raise HTTPException(status_code=400, detail="Invalid side. Use BUY or SELL")


@router.delete("/trades/{trade_id}")
def close_trade(trade_id: str):
    """Close a specific trade"""
    trade = None
    for t in engine.trade_manager.trades:
        if t["id"] == trade_id and t["status"] == "OPEN":
            trade = t
            break
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    price = engine.client.get_ticker_price(trade["symbol"])
    if not price:
        raise HTTPException(status_code=400, detail="Could not get current price")

    result = engine.trade_manager.execute_sell(trade_id, price, "MANUAL_CLOSE")
    if result:
        return {"message": "Trade closed", "trade": result}
    raise HTTPException(status_code=400, detail="Could not close trade")
