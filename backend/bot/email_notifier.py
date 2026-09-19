"""
Email Notifier
Sends trade alerts via Gmail SMTP
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# Pakistan Standard Time = UTC+5
PST = timezone(timedelta(hours=5))

def now_pst() -> str:
    return datetime.now(PST).strftime("%Y-%m-%d %I:%M %p PKT")

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, sender_email: str, app_password: str, receiver_email: str):
        self.sender_email   = sender_email
        self.app_password   = app_password
        self.receiver_email = receiver_email
        self.enabled        = bool(sender_email and app_password and receiver_email)

    def send(self, subject: str, html_body: str) -> bool:
        """Send an HTML email via Gmail SMTP"""
        if not self.enabled:
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.sender_email
            msg["To"]      = self.receiver_email
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, self.receiver_email, msg.as_string())
            return True
        except Exception as e:
            logger.warning(f"Email send failed: {e}")
            return False

    # ── Trade alerts ───────────────────────────────────────────────────────────

    def trade_opened(self, trade: dict):
        if not self.enabled:
            return
        symbol  = trade.get("symbol", "?")
        price   = trade.get("entry_price", 0)
        qty     = trade.get("quantity", 0)
        sl      = trade.get("stop_loss", "—")
        tp      = trade.get("take_profit", "—")
        conf    = trade.get("confidence", 0)
        now     = now_pst()

        subject = f"🟢 BUY Executed — {symbol} @ ${price:,.4f}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
          <h2 style="color:#26a69a;margin:0 0 16px">🟢 BUY EXECUTED</h2>
          <table style="width:100%;border-collapse:collapse">
            <tr><td style="padding:6px 0;color:#787b86">Symbol</td>      <td style="font-weight:700;color:#fff">{symbol}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Entry Price</td> <td style="font-weight:700;color:#fff">${price:,.4f}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Quantity</td>    <td style="font-weight:700;color:#fff">{qty}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Stop Loss</td>   <td style="font-weight:700;color:#ef5350">${sl}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Take Profit</td> <td style="font-weight:700;color:#26a69a">${tp}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Confidence</td>  <td style="font-weight:700;color:#4c8dff">{conf}%</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Time</td>        <td style="color:#787b86">{now}</td></tr>
          </table>
        </div>
        """
        self.send(subject, html)

    def trade_closed(self, trade: dict):
        if not self.enabled:
            return
        symbol   = trade.get("symbol", "?")
        entry    = trade.get("entry_price", 0)
        exit_p   = trade.get("exit_price", 0)
        pnl      = trade.get("pnl", 0) or 0
        pnl_pct  = trade.get("pnl_percent", 0) or 0
        reason   = trade.get("close_reason", "SIGNAL")
        now      = now_pst()

        is_win   = pnl >= 0
        color    = "#26a69a" if is_win else "#ef5350"
        emoji    = "🟢" if is_win else "🔴"
        pnl_str  = f"{'+' if is_win else ''}{pnl:.4f} USDT"
        pct_str  = f"{'+' if is_win else ''}{pnl_pct:.2f}%"

        reason_map = {
            "TAKE_PROFIT":   "🎯 Take Profit",
            "STOP_LOSS":     "🛑 Stop Loss",
            "TRAILING_STOP": "📉 Trailing Stop",
            "SIGNAL":        "📊 Signal",
            "MANUAL":        "👤 Manual",
            "MANUAL_CLOSE":  "👤 Manual",
        }
        reason_label = reason_map.get(reason, reason)

        subject = f"{emoji} Trade Closed — {symbol} | P&L: {pnl_str}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
          <h2 style="color:{color};margin:0 0 16px">{emoji} TRADE CLOSED</h2>
          <table style="width:100%;border-collapse:collapse">
            <tr><td style="padding:6px 0;color:#787b86">Symbol</td>     <td style="font-weight:700;color:#fff">{symbol}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Entry</td>      <td style="font-weight:700;color:#fff">${entry:,.4f}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Exit</td>       <td style="font-weight:700;color:#fff">${exit_p:,.4f}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">P&L</td>        <td style="font-weight:800;color:{color}">{pnl_str}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">P&L %</td>      <td style="font-weight:800;color:{color}">{pct_str}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Reason</td>     <td style="font-weight:700;color:#fff">{reason_label}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Time</td>       <td style="color:#787b86">{now}</td></tr>
          </table>
        </div>
        """
        self.send(subject, html)

    def bot_started(self, symbols: list, interval: str):
        if not self.enabled:
            return
        syms = ", ".join(symbols)
        now  = now_pst()
        subject = f"🚀 Trading Bot Started — {syms}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
          <h2 style="color:#26a69a;margin:0 0 16px">🚀 Bot Started</h2>
          <table style="width:100%;border-collapse:collapse">
            <tr><td style="padding:6px 0;color:#787b86">Symbols</td>   <td style="font-weight:700;color:#fff">{syms}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Interval</td>  <td style="font-weight:700;color:#fff">{interval}</td></tr>
            <tr><td style="padding:6px 0;color:#787b86">Time</td>      <td style="color:#787b86">{now}</td></tr>
          </table>
        </div>
        """
        self.send(subject, html)

    def bot_stopped(self):
        if not self.enabled:
            return
        now = now_pst()
        self.send(
            "🛑 Trading Bot Stopped",
            f"""<div style="font-family:Arial,sans-serif;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
            <h2 style="color:#ef5350">🛑 Bot Stopped</h2>
            <p style="color:#787b86">{now}</p></div>"""
        )

    def test_email(self) -> bool:
        """Send a test email to verify configuration"""
        return self.send(
            "✅ Trading Bot — Email Connected!",
            """<div style="font-family:Arial,sans-serif;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
            <h2 style="color:#26a69a">✅ Email Notifications Active</h2>
            <p>Your trading bot email alerts are working correctly.</p>
            <p style="color:#787b86">You will receive alerts for every trade execution, stop loss, and take profit.</p>
            </div>"""
        )
