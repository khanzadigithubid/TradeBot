"""
Main FastAPI Application Entry Point
AI Trading Bot - Backend Server

Auto-start: Bot server start hote hi apne aap trading shuru kar deta hai.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
import sys
import os

# Add backend directory to Python path
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from api.routes    import router
from api.websocket import manager
from bot.engine    import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Trading Bot API",
    description="Professional AI Trading Bot — Auto Trading",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Register WebSocket broadcast callback
async def broadcast_callback(data: dict):
    await manager.broadcast(data)

engine.add_callback(broadcast_callback)


# ─── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await manager.send_personal(websocket, {
            "type":   "CONNECTED",
            "status": engine.get_status(),
        })

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                import json
                message = json.loads(data)

                if message.get("type") == "PING":
                    await manager.send_personal(websocket, {"type": "PONG"})

                elif message.get("type") == "SUBSCRIBE":
                    symbol = message.get("symbol", engine.current_symbol)
                    price  = engine.client.get_ticker_price(symbol)
                    await manager.send_personal(websocket, {
                        "type": "PRICE_UPDATE", "symbol": symbol, "price": price,
                    })

            except asyncio.TimeoutError:
                await manager.send_personal(websocket, {
                    "type": "HEARTBEAT", "running": engine.running,
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ─── Self-Ping Loop (Render keep-alive) ───────────────────────────────────────

async def keep_alive_loop():
    """
    Pings own /ping endpoint every 10 minutes so Render free tier
    does not put the server to sleep after 15 min inactivity.
    """
    import httpx
    await asyncio.sleep(60)          # wait 1 min after startup
    # Render pe PORT env var use karo, local pe 8000
    port = os.environ.get("PORT", "8000")
    ping_url = f"http://localhost:{port}/ping"
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get(ping_url, timeout=10)
            logger.info("🏓 Self-ping OK — Render keep-alive")
        except Exception as e:
            logger.debug(f"Self-ping failed (harmless): {e}")
        await asyncio.sleep(600)     # every 10 minutes


# ─── Daily Summary Email ───────────────────────────────────────────────────────

async def daily_summary_loop():
    """Every 24 hours — send a performance summary email."""
    await asyncio.sleep(5)  # wait for bot to fully start
    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            stats  = engine.trade_manager.get_stats()
            trades = engine.trade_manager.get_trade_history(limit=50)

            today_trades = []
            from datetime import datetime, timezone, timedelta
            PST = timezone(timedelta(hours=5))
            now = datetime.now(PST)
            for t in trades:
                et = t.get("exit_time", "")
                if et:
                    try:
                        td = datetime.fromisoformat(et.replace("Z", "+00:00"))
                        if (now - td).total_seconds() < 86400:
                            today_trades.append(t)
                    except Exception:
                        pass

            today_pnl  = sum(t.get("pnl") or 0 for t in today_trades)
            today_wins = len([t for t in today_trades if (t.get("pnl") or 0) > 0])
            today_loss = len([t for t in today_trades if (t.get("pnl") or 0) <= 0])
            pos        = today_pnl >= 0
            color      = "#26a69a" if pos else "#ef5350"
            emoji      = "📈" if pos else "📉"

            subject = f"{emoji} Daily Summary — P&L: {'+' if pos else ''}{today_pnl:.4f} USDT"
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:500px;background:#131722;color:#d1d4dc;padding:24px;border-radius:10px">
              <h2 style="color:{color};margin:0 0 16px">{emoji} Daily Performance Summary</h2>
              <table style="width:100%;border-collapse:collapse">
                <tr><td style="padding:6px 0;color:#787b86">Today Trades</td>  <td style="font-weight:700;color:#fff">{len(today_trades)}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Wins</td>          <td style="font-weight:700;color:#26a69a">{today_wins}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Losses</td>        <td style="font-weight:700;color:#ef5350">{today_loss}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Today P&L</td>     <td style="font-weight:800;color:{color}">{'+' if pos else ''}{today_pnl:.4f} USDT</td></tr>
                <tr><td colspan="2" style="padding-top:12px;border-top:1px solid #2a2f45"></td></tr>
                <tr><td style="padding:6px 0;color:#787b86">All Time Trades</td><td style="font-weight:700;color:#fff">{stats['total_trades']}</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Win Rate</td>       <td style="font-weight:700;color:#ce93d8">{stats['win_rate']}%</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Total P&L</td>      <td style="font-weight:800;color:{'#26a69a' if stats['total_pnl']>=0 else '#ef5350'}">{'+' if stats['total_pnl']>=0 else ''}{stats['total_pnl']:.4f} USDT</td></tr>
                <tr><td style="padding:6px 0;color:#787b86">Open Trades</td>    <td style="font-weight:700;color:#fff">{stats['open_trades']}</td></tr>
              </table>
              <p style="color:#787b86;font-size:11px;margin-top:16px">{now.strftime('%Y-%m-%d %I:%M %p PKT')}</p>
            </div>
            """
            engine.email_notifier.send(subject, html)
            logger.info("📧 Daily summary email sent")
        except Exception as e:
            logger.error(f"Daily summary error: {e}")


# ─── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Trading Bot API Server Started!")
    logger.info("📡 WebSocket: ws://localhost:8000/ws")
    logger.info("📚 API Docs:  http://localhost:8000/docs")

    # ── AUTO-START BOT ──────────────────────────────────────────────────────────
    logger.info("🤖 Auto-starting trading bot...")
    asyncio.create_task(engine.start())

    # ── DAILY SUMMARY ───────────────────────────────────────────────────────────
    asyncio.create_task(daily_summary_loop())

    # ── KEEP-ALIVE (Render free tier) ────────────────────────────────────────────
    asyncio.create_task(keep_alive_loop())


@app.on_event("shutdown")
async def shutdown_event():
    engine.stop()
    logger.info("👋 Server stopped")


# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name":        "AI Trading Bot API",
        "version":     "2.0.0",
        "bot_running": engine.running,
        "docs":        "/docs",
    }

@app.get("/health")
def health():
    return {"status": "healthy", "bot_running": engine.running}

@app.get("/ping")
def ping():
    """Keep-alive endpoint — prevents Render free tier from sleeping"""
    return {"pong": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
