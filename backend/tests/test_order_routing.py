"""
Testnet used to fabricate a filled order locally:

    if TESTNET:
        order = {"orderId": uuid4()[:8], "status": "FILLED", ...}

Nothing ever reached Binance, so the entire order path was unverified — the
exchange filters, the signing, the sizing and the fill price were never
exercised against a real venue.

Testnet now places real orders on testnet.binance.vision. PAPER_TRADING is the
only path that may simulate, and it is opt-in and marked on the trade record.
"""
import pytest

from bot.trade_manager import TradeManager


def _manager(testnet=True, paper=False):
    tm = TradeManager.__new__(TradeManager)
    placed = []

    class C:
        def get_balance(self, asset="USDT"):
            return 10000.0

        def normalize_quantity(self, symbol, quantity, price=0.0):
            return quantity, None

        def normalize_price(self, symbol, price):
            return price

        def place_market_buy(self, symbol, quantity):
            placed.append(("BUY", symbol, quantity))
            return {
                "orderId": 12345,
                "status": "FILLED",
                "executedQty": str(quantity),
                "cummulativeQuoteQty": str(quantity * 84000.0),
                "price": "0.0",
            }

        def place_market_sell(self, symbol, quantity):
            placed.append(("SELL", symbol, quantity))
            return {
                "orderId": 12346,
                "status": "FILLED",
                "executedQty": str(quantity),
                "cummulativeQuoteQty": str(quantity * 84100.0),
                "price": "0.0",
            }

    tm.client = C()
    tm.config = {
        "TESTNET": testnet, "PAPER_TRADING": paper,
        "TRADE_QUANTITY_PERCENT": 10, "MAX_OPEN_TRADES": 3,
    }
    tm.trades = []
    tm.open_trades = {}
    tm._peak_prices = {}
    tm.notifier = tm.email_notifier = tm.resend_notifier = tm.discord_notifier = None
    return tm, placed


# ── routing ──────────────────────────────────────────────────────────────────

def test_testnet_placeholder_forbidden():
    """The old code branched on TESTNET to fabricate. That must not come back."""
    import inspect
    src = inspect.getsource(TradeManager.execute_buy)
    assert '"status":  "FILLED"' not in src
    assert '"status": "FILLED"' not in src, "execute_buy fabricates a fill again"


def test_testnet_places_a_real_order_by_default():
    tm, placed = _manager(testnet=True, paper=False)
    trade = tm.execute_buy("BTCUSDT", {"price": 84000.0}, force=True)

    assert trade is not None
    assert placed == [("BUY", "BTCUSDT", trade["quantity"])]
    assert trade["order_id"] == 12345, "must record the exchange's own order id"
    assert trade["simulated"] is False


def test_paper_mode_does_not_touch_binance():
    tm, placed = _manager(testnet=True, paper=True)
    trade = tm.execute_buy("BTCUSDT", {"price": 84000.0}, force=True)

    assert trade is not None
    assert placed == [], "paper mode must not send anything to Binance"
    assert trade["simulated"] is True


def test_live_never_papers_even_if_flag_set():
    """PAPER_TRADING must never be able to fake a real-money order."""
    tm, placed = _manager(testnet=False, paper=True)
    trade = tm.execute_buy("BTCUSDT", {"price": 84000.0}, force=True)

    assert trade is not None
    assert placed == [("BUY", "BTCUSDT", trade["quantity"])]
    assert trade["simulated"] is False


# ── fill price ───────────────────────────────────────────────────────────────

def test_entry_uses_the_exchange_fill_not_the_ticker():
    """A market order fills at the book price, not at the ticker estimate."""
    tm, _ = _manager(testnet=True, paper=False)
    trade = tm.execute_buy("BTCUSDT", {"price": 80000.0}, force=True)

    assert trade["entry_price"] == pytest.approx(84000.0)
    assert trade["entry_price"] != 80000.0


def test_fill_price_prefers_cumulative_quote():
    order = {
        "executedQty": "0.5",
        "cummulativeQuoteQty": "42000",
        "price": "0.0",
    }
    assert TradeManager._fill_price(order, 1.0) == pytest.approx(84000.0)


def test_fill_price_falls_back_to_individual_fills():
    order = {
        "executedQty": "0",
        "cummulativeQuoteQty": "0",
        "fills": [
            {"qty": "0.2", "price": "100"},
            {"qty": "0.3", "price": "200"},
        ],
    }
    assert TradeManager._fill_price(order, 1.0) == pytest.approx(160.0)


def test_fill_price_falls_back_to_ticker_when_order_is_empty():
    assert TradeManager._fill_price({}, 123.45) == 123.45
    assert TradeManager._fill_price({"price": "0.0"}, 99.0) == 99.0


# ── exit path ────────────────────────────────────────────────────────────────

def test_sell_places_a_real_order_and_uses_its_fill():
    tm, placed = _manager(testnet=True, paper=False)
    trade = tm.execute_buy("BTCUSDT", {"price": 84000.0}, force=True)
    closed = tm.execute_sell(trade["id"], 84100.0, "TEST")

    assert closed["status"] == "CLOSED"
    assert closed["exit_price"] == pytest.approx(84100.0)
    assert closed["exit_order_id"] == 12346
    assert [p[0] for p in placed] == ["BUY", "SELL"]


def test_sell_in_paper_mode_never_hits_binance():
    tm, placed = _manager(testnet=True, paper=True)
    trade = tm.execute_buy("BTCUSDT", {"price": 84000.0}, force=True)
    closed = tm.execute_sell(trade["id"], 84100.0, "TEST")

    assert closed["status"] == "CLOSED"
    assert placed == []


def test_failed_order_leaves_no_trade_recorded():
    tm, _ = _manager(testnet=True, paper=False)
    tm.client.place_market_buy = lambda s, q: {"error": "HTTP 400 filter failure"}

    result = tm.execute_buy("BTCUSDT", {"price": 84000.0}, force=True)

    assert result is None
    assert tm.trades == [], "a rejected order must not be recorded as a trade"
