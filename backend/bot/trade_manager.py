"""
Trade Manager
Handles all trade execution, tracking, and risk management.

Improvements over v1:
- Stop Loss / Take Profit based on user-configured % (not just ATR)
- Trailing Stop with peak-tracking per trade
- Telegram notifications on every trade event
- File I/O lock to prevent race conditions
- open_trades dict rebuilt from file on startup
"""

import json
import os
import uuid
import math
import threading
from datetime import datetime
from typing import Optional, List, Dict
from bot.binance_client import BinanceClient
import logging

logger = logging.getLogger(__name__)

TRADES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "trades.json")
_file_lock = threading.Lock()


# ── File helpers ───────────────────────────────────────────────────────────────

def load_trades() -> List[dict]:
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_trades(trades: List[dict]):
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    with _file_lock:
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f, indent=2, default=str)


def round_step_size(quantity: float, step_size: float) -> float:
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)


# ── Trade Manager ──────────────────────────────────────────────────────────────

class TradeManager:
    def __init__(self, client: BinanceClient, config: dict, notifier=None,
                 email_notifier=None, resend_notifier=None, discord_notifier=None):
        self.client           = client
        self.config           = config
        self.notifier         = notifier
        self.email_notifier   = email_notifier
        self.resend_notifier  = resend_notifier
        self.discord_notifier = discord_notifier
        self.trades: List[dict] = load_trades()

        # Rebuild open_trades dict from file (survives restarts)
        self.open_trades: Dict[str, dict] = {
            t["id"]: t for t in self.trades if t.get("status") == "OPEN"
        }

        # Trailing stop peak tracking: trade_id → highest_price_seen
        self._peak_prices: Dict[str, float] = {
            t["id"]: t["entry_price"]
            for t in self.trades if t.get("status") == "OPEN"
        }

        self.bot_running = False

    # ── Quantity ───────────────────────────────────────────────────────────────

    def get_trade_quantity(self, symbol: str, price: float) -> tuple:
        """
        Size a position from a percentage of the real USDT balance.

        Fails closed. A previous version substituted a fictional $1000 balance
        whenever the read returned 0, which meant an invalid API key, a network
        failure or a Binance outage all produced orders sized against money the
        account never had. An unreadable balance now refuses the trade.

        Returns (quantity, error).
        """
        if not price or price <= 0:
            return 0.0, f"Cannot size {symbol}: invalid price {price}"

        balance = self.client.get_balance("USDT")

        if balance is None:
            return 0.0, (
                f"Cannot size {symbol}: USDT balance could not be read from "
                f"Binance (check the API key, permissions and network)"
            )
        if balance <= 0:
            return 0.0, (
                f"Cannot size {symbol}: USDT balance is {balance:.8f} — "
                f"no funds available to trade with"
            )

        trade_pct   = self.config.get("TRADE_QUANTITY_PERCENT", 10) / 100
        usdt_to_use = balance * trade_pct
        if usdt_to_use <= 0:
            return 0.0, f"Cannot size {symbol}: TRADE_QUANTITY_PERCENT produced 0"

        return round(usdt_to_use / price, 8), None

    def size_order(self, symbol: str, quantity: float, price: float) -> tuple:
        """
        Snap the order size onto Binance's LOT_SIZE grid and check MIN_NOTIONAL.
        Returns (quantity, error). Falls back to the raw quantity when exchange
        info is unavailable (e.g. no network) so trading is not hard-blocked.
        """
        try:
            qty, err = self.client.normalize_quantity(symbol, quantity, price)
            if err:
                logger.warning(f"Order sizing rejected for {symbol}: {err}")
                return 0.0, err
            if abs(qty - quantity) > 1e-12:
                logger.debug(f"Order size {quantity} -> {qty} (LOT_SIZE grid)")
            return qty, None
        except Exception as e:
            logger.warning(f"Could not read exchange filters for {symbol}: {e}")
            return quantity, None

    # ── SL / TP calculation ────────────────────────────────────────────────────

    def _calculate_sl_tp(self, side: str, entry_price: float, signal: dict) -> tuple:
        """
        Returns (stop_loss, take_profit) using the larger of:
        - User-configured % from settings
        - ATR-based value from signal (already computed in indicators.py)
        """
        sl_pct = self.config.get("STOP_LOSS_PERCENT", 2.0) / 100
        tp_pct = self.config.get("TAKE_PROFIT_PERCENT", 4.0) / 100

        # ATR-based values from signal generator
        atr_sl = signal.get("stop_loss")
        atr_tp = signal.get("take_profit")

        if side == "BUY":
            sl_from_pct = entry_price * (1 - sl_pct)
            tp_from_pct = entry_price * (1 + tp_pct)
            # Use whichever stop loss is lower (wider protection)
            stop_loss   = min(sl_from_pct, atr_sl) if atr_sl else sl_from_pct
            take_profit = max(tp_from_pct, atr_tp) if atr_tp else tp_from_pct
        else:
            sl_from_pct = entry_price * (1 + sl_pct)
            tp_from_pct = entry_price * (1 - tp_pct)
            stop_loss   = max(sl_from_pct, atr_sl) if atr_sl else sl_from_pct
            take_profit = min(tp_from_pct, atr_tp) if atr_tp else tp_from_pct

        # Snap to the exchange tick size so stops are actually triggerable.
        sym = signal.get("_symbol") or ""
        if sym:
            try:
                stop_loss   = self.client.normalize_price(sym, stop_loss)
                take_profit = self.client.normalize_price(sym, take_profit)
            except Exception:
                pass
        return round(stop_loss, 8), round(take_profit, 8)

    # ── Execute BUY ────────────────────────────────────────────────────────────

    def execute_buy(self, symbol: str, signal: dict, force: bool = False,
                    quantity: Optional[float] = None) -> Optional[dict]:
        # Max open trades check (global) — force=True pe skip (manual trade)
        if not force:
            open_count = len([t for t in self.trades if t.get("status") == "OPEN"])
            max_trades = self.config.get("MAX_OPEN_TRADES", 3)
            if open_count >= max_trades:
                logger.info(f"Max open trades ({max_trades}) reached — skipping BUY")
                return None

        price = signal["price"]

        if quantity and quantity > 0:
            raw_qty = float(quantity)
        else:
            raw_qty, qty_err = self.get_trade_quantity(symbol, price)
            if qty_err:
                logger.error(f"Skipping BUY {symbol}: {qty_err}")
                return None

        # Snap to Binance LOT_SIZE grid and verify MIN_NOTIONAL before sending
        quantity, size_err = self.size_order(symbol, raw_qty, price)
        if size_err or quantity <= 0:
            logger.warning(f"Skipping BUY {symbol}: {size_err or 'quantity 0'}")
            return None

        signal = dict(signal)
        signal["_symbol"] = symbol
        stop_loss, take_profit = self._calculate_sl_tp("BUY", price, signal)
        signal.pop("_symbol", None)

        # Place order
        if self.config.get("TESTNET", True):
            order = {
                "orderId": str(uuid.uuid4())[:8],
                "symbol":  symbol,
                "status":  "FILLED",
                "executedQty": str(quantity),
                "price":   str(price),
                "side":    "BUY",
            }
        else:
            order = self.client.place_market_buy(symbol, quantity)

        if not isinstance(order, dict) or "error" in order:
            err = order.get("error") if isinstance(order, dict) else order
            logger.error(f"BUY order failed: {err}")
            return None

        trade = {
            "id":           str(uuid.uuid4()),
            "symbol":       symbol,
            "side":         "BUY",
            "entry_price":  price,
            "quantity":     float(quantity),
            "stop_loss":    stop_loss,
            "take_profit":  take_profit,
            "peak_price":   price,          # for trailing stop
            "status":       "OPEN",
            "confidence":   signal.get("confidence", 0),
            "signals":      signal.get("signals", []),
            "order_id":     order.get("orderId"),
            "entry_time":   datetime.utcnow().isoformat(),
            "exit_price":   None,
            "exit_time":    None,
            "pnl":          None,
            "pnl_percent":  None,
            "close_reason": None,
        }

        self.trades.append(trade)
        self.open_trades[trade["id"]] = trade
        self._peak_prices[trade["id"]] = price
        save_trades(self.trades)

        # Telegram + Email + Resend + Discord
        if self.notifier:         self.notifier.trade_opened(trade)
        if self.email_notifier:   self.email_notifier.trade_opened(trade)
        if self.resend_notifier:  self.resend_notifier.trade_opened(trade)
        if self.discord_notifier: self.discord_notifier.trade_opened(trade)

        logger.info(f"✅ BUY {symbol} @ {price} | SL: {stop_loss} | TP: {take_profit}")
        return trade

    # ── Execute SELL ───────────────────────────────────────────────────────────

    def execute_sell(self, trade_id: str, current_price: float,
                     reason: str = "SIGNAL") -> Optional[dict]:
        trade = next((t for t in self.trades
                      if t["id"] == trade_id and t["status"] == "OPEN"), None)
        if not trade:
            return None

        symbol   = trade["symbol"]
        quantity = trade["quantity"]

        if self.config.get("TESTNET", True):
            order = {"orderId": str(uuid.uuid4())[:8], "status": "FILLED", "side": "SELL"}
        else:
            order = self.client.place_market_sell(symbol, quantity)

        if not isinstance(order, dict) or "error" in order:
            err = order.get("error") if isinstance(order, dict) else order
            logger.error(f"SELL order failed: {err}")
            return None

        entry_price  = trade["entry_price"]
        pnl          = (current_price - entry_price) * quantity
        pnl_percent  = ((current_price - entry_price) / entry_price) * 100

        trade["status"]       = "CLOSED"
        trade["exit_price"]   = round(current_price, 8)
        trade["exit_time"]    = datetime.utcnow().isoformat()
        trade["pnl"]          = round(pnl, 4)
        trade["pnl_percent"]  = round(pnl_percent, 2)
        trade["close_reason"] = reason

        self.open_trades.pop(trade_id, None)
        self._peak_prices.pop(trade_id, None)
        save_trades(self.trades)

        # Telegram + Email + Resend + Discord
        if self.notifier:         self.notifier.trade_closed(trade)
        if self.email_notifier:   self.email_notifier.trade_closed(trade)
        if self.resend_notifier:  self.resend_notifier.trade_closed(trade)
        if self.discord_notifier: self.discord_notifier.trade_closed(trade)

        logger.info(f"✅ SELL {symbol} @ {current_price} | PnL: {pnl:.4f} ({reason})")
        return trade

    # ── SL / TP / Trailing Stop checker ───────────────────────────────────────

    def check_stop_loss_take_profit(self, symbol: str,
                                    current_price: float) -> List[dict]:
        """
        Called every bot cycle (or from price stream).
        Checks SL, TP, and trailing stop for all open trades of `symbol`.
        """
        closed = []
        trailing_enabled = self.config.get("TRAILING_STOP", True)
        trail_pct        = self.config.get("TRAILING_STOP_PERCENT", 1.0) / 100

        for trade in list(self.trades):
            if trade["symbol"] != symbol or trade["status"] != "OPEN":
                continue

            tid = trade["id"]
            sl  = trade.get("stop_loss")
            tp  = trade.get("take_profit")

            # Update trailing stop peak
            if trailing_enabled:
                peak = self._peak_prices.get(tid, trade["entry_price"])
                if current_price > peak:
                    peak = current_price
                    self._peak_prices[tid] = peak
                    trade["peak_price"] = peak
                    # Raise stop loss to trail below peak
                    new_sl = round(peak * (1 - trail_pct), 4)
                    if sl is None or new_sl > sl:
                        trade["stop_loss"] = new_sl
                        sl = new_sl
                        logger.debug(f"Trailing SL updated → {new_sl} for {tid[:8]}")

            # Take Profit hit
            if tp and current_price >= tp:
                result = self.execute_sell(tid, current_price, "TAKE_PROFIT")
                if result:
                    closed.append(result)
                continue

            # Stop Loss hit
            if sl and current_price <= sl:
                reason = "TRAILING_STOP" if trailing_enabled and trade.get("peak_price", trade["entry_price"]) > trade["entry_price"] else "STOP_LOSS"
                result = self.execute_sell(tid, current_price, reason)
                if result:
                    closed.append(result)

        return closed

    # ── Accessors ──────────────────────────────────────────────────────────────

    def get_open_trades(self) -> List[dict]:
        return [t for t in self.trades if t["status"] == "OPEN"]

    def get_trade_history(self, limit: int = 50) -> List[dict]:
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        return sorted(closed, key=lambda x: x.get("exit_time", ""), reverse=True)[:limit]

    def get_stats(self) -> dict:
        closed      = [t for t in self.trades if t["status"] == "CLOSED"]
        open_trades = self.get_open_trades()
        total       = len(closed)
        winning     = [t for t in closed if (t.get("pnl") or 0) > 0]
        losing      = [t for t in closed if (t.get("pnl") or 0) <= 0]
        total_pnl   = sum(t.get("pnl") or 0 for t in closed)
        win_rate    = (len(winning) / total * 100) if total > 0 else 0

        return {
            "total_trades":    total,
            "open_trades":     len(open_trades),
            "winning_trades":  len(winning),
            "losing_trades":   len(losing),
            "win_rate":        round(win_rate, 2),
            "total_pnl":       round(total_pnl, 4),
            "bot_running":     self.bot_running,
        }
