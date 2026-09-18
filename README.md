# ⚡ AI TradeBot — Binance (International Level)

Professional AI Trading Bot with auto buy/sell, risk management, and real-time dashboard.

---

## 🗂️ Project Structure

```
Trading Bot/
├── backend/                  # Python AI Bot + FastAPI Server
│   ├── bot/
│   │   ├── config.py         # All settings
│   │   ├── indicators.py     # AI signal engine (EMA/RSI/MACD/BB)
│   │   ├── binance_client.py # Binance API
│   │   ├── trade_manager.py  # Buy/Sell/SL/TP logic
│   │   └── engine.py         # Main bot loop
│   ├── api/
│   │   ├── routes.py         # REST API endpoints
│   │   └── websocket.py      # Real-time WebSocket
│   ├── data/
│   │   └── trades.json       # Trade history storage
│   ├── main.py               # Server entry point
│   └── requirements.txt
│
└── frontend/                 # React Dashboard
    ├── src/
    │   ├── pages/            # Dashboard, Settings, History
    │   ├── components/       # Navbar, StatCard, etc.
    │   ├── hooks/            # useWebSocket
    │   ├── services/         # API calls
    │   ├── App.jsx
    │   └── App.css
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## 🚀 Setup & Run (Step by Step)

### Step 1 — Python Setup (Backend)

```bash
cd "Trading Bot/backend"
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### Step 2 — Start Backend Server

```bash
cd "Trading Bot/backend"
python main.py
```

Server runs at: http://localhost:8000
API Docs at:    http://localhost:8000/docs

### Step 3 — Node.js Setup (Frontend)

```bash
cd "Trading Bot/frontend"
npm install
npm run dev
```

Dashboard at: http://localhost:3000

---

## 🔑 Binance API Setup

### Testnet (Recommended for testing — FREE fake money):
1. Go to: https://testnet.binance.vision
2. Login with GitHub
3. Generate API Key
4. In dashboard Settings → paste API Key & Secret
5. Toggle "Testnet" ON

### Live Trading:
1. Go to: https://www.binance.com
2. Profile → API Management → Create API
3. Enable "Spot & Margin Trading"
4. In dashboard Settings → paste keys
5. Toggle "Testnet" OFF ⚠️

---

## 🤖 How the AI Works

```
Every 15 minutes:
1. Fetch latest candles from Binance
2. Calculate EMA(9/21), RSI(14), MACD, Bollinger Bands
3. Score buy/sell signals (0-100)
4. If BUY score ≥ 60% confidence → Auto BUY
5. Set Stop Loss & Take Profit automatically using ATR
6. If SELL signal → Auto close position
7. Broadcast update to dashboard via WebSocket
```

### Signal Scoring System:
| Indicator | Max Score |
|-----------|-----------|
| EMA Crossover | 25 pts |
| RSI Oversold/Overbought | 30 pts |
| MACD Crossover | 25 pts |
| Bollinger Band touch | 20 pts |
| Volume confirmation | 15 pts |

---

## ⚙️ Key Settings (Settings Page)

| Setting | Default | Description |
|---------|---------|-------------|
| Testnet | ON | Fake money trading |
| Symbol | BTCUSDT | Trading pair |
| Interval | 15m | Candle timeframe |
| Trade Size | 10% | % of balance per trade |
| Max Trades | 3 | Max open positions |
| Stop Loss | 2% | Auto close on loss |
| Take Profit | 4% | Auto close on profit |

---

## 🛡️ Risk Warning

> Trading involves risk. Always test with Testnet first before using real money.
> Start with small amounts. Never invest more than you can afford to lose.
