"""
Main FastAPI Application Entry Point
AI Trading Bot - Backend Server
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging

from api.routes import router
from api.websocket import manager
from bot.engine import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Trading Bot API",
    description="Professional AI Trading Bot for Binance - International Level",
    version="1.0.0",
)

# CORS - Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST routes
app.include_router(router, prefix="/api")

# Register broadcast callback with engine
async def broadcast_callback(data: dict):
    await manager.broadcast(data)

engine.add_callback(broadcast_callback)


# ─── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state on connect
        await manager.send_personal(websocket, {
            "type": "CONNECTED",
            "status": engine.get_status(),
        })

        # Keep connection alive and listen for messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                import json
                message = json.loads(data)

                # Handle ping
                if message.get("type") == "PING":
                    await manager.send_personal(websocket, {"type": "PONG"})

                # Handle subscribe to symbol
                elif message.get("type") == "SUBSCRIBE":
                    symbol = message.get("symbol", engine.current_symbol)
                    price = engine.client.get_ticker_price(symbol)
                    await manager.send_personal(websocket, {
                        "type": "PRICE_UPDATE",
                        "symbol": symbol,
                        "price": price,
                    })

            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal(websocket, {
                    "type": "HEARTBEAT",
                    "running": engine.running,
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ─── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Trading Bot API Server Started!")
    logger.info("📡 WebSocket available at ws://localhost:8000/ws")
    logger.info("📚 API Docs available at http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    engine.stop()
    logger.info("👋 Trading Bot API Server Stopped")


# ─── Health Check ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "AI Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "websocket": "/ws",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "bot_running": engine.running}


# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
