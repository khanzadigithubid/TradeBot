"""
Trading Bot Configuration — EXAMPLE FILE
Copy this file to config.py and fill in your API keys
DO NOT commit config.py to GitHub
"""

# Binance API Settings
BINANCE_API_KEY = "YOUR_BINANCE_API_KEY_HERE"
BINANCE_SECRET_KEY = "YOUR_BINANCE_SECRET_KEY_HERE"
TESTNET = True             # True = Paper trading, False = Real trading

# Trading Settings
DEFAULT_SYMBOL = "BTCUSDT"
TRADE_QUANTITY_PERCENT = 10
MAX_OPEN_TRADES = 3

# Risk Management
STOP_LOSS_PERCENT = 2.0
TAKE_PROFIT_PERCENT = 4.0
TRAILING_STOP = True

# AI Strategy Settings
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2.0

# Candle Settings
CANDLE_INTERVAL = "15m"
CANDLE_LIMIT = 200

# Supported Trading Pairs
SUPPORTED_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT",
    "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT",
]

# WebSocket Settings
WS_HOST = "0.0.0.0"
WS_PORT = 8000
