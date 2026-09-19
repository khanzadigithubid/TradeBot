"""
Trading Bot Configuration
Loads sensitive values from .env — NEVER hardcode API keys here
"""

import os
from pathlib import Path

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass  # python-dotenv not installed; fall back to OS env vars

# ── Binance API ────────────────────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
TESTNET            = os.getenv("TESTNET", "True").lower() not in ("false", "0", "no")

# ── Telegram Notifications ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Email Notifications ────────────────────────────────────────────────────────
EMAIL_SENDER       = os.getenv("EMAIL_SENDER", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
EMAIL_RECEIVER     = os.getenv("EMAIL_RECEIVER", "")

# ── Resend Email (works on Render) ─────────────────────────────────────────────
RESEND_API_KEY     = os.getenv("RESEND_API_KEY", "")

# ── Trading Settings ───────────────────────────────────────────────────────────
DEFAULT_SYMBOL          = "BTCUSDT"
TRADE_QUANTITY_PERCENT  = 10      # Portfolio ka kitna % ek trade mein lagao
MAX_OPEN_TRADES         = 3       # Ek waqt mein kitni trades open rakhein

# ── Risk Management ────────────────────────────────────────────────────────────
STOP_LOSS_PERCENT    = 2.0        # 2% stop loss
TAKE_PROFIT_PERCENT  = 4.0        # 4% take profit
TRAILING_STOP        = True       # Trailing stop loss enable
TRAILING_STOP_PERCENT = 1.0       # Trail by 1% below peak

# ── AI Strategy Settings ───────────────────────────────────────────────────────
EMA_FAST      = 9
EMA_SLOW      = 21
RSI_PERIOD    = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30
MACD_FAST     = 12
MACD_SLOW     = 26
MACD_SIGNAL   = 9
BB_PERIOD     = 20
BB_STD        = 2.0

# ── Candle Settings ────────────────────────────────────────────────────────────
CANDLE_INTERVAL = "15m"
CANDLE_LIMIT    = 200

# ── Supported Trading Pairs ────────────────────────────────────────────────────
SUPPORTED_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
    "DOTUSDT", "MATICUSDT",
]

# ── Multi-Symbol Settings ──────────────────────────────────────────────────────
MULTI_SYMBOL_MODE    = False      # True = trade multiple pairs simultaneously
ACTIVE_SYMBOLS       = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

# ── WebSocket Settings ─────────────────────────────────────────────────────────
WS_HOST = "0.0.0.0"
WS_PORT = 8000
