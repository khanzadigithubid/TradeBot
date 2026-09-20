"""
Discord Webhook Notifier
Sends trade alerts to a Discord channel via webhook
"""

import requests
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
PST = timezone(timedelta(hours=5))

def now_pkt() -> str:
    return datetime.now(PST).strftime("%Y-%m-%d %I:%M %p PKT")


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.enabled     = bool(webhook_url)

    def send(self, content: str = None, embeds: list = None) -> bool:
        if not self.enabled:
            return False
        try:
            payload = {}
            if content: payload["content"] = content
            if embeds:  payload["embeds"]  = embeds
            r = requests.post(self.webhook_url, json=payload, timeout=8)
            return r.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"Discord send failed: {e}")
            return False

    def trade_opened(self, trade: dict):
        if not self.enabled: return
        symbol = trade.get("symbol", "?")
        price  = trade.get("entry_price", 0)
        sl     = trade.get("stop_loss", "—")
        tp     = trade.get("take_profit", "—")
        conf   = trade.get("confidence", 0)
        self.send(embeds=[{
            "title":       "🟢 BUY EXECUTED",
            "color":       3066993,
            "fields": [
                {"name": "Symbol",      "value": f"**{symbol}**",          "inline": True},
                {"name": "Entry",       "value": f"**${price:,.4f}**",     "inline": True},
                {"name": "Confidence",  "value": f"**{conf}%**",           "inline": True},
                {"name": "Stop Loss",   "value": f"🛑 ${sl}",              "inline": True},
                {"name": "Take Profit", "value": f"🎯 ${tp}",              "inline": True},
                {"name": "Time",        "value": now_pkt(),                 "inline": True},
            ],
            "footer": {"text": "AI Trading Bot"}
        }])

    def trade_closed(self, trade: dict):
        if not self.enabled: return
        symbol  = trade.get("symbol", "?")
        entry   = trade.get("entry_price", 0)
        exit_p  = trade.get("exit_price", 0)
        pnl     = trade.get("pnl", 0) or 0
        pnl_pct = trade.get("pnl_percent", 0) or 0
        reason  = trade.get("close_reason", "SIGNAL")
        is_win  = pnl >= 0
        color   = 3066993 if is_win else 15158332
        emoji   = "🟢" if is_win else "🔴"
        self.send(embeds=[{
            "title": f"{emoji} TRADE CLOSED",
            "color": color,
            "fields": [
                {"name": "Symbol", "value": f"**{symbol}**",                                   "inline": True},
                {"name": "P&L",    "value": f"**{'+' if is_win else ''}{pnl:.4f} USDT**",      "inline": True},
                {"name": "P&L %",  "value": f"**{'+' if is_win else ''}{pnl_pct:.2f}%**",      "inline": True},
                {"name": "Entry",  "value": f"${entry:,.4f}",                                   "inline": True},
                {"name": "Exit",   "value": f"${exit_p:,.4f}",                                  "inline": True},
                {"name": "Reason", "value": reason,                                              "inline": True},
                {"name": "Time",   "value": now_pkt(),                                           "inline": False},
            ],
            "footer": {"text": "AI Trading Bot"}
        }])

    def bot_started(self, symbols: list, interval: str):
        if not self.enabled: return
        self.send(embeds=[{
            "title": "🚀 Trading Bot Started",
            "color": 3447003,
            "fields": [
                {"name": "Symbols",  "value": ", ".join(symbols), "inline": True},
                {"name": "Interval", "value": interval,           "inline": True},
                {"name": "Time",     "value": now_pkt(),           "inline": False},
            ]
        }])

    def bot_stopped(self):
        if not self.enabled: return
        self.send(embeds=[{
            "title": "🛑 Trading Bot Stopped",
            "color": 15158332,
            "fields": [{"name": "Time", "value": now_pkt()}]
        }])

    def daily_loss_alert(self, loss_pct: float, limit_pct: float):
        if not self.enabled: return
        self.send(embeds=[{
            "title": "⚠️ DAILY LOSS LIMIT HIT — Bot Stopped",
            "color": 15158332,
            "description": f"Daily loss **{loss_pct:.2f}%** exceeded limit **{limit_pct:.2f}%**\nBot has been automatically stopped.",
            "footer": {"text": now_pkt()}
        }])

    def sentiment_alert(self, sentiment: dict):
        if not self.enabled: return
        fng = sentiment.get("fear_greed", {})
        self.send(embeds=[{
            "title": "📊 Market Sentiment Update",
            "color": 10181046,
            "fields": [
                {"name": "Fear & Greed", "value": f"**{fng.get('value', 50)}** — {fng.get('category', 'Neutral')}", "inline": True},
                {"name": "Overall",      "value": sentiment.get("overall", "NEUTRAL"),                               "inline": True},
            ]
        }])

    def test_discord(self) -> bool:
        return self.send(embeds=[{
            "title": "✅ Discord Connected!",
            "color": 3066993,
            "description": "Your trading bot Discord notifications are working correctly.",
            "footer": {"text": now_pkt()}
        }])
