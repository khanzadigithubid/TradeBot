# ⚡ AI TradeBot — Crypto Auto Trading Bot

> Professional AI-powered trading bot with real-time dashboard, multi-symbol support, backtesting, and 4-channel notifications.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react)](https://react.dev)
[![Binance](https://img.shields.io/badge/Binance-Testnet-yellow?logo=binance)](https://testnet.binance.vision)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)

---

## 📸 Screenshots

| Dashboard | Analytics | Backtest |
|---|---|---|
| Real-time signal + chart | P&L curve + drawdown | Historical strategy sim |

---

## ✨ Features

| Feature | Details |
|---|---|
| 🤖 **Auto Trading** | Bot starts automatically, no manual intervention |
| 📊 **12 Indicators** | EMA, RSI, MACD, BB, VWAP, StochRSI, SuperTrend, Williams%R, OBV, S/R |
| 🕐 **Multi-Timeframe** | 15m + 1h + 4h analysis combined |
| 🧠 **Sentiment Filter** | Fear & Greed Index + CryptoPanic news |
| 🛡️ **Risk Management** | Stop Loss, Take Profit, Trailing Stop, Daily Loss Limit |
| ⚡ **Real-time SL/TP** | Binance WebSocket — ~100ms tick-by-tick monitoring |
| 🔄 **Multi-Symbol** | Trade BTC, ETH, BNB, SOL... simultaneously |
| 🧪 **Backtesting** | Test strategy on historical data with full metrics |
| 📉 **Analytics** | P&L curve, Drawdown, Sharpe Ratio, Monthly breakdown |
| 📱 **Telegram** | Trade alerts on every buy/sell |
| 📧 **Email (Gmail + Resend)** | HTML trade reports + daily summary |
| 🎮 **Discord** | Rich embed notifications via webhook |
| 🌐 **Fallback Data** | Binance → Kraken → CoinGecko (works even if Binance is blocked) |

---

## 🗺️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND  (React + Vite)                      │
│  Dashboard │ Analytics │ Backtest │ History │ Settings          │
│       ↕ REST API              ↕ WebSocket /ws                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                BACKEND  (FastAPI — main.py)                     │
│    api/routes.py (30+ endpoints)  │  api/websocket.py           │
│                       │                                         │
│            bot/engine.py  (TradingEngine)                       │
│    ┌──────────┬──────────┬──────────┬───────────┐               │
│    │indicators│  trade_  │ market_  │sentiment  │ price_stream  │
│    │   .py    │ manager  │  data    │   .py     │    .py        │
│    │12 indic. │ SL/TP/TS │ Fallback │ Fear&Greed│ WS ~100ms     │
│    └──────────┴──────────┴──────────┴───────────┘               │
└─────────────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   Telegram         Gmail          Discord
   Alerts           SMTP           Webhook
                    + Resend
```

---

## 🗂️ Project Structure

```
Trading Bot/
├── backend/
│   ├── bot/
│   │   ├── engine.py           # Main trading loop (multi-symbol asyncio)
│   │   ├── indicators.py       # 12 indicators + AI signal scoring
│   │   ├── trade_manager.py    # Buy/Sell/SL/TP/Trailing Stop
│   │   ├── backtester.py       # Historical strategy simulation
│   │   ├── market_data.py      # Binance → Kraken → CoinGecko fallback
│   │   ├── price_stream.py     # Binance WebSocket (real-time SL/TP)
│   │   ├── sentiment.py        # Fear & Greed + News sentiment
│   │   ├── notifier.py         # Telegram alerts
│   │   ├── email_notifier.py   # Gmail SMTP alerts
│   │   ├── resend_notifier.py  # Resend API (works on Render)
│   │   ├── discord_notifier.py # Discord webhook
│   │   ├── binance_client.py   # Binance REST API (HMAC signed)
│   │   ├── settings_store.py   # Persist settings to JSON
│   │   └── config.py           # Default config (loads from .env)
│   ├── api/
│   │   ├── routes.py           # 30+ REST API endpoints
│   │   └── websocket.py        # WebSocket connection manager
│   ├── data/
│   │   ├── trades.json         # All trades (auto-created)
│   │   └── settings.json       # UI settings (auto-created)
│   ├── .env.example            # Template — copy to .env
│   ├── main.py                 # FastAPI entry point (auto-starts bot)
│   ├── requirements.txt
│   └── render.yaml             # Render.com deployment config
│
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── Dashboard.jsx   # Main page: signal, chart, trades
    │   │   ├── Analytics.jsx   # P&L curve, drawdown, monthly
    │   │   ├── Backtest.jsx    # Run backtests
    │   │   ├── History.jsx     # Closed trade history
    │   │   └── Settings.jsx    # All bot settings
    │   ├── components/
    │   │   ├── PriceChart.jsx  # Candlestick + indicator overlays
    │   │   ├── SignalBadge.jsx # BUY/SELL/HOLD badge
    │   │   ├── OpenTradeCard.jsx
    │   │   ├── StatCard.jsx
    │   │   └── Navbar.jsx
    │   ├── hooks/
    │   │   └── useWebSocket.js # Auto-reconnect WS hook
    │   └── services/
    │       └── api.js          # All REST API calls
    └── vercel.json             # Vercel deployment config
```

---

## 🚀 Setup & Run

### Prerequisites

- Python 3.11+
- Node.js 18+
- Binance account (Testnet recommended)

---

### Step 1 — Clone

```bash
git clone https://github.com/khanzadigithubid/TradeBot.git
cd TradeBot
```

---

### Step 2 — Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file
copy .env.example .env
```

Edit `backend/.env`:

```env
# ── Binance ──────────────────────────────
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
TESTNET=True                    # Keep True for safe testing

# ── Telegram (optional) ──────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── Email Gmail (optional) ───────────────
EMAIL_SENDER=yourbot@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECEIVER=you@gmail.com

# ── Resend API (optional, works on Render)
RESEND_API_KEY=

# ── Discord (optional) ───────────────────
DISCORD_WEBHOOK_URL=

# ── Risk Management ───────────────────────
DAILY_LOSS_LIMIT_PERCENT=5.0
SENTIMENT_FILTER=True
MTF_ENABLED=True
```

Start the backend:

```bash
python -m uvicorn main:app --reload --port 8000
```

> Bot automatically starts trading on server launch!

---

### Step 3 — Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open: **http://localhost:5173**

> For local development, create `frontend/.env.local`:
> ```
> VITE_API_URL=http://localhost:8000/api
> VITE_WS_URL=ws://localhost:8000/ws
> ```

---

### Step 4 — (Optional) Windows Quick Start

Double-click the batch files:
- `start_backend.bat` — starts the Python server
- `start_frontend.bat` — starts the React dev server
- `start_all.bat` — starts both together

---

## 🔑 Binance API Setup

### Testnet (Recommended — Free fake money)
1. Go to → https://testnet.binance.vision
2. Login with GitHub → **Generate HMAC API Key**
3. Copy Key + Secret → paste in `.env`
4. Keep `TESTNET=True`

### Live Trading (Real money — careful!)
1. Go to → https://www.binance.com → API Management
2. Enable **"Spot & Margin Trading"**
3. Paste Key + Secret → set `TESTNET=False`

> ⚠️ **WARNING:** Always test on Testnet first. Never risk money you can't afford to lose.

---

## 📧 Email Notifications Setup

### Gmail
1. Enable **2-Step Verification** on your Google account
2. Go to → https://myaccount.google.com/apppasswords
3. Create App Password → name it `Trading Bot`
4. Copy the 16-character password → paste in `.env`

### Resend (recommended for cloud deployment)
1. Sign up → https://resend.com (free tier: 100 emails/day)
2. Get API Key → paste `RESEND_API_KEY` in `.env`

---

## 📱 Telegram Notifications Setup

1. Open Telegram → search **@BotFather** → `/newbot`
2. Follow steps → get your **Bot Token**
3. Search **@userinfobot** → get your **Chat ID**
4. Paste both in `.env`

---

## 🎮 Discord Notifications Setup

1. Open Discord → Server Settings → **Integrations** → Webhooks
2. Create Webhook → Copy URL
3. Paste `DISCORD_WEBHOOK_URL` in `.env`

---

## 🤖 How the AI Signal Works

Every candle interval (default **15 minutes**):

```
1. Fetch 200 candles from Binance (or Kraken/CoinGecko fallback)
2. Fetch 1h + 4h candles for Multi-Timeframe analysis
3. Check Fear & Greed Index + News sentiment
4. Calculate all 12 indicators
5. Score BUY vs SELL (0-250 points each)
6. Apply sentiment adjustment (±15~25 pts)
7. Confidence ≥ 60% → Execute trade
8. Set Stop Loss + Take Profit (ATR-based)
9. Real-time WebSocket monitors price every ~100ms
10. SL/TP hit → auto-close + notifications
```

### Indicator Scoring Table

| # | Indicator | Max Points |
|---|---|---|
| 1 | EMA Crossover (9/21) | 25 pts |
| 2 | RSI Oversold/Overbought | 30 pts |
| 3 | MACD Crossover | 25 pts |
| 4 | Bollinger Band touch | 20 pts |
| 5 | VWAP position | 15 pts |
| 6 | Stochastic RSI crossover | 20 pts |
| 7 | SuperTrend direction | 20 pts |
| 8 | Williams %R | 15 pts |
| 9 | Support/Resistance proximity | 15 pts |
| 10 | OBV momentum | 10 pts |
| 11 | Volume confirmation | 15 pts |
| 12 | Multi-Timeframe (15m+1h+4h) | 30 pts |
| | **Total possible** | **240 pts** |

---

## ⚙️ Settings Reference

| Setting | Default | Description |
|---|---|---|
| Testnet | `ON` | Fake money — safe for testing |
| Symbol | `BTCUSDT` | Trading pair |
| Interval | `15m` | Candle timeframe |
| Trade Size | `10%` | % of USDT balance per trade |
| Max Trades | `3` | Max open positions at once |
| Stop Loss | `2%` | Auto-close on loss |
| Take Profit | `4%` | Auto-close on profit |
| Trailing Stop | `ON` | SL moves up as price rises |
| Trail % | `1%` | Trail distance below peak |
| Daily Loss Limit | `5%` | Auto-stop bot on big loss day |
| Sentiment Filter | `ON` | Block trades on extreme greed |
| MTF Analysis | `ON` | 15m + 1h + 4h combined |
| Multi-Symbol | `OFF` | Trade multiple pairs at once |

---

## 📊 REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Bot running status |
| POST | `/api/bot/start` | Start the bot |
| POST | `/api/bot/stop` | Stop the bot |
| GET | `/api/settings` | Get all settings |
| POST | `/api/settings` | Update settings |
| GET | `/api/market/{symbol}/signal` | Get AI signal |
| GET | `/api/market/{symbol}/candles` | Candle data |
| GET | `/api/market/{symbol}/indicators` | Chart indicators |
| GET | `/api/trades/open` | Open positions |
| GET | `/api/trades/history` | Trade history |
| GET | `/api/trades/stats` | Win rate, P&L |
| POST | `/api/trades/manual` | Manual buy/sell |
| DELETE | `/api/trades/{id}` | Close a trade |
| POST | `/api/backtest` | Run backtest |
| GET | `/api/analytics` | Analytics data |

**API Docs:** http://localhost:8000/docs

---

## ☁️ Deployment

### Backend → Render.com (Free tier)
```bash
# render.yaml is already configured
# Push to GitHub → connect Render → auto-deploy
```

### Frontend → Vercel (Free tier)
```bash
cd frontend
npm run build
# Push to GitHub → connect Vercel → auto-deploy
```

Set environment variables on Vercel:
```
VITE_API_URL=https://your-render-app.onrender.com/api
VITE_WS_URL=wss://your-render-app.onrender.com/ws
```

---

## 📁 Data Files

| File | Description |
|---|---|
| `backend/data/trades.json` | All trade records (auto-created) |
| `backend/data/settings.json` | UI-saved settings (auto-created) |
| `backend/.env` | Secret keys — never commit! |

---

## ⚠️ Risk Warning

> Trading cryptocurrencies involves significant risk of loss.
> Always test thoroughly on **Testnet** before using real money.
> Never invest money you cannot afford to lose.
> Past performance does not guarantee future results.
> This bot is for educational purposes.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.

---

## 🙏 Tech Stack

- **Backend:** Python 3.11, FastAPI, asyncio, websockets, pandas, numpy
- **Frontend:** React 18, Vite, Lightweight Charts, Lucide Icons
- **Exchange:** Binance API (Testnet + Live)
- **Deployment:** Render.com (backend) + Vercel (frontend)
- **Notifications:** Telegram Bot API, Gmail SMTP, Resend API, Discord Webhooks
