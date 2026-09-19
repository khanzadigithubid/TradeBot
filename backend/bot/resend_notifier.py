"""
Resend Email Notifier
Uses Resend API (works on Render free tier — no SMTP needed)
"""

import requests
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
PST = timezone(timedelta(hours=5))

def now_pkt() -> str:
    return datetime.now(PST).strftime("%Y-%m-%d %I:%M %p PKT")


class ResendNotifier:
    def __init__(self, api_key: str, receiver_email: str, sender_email: str = "onboarding@resend.dev"):
        self.api_key        = api_key
        self.receiver_email = receiver_email
        self.sender_email   = sender_email if sender_email else "onboarding@resend.dev"
        self.enabled        = bool(api_key and receiver_email)

    def send(self, subject: str, html: str) -> bool:
        if not self.enabled:
            return False
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from":    self.sender_email,
                    "to":      [self.receiver_email],
                    "subject": subject,
                    "html":    html,
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning(f"Resend failed: {resp.status_code} {resp.text}")
            return False
        except Exception as e:
            logger.warning(f"Resend error: {e}")
            return False

    def trade_opened(self, trade: dict):
        if not self.enabled: return
        symbol = trade.get("symbol", "?")
        price  = trade.get("entry_price", 0)
        qty    = trade.get("quantity", 0)
        sl     = trade.get("stop_loss", "—")
        tp     = trade.get("take_profit", "—")
        conf   = trade.get("confidence", 0)
        self.send(
            f"🟢 BUY Executed — {symbol} @ ${price:,.4f}",
            f"""<div style="font-family:Arial,sans-serif;max-width:480px;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
              <h2 style="color:#26a69a;margin:0 0 16px">🟢 BUY EXECUTED</h2>
              <table style="width:100%;border-collapse:collapse">
                <tr><td style="padding:6px 0;color:#787b86">Symbol</td>      <td style="font-weight:700;color:#fff">{symbol}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Entry Price</td> <td style="font-weight:700;color:#fff">${price:,.4f}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Quantity</td>    <td style="font-weight:700;color:#fff">{qty}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Stop Loss</td>   <td style="font-weight:700;color:#ef5350">${sl}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Take Profit</td> <td style="font-weight:700;color:#26a69a">${tp}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Confidence</td>  <td style="font-weight:700;color:#4c8dff">{conf}%</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Time</td>        <td style="color:#787b86">{now_pkt()}</td></tr>
              </table>
            </div>"""
        )

    def trade_closed(self, trade: dict):
        if not self.enabled: return
        symbol  = trade.get("symbol", "?")
        entry   = trade.get("entry_price", 0)
        exit_p  = trade.get("exit_price", 0)
        pnl     = trade.get("pnl", 0) or 0
        pnl_pct = trade.get("pnl_percent", 0) or 0
        reason  = trade.get("close_reason", "SIGNAL")
        is_win  = pnl >= 0
        color   = "#26a69a" if is_win else "#ef5350"
        emoji   = "🟢" if is_win else "🔴"
        reason_map = {
            "TAKE_PROFIT": "🎯 Take Profit", "STOP_LOSS": "🛑 Stop Loss",
            "TRAILING_STOP": "📉 Trailing Stop", "SIGNAL": "📊 Signal",
            "MANUAL": "👤 Manual", "MANUAL_CLOSE": "👤 Manual",
        }
        self.send(
            f"{emoji} Trade Closed — {symbol} | P&L: {'+' if is_win else ''}{pnl:.4f} USDT",
            f"""<div style="font-family:Arial,sans-serif;max-width:480px;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
              <h2 style="color:{color};margin:0 0 16px">{emoji} TRADE CLOSED</h2>
              <table style="width:100%;border-collapse:collapse">
                <tr><td style="padding:6px 0;color:#787b86">Symbol</td>  <td style="font-weight:700;color:#fff">{symbol}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Entry</td>   <td style="font-weight:700;color:#fff">${entry:,.4f}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Exit</td>    <td style="font-weight:700;color:#fff">${exit_p:,.4f}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">P&L</td>     <td style="font-weight:800;color:{color}">{'+' if is_win else ''}{pnl:.4f} USDT</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">P&L %</td>   <td style="font-weight:800;color:{color}">{'+' if is_win else ''}{pnl_pct:.2f}%</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Reason</td>  <td style="font-weight:700;color:#fff">{reason_map.get(reason, reason)}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Time</td>    <td style="color:#787b86">{now_pkt()}</td></tr>
              </table>
            </div>"""
        )

    def bot_started(self, symbols: list, interval: str):
        if not self.enabled: return
        self.send(
            f"🚀 Trading Bot Started — {', '.join(symbols)}",
            f"""<div style="font-family:Arial,sans-serif;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
              <h2 style="color:#26a69a">🚀 Bot Started</h2>
              <p>Symbols: <b>{', '.join(symbols)}</b> | Interval: <b>{interval}</b></p>
              <p style="color:#787b86">{now_pkt()}</p>
            </div>"""
        )

    def bot_stopped(self):
        if not self.enabled: return
        self.send(
            "🛑 Trading Bot Stopped",
            f"""<div style="font-family:Arial,sans-serif;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
              <h2 style="color:#ef5350">🛑 Bot Stopped</h2>
              <p style="color:#787b86">{now_pkt()}</p>
            </div>"""
        )

    def test_email(self) -> bool:
        return self.send(
            "✅ Trading Bot — Email Connected!",
            """<div style="font-family:Arial,sans-serif;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
              <h2 style="color:#26a69a">✅ Resend Email Active</h2>
              <p>Your trading bot email alerts are working correctly via Resend.</p>
            </div>"""
        )
