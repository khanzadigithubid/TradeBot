"""Tests for the live-trading interlock — the most important safety surface."""

import importlib
import os

import pytest

from bot.safety import (
    LiveTradingBlocked,
    assert_live_allowed,
    describe_mode,
    live_opt_in,
)


def test_testnet_always_allowed():
    assert_live_allowed(True, "unit test")   # must not raise


def test_live_blocked_without_opt_in(monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    with pytest.raises(LiveTradingBlocked) as e:
        assert_live_allowed(False, "unit test")
    assert "LIVE_TRADING_ENABLED" in str(e.value)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_live_allowed_with_opt_in(monkeypatch, value):
    monkeypatch.setenv("LIVE_TRADING_ENABLED", value)
    assert live_opt_in() is True
    assert_live_allowed(False, "unit test")   # must not raise


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "banana"])
def test_live_stays_blocked_for_junk_values(monkeypatch, value):
    monkeypatch.setenv("LIVE_TRADING_ENABLED", value)
    assert live_opt_in() is False
    with pytest.raises(LiveTradingBlocked):
        assert_live_allowed(False)


def test_describe_mode(monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    assert describe_mode(True) == {
        "testnet": True, "live_opt_in": False, "live_allowed": True
    }
    assert describe_mode(False)["live_allowed"] is False

    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    assert describe_mode(False)["live_allowed"] is True


def test_engine_forces_testnet_when_live_requested(monkeypatch):
    """
    The engine used to boot straight into live trading because settings.json
    said TESTNET=false. engine.start() must now refuse and force testnet.
    """
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    from bot.engine import TradingEngine

    eng = TradingEngine.__new__(TradingEngine)   # bypass __init__ side effects
    eng.config = {"TESTNET": False}
    eng.trade_manager = type("TM", (), {
        "bot_running": False, "config": {"TESTNET": False},
        "client": None, "notifier": None, "email_notifier": None,
        "resend_notifier": None, "discord_notifier": None,
    })()
    eng._build_client = lambda: setattr(eng, "client", object())
    eng._symbol_tasks = {}

    class FakePS:
        testnet = False
        def set_testnet(self, v): self.testnet = v
    eng.price_stream = FakePS()

    forced = eng._force_testnet_if_unsafe()
    assert forced is True
    assert eng.config["TESTNET"] is True
    assert eng.price_stream.testnet is True


def test_engine_leaves_testnet_alone(monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    from bot.engine import TradingEngine

    eng = TradingEngine.__new__(TradingEngine)
    eng.config = {"TESTNET": True}
    assert eng._force_testnet_if_unsafe() is False
    assert eng.config["TESTNET"] is True
