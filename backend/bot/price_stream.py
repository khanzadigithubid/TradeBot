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
# NOTE: the testnet market-data host is stream.testnet.binance.vision —
# testnet.binance.vision only serves REST and rejects /ws with HTTP 404,
# which silently killed stop-loss monitoring in testnet mode.
_STREAM_BASE      = "wss://stream.binance.com:9443/ws"
_STREAM_BASE_443  = "wss://stream.binance.com:443/ws"
_TESTNET_STREAM   = "wss://stream.testnet.binance.vision/ws"


class PriceStream:
    """
    Manages one WebSocket stream per symbol.
    Calls `on_price(symbol, price)` on every tick.
    """

    def __init__(self, testnet: bool = False):
        self.testnet   = testnet
        self._base     = self._resolve_base(testnet)
        self._tasks:   Dict[str, asyncio.Task] = {}
        self._callbacks: list[Callable]        = []
        self._active:  Set[str]                = set()
        self.healthy: Dict[str, bool]          = {}

    @staticmethod
    def _resolve_base(testnet: bool) -> str:
        return _TESTNET_STREAM if testnet else _STREAM_BASE

    @property
    def base(self) -> str:
        """Current stream base URL (kept in sync with `testnet`)."""
        return self._base

    @base.setter
    def base(self, value: str):
        self._base = value

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
        self.healthy.pop(sym, None)
        task = self._tasks.pop(sym, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info(f"[PriceStream] Unsubscribed from {sym}")

    def is_healthy(self, symbol: str) -> bool:
        """True only if ticks are currently arriving for this symbol."""
        return self.healthy.get(symbol.upper(), False)

    def set_testnet(self, testnet: bool):
        """
        Switch live/testnet. Rebuilds the base URL (not just the flag) and drops
        existing connections so they reconnect against the new endpoint.
        """
        if bool(testnet) == bool(self.testnet) and self._base == self._resolve_base(testnet):
            return
        self.testnet = bool(testnet)
        self._base   = self._resolve_base(self.testnet)
        stale = list(self._active)
        for sym in stale:
            self.healthy.pop(sym, None)
            task = self._tasks.get(sym)
            if task and not task.done():
                task.cancel()
            self._tasks.pop(sym, None)
        for sym in stale:
            self._active.discard(sym)
        if stale:
            logger.info(f"[PriceStream] testnet={self.testnet} — reconnecting {stale}")
            for sym in stale:
                self._active.add(sym)
                self._tasks[sym] = asyncio.create_task(
                    self._stream_loop(sym), name=f"stream-{sym}"
                )

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
        Stops retrying when the endpoint is permanently unusable (404/451),
        so the engine falls back to candle-level SL/TP.
        """
        stream_name = f"{symbol.lower()}@aggTrade"
        backoff     = 1
        # Port 9443 is rate-limited/geo-blocked in some regions; 443 is the
        # same feed on the standard TLS port. Try 9443 first, then 443.
        candidates  = [f"{self._base}/{stream_name}"]
        if not self.testnet and self._base == _STREAM_BASE:
            candidates.append(f"{_STREAM_BASE_443}/{stream_name}")

        idx = 0
        while symbol in self._active:
            url = candidates[min(idx, len(candidates) - 1)]
            try:
                async with websockets.connect(url, ping_interval=20,
                                              ping_timeout=20) as ws:
                    backoff = 1  # reset on successful connect
                    self.healthy[symbol] = True
                    logger.info(f"[PriceStream] Connected: {stream_name} @ {url}")
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
                self.healthy[symbol] = False
                err_str = str(e)
                # 404 = wrong endpoint (e.g. bad testnet host).
                # 451 = geographic/legal block. Neither is worth retrying.
                if "404" in err_str or "451" in err_str:
                    if idx + 1 < len(candidates):
                        logger.warning(
                            f"[PriceStream] {symbol} {url} unusable ({err_str[:60]}) "
                            f"— trying fallback endpoint"
                        )
                        idx += 1
                        continue
                    logger.error(
                        f"[PriceStream] {symbol} permanently unavailable ({err_str[:60]}) "
                        f"— price stream disabled. Engine will use candle-level SL/TP."
                    )
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
