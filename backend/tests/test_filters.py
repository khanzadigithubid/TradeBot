"""Tests for Binance exchange filter handling and order sizing."""

import pytest


def test_filters_parsed_from_exchange_info():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s", testnet=True)
    c.get_exchange_info = lambda sym=None: {
        "filters": [
            {"filterType": "LOT_SIZE", "minQty": "0.00001000",
             "maxQty": "9000.00000000", "stepSize": "0.00001000"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "5.00000000"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
        ]
    }
    f = c.get_symbol_filters("BTCUSDT")
    assert f["step_size"] == pytest.approx(0.00001)
    assert f["min_qty"] == pytest.approx(0.00001)
    assert f["min_notional"] == pytest.approx(5.0)
    assert f["tick_size"] == pytest.approx(0.01)
    assert f["qty_precision"] == 5
    assert f["found"] is True


def test_quantity_snapped_to_step_grid():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s")
    c.get_exchange_info = lambda sym=None: {
        "filters": [
            {"filterType": "LOT_SIZE", "minQty": "0.001",
             "maxQty": "1000", "stepSize": "0.001"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
        ]
    }
    # 0.1234567 must land on the 0.001 grid
    qty, err = c.normalize_quantity("BTCUSDT", 0.1234567, price=80000)
    assert err is None
    assert qty == pytest.approx(0.123)


def test_min_qty_enforced():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s")
    c.get_exchange_info = lambda sym=None: {
        "filters": [{"filterType": "LOT_SIZE", "minQty": "0.01",
                     "maxQty": "1000", "stepSize": "0.01"}]
    }
    qty, err = c.normalize_quantity("BTCUSDT", 0.00001, price=100)
    assert qty == pytest.approx(0.01)
    assert err is None


def test_max_qty_rejected():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s")
    c.get_exchange_info = lambda sym=None: {
        "filters": [{"filterType": "LOT_SIZE", "minQty": "0.001",
                     "maxQty": "1", "stepSize": "0.001"}]
    }
    qty, err = c.normalize_quantity("BTCUSDT", 5.0, price=100)
    assert qty == 0.0
    assert "max qty" in err


def test_min_notional_rejected_with_clear_message():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s")
    c.get_exchange_info = lambda sym=None: {
        "filters": [
            {"filterType": "LOT_SIZE", "minQty": "0.001",
             "maxQty": "1000", "stepSize": "0.001"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
        ]
    }
    qty, err = c.normalize_quantity("BTCUSDT", 0.05, price=100)  # $5 notional
    assert qty == 0.0
    assert "minimum notional" in err
    assert "TRADE_QUANTITY_PERCENT" in err, "error should tell the user how to fix it"


def test_zero_and_negative_quantity_rejected():
    from bot.binance_client import BinanceClient
    c = BinanceClient("k", "s")
    for bad in (0, -1, -0.5):
        qty, err = c.normalize_quantity("BTCUSDT", bad, price=100)
        assert qty == 0.0
        assert err


def test_price_snapped_to_tick():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s")
    c.get_exchange_info = lambda sym=None: {
        "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.10"}]
    }
    assert c.normalize_price("BTCUSDT", 100.127) == pytest.approx(100.1)
    assert c.normalize_price("BTCUSDT", 100.181) == pytest.approx(100.2)


def test_missing_exchange_info_falls_back_to_defaults():
    from bot.binance_client import BinanceClient

    c = BinanceClient("k", "s")
    c.get_exchange_info = lambda sym=None: {}
    qty, err = c.normalize_quantity("BTCUSDT", 1.23456789, price=100)
    assert err is None
    assert qty > 0


def test_size_order_blocks_undersized_trade(trade_manager, fake_client):
    fake_client._filters = dict(fake_client._filters, min_notional=1000.0)
    qty, err = trade_manager.size_order("BTCUSDT", 1.0, price=100.0)
    assert qty == 0.0
    assert err and "notional" in err


def test_execute_buy_refuses_undersized_order(trade_manager, fake_client):
    """No trade record and no order when the size cannot be placed."""
    fake_client._filters = dict(fake_client._filters, min_notional=100000.0)
    signal = {"price": 100.0, "confidence": 99, "signals": [],
              "stop_loss": None, "take_profit": None}
    trade = trade_manager.execute_buy("BTCUSDT", signal, force=True)
    assert trade is None
    assert trade_manager.get_open_trades() == []


def test_execute_buy_honours_explicit_quantity(trade_manager):
    signal = {"price": 100.0, "confidence": 99, "signals": [],
              "stop_loss": None, "take_profit": None}
    trade = trade_manager.execute_buy("BTCUSDT", signal, force=True, quantity=2.5)
    assert trade is not None
    assert trade["quantity"] == pytest.approx(2.5)   # already on the 0.001 grid


def test_execute_buy_snapshots_to_lot_grid(trade_manager):
    signal = {"price": 100.0, "confidence": 99, "signals": [],
              "stop_loss": None, "take_profit": None}
    trade = trade_manager.execute_buy("BTCUSDT", signal, force=True, quantity=1.23456789)
    assert trade is not None
    assert trade["quantity"] == pytest.approx(1.235)


def test_sl_tp_snap_to_tick_size(trade_manager, fake_client):
    """Stop levels must be on the exchange tick or they may never trigger."""
    fake_client._filters = dict(fake_client._filters, tick_size=0.10)
    signal = {"price": 100.37, "confidence": 99, "signals": [],
              "stop_loss": None, "take_profit": None, "_symbol": "BTCUSDT"}
    sl, tp = trade_manager._calculate_sl_tp("BUY", 100.37, signal)
    # Every level must be an exact multiple of the tick size.
    assert abs(round(sl / 0.10) - sl / 0.10) < 1e-6
    assert abs(round(tp / 0.10) - tp / 0.10) < 1e-6
    assert sl < 100.37 < tp


def test_execute_buy_stores_tick_aligned_stops(trade_manager, fake_client):
    """End-to-end: the persisted trade's SL/TP must be triggerable."""
    fake_client._filters = dict(fake_client._filters, tick_size=0.10)
    signal = {"price": 100.37, "confidence": 99, "signals": [],
              "stop_loss": None, "take_profit": None}
    trade = trade_manager.execute_buy("BTCUSDT", signal, force=True, quantity=1.0)
    assert trade is not None
    for level in (trade["stop_loss"], trade["take_profit"]):
        assert abs(round(level / 0.10) - level / 0.10) < 1e-6
    assert trade["stop_loss"] < trade["entry_price"] < trade["take_profit"]


def test_max_open_trades_blocks_auto_buy(trade_manager, config):
    from tests.test_risk import open_trade
    for i in range(config["MAX_OPEN_TRADES"]):
        t = open_trade(trade_manager, symbol=f"SYM{i}USDT")
        t["id"] = f"t{i}"
    signal = {"price": 100.0, "confidence": 99, "signals": [],
              "stop_loss": None, "take_profit": None}
    assert trade_manager.execute_buy("BTCUSDT", signal) is None
