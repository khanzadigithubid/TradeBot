"""
Bot Engine - Main Loop
Runs continuously, fetches market data, generates AI signals, executes trades
"""

import asyncio
import time
import logging
from datetime import datetime
from bot.binance_client import BinanceClient
from bot.indicators import generate_ai_signal
from bot.trade_manager import TradeManager
from bot import config as cfg
from bot.settings_store import load_settings, save_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self):
        # Start with defaults from config.py
        self.config = {
            "BINANCE_API_KEY": cfg.BINANCE_API_KEY,
            "BINANCE_SECRET_KEY": cfg.BINANCE_SECRET_KEY,
            "TESTNET": cfg.TESTNET,
            "TRADE_QUANTITY_PERCENT": cfg.TRADE_QUANTITY_PERCENT,
            "MAX_OPEN_TRADES": cfg.MAX_OPEN_TRADES,
            "STOP_LOSS_PERCENT": cfg.STOP_LOSS_PERCENT,
            "TAKE_PROFIT_PERCENT": cfg.TAKE_PROFIT_PERCENT,
            "EMA_FAST": cfg.EMA_FAST,
            "EMA_SLOW": cfg.EMA_SLOW,
            "RSI_PERIOD": cfg.RSI_PERIOD,
            "RSI_OVERBOUGHT": cfg.RSI_OVERBOUGHT,
            "RSI_OVERSOLD": cfg.RSI_OVERSOLD,
            "MACD_FAST": cfg.MACD_FAST,
            "MACD_SLOW": cfg.MACD_SLOW,
            "MACD_SIGNAL": cfg.MACD_SIGNAL,
            "BB_PERIOD": cfg.BB_PERIOD,
            "BB_STD": cfg.BB_STD,
        }

        # Override with any saved UI settings (persistent across restarts)
        saved = load_settings()
        if saved:
            self.config.update(saved)
            logger.info(f"Loaded saved settings: {list(saved.keys())}")

        self.current_symbol = saved.get("SYMBOL", cfg.DEFAULT_SYMBOL)
        self.interval = saved.get("INTERVAL", cfg.CANDLE_INTERVAL)

        self.client = BinanceClient(
            api_key=self.config.get("BINANCE_API_KEY", ""),
            secret_key=self.config.get("BINANCE_SECRET_KEY", ""),
            testnet=self.config.get("TESTNET", True)
        )

        self.trade_manager = TradeManager(self.client, self.config)
        self.running = False
        self.last_signal = {}
        self.callbacks = []

    def update_config(self, new_config: dict):
        """Update bot configuration at runtime and persist to disk"""
        self.config.update(new_config)

        # Rebuild Binance client if keys or testnet changed
        if any(k in new_config for k in ("BINANCE_API_KEY", "BINANCE_SECRET_KEY", "TESTNET")):
            self.client = BinanceClient(
                api_key=self.config.get("BINANCE_API_KEY", ""),
                secret_key=self.config.get("BINANCE_SECRET_KEY", ""),
                testnet=self.config.get("TESTNET", True)
            )
            self.trade_manager.client = self.client

        self.trade_manager.config = self.config

        # Persist to disk so settings survive restart
        save_settings(new_config)
        logger.info(f"Config updated & saved: {list(new_config.keys())}")

    def add_callback(self, callback):
        """Add WebSocket broadcast callback"""
        self.callbacks.append(callback)

    async def broadcast(self, data: dict):
        """Broadcast data to all WebSocket clients"""
        for cb in self.callbacks:
            try:
                await cb(data)
            except Exception:
                pass

    def get_interval_seconds(self) -> int:
        """Convert candle interval to seconds"""
        mapping = {
            "1m": 60, "3m": 180, "5m": 300,
            "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400
        }
        return mapping.get(self.interval, 900)

    async def run_cycle(self):
        """Single bot cycle - analyze and trade"""
        try:
            symbol = self.current_symbol

            # 1. Fetch market data
            df = self.client.get_klines(symbol, self.interval, cfg.CANDLE_LIMIT)
            if df.empty:
                logger.warning(f"No data for {symbol}")
                return

            # 2. Get current price
            current_price = self.client.get_ticker_price(symbol)
            if not current_price:
                current_price = float(df['close'].iloc[-1])

            # 3. Generate AI signal
            signal = generate_ai_signal(df, self.config)
            signal["symbol"] = symbol
            signal["timestamp"] = datetime.utcnow().isoformat()
            self.last_signal = signal

            logger.info(
                f"[{symbol}] Price: {current_price:.4f} | "
                f"Signal: {signal['action']} | "
                f"Confidence: {signal['confidence']}% | "
                f"RSI: {signal['rsi']:.1f}"
            )

            # 4. Check stop loss / take profit
            self.trade_manager.check_stop_loss_take_profit(symbol, current_price)

            # 5. Execute trade based on signal
            if signal["action"] == "BUY" and signal["confidence"] >= 60:
                # Check if already have open trade for this symbol
                open_for_symbol = [
                    t for t in self.trade_manager.get_open_trades()
                    if t["symbol"] == symbol
                ]
                if not open_for_symbol:
                    trade = self.trade_manager.execute_buy(symbol, signal)
                    if trade:
                        logger.info(f"✅ BUY executed: {symbol} @ {current_price} | SL: {trade['stop_loss']} | TP: {trade['take_profit']}")
                        await self.broadcast({
                            "type": "TRADE_EXECUTED",
                            "trade": trade,
                            "signal": signal
                        })

            elif signal["action"] == "SELL" and signal["confidence"] >= 60:
                # Close all open buy trades for this symbol
                open_trades = [
                    t for t in self.trade_manager.get_open_trades()
                    if t["symbol"] == symbol
                ]
                for trade in open_trades:
                    result = self.trade_manager.execute_sell(trade["id"], current_price, "SIGNAL")
                    if result:
                        logger.info(f"✅ SELL executed: {symbol} @ {current_price} | PnL: {result['pnl']} USDT")
                        await self.broadcast({
                            "type": "TRADE_CLOSED",
                            "trade": result,
                            "signal": signal
                        })

            # 6. Broadcast current state
            await self.broadcast({
                "type": "SIGNAL_UPDATE",
                "signal": signal,
                "stats": self.trade_manager.get_stats(),
                "open_trades": self.trade_manager.get_open_trades(),
                "balance": self.client.get_balance("USDT"),
            })

        except Exception as e:
            logger.error(f"Error in bot cycle: {e}")

    async def start(self):
        """Start the trading bot"""
        self.running = True
        self.trade_manager.bot_running = True
        logger.info("🚀 Trading Bot Started!")
        logger.info(f"Symbol: {self.current_symbol} | Interval: {self.interval} | Testnet: {cfg.TESTNET}")

        while self.running:
            await self.run_cycle()
            sleep_time = self.get_interval_seconds()
            logger.info(f"⏳ Next cycle in {sleep_time}s...")
            await asyncio.sleep(sleep_time)

    def stop(self):
        """Stop the trading bot"""
        self.running = False
        self.trade_manager.bot_running = False
        logger.info("🛑 Trading Bot Stopped!")

    def get_status(self) -> dict:
        """Get current bot status"""
        return {
            "running": self.running,
            "symbol": self.current_symbol,
            "interval": self.interval,
            "testnet": self.config.get("TESTNET", True),
            "last_signal": self.last_signal,
            "stats": self.trade_manager.get_stats(),
            "open_trades": self.trade_manager.get_open_trades(),
        }


# Global engine instance
engine = TradingEngine()
