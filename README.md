# ⚡ AI TradeBot — Auto Trading Bot

Professional AI Trading Bot with auto buy/sell, real-time dashboard, email notifications, backtesting, and multi-symbol support.

---

## ✨ Features

- 🤖 **Auto Trading** — Bot starts automatically, no manual intervention needed
- 📊 **Live Dashboard** — Real-time price, signals, open trades
- 📈 **Chart Overlays** — RSI, MACD, EMA, Bollinger Bands
- 🛡️ **Risk Management** — Stop Loss, Take Profit, Trailing Stop
- 📧 **Email Alerts** — Get notified on every trade (Gmail)
- 📱 **Telegram Alerts** — Phone notifications
- 🔄 **Multi-Symbol** — Trade multiple pairs simultaneously
- 🧪 **Backtesting** — Test strategy on historical data
- 📉 **Analytics** — P&L curve, Drawdown, Sharpe Ratio

---

## 🗂️ Project Structure

```
Trading Bot/
├── backend/
│   ├── bot/
│   │   ├── config.py          # Settings (loads from .env)
│   │   ├── engine.py          # Main bot loop (multi-symbol)
│   │   ├── indicators.py      # EMA, RSI, MACD, BB signals
│   │   ├── trade_manager.py   # Buy/Sell/SL/TP/Trailing Stop
│   │   ├── backtester.py      # Historical strategy simulation
│   │   ├── price_stream.py    # Binance WebSocket price stream
│   │   ├── notifier.py        # Telegram notifications
│   │   ├── email_notifier.py  # Gmail notifications
│   │   └── binance_client.py  # Binance API
│   ├── api/
│   │   ├── routes.py          # REST API endpoints
│   │   └── websocket.py       # Real-time WebSocket
│   ├── data/                  # trades.json, settings.json (auto-created)
│   ├── .env.example           # Template — copy to .env and fill in
│   ├── main.py                # Server entry point (auto-starts bot)
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── pages/             # Dashboard, History, Analytics, Backtest, Settings
    │   ├── components/        # Navbar, PriceChart, StatCard, etc.
    │   ├── hooks/             # useWebSocket
    │   └── services/          # API calls
    └── package.json
```

---

## 🚀 Setup & Run

### Step 1 — Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/trading-bot.git
cd "trading-bot/backend"
```

Copy the example env file and fill in your credentials:

```bash
copy .env.example .env
```

Open `backend/.env` and fill in:

```env
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
TESTNET=True

# Optional — Telegram alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Optional — Gmail alerts
EMAIL_SENDER=yourbot@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECEIVER=you@gmail.com
```

### Step 2 — Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
pip install -r requirements.txt

# Start server (bot auto-starts!)
python -m uvicorn main:app --reload --port 8000
```

### Step 3 — Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

**Open:** http://localhost:3000

---

## 🔑 Binance API Keys

### Testnet (Free fake money — recommended for testing):
1. Go to: https://testnet.binance.vision
2. Login with GitHub → Generate API Key
3. Paste in `.env` → set `TESTNET=True`

### Live Trading:
1. Go to: https://www.binance.com → API Management
2. Enable "Spot & Margin Trading"
3. Paste in `.env` → set `TESTNET=False`

---

## 📧 Email Notifications Setup

You will receive emails for every trade automatically.

1. Go to: https://myaccount.google.com/apppasswords
2. Enable 2-Step Verification first
3. Create App Password → name it `Trading Bot`
4. Copy the 16-character password
5. Fill in `.env`:
```env
EMAIL_SENDER=yourbot@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECEIVER=you@gmail.com
```

---

## 📱 Telegram Notifications Setup

1. Open Telegram → search `@BotFather` → `/newbot`
2. Get your token
3. Search `@userinfobot` → get your Chat ID
4. Fill in `.env`:
```env
TELEGRAM_BOT_TOKEN=123456:ABCdef...
TELEGRAM_CHAT_ID=987654321
```

---

## 🤖 How the AI Works

Every candle interval (default 15 min):
1. Fetch 200 candles from Binance
2. Calculate indicators: EMA(9/21), RSI(14), MACD, Bollinger Bands, ATR
3. Score BUY/SELL signals (0-100 points)
4. If confidence ≥ 60% → Execute trade automatically
5. Set Stop Loss & Take Profit using ATR + configured %
6. Trailing Stop moves SL up as price rises
7. Real-time price stream monitors SL/TP between candles
8. Send email + Telegram notification

### Signal Scoring:
| Indicator | Max Points |
|---|---|
| EMA Crossover | 25 pts |
| RSI Oversold/Overbought | 30 pts |
| MACD Crossover | 25 pts |
| Bollinger Band touch | 20 pts |
| Volume confirmation | 15 pts |

---

## ⚙️ Settings (Dashboard → Settings Page)

| Setting | Default | Description |
|---|---|---|
| Testnet | ON | Fake money — safe for testing |
| Symbol | BTCUSDT | Trading pair |
| Interval | 15m | Candle timeframe |
| Trade Size | 10% | % of balance per trade |
| Max Trades | 3 | Max open positions at once |
| Stop Loss | 2% | Auto close on loss |
| Take Profit | 4% | Auto close on profit |
| Trailing Stop | ON | SL moves up with price |
| Multi-Symbol | OFF | Trade multiple pairs at once |

---

## ⚠️ Risk Warning

> Trading involves significant risk of loss. Always test with Testnet first.
> Never invest money you cannot afford to lose. Past performance is not indicative of future results.
