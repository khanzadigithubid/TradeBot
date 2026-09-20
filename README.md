# ⚡ AI TradeBot — Crypto Auto Trading Bot

> Professional AI-powered crypto trading bot with real-time dashboard, 12-indicator signal engine, backtesting, multi-symbol support, and 4-channel notifications.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react)](https://react.dev)
[![Binance](https://img.shields.io/badge/Binance-API-F0B90B?logo=binance)](https://binance.com)
[![Render](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render)](https://render.com)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel-000?logo=vercel)](https://vercel.com)
[![License](https://img.shields.io/badge/License-MIT-8b5cf6)](LICENSE)

---

## 🌐 Live Demo

| | Link |
|---|---|
| 🖥️ **Frontend Dashboard** | [https://trade-bot-sigma-five.vercel.app](https://trade-bot-sigma-five.vercel.app) |
| ⚙️ **Backend API** | [https://tradebot-omuy.onrender.com](https://tradebot-omuy.onrender.com) |
| 📚 **API Docs (Swagger)** | [https://tradebot-omuy.onrender.com/docs](https://tradebot-omuy.onrender.com/docs) |

> ℹ️ Backend runs on Render free tier — first load may take ~10 seconds to wake up.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🤖 **Auto Trading** | Bot starts automatically on server launch |
| 📊 **12 Indicators** | EMA, RSI, MACD, Bollinger Bands, VWAP, Stoch RSI, SuperTrend, Williams %R, OBV, Support/Resistance |
| 🕐 **Multi-Timeframe** | 15m + 1h + 4h analysis — all 3 must agree for strong signal |
| 🧠 **Sentiment Filter** | Fear & Greed Index + CryptoPanic news headlines |
| 🛡️ **Risk Management** | Stop Loss, Take Profit, Trailing Stop, Daily Loss Limit |
| ⚡ **Real-time SL/TP** | Binance WebSocket ~100ms tick — no waiting for candle close |
| 🔄 **Multi-Symbol** | Trade BTC, ETH, BNB, SOL... simultaneously |
| 🧪 **Backtesting** | Full historical simulation with Sharpe, Drawdown, Profit Factor |
| 📉 **Analytics Page** | P&L curve, Drawdown chart, Monthly breakdown, Win/Loss by symbol |
| 📱 **Telegram** | Instant alerts on every trade |
| 📧 **Email** | HTML trade reports via Gmail SMTP + Resend API |
| 🎮 **Discord** | Rich embed notifications via webhook |
| 🌐 **Fallback Data** | Binance → Kraken → CoinGecko (works even if Binance is blocked) |

---

## 🗺️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND  (React 18 + Vite)                    │
│  Dashboard │ Analytics │ Backtest │ History │ Settings      │
│       ↕ REST API (30+ endpoints)   ↕ WebSocket /ws          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               BACKEND  (FastAPI + asyncio)                  │
│   api/routes.py  ─────────  api/websocket.py                │
│                                                             │
│            bot/engine.py  (TradingEngine)                   │
│  ┌──────────┬─────────────┬────────────┬──────────────────┐ │
│  │indicators│trade_manager│market_data │ sentiment.py     │ │
│  │ 12 indic │ SL/TP/Trail │ 3 fallbacks│ Fear&Greed+News  │ │
│  └──────────┴─────────────┴────────────┴──────────────────┘ │
│                  price_stream.py (WS ~100ms)                 │
│                  backtester.py                               │
│                  settings_store.py ─── data/settings.json   │
│                  trade_manager.py  ─── data/trades.json      │
└─────────────────────────────────────────────────────────────┘
         │              │              │            │
      Telegram        Gmail         Resend       Discord
      Bot API         SMTP          API          Webhook
```

---

## 🗂️ Project Structure

```
Trading Bot/
├── backend/
│   ├── bot/
│   │   ├── engine.py            # Main trading loop (multi-symbol asyncio)
│   │   ├── indicators.py        # 12 indicators + AI signal scoring (0–240 pts)
│   │   ├── trade_manager.py     # Buy/Sell/SL/TP/Trailing Stop
│   │   ├── backtester.py        # Historical strategy simulation
│   │   ├── market_data.py       # Binance → Kraken → CoinGecko fallback
│   │   ├── price_stream.py      # Binance WebSocket real-time price feed
│   │   ├── sentiment.py         # Fear & Greed Index + News sentiment
│   │   ├── notifier.py          # Telegram alerts
│   │   ├── email_notifier.py    # Gmail SMTP alerts
│   │   ├── resend_notifier.py   # Resend API (works on Render free tier)
│   │   ├── discord_notifier.py  # Discord webhook notifications
│   │   ├── binance_client.py    # Binance REST API (HMAC SHA256 signed)
│   │   ├── settings_store.py    # Persist UI settings to JSON
│   │   └── config.py            # Default config (loads from .env)
│   ├── api/
│   │   ├── routes.py            # 30+ REST API endpoints
│   │   └── websocket.py         # WebSocket connection manager
│   ├── data/
│   │   ├── trades.json          # Trade records (auto-created)
│   │   └── settings.json        # UI settings (auto-created)
│   ├── .env.example             # Template — copy to .env
│   ├── main.py                  # FastAPI entry point (auto-starts bot)
│   ├── requirements.txt
│   └── render.yaml              # Render.com deployment config
│
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── Dashboard.jsx    # Signal panel, chart, open trades
    │   │   ├── Analytics.jsx    # P&L curve, drawdown, monthly stats
    │   │   ├── Backtest.jsx     # Run historical backtests
    │   │   ├── History.jsx      # Closed trades table
    │   │   └── Settings.jsx     # Bot config, API keys, notifications
    │   ├── components/
    │   │   ├── PriceChart.jsx   # Candlestick + EMA/BB overlays
    │   │   ├── SignalBadge.jsx  # BUY / SELL / HOLD badge
    │   │   ├── OpenTradeCard.jsx
    │   │   ├── StatCard.jsx
    │   │   └── Navbar.jsx
    │   ├── hooks/
    │   │   └── useWebSocket.js  # Auto-reconnect WebSocket hook
    │   └── services/
    │       └── api.js           # All REST API calls
    ├── .env.example             # Frontend env template
    └── vercel.json              # Vercel deployment config
```

---

## 🚀 Local Setup & Run

### Prerequisites
- Python 3.11+
- Node.js 18+
- Binance Testnet account (free)

---

### Step 1 — Clone

```bash
git clone https://github.com/khanzadigithubid/TradeBot.git
cd TradeBot
```

---

### Step 2 — Backend

```bash
cd backend

# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Configure environment
copy .env.example .env        # Windows
cp .env.example .env          # Mac/Linux
```

Edit `backend/.env`:

```env
# ── Binance ──────────────────────────────────
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
TESTNET=True                    # True = safe testing, False = real money

# ── Optional: Telegram alerts ────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── Optional: Email alerts ────────────────────
EMAIL_SENDER=yourbot@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECEIVER=you@gmail.com

# ── Optional: Resend API ─────────────────────
RESEND_API_KEY=

# ── Optional: Discord ────────────────────────
DISCORD_WEBHOOK_URL=

# ── Risk Management ───────────────────────────
DAILY_LOSS_LIMIT_PERCENT=5.0
SENTIMENT_FILTER=True
MTF_ENABLED=True
```

```bash
# Start backend (bot auto-starts!)
python -m uvicorn main:app --reload --port 8000
```

API Docs: http://localhost:8000/docs

---

### Step 3 — Frontend

```bash
cd frontend

# Create local env file
copy .env.example .env.local   # Windows
cp .env.example .env.local     # Mac/Linux

npm install
npm run dev
```

Open: **http://localhost:3000**

> `.env.local` already points to `localhost:8000` — no extra config needed.

---

### Windows Quick Start (One Click)

```
start_backend.bat   ← starts Python server
start_frontend.bat  ← starts React dev server
start_all.bat       ← starts both together
```

---

## 🔑 Binance API Keys

### Testnet (Free — Recommended for testing)
1. Go to → https://testnet.binance.vision
2. Login with GitHub → **Generate HMAC API Key**
3. Copy Key + Secret → paste into `.env`
4. Keep `TESTNET=True`

### Live Trading (Real money)
1. Go to → https://www.binance.com → API Management
2. Enable **Spot & Margin Trading**
3. Paste Key + Secret → set `TESTNET=False`

> ⚠️ Always test on Testnet first. Start with a small amount ($50–$100).

---

## 📧 Notification Setup

### Telegram
1. Search **@BotFather** on Telegram → `/newbot` → get token
2. Search **@userinfobot** → get your Chat ID
3. Add both to `.env`

### Gmail
1. Enable 2-Step Verification on Google account
2. Go to → https://myaccount.google.com/apppasswords
3. Create App Password → `Trading Bot`
4. Copy 16-char password → add to `.env`

### Resend API *(recommended for cloud deploy)*
1. Sign up → https://resend.com (free: 100 emails/day)
2. Get API Key → add `RESEND_API_KEY` to `.env`

### Discord
1. Server Settings → Integrations → Webhooks → New Webhook
2. Copy URL → add `DISCORD_WEBHOOK_URL` to `.env`

---

## 🤖 How the AI Signal Works

Every candle interval (default **15 minutes**):

```
1.  Fetch 200 candles from Binance (Kraken/CoinGecko fallback)
2.  Fetch 1h + 4h candles for Multi-Timeframe analysis
3.  Check Fear & Greed Index + News sentiment
4.  Calculate all 12 indicators
5.  Score BUY vs SELL (0–240 points each side)
6.  Apply sentiment adjustment (±15 to ±25 pts)
7.  Confidence ≥ 60% → Execute trade
8.  Set Stop Loss + Take Profit (ATR-based + % configured)
9.  Real-time Binance WebSocket monitors price every ~100ms
10. SL/TP hit → auto-close + send all notifications
```

### Indicator Scoring

| # | Indicator | Max Points |
|---|---|---|
| 1 | EMA Crossover (9/21) | 25 pts |
| 2 | RSI Oversold / Overbought | 30 pts |
| 3 | MACD Crossover | 25 pts |
| 4 | Bollinger Band touch | 20 pts |
| 5 | VWAP position | 15 pts |
| 6 | Stochastic RSI crossover | 20 pts |
| 7 | SuperTrend direction | 20 pts |
| 8 | Williams %R | 15 pts |
| 9 | Support / Resistance proximity | 15 pts |
| 10 | OBV momentum | 10 pts |
| 11 | Volume confirmation | 15 pts |
| 12 | Multi-Timeframe (15m + 1h + 4h) | 30 pts |
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
| Trail % | `1%` | Trail distance below peak price |
| Daily Loss Limit | `5%` | Auto-stop bot on bad day |
| Sentiment Filter | `ON` | Block BUY on Extreme Greed |
| MTF Analysis | `ON` | 15m + 1h + 4h combined signal |
| Multi-Symbol | `OFF` | Trade multiple pairs at once |

---

## 📊 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Bot status + stats |
| POST | `/api/bot/start` | Start the bot |
| POST | `/api/bot/stop` | Stop the bot |
| GET | `/api/settings` | Get all settings |
| POST | `/api/settings` | Update settings |
| GET | `/api/market/{symbol}/price` | Current price |
| GET | `/api/market/{symbol}/signal` | AI signal |
| GET | `/api/market/{symbol}/candles` | OHLCV candles |
| GET | `/api/market/{symbol}/indicators` | Chart indicators |
| GET | `/api/market/{symbol}/stats` | 24h stats |
| GET | `/api/trades/open` | Open positions |
| GET | `/api/trades/history` | Trade history |
| GET | `/api/trades/stats` | Win rate, P&L, balance |
| POST | `/api/trades/manual` | Manual buy/sell |
| DELETE | `/api/trades/{id}` | Close a trade |
| POST | `/api/backtest` | Run backtest |
| GET | `/api/analytics` | Analytics data |
| GET | `/ping` | Keep-alive / health check |

---

## ☁️ Deployment

### Backend → Render.com

`render.yaml` is already configured. Just:
1. Push to GitHub
2. Connect repo on [render.com](https://render.com)
3. Add environment variables from `.env`
4. Auto-deploys on every push

### Frontend → Vercel

```bash
cd frontend
npm run build
```

1. Push to GitHub
2. Connect repo on [vercel.com](https://vercel.com)
3. Add environment variables:
```
VITE_API_URL = https://your-app.onrender.com/api
VITE_WS_URL  = wss://your-app.onrender.com/ws
```

---

## 📁 Important Files

| File | Description |
|---|---|
| `backend/.env` | Secret keys — **never commit!** |
| `backend/data/trades.json` | All trade records (auto-created) |
| `backend/data/settings.json` | UI-saved settings (auto-created) |
| `frontend/.env.local` | Local dev URLs (auto-ignored by git) |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, asyncio, websockets |
| Data | pandas, numpy |
| Frontend | React 18, Vite, Lightweight Charts, Lucide Icons |
| Exchange | Binance REST + WebSocket API |
| Hosting | Render.com (backend) + Vercel (frontend) |
| Notifications | Telegram Bot API, Gmail SMTP, Resend API, Discord Webhooks |

---

## 👤 Author

**Khanzadi**
- GitHub: [@khanzadigithubid](https://github.com/khanzadigithubid)

> 💼 Available for freelance work — custom trading bots, dashboards, and automation.
> Open an [issue](https://github.com/khanzadigithubid/TradeBot/issues) or reach out directly.

---

## ⚠️ Risk Warning

Trading cryptocurrencies involves **significant risk of loss**.
- Always test thoroughly on **Testnet** before using real money
- Never invest money you cannot afford to lose
- Past performance does not guarantee future results
- This project is for **educational purposes**

---

## 📄 License

MIT License — free to use, modify, and distribute.
