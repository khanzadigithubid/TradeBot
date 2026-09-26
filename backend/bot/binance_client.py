"""
Binance API Client
Handles all communication with Binance exchange
"""

import pandas as pd
import requests
import hmac
import hashlib
import logging
import math
import time
from urllib.parse import urlencode
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Binance rejects a signed request with -1021 when its timestamp falls outside
# this window. The default is only 5000ms, which a few seconds of clock drift
# (or a slow request) will blow through.
RECV_WINDOW_MS = 60_000


class BinanceClient:
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self._info_cache: dict = {}
        self._clock_offset: Optional[int] = None

        if testnet:
            self.base_url = "https://testnet.binance.vision/api"
        else:
            self.base_url = "https://api.binance.com/api"

        self.headers = {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

    def _server_time_offset_ms(self) -> int:
        """
        Signed requests are rejected with -1021 when the local clock drifts
        outside Binance's recvWindow. A machine only ~600ms slow is enough to
        start losing orders intermittently, so the offset is measured once
        against the exchange and applied to every signature.
        """
        if self._clock_offset is not None:
            return self._clock_offset
        try:
            server = self._get("/v3/time")
            if isinstance(server, dict) and "serverTime" in server:
                self._clock_offset = int(server["serverTime"]) - int(time.time() * 1000)
                if abs(self._clock_offset) > 500:
                    logger.warning(
                        f"Local clock is {self._clock_offset/1000:+.2f}s away from "
                        f"Binance — correcting signed request timestamps"
                    )
            else:
                # An error payload is not an exception, so the offset would
                # otherwise stay None and break every later signature.
                logger.debug(f"Unexpected /v3/time response: {str(server)[:120]}")
                self._clock_offset = 0
        except Exception as e:
            logger.debug(f"Could not read Binance server time: {e}")
            self._clock_offset = 0
        return self._clock_offset

    def _sign(self, params: dict) -> dict:
        """Sign request with HMAC SHA256.

        Builds a new dict instead of mutating the caller's. The retry path has to
        be able to sign the original values again with a corrected timestamp —
        a params dict that still carries the rejected signature would be sent
        to the exchange unchanged.
        """
        signed = {k: v for k, v in (params or {}).items()
                  if k not in ("timestamp", "recvWindow", "signature")}
        signed["timestamp"]  = int(time.time() * 1000) + self._server_time_offset_ms()
        signed["recvWindow"] = RECV_WINDOW_MS
        query_string = urlencode(signed)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        signed['signature'] = signature
        return signed

    def _request(self, method: str, endpoint: str, params: dict = None,
                 signed: bool = False, _retry: bool = True) -> dict:
        params = dict(params or {})
        # Keep the unsigned values so a clock retry can sign them again.
        unsigned = dict(params)
        if signed:
            params = self._sign(params)
        try:
            fn = {
                "GET": requests.get,
                "POST": requests.post,
                "DELETE": requests.delete,
            }[method]
            response = fn(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Keep Binance's own error code and message. str(e) on an HTTPError is
            # just "400 Client Error", which hides -1021 and every other reason
            # the exchange actually rejected the request.
            body = getattr(getattr(e, "response", None), "text", "") or ""
            detail = body[:300]
            if not detail:
                detail = str(e)

            if signed and _retry and "-1021" in detail:
                # Clock slipped mid-flight. Resync and sign the ORIGINAL values
                # again — resending the rejected signature would fail identically.
                logger.warning("Binance rejected the timestamp (-1021) — resyncing clock and retrying")
                self._clock_offset = None
                return self._request(method, endpoint, unsigned, signed=True, _retry=False)

            logger.error(f"{method} {endpoint} failed: {detail}")
            return {"error": detail, "status": getattr(e, "response", None) and e.response.status_code}

    def _get(self, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """GET request"""
        return self._request("GET", endpoint, params, signed)

    def _post(self, endpoint: str, params: dict = None) -> dict:
        """POST request"""
        return self._request("POST", endpoint, params, signed=True)

    def _delete(self, endpoint: str, params: dict = None) -> dict:
        """DELETE request"""
        return self._request("DELETE", endpoint, params, signed=True)

    # ─── Market Data ───────────────────────────────────────────────────────────

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV candle data"""
        from bot.market_data import get_klines as _get_klines
        return _get_klines(symbol, interval, limit)

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get current price"""
        from bot.market_data import get_price as _get_price
        return _get_price(symbol)

    def get_24h_stats(self, symbol: str) -> dict:
        """Get 24h price statistics"""
        from bot.market_data import get_24h_stats as _get_24h_stats
        return _get_24h_stats(symbol)

    def get_order_book(self, symbol: str, limit: int = 10) -> dict:
        """Get order book"""
        return self._get("/v3/depth", {"symbol": symbol, "limit": limit})

    # ─── Account ───────────────────────────────────────────────────────────────

    def get_account_info(self) -> dict:
        """Get account balances"""
        return self._get("/v3/account", signed=True)

    def get_balance(self, asset: str = "USDT"):
        """
        Free balance for `asset`.

        Returns None when the balance could NOT be read (bad key, network down,
        exchange error) and a float when the read succeeded. A genuine zero
        balance returns 0.0 — callers must be able to tell the two apart, or
        they will size orders from a number that does not exist.
        """
        try:
            account = self.get_account_info()
        except Exception as e:
            logger.error(f"Balance read failed for {asset}: {e}")
            return None

        if not isinstance(account, dict) or "error" in account:
            err = account.get("error") if isinstance(account, dict) else account
            logger.error(f"Balance read failed for {asset}: {err}")
            return None

        for bal in account.get("balances", []) or []:
            if bal.get("asset") == asset:
                try:
                    return float(bal.get("free", 0))
                except (TypeError, ValueError):
                    return None
        return 0.0

    # ─── Orders ────────────────────────────────────────────────────────────────

    def place_market_buy(self, symbol: str, quantity: float) -> dict:
        """Place market buy order"""
        return self._post("/v3/order", {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": quantity
        })

    def place_market_sell(self, symbol: str, quantity: float) -> dict:
        """Place market sell order"""
        return self._post("/v3/order", {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": quantity
        })

    def place_limit_buy(self, symbol: str, quantity: float, price: float) -> dict:
        """Place limit buy order"""
        return self._post("/v3/order", {
            "symbol": symbol,
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": price
        })

    def place_limit_sell(self, symbol: str, quantity: float, price: float) -> dict:
        """Place limit sell order"""
        return self._post("/v3/order", {
            "symbol": symbol,
            "side": "SELL",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": price
        })

    def place_oco_sell(self, symbol: str, quantity: float, price: float, stop_price: float, stop_limit_price: float) -> dict:
        """Place OCO order (Take Profit + Stop Loss together)"""
        return self._post("/v3/order/oco", {
            "symbol": symbol,
            "side": "SELL",
            "quantity": quantity,
            "price": price,              # Take Profit
            "stopPrice": stop_price,     # Stop trigger
            "stopLimitPrice": stop_limit_price,
            "stopLimitTimeInForce": "GTC"
        })

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order"""
        return self._delete("/v3/order", {
            "symbol": symbol,
            "orderId": order_id
        })

    def get_open_orders(self, symbol: str = None) -> list:
        """Get all open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._get("/v3/openOrders", params, signed=True)

    # ─── Exchange Filters ───────────────────────────────────────────────────

    def get_exchange_info(self, symbol: str = None) -> dict:
        """Raw /v3/exchangeInfo payload (cached per symbol)."""
        sym = (symbol or "").upper()
        if sym not in self._info_cache:
            info = self._get("/v3/exchangeInfo")
            entry = None
            if isinstance(info, dict) and "symbols" in info:
                for s in info["symbols"]:
                    if s.get("symbol") == sym:
                        entry = s
                        break
            self._info_cache[sym] = entry
        return self._info_cache[sym] or {}

    def get_symbol_filters(self, symbol: str) -> dict:
        """
        Extract the filters that matter for sizing a market order.
        Returns a dict of the LOT_SIZE and NOTIONAL constraints for `symbol`.
        """
        info  = self.get_exchange_info(symbol)
        out   = {
            "step_size":        0.00001,
            "min_qty":          0.0,
            "max_qty":          0.0,
            "min_notional":     0.0,
            "tick_size":        0.01,
            "price_precision":  2,
            "found":            False,
        }
        for f in info.get("filters", []) or []:
            ftype = f.get("filterType")
            if ftype == "LOT_SIZE":
                out["step_size"] = float(f.get("stepSize", out["step_size"]))
                out["min_qty"]   = float(f.get("minQty", 0))
                out["max_qty"]   = float(f.get("maxQty", 0))
                out["found"]     = True
            elif ftype in ("MARKET_LOT_SIZE",):
                if not float(f.get("minQty", 0)):
                    continue
                out["step_size"] = float(f.get("stepSize", out["step_size"]))
                out["min_qty"]   = float(f.get("minQty", 0))
                out["max_qty"]   = float(f.get("maxQty", 0))
                out["found"]     = True
            elif ftype in ("MIN_NOTIONAL", "NOTIONAL"):
                out["min_notional"] = float(
                    f.get("minNotional", f.get("notional", 0)) or 0
                )
                out["found"] = True
            elif ftype == "PRICE_FILTER":
                out["tick_size"] = float(f.get("tickSize", out["tick_size"]))
        # Derive precision from step size (0.001 -> 3 dp)
        if out["step_size"] > 0:
            out["qty_precision"] = max(
                0, int(round(-math.log10(out["step_size"])))
            )
        else:
            out["qty_precision"] = 5
        return out

    def normalize_quantity(self, symbol: str, quantity: float,
                           price: float = 0.0) -> tuple:
        """
        Snap `quantity` onto the exchange's LOT_SIZE grid and verify it
        satisfies MIN_NOTIONAL.
        Returns (quantity, error_message). `error_message` is None on success.
        """
        if quantity <= 0:
            return 0.0, f"Quantity must be > 0 (got {quantity})"

        f = self.get_symbol_filters(symbol)
        step   = f["step_size"] or 0.00001
        prec   = f["qty_precision"]

        # Snap to step size using decimal-safe rounding
        steps     = round(quantity / step)
        snapped   = round(steps * step, prec)

        if snapped <= 0:
            # Below a single step. If the exchange defines a min qty we can
            # still place a valid order by rounding up to it; otherwise the
            # request is genuinely unusable.
            if f["min_qty"] > 0:
                snapped = round(f["min_qty"], prec)
            else:
                return 0.0, (
                    f"Quantity {quantity} rounds to 0 at step size {step} "
                    f"for {symbol}"
                )

        if f["min_qty"] and snapped < f["min_qty"]:
            snapped = round(f["min_qty"], prec)
            if snapped <= 0:
                return 0.0, (
                    f"Quantity below min qty {f['min_qty']} for {symbol}"
                )

        if f["max_qty"] and snapped > f["max_qty"]:
            return 0.0, f"Quantity exceeds max qty {f['max_qty']} for {symbol}"

        if price > 0 and f["min_notional"]:
            notional = snapped * price
            if notional < f["min_notional"]:
                return 0.0, (
                    f"Order value ${notional:.4f} is below Binance minimum "
                    f"notional ${f['min_notional']} for {symbol}. "
                    f"Increase TRADE_QUANTITY_PERCENT or the account balance."
                )

        return snapped, None

    def normalize_price(self, symbol: str, price: float) -> float:
        """Snap a price onto the exchange's PRICE_FILTER tick size."""
        f   = self.get_symbol_filters(symbol)
        tick = f["tick_size"] or 0.01
        return round(round(price / tick) * tick, 8)

    def clear_filter_cache(self):
        self._info_cache.clear()

    def get_order_history(self, symbol: str, limit: int = 50) -> list:
        """Get order history"""
        return self._get("/v3/allOrders", {
            "symbol": symbol,
            "limit": limit
        }, signed=True)

    def test_connection(self) -> bool:
        """Test API connection"""
        result = self._get("/v3/ping")
        return result == {}
