"""
Binance API Client
Handles all communication with Binance exchange
"""

import pandas as pd
import requests
import hmac
import hashlib
import time
from urllib.parse import urlencode
from typing import Optional, List, Dict


class BinanceClient:
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet

        if testnet:
            self.base_url = "https://testnet.binance.vision/api"
        else:
            self.base_url = "https://api.binance.com/api"

        self.headers = {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

    def _sign(self, params: dict) -> dict:
        """Sign request with HMAC SHA256"""
        params['timestamp'] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params

    def _get(self, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """GET request"""
        if params is None:
            params = {}
        if signed:
            params = self._sign(params)
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, endpoint: str, params: dict = None) -> dict:
        """POST request"""
        if params is None:
            params = {}
        params = self._sign(params)
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def _delete(self, endpoint: str, params: dict = None) -> dict:
        """DELETE request"""
        if params is None:
            params = {}
        params = self._sign(params)
        try:
            response = requests.delete(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    # ─── Market Data ───────────────────────────────────────────────────────────

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV candle data — uses public Binance API (no auth needed)"""
        # Always use public Binance for market data (works on all servers)
        public_url = "https://api.binance.com/api/v3/klines"
        try:
            response = requests.get(public_url, params={
                "symbol": symbol, "interval": interval, "limit": limit
            }, timeout=10)
            data = response.json()
        except Exception:
            data = self._get("/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})

        if isinstance(data, list):
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return df
        return pd.DataFrame()

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get current price — uses public Binance API"""
        try:
            resp = requests.get("https://api.binance.com/api/v3/ticker/price",
                                params={"symbol": symbol}, timeout=10)
            data = resp.json()
        except Exception:
            data = self._get("/v3/ticker/price", {"symbol": symbol})
        if "price" in data:
            return float(data["price"])
        return None

    def get_24h_stats(self, symbol: str) -> dict:
        """Get 24h price statistics — uses public Binance API"""
        try:
            resp = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                                params={"symbol": symbol}, timeout=10)
            return resp.json()
        except Exception:
            return self._get("/v3/ticker/24hr", {"symbol": symbol})

    def get_order_book(self, symbol: str, limit: int = 10) -> dict:
        """Get order book"""
        return self._get("/v3/depth", {"symbol": symbol, "limit": limit})

    # ─── Account ───────────────────────────────────────────────────────────────

    def get_account_info(self) -> dict:
        """Get account balances"""
        return self._get("/v3/account", signed=True)

    def get_balance(self, asset: str = "USDT") -> float:
        """Get specific asset balance"""
        account = self.get_account_info()
        if "balances" in account:
            for bal in account["balances"]:
                if bal["asset"] == asset:
                    return float(bal["free"])
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
