"""
Bot Engine — Multi-Symbol Trading Loop
Improvements over v1:
  - Trades multiple symbols in parallel (asyncio tasks per symbol)
  - Real-time Binance WebSocket price stream for intra-candle SL/TP
  - Telegram notifications on start/stop/trade events
  - Trailing stop integrated via TradeManager
  - Backtesting endpoint supported via backtester module
"""

import asyncio
import logging
from datetime import datetime
import sys
import os

# Add backend dir to path
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from bot.binance_client   import BinanceClient
from bot.indicators       import generate_ai_signal, generate_mtf_score
from bot.trade_manager    import TradeManager
from bot.notifier         import TelegramNotifier
from bot.email_notifier   import EmailNotifier
from bot.resend_notifier  import ResendNotifier
from bot.discord_notifier import DiscordNotifier
from bot.sentiment        import get_combined_sentiment
from bot.price_stream     import PriceStream
from bot                  import config as cfg
from bot.settings_store   import load_settings, save_settings
from bot.market_data      import get_klines

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self):
        # ── Load config ────────────────────────────────────────────────────────
        self.config = {
            "BINANCE_API_KEY":       cfg.BINANCE_API_KEY,
            "BINANCE_SECRET_KEY":    cfg.BINANCE_SECRET_KEY,
            "TESTNET":               cfg.TESTNET,
            "TRADE_QUANTITY_PERCENT":cfg.TRADE_QUANTITY_PERCENT,
            "MAX_OPEN_TRADES":       cfg.MAX_OPEN_TRADES,
            "STOP_LOSS_PERCENT":     cfg.STOP_LOSS_PERCENT,
            "TAKE_PROFIT_PERCENT":   cfg.TAKE_PROFIT_PERCENT,
            "TRAILING_STOP":         cfg.TRAILING_STOP,
            "TRAILING_STOP_PERCENT": cfg.TRAILING_STOP_PERCENT,
            "EMA_FAST":              cfg.EMA_FAST,
            "EMA_SLOW":              cfg.EMA_SLOW,
            "RSI_PERIOD":            cfg.RSI_PERIOD,
            "RSI_OVERBOUGHT":        cfg.RSI_OVERBOUGHT,
            "RSI_OVERSOLD":          cfg.RSI_OVERSOLD,
            "MACD_FAST":             cfg.MACD_FAST,
            "MACD_SLOW":             cfg.MACD_SLOW,
            "MACD_SIGNAL":           cfg.MACD_SIGNAL,
            "BB_PERIOD":             cfg.BB_PERIOD,
            "BB_STD":                cfg.BB_STD,
            "TELEGRAM_BOT_TOKEN":    cfg.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_CHAT_ID":      cfg.TELEGRAM_CHAT_ID,
            "EMAIL_SENDER":          cfg.EMAIL_SENDER,
            "EMAIL_APP_PASSWORD":    cfg.EMAIL_APP_PASSWORD,
            "EMAIL_RECEIVER":        cfg.EMAIL_RECEIVER,
            "RESEND_API_KEY":        cfg.RESEND_API_KEY,
            "DISCORD_WEBHOOK_URL":   cfg.DISCORD_WEBHOOK_URL,
            "TWILIO_ACCOUNT_SID":    cfg.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN":     cfg.TWILIO_AUTH_TOKEN,
            "TWILIO_FROM_NUMBER":    cfg.TWILIO_FROM_NUMBER,
            "TWILIO_TO_NUMBER":      cfg.TWILIO_TO_NUMBER,
            "DAILY_LOSS_LIMIT_PERCENT": cfg.DAILY_LOSS_LIMIT_PERCENT,
            "SENTIMENT_FILTER":      cfg.SENTIMENT_FILTER,
            "MTF_ENABLED":           cfg.MTF_ENABLED,
        }

        # Override with UI-saved settings
        try:
            saved = load_settings()
            if saved:
                self.config.update(saved)
                logger.info(f"Loaded saved settings: {list(saved.keys())}")
        except Exception as e:
            logger.warning(f"Could not load saved settings: {e}")
            saved = {}

        # Single-symbol legacy support + multi-symbol list
        self.current_symbol  = saved.get("SYMBOL",   cfg.DEFAULT_SYMBOL)
        self.interval        = saved.get("INTERVAL",  cfg.CANDLE_INTERVAL)
        self.active_symbols: list[str] = saved.get(
            "ACTIVE_SYMBOLS", cfg.ACTIVE_SYMBOLS
        )

        # ── Sub-systems ────────────────────────────────────────────────────────
        self._build_client()

        self.notifier = TelegramNotifier(
            self.config.get("TELEGRAM_BOT_TOKEN", ""),
            self.config.get("TELEGRAM_CHAT_ID", ""),
        )

        self.email_notifier = EmailNotifier(
            sender_email   = self.config.get("EMAIL_SENDER", ""),
            app_password   = self.config.get("EMAIL_APP_PASSWORD", ""),
            receiver_email = self.config.get("EMAIL_RECEIVER", ""),
        )

        self.resend_notifier = ResendNotifier(
            api_key        = self.config.get("RESEND_API_KEY", ""),
            receiver_email = self.config.get("EMAIL_RECEIVER", ""),
            sender_email   = self.config.get("EMAIL_SENDER", ""),
        )

        self.discord_notifier = DiscordNotifier(
            webhook_url = self.config.get("DISCORD_WEBHOOK_URL", ""),
        )

        self.trade_manager = TradeManager(
            self.client, self.config, self.notifier,
            self.email_notifier, self.resend_notifier, self.discord_notifier
        )

        # Daily loss tracking
        self._daily_start_balance: float = 0.0
        self._daily_loss_stopped: bool   = False
        self._last_sentiment: dict       = {}

        self.price_stream = PriceStream(
            testnet=self.config.get("TESTNET", True)
        )
        self.price_stream.add_callback(self._on_price_tick)

        self.running      = False
        self.last_signal: dict[str, dict] = {}    # symbol → latest signal
        self.callbacks    = []

        # Per-symbol tasks
        self._symbol_tasks: dict[str, asyncio.Task] = {}

    # ── Client builder ─────────────────────────────────────────────────────────

    def _build_client(self):
        self.client = BinanceClient(
            api_key    = self.config.get("BINANCE_API_KEY",    ""),
            secret_key = self.config.get("BINANCE_SECRET_KEY", ""),
            testnet    = self.config.get("TESTNET", True),
        )

    # ── Config update ──────────────────────────────────────────────────────────

    def update_config(self, new_config: dict):
        self.config.update(new_config)

        if any(k in new_config for k in
               ("BINANCE_API_KEY", "BINANCE_SECRET_KEY", "TESTNET")):
            self._build_client()
            self.trade_manager.client = self.client
            self.price_stream.testnet = self.config.get("TESTNET", True)

        if any(k in new_config for k in
               ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")):
            self.notifier = TelegramNotifier(
                self.config.get("TELEGRAM_BOT_TOKEN", ""),
                self.config.get("TELEGRAM_CHAT_ID", ""),
            )
            self.trade_manager.notifier = self.notifier

        if any(k in new_config for k in
               ("EMAIL_SENDER", "EMAIL_APP_PASSWORD", "EMAIL_RECEIVER")):
            self.email_notifier = EmailNotifier(
                sender_email   = self.config.get("EMAIL_SENDER", ""),
                app_password   = self.config.get("EMAIL_APP_PASSWORD", ""),
                receiver_email = self.config.get("EMAIL_RECEIVER", ""),
            )
            self.trade_manager.email_notifier = self.email_notifier

        if any(k in new_config for k in ("RESEND_API_KEY", "EMAIL_RECEIVER")):
            self.resend_notifier = ResendNotifier(
                api_key        = self.config.get("RESEND_API_KEY", ""),
                receiver_email = self.config.get("EMAIL_RECEIVER", ""),
                sender_email   = self.config.get("EMAIL_SENDER", ""),
            )
            self.trade_manager.resend_notifier = self.resend_notifier

        self.trade_manager.config = self.config

        # Handle active symbols update
        if "ACTIVE_SYMBOLS" in new_config:
            self.active_symbols = new_config["ACTIVE_SYMBOLS"]

        save_settings(new_config)
        logger.info(f"Config updated & saved: {list(new_config.keys())}")

    # ── WebSocket broadcast ────────────────────────────────────────────────────

    def add_callback(self, cb):
        self.callbacks.append(cb)

    async def broadcast(self, data: dict):
        for cb in self.callbacks:
            try:
                await cb(data)
            except Exception:
                pass

    # ── Price tick handler (from Binance WS stream) ────────────────────────────

    async def _on_price_tick(self, symbol: str, price: float):
        """Called on every aggTrade tick — checks SL/TP immediately."""
        closed = self.trade_manager.check_stop_loss_take_profit(symbol, price)
        for trade in closed:
            await self.broadcast({
                "type":   "TRADE_CLOSED",
                "trade":  trade,
                "reason": trade.get("close_reason"),
            })

    # ── Interval helpers ───────────────────────────────────────────────────────

    def get_interval_seconds(self) -> int:
        mapping = {
            "1m": 60, "3m": 180, "5m": 300,
            "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400,
        }
        return mapping.get(self.interval, 900)

    # ── Single symbol cycle ────────────────────────────────────────────────────

    async def run_cycle(self, symbol: str):
        """One analysis + trade cycle for a single symbol."""
        try:
            # ── Daily loss limit check ─────────────────────────────────────────
            if self._daily_loss_stopped:
                logger.warning(f"[{symbol}] Daily loss limit hit — skipping cycle")
                return

            df = self.client.get_klines(symbol, self.interval, cfg.CANDLE_LIMIT)
            if df.empty:
                logger.warning(f"[{symbol}] No candle data")
                return

            current_price = self.client.get_ticker_price(symbol)
            if not current_price:
                current_price = float(df["close"].iloc[-1])

            # ── Daily loss limit ───────────────────────────────────────────────
            await self._check_daily_loss_limit(current_price)
            if self._daily_loss_stopped:
                return

            # ── Multi-Timeframe data ───────────────────────────────────────────
            df_1h = None
            df_4h = None
            if self.config.get("MTF_ENABLED", True):
                try:
                    df_1h = get_klines(symbol, "1h", 100)
                    df_4h = get_klines(symbol, "4h", 100)
                except Exception:
                    pass

            # ── Sentiment filter ───────────────────────────────────────────────
            sentiment = {}
            if self.config.get("SENTIMENT_FILTER", True):
                try:
                    sentiment = get_combined_sentiment(symbol)
                    self._last_sentiment = sentiment
                except Exception:
                    pass

            # ── Generate signal ────────────────────────────────────────────────
            signal = generate_ai_signal(df, self.config, df_1h, df_4h)

            # Apply sentiment adjustment
            if sentiment:
                adj = sentiment.get("score_adjust", 0)
                if adj > 0:
                    signal["buy_score"]  += adj
                    signal["signals"].append(f"Sentiment Bullish (+{adj})")
                elif adj < 0:
                    signal["sell_score"] += abs(adj)
                    signal["signals"].append(f"Sentiment Bearish ({adj})")

            signal["symbol"]    = symbol
            signal["timestamp"] = datetime.utcnow().isoformat()
            signal["sentiment"] = sentiment
            self.last_signal[symbol] = signal

            logger.info(
                f"[{symbol}] ${current_price:.4f} | "
                f"{signal['action']} {signal['confidence']}% | "
                f"RSI:{signal['rsi']:.1f} | "
                f"MTF:{signal.get('mtf', {}).get('mtf_trend', 'N/A') if signal.get('mtf') else 'OFF'}"
            )

            # ── BUY ────────────────────────────────────────────────────────────
            if signal["action"] == "BUY" and signal["confidence"] >= 60:
                # Block if extreme greed sentiment
                fng_signal = sentiment.get("fear_greed", {}).get("signal", "NEUTRAL")
                if fng_signal == "EXTREME_GREED" and self.config.get("SENTIMENT_FILTER", True):
                    logger.info(f"[{symbol}] BUY blocked — Extreme Greed sentiment")
                else:
                    already_open = [t for t in self.trade_manager.get_open_trades()
                                    if t["symbol"] == symbol]
                    if not already_open:
                        trade = self.trade_manager.execute_buy(symbol, signal)
                        if trade:
                            await self.broadcast({
                                "type": "TRADE_EXECUTED", "trade": trade, "signal": signal,
                            })

            # ── SELL ───────────────────────────────────────────────────────────
            elif signal["action"] == "SELL" and signal["confidence"] >= 60:
                open_for_sym = [t for t in self.trade_manager.get_open_trades()
                                if t["symbol"] == symbol]
                for trade in open_for_sym:
                    result = self.trade_manager.execute_sell(trade["id"], current_price, "SIGNAL")
                    if result:
                        await self.broadcast({
                            "type": "TRADE_CLOSED", "trade": result, "signal": signal,
                        })

            # ── Broadcast state ────────────────────────────────────────────────
            await self.broadcast({
                "type":        "SIGNAL_UPDATE",
                "symbol":      symbol,
                "signal":      signal,
                "stats":       self.trade_manager.get_stats(),
                "open_trades": self.trade_manager.get_open_trades(),
                "balance":     self.client.get_balance("USDT"),
                "sentiment":   sentiment,
            })

        except Exception as e:
            logger.error(f"[{symbol}] Cycle error: {e}")

    # ── Per-symbol loop ────────────────────────────────────────────────────────

    async def _symbol_loop(self, symbol: str):
        """Runs indefinitely for one symbol — one candle-interval per cycle."""
        logger.info(f"[{symbol}] Loop started")
        while self.running:
            await self.run_cycle(symbol)
            sleep_sec = self.get_interval_seconds()
            logger.info(f"[{symbol}] Next cycle in {sleep_sec}s")
            await asyncio.sleep(sleep_sec)
        logger.info(f"[{symbol}] Loop stopped")

    # ── Start / Stop ───────────────────────────────────────────────────────────

    async def start(self):
        """Start all symbol loops + price stream."""
        self.running = True
        self.trade_manager.bot_running = True

        symbols = self._resolve_symbols()
        logger.info(f"🚀 Bot started — symbols: {symbols} | interval: {self.interval}")

        # Start real-time price stream for all symbols
        try:
            await self.price_stream.subscribe_many(symbols)
        except Exception as e:
            logger.warning(f"Price stream failed to start: {e} (SL/TP will use candle-level checking)")

        # Launch a loop task per symbol
        for sym in symbols:
            if sym not in self._symbol_tasks or self._symbol_tasks[sym].done():
                task = asyncio.create_task(self._symbol_loop(sym), name=f"loop-{sym}")
                self._symbol_tasks[sym] = task

        # Init daily loss tracking
        try:
            self._daily_start_balance = self.client.get_balance("USDT")
            self._daily_loss_stopped  = False
        except Exception as e:
            logger.warning(f"Could not fetch initial balance: {e}")
            self._daily_start_balance = 0.0

        # Notifications — wrapped individually so one failure doesn't crash start
        try: self.notifier.bot_started(symbols, self.interval)
        except Exception: pass
        try: self.email_notifier.bot_started(symbols, self.interval)
        except Exception: pass
        try: self.resend_notifier.bot_started(symbols, self.interval)
        except Exception: pass
        try: self.discord_notifier.bot_started(symbols, self.interval)
        except Exception: pass

        # Wait for all tasks to finish (they run until self.running = False)
        await asyncio.gather(*self._symbol_tasks.values(), return_exceptions=True)

    def stop(self):
        """Stop all symbol loops + price stream."""
        self.running = False
        self.trade_manager.bot_running = False
        for task in self._symbol_tasks.values():
            if not task.done():
                task.cancel()
        self._symbol_tasks.clear()
        # Stop price stream (fire-and-forget via create_task)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.price_stream.stop_all())
        except Exception:
            pass
        self.notifier.bot_stopped()
        self.email_notifier.bot_stopped()
        self.resend_notifier.bot_stopped()
        self.discord_notifier.bot_stopped()
        logger.info("🛑 Bot stopped")

    def _resolve_symbols(self) -> list[str]:
        """Return the active symbol list (multi or single)."""
        if self.config.get("MULTI_SYMBOL_MODE", False):
            return [s.upper() for s in self.active_symbols]
        return [self.current_symbol.upper()]

    async def _check_daily_loss_limit(self, current_price: float = None):
        """Check if daily loss limit has been hit — auto-stop bot if so."""
        limit_pct = self.config.get("DAILY_LOSS_LIMIT_PERCENT", 5.0)
        if limit_pct <= 0:
            return
        try:
            balance = self.client.get_balance("USDT")
            if self._daily_start_balance <= 0:
                self._daily_start_balance = balance
                return
            loss_pct = ((self._daily_start_balance - balance) / self._daily_start_balance) * 100
            if loss_pct >= limit_pct:
                logger.warning(f"🛑 Daily loss limit hit: {loss_pct:.2f}% >= {limit_pct:.2f}% — stopping bot")
                self._daily_loss_stopped = True
                self.stop()
                # Send alerts
                msg = f"⚠️ Daily loss limit hit: -{loss_pct:.2f}% | Bot stopped automatically"
                self.notifier.send(msg)
                self.resend_notifier.send("⚠️ Daily Loss Limit Hit — Bot Stopped", f"<p>{msg}</p>")
                self.discord_notifier.daily_loss_alert(loss_pct, limit_pct)
                await self.broadcast({
                    "type": "DAILY_LOSS_LIMIT",
                    "loss_pct": loss_pct,
                    "limit_pct": limit_pct,
                })
        except Exception as e:
            logger.debug(f"Daily loss check error: {e}")

    # ── Status ─────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "running":        self.running,
            "symbol":         self.current_symbol,
            "active_symbols": self._resolve_symbols(),
            "interval":       self.interval,
            "testnet":        self.config.get("TESTNET", True),
            "multi_symbol":   self.config.get("MULTI_SYMBOL_MODE", False),
            "last_signal":    self.last_signal,
            "stats":          self.trade_manager.get_stats(),
            "open_trades":    self.trade_manager.get_open_trades(),
        }


# Global singleton
engine = TradingEngine()
