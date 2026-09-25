"""Tests for stop-loss / take-profit / trailing-stop behaviour."""

import pytest

from tests.conftest import make_candles


def open_trade(tm, symbol="BTCUSDT", entry=100.0, sl=98.0, tp=104.0, qty=1.0):
    trade = {
        "id": "t1", "symbol": symbol, "side": "BUY",
        "entry_price": entry, "quantity": qty,
        "stop_loss": sl, "take_profit": tp, "peak_price": entry,
        "status": "OPEN", "confidence": 70, "signals": [],
        "order_id": "1", "entry_time": "2026-01-01T00:00:00",
        "exit_price": None, "exit_time": None, "pnl": None,
        "pnl_percent": None, "close_reason": None,
    }
    tm.trades.append(trade)
    tm.open_trades[trade["id"]] = trade
    tm._peak_prices[trade["id"]] = entry
    return trade


def test_take_profit_closes(trade_manager):
    open_trade(trade_manager)
    closed = trade_manager.check_stop_loss_take_profit("BTCUSDT", 105.0)
    assert len(closed) == 1
    assert closed[0]["close_reason"] == "TAKE_PROFIT"
    assert trade_manager.get_open_trades() == []


def test_stop_loss_closes(trade_manager):
    open_trade(trade_manager)
    closed = trade_manager.check_stop_loss_take_profit("BTCUSDT", 97.0)
    assert len(closed) == 1
    assert closed[0]["close_reason"] == "STOP_LOSS"
    assert closed[0]["pnl"] < 0


def test_price_between_levels_keeps_trade_open(trade_manager):
    open_trade(trade_manager)
    closed = trade_manager.check_stop_loss_take_profit("BTCUSDT", 101.0)
    assert closed == []
    assert len(trade_manager.get_open_trades()) == 1


def test_trailing_stop_raises_stop_and_then_triggers(trade_manager):
    trade = open_trade(trade_manager)
    # Rally well above entry — trailing stop should lift above the original 98.0
    trade_manager.check_stop_loss_take_profit("BTCUSDT", 103.0)
    assert trade["stop_loss"] > 98.0
    lifted = trade["stop_loss"]

    # Drop back to just under the lifted stop
    closed = trade_manager.check_stop_loss_take_profit("BTCUSDT", lifted - 0.01)
    assert len(closed) == 1
    assert closed[0]["close_reason"] == "TRAILING_STOP"
    assert closed[0]["pnl"] > 0, "trailing exit should still be in profit"


def test_trailing_stop_disabled(trade_manager, config):
    trade_manager.config = dict(config, TRAILING_STOP=False)
    trade = open_trade(trade_manager)
    trade_manager.check_stop_loss_take_profit("BTCUSDT", 103.0)
    assert trade["stop_loss"] == 98.0, "stop must not move when trailing is off"


def test_pnl_maths(trade_manager):
    open_trade(trade_manager, entry=100.0, sl=98.0, tp=110.0, qty=2.0)
    closed = trade_manager.check_stop_loss_take_profit("BTCUSDT", 110.0)
    t = closed[0]
    assert t["pnl"] == pytest.approx((110.0 - 100.0) * 2.0)
    assert t["pnl_percent"] == pytest.approx(10.0)


def test_only_matching_symbol_is_touched(trade_manager):
    open_trade(trade_manager, symbol="BTCUSDT")
    closed = trade_manager.check_stop_loss_take_profit("ETHUSDT", 0.1)
    assert closed == []
    assert len(trade_manager.get_open_trades()) == 1


def test_trade_survives_restart(trade_manager, tmp_path, monkeypatch):
    """open_trades must be rebuilt from the trades file on reload."""
    from bot import trade_manager as tm_mod
    t = open_trade(trade_manager)
    tm_mod.save_trades(trade_manager.trades)      # persist, like a real order

    reloaded = tm_mod.TradeManager(trade_manager.client, trade_manager.config)
    assert len(reloaded.get_open_trades()) == 1
    assert reloaded.open_trades[t["id"]]["symbol"] == "BTCUSDT"
    # trailing-stop peak must also be restored
    assert t["id"] in reloaded._peak_prices


def test_candle_fallback_helper_exists():
    """
    engine._enforce_sltp_candle_level is the safety net for when the price
    stream is down; it must exist and use the candle high/low.
    """
    from bot.engine import TradingEngine
    assert hasattr(TradingEngine, "_enforce_sltp_candle_level")


@pytest.mark.asyncio
async def test_candle_fallback_closes_on_candle_low(trade_manager, candles):
    """Simulates the stream being dead: a candle low below SL must still exit."""
    from bot.engine import TradingEngine

    open_trade(trade_manager, symbol="BTCUSDT", entry=100.0, sl=95.0, tp=120.0)

    eng = TradingEngine.__new__(TradingEngine)
    eng.trade_manager = trade_manager

    # Candle whose low breaches the stop
    df = candles.copy()
    df.loc[df.index[-1], "low"]  = 90.0
    df.loc[df.index[-1], "high"] = 101.0

    closed = await eng._enforce_sltp_candle_level("BTCUSDT", df)
    assert len(closed) == 1
    assert closed[0]["close_reason"] in ("STOP_LOSS", "TRAILING_STOP")
    assert trade_manager.get_open_trades() == []


@pytest.mark.asyncio
async def test_candle_fallback_no_false_trigger(trade_manager, candles):
    from bot.engine import TradingEngine
    open_trade(trade_manager, symbol="BTCUSDT", entry=100.0, sl=95.0, tp=120.0)

    eng = TradingEngine.__new__(TradingEngine)
    eng.trade_manager = trade_manager

    df = candles.copy()
    df.loc[df.index[-1], "low"]  = 99.0
    df.loc[df.index[-1], "high"] = 101.0

    closed = await eng._enforce_sltp_candle_level("BTCUSDT", df)
    assert closed == []
    assert len(trade_manager.get_open_trades()) == 1
