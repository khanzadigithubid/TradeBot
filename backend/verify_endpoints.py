"""
End-to-end endpoint smoke test.

Read-only against real accounts: the engine startup is disabled so no trading
loop runs, and all file storage is redirected to a temp directory so the
developer's settings.json / trades.json are never touched.
"""
import os
import sys
import tempfile

os.environ.setdefault("TESTNET", "true")
os.environ.pop("LIVE_TRADING_ENABLED", None)
os.environ.pop("API_SECRET", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Isolate storage BEFORE importing main ─────────────────────────────────────
_TMP = tempfile.mkdtemp(prefix="bot-verify-")
import bot.settings_store as _store
import bot.trade_manager as _tm
_store.SETTINGS_FILE = os.path.join(_TMP, "settings.json")
_tm.TRADES_FILE     = os.path.join(_TMP, "trades.json")

from fastapi.testclient import TestClient

import main

main.app.router.on_startup = []          # never boot the trading engine
client = TestClient(main.app)

GETS = [
    "/api/status",
    "/api/settings",
    "/api/market/sentiment?symbol=BTCUSDT",
    "/api/market/fear-greed",
    "/api/market/prices?symbols=BTCUSDT,ETHUSDT",
    "/api/market/BTCUSDT/price",
    "/api/market/BTCUSDT/stats",
    "/api/market/BTCUSDT/candles?interval=15m&limit=50",
    "/api/market/BTCUSDT/signal",
    "/api/market/BTCUSDT/indicators?interval=15m&limit=100",
    "/api/trades/open",
    "/api/trades/history?limit=10",
    "/api/trades/stats",
    "/api/analytics",
]
NEGATIVE = [
    ("/api/market/BTC%20USDT/candles", "junk symbol"),
    ("/api/market/BTCUSDT/candles?interval=1y", "junk interval"),
    ("/api/market/BTC-USDT/signal", "dash in symbol"),
    ("/api/market/BTCUSDT/indicators?interval=nope", "junk interval"),
]
POSTS_422 = [
    ("/api/trades/manual", {"symbol": "BTC USDT", "side": "BUY"}),
    ("/api/trades/manual", {"symbol": "BTCUSDT", "side": "HODL"}),
    ("/api/trades/manual", {"symbol": "BTCUSDT", "side": "BUY", "quantity": -1}),
    ("/api/settings", {"trailing_stopp": True}),
    ("/api/settings", {"trade_quantity_percent": 900}),
    ("/api/backtest", {"symbol": "BTCUSDT", "interval": "1y"}),
]

fails = 0


def check(label, cond, extra=""):
    global fails
    if not cond:
        fails += 1
    print(f"{'PASS' if cond else 'FAIL'}  {label} {extra}")


print("--- read endpoints ---")
for path in GETS:
    try:
        r = client.get(path, timeout=60)
        check(f"GET {path}", r.status_code == 200, f"-> {r.status_code}")
    except Exception as e:
        check(f"GET {path}", False, f"-> EXCEPTION {type(e).__name__}: {e}")

print("\n--- bad input must be a clean 4xx, never a 500 ---")
for path, why in NEGATIVE:
    r = client.get(path, timeout=30)
    check(f"GET {path} ({why})", 400 <= r.status_code < 500, f"-> {r.status_code}")

print("\n--- invalid bodies rejected ---")
for path, body in POSTS_422:
    r = client.post(path, json=body, timeout=30)
    check(f"POST {path} {body}", 400 <= r.status_code < 500, f"-> {r.status_code}")

print("\n--- live-trading interlock ---")
r = client.post("/api/settings", json={"testnet": False}, timeout=30)
check("POST /settings testnet=false refused", r.status_code == 403, f"-> {r.status_code}")

r = client.post("/api/trades/manual", json={"symbol": "BTCUSDT", "side": "BUY"}, timeout=60)
check("POST /trades/manual on testnet allowed", r.status_code in (200, 400, 404),
      f"-> {r.status_code}")

print("\n--- websocket ---")
try:
    with client.websocket_connect("/ws") as ws:
        got = [ws.receive_json() for _ in range(2)]
        check("ws connected + first frames", True, f"-> {got}")
except Exception as e:
    check("ws", False, f"-> {type(e).__name__}: {e}")

print(f"\n{'ALL CHECKS PASSED' if fails == 0 else str(fails) + ' CHECK(S) FAILED'}")
sys.exit(1 if fails else 0)
