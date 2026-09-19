"""
Telegram Notifier
Sends trade alerts to Telegram bot
"""

import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id   = chat_id
        self.enabled   = bool(bot_token and chat_id)
        self.base_url  = f"https://api.telegram.org/bot{bot_token}"

    def send(self, message: str) -> bool:
        """Send a message to Telegram chat"""
        if not self.enabled:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id":    self.chat_id,
                    "text":       message,
                    "parse_mode": "HTML",
                },
                timeout=8,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")
            return False

    def trade_opened(self, trade: dict):
        """Alert on new BUY"""
        if not self.enabled:
            return
        symbol    = trade.get("symbol", "?")
        price     = trade.get("entry_price", 0)
        qty       = trade.get("quantity", 0)
        sl        = trade.get("stop_loss", "—")
        tp        = trade.get("take_profit", "—")
        conf      = trade.get("confidence", 0)
        msg = (
            f"🟢 <b>BUY EXECUTED</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"📌 Symbol:      <b>{symbol}</b>\n"
            f"💰 Entry:       <b>${price:,.4f}</b>\n"
            f"📦 Quantity:    <b>{qty}</b>\n"
            f"🛑 Stop Loss:   <b>${sl}</b>\n"
            f"🎯 Take Profit: <b>${tp}</b>\n"
            f"🤖 Confidence:  <b>{conf}%</b>\n"
            f"🕐 Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        self.send(msg)

    def trade_closed(self, trade: dict):
        """Alert on closed trade"""
        if not self.enabled:
            return
        symbol  = trade.get("symbol", "?")
        entry   = trade.get("entry_price", 0)
        exit_p  = trade.get("exit_price", 0)
        pnl     = trade.get("pnl", 0) or 0
        pnl_pct = trade.get("pnl_percent", 0) or 0
        reason  = trade.get("close_reason", "SIGNAL")

        emoji = "🟢" if pnl >= 0 else "🔴"
        reason_map = {
            "TAKE_PROFIT": "🎯 Take Profit",
            "STOP_LOSS":   "🛑 Stop Loss",
            "TRAILING_STOP": "📉 Trailing Stop",
            "SIGNAL":      "📊 Signal",
            "MANUAL":      "👤 Manual",
            "MANUAL_CLOSE":"👤 Manual",
        }
        reason_label = reason_map.get(reason, reason)

        msg = (
            f"{emoji} <b>TRADE CLOSED</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"📌 Symbol:  <b>{symbol}</b>\n"
            f"📥 Entry:   <b>${entry:,.4f}</b>\n"
            f"📤 Exit:    <b>${exit_p:,.4f}</b>\n"
            f"💵 P&L:     <b>{'+' if pnl>=0 else ''}{pnl:.4f} USDT</b>\n"
            f"📈 P&L %:   <b>{'+' if pnl_pct>=0 else ''}{pnl_pct:.2f}%</b>\n"
            f"📋 Reason:  {reason_label}\n"
            f"🕐 Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        self.send(msg)

    def bot_started(self, symbols: list, interval: str):
        """Alert when bot starts"""
        if not self.enabled:
            return
        syms = ", ".join(symbols)
        self.send(
            f"🚀 <b>Trading Bot STARTED</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"📊 Symbols:  <b>{syms}</b>\n"
            f"⏱ Interval: <b>{interval}</b>\n"
            f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

    def bot_stopped(self):
        """Alert when bot stops"""
        if not self.enabled:
            return
        self.send(
            f"🛑 <b>Trading Bot STOPPED</b>\n"
            f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

    def error_alert(self, message: str):
        """Alert on critical error"""
        if not self.enabled:
            return
        self.send(f"⚠️ <b>BOT ERROR</b>\n<code>{message}</code>")
