"""
Trade Manager
Handles all trade execution, tracking, and risk management
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from bot.binance_client import BinanceClient
from bot.indicators import generate_ai_signal
import math


TRADES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "trades.json")


def load_trades() -> List[dict]:
    """Load trades from file"""
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    return []


def save_trades(trades: List[dict]):
    """Save trades to file"""
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2, default=str)


def round_step_size(quantity: float, step_size: float) -> float:
    """Round quantity to valid step size"""
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)


class TradeManager:
    def __init__(self, client: BinanceClient, config: dict):
        self.client = client
        self.config = config
        self.trades = load_trades()
        self.open_trades: Dict[str, dict] = {}
        self.bot_running = False

    def get_trade_quantity(self, symbol: str, price: float) -> float:
        """Calculate how much to buy based on % of balance"""
        balance = self.client.get_balance("USDT")
        trade_percent = self.config.get("TRADE_QUANTITY_PERCENT", 10) / 100
        usdt_to_use = balance * trade_percent
        quantity = usdt_to_use / price
        return round(quantity, 5)

    def execute_buy(self, symbol: str, signal: dict) -> Optional[dict]:
        """Execute a buy trade"""
        # Check max open trades
        open_for_symbol = [t for t in self.trades if t.get("symbol") == symbol and t.get("status") == "OPEN"]
        max_trades = self.config.get("MAX_OPEN_TRADES", 3)
        if len(open_for_symbol) >= max_trades:
            return None

        price = signal["price"]
        quantity = self.get_trade_quantity(symbol, price)

        if quantity <= 0:
            return None

        # Place order on Binance
        if self.config.get("TESTNET", True):
            # Simulated order for paper trading
            order = {
                "orderId": str(uuid.uuid4())[:8],
                "symbol": symbol,
                "status": "FILLED",
                "executedQty": str(quantity),
                "price": str(price),
                "side": "BUY",
            }
        else:
            order = self.client.place_market_buy(symbol, quantity)

        if "error" not in order:
            trade = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "side": "BUY",
                "entry_price": price,
                "quantity": float(quantity),
                "stop_loss": signal.get("stop_loss"),
                "take_profit": signal.get("take_profit"),
                "status": "OPEN",
                "confidence": signal.get("confidence", 0),
                "signals": signal.get("signals", []),
                "order_id": order.get("orderId"),
                "entry_time": datetime.utcnow().isoformat(),
                "exit_price": None,
                "exit_time": None,
                "pnl": None,
                "pnl_percent": None,
            }
            self.trades.append(trade)
            self.open_trades[trade["id"]] = trade
            save_trades(self.trades)
            return trade
        return None

    def execute_sell(self, trade_id: str, current_price: float, reason: str = "SIGNAL") -> Optional[dict]:
        """Execute a sell/close trade"""
        trade = None
        for t in self.trades:
            if t["id"] == trade_id and t["status"] == "OPEN":
                trade = t
                break

        if not trade:
            return None

        symbol = trade["symbol"]
        quantity = trade["quantity"]

        if self.config.get("TESTNET", True):
            order = {
                "orderId": str(uuid.uuid4())[:8],
                "status": "FILLED",
                "side": "SELL"
            }
        else:
            order = self.client.place_market_sell(symbol, quantity)

        if "error" not in order:
            entry_price = trade["entry_price"]
            pnl = (current_price - entry_price) * quantity
            pnl_percent = ((current_price - entry_price) / entry_price) * 100

            trade["status"] = "CLOSED"
            trade["exit_price"] = current_price
            trade["exit_time"] = datetime.utcnow().isoformat()
            trade["pnl"] = round(pnl, 4)
            trade["pnl_percent"] = round(pnl_percent, 2)
            trade["close_reason"] = reason

            if trade["id"] in self.open_trades:
                del self.open_trades[trade["id"]]

            save_trades(self.trades)
            return trade
        return None

    def check_stop_loss_take_profit(self, symbol: str, current_price: float):
        """Check and trigger stop loss / take profit for open trades"""
        closed = []
        for t in self.trades:
            if t["symbol"] == symbol and t["status"] == "OPEN":
                sl = t.get("stop_loss")
                tp = t.get("take_profit")

                if sl and current_price <= sl:
                    result = self.execute_sell(t["id"], current_price, "STOP_LOSS")
                    if result:
                        closed.append(result)

                elif tp and current_price >= tp:
                    result = self.execute_sell(t["id"], current_price, "TAKE_PROFIT")
                    if result:
                        closed.append(result)
        return closed

    def get_open_trades(self) -> List[dict]:
        """Get all currently open trades"""
        return [t for t in self.trades if t["status"] == "OPEN"]

    def get_trade_history(self, limit: int = 50) -> List[dict]:
        """Get closed trade history"""
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        return sorted(closed, key=lambda x: x.get("exit_time", ""), reverse=True)[:limit]

    def get_stats(self) -> dict:
        """Get overall bot performance stats"""
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        open_trades = self.get_open_trades()

        total_trades = len(closed)
        winning = [t for t in closed if (t.get("pnl") or 0) > 0]
        losing = [t for t in closed if (t.get("pnl") or 0) <= 0]
        total_pnl = sum(t.get("pnl") or 0 for t in closed)
        win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0

        return {
            "total_trades": total_trades,
            "open_trades": len(open_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 4),
            "bot_running": self.bot_running,
        }
