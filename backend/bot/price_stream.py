"""
Binance WebSocket Price Stream
Real-time tick-by-tick price updates via Binance WS streams.
Used for intra-candle Stop Loss / Take Profit monitoring.

Each symbol gets its own stream connection.
Price callbacks are fired on every trade tick (~100ms).
"""

import asyncio
import json
import logging
import websockets
from typing import Callable, Dict, Set

logger = logging.getLogger(__name__)

# Binance public stream URLs (no auth needed)
_STREAM_BASE      = "wss://stream.binance.com:9443/ws"
_TESTNET_STREAM   = "wss://testnet.binance.vision/ws"


class PriceStream:
    """
    Manages one WebSocket stream per symbol.
    Calls `on_price(symbol, price)` on every tick.
    """

    def __init__(self, testnet: bool = False):
        self.testnet   = testnet
        self._base     = _TESTNET_STREAM if testnet else _STREAM_BASE
        self._tasks:   Dict[str, asyncio.Task] = {}
        self._callbacks: list[Callable]        = []
        self._active:  Set[str]                = set()

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_callback(self, cb: Callable):
        """Register a callback: cb(symbol: str, price: float)"""
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    async def subscribe(self, symbol: str):
        """Start streaming prices for a symbol (idempotent)"""
        sym = symbol.upper()
        if sym in self._active:
            return
        self._active.add(sym)
        task = asyncio.create_task(self._stream_loop(sym), name=f"stream-{sym}")
        self._tasks[sym] = task
        logger.info(f"[PriceStream] Subscribed to {sym}")

    async def unsubscribe(self, symbol: str):
        """Stop streaming for a symbol"""
        sym = symbol.upper()
        self._active.discard(sym)
        task = self._tasks.pop(sym, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info(f"[PriceStream] Unsubscribed from {sym}")

    async def subscribe_many(self, symbols: list[str]):
        await asyncio.gather(*[self.subscribe(s) for s in symbols])

    async def stop_all(self):
        """Cancel all streams"""
        syms = list(self._active)
        await asyncio.gather(*[self.unsubscribe(s) for s in syms])

    # ── Internal stream loop ───────────────────────────────────────────────────

    async def _stream_loop(self, symbol: str):
        """
        Connects to Binance aggTrade stream and fires callbacks.
        Auto-reconnects with exponential backoff on disconnect.
        Stops retrying on HTTP 451 (geographic/legal block).
        """
        stream_name = f"{symbol.lower()}@aggTrade"
        url         = f"{self._base}/{stream_name}"
        backoff     = 1

        while symbol in self._active:
            try:
                async with websockets.connect(url, ping_interval=20,
                                              ping_timeout=20) as ws:
                    backoff = 1  # reset on successful connect
                    logger.info(f"[PriceStream] Connected: {stream_name}")
                    async for raw in ws:
                        if symbol not in self._active:
                            break
                        try:
                            msg   = json.loads(raw)
                            price = float(msg["p"])   # aggTrade price field
                            await self._fire(symbol, price)
                        except (KeyError, ValueError):
                            pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                if symbol not in self._active:
                    break
                err_str = str(e)
                # HTTP 451 = geographic/legal block — stop retrying
                if "451" in err_str:
                    logger.warning(f"[PriceStream] {symbol} blocked (HTTP 451) — price stream disabled. SL/TP will use candle-level checking.")
                    self._active.discard(symbol)
                    break
                logger.warning(f"[PriceStream] {symbol} disconnected: {e} — retry in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _fire(self, symbol: str, price: float):
        """Call all registered callbacks"""
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(symbol, price)
                else:
                    cb(symbol, price)
            except Exception as e:
                logger.debug(f"[PriceStream] callback error: {e}")
