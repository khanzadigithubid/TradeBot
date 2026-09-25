"""Tests for signal generation, sentiment application and path consistency."""

import pytest

from bot.indicators import generate_ai_signal
from bot.strategy import compute_signal, sentiment_blocks_buy


def test_signal_shape(candles, config):
    s = generate_ai_signal(candles, config)
    for key in ("action", "confidence", "price", "rsi", "buy_score",
                "sell_score", "signals", "stop_loss", "take_profit"):
        assert key in s, f"missing key {key}"
    assert s["action"] in ("BUY", "SELL", "HOLD")
    assert 0 <= s["confidence"] <= 99
    assert isinstance(s["signals"], list) and s["signals"]


def test_confidence_never_reaches_100(candles, config):
    s = generate_ai_signal(candles, config)
    assert s["confidence"] <= 99


def test_stop_below_entry_and_target_above(candles, config):
    s = generate_ai_signal(candles, config)
    if s["action"] == "BUY":
        assert s["stop_loss"] < s["price"] < s["take_profit"]


def test_sentiment_adjusts_the_decision_not_just_the_score(candles, config):
    """
    Regression: sentiment used to be added AFTER action/confidence were chosen,
    so it only changed the displayed numbers and never influenced trading.
    """
    base = generate_ai_signal(candles, config)

    bull = generate_ai_signal(candles, config, sentiment_adjust=15)
    assert bull["buy_score"] == base["buy_score"] + 15
    assert bull["tech_buy_score"] == base["buy_score"], "tech score must be unchanged"
    assert any("Sentiment Bullish" in s for s in bull["signals"])

    bear = generate_ai_signal(candles, config, sentiment_adjust=-15)
    assert bear["sell_score"] == base["sell_score"] + 15
    assert bear["tech_sell_score"] == base["sell_score"]
    assert any("Sentiment Bearish" in s for s in bear["signals"])


def test_action_is_derived_from_adjusted_scores(candles, config):
    """
    The action must be exactly the decision the adjusted scores imply —
    that is only true if sentiment feeds the decision, not a display field.
    """
    for adj in (-40, -20, -5, 0, 5, 20, 40):
        s = generate_ai_signal(candles, config, sentiment_adjust=adj)
        b, sl = s["buy_score"], s["sell_score"]
        if b > sl and b >= 50:
            expected = "BUY"
        elif sl > b and sl >= 50:
            expected = "SELL"
        else:
            expected = "HOLD"
        assert s["action"] == expected, f"sentiment_adjust={adj} inconsistent"


def test_sentiment_can_flip_the_action(config):
    """
    Across a range of sentiment values the bot must be able to reach both BUY
    and SELL, and at least one chart must change its action when sentiment
    changes. Proves sentiment is a real input to the decision, not a label.
    """
    from tests.conftest import make_candles

    scenarios = {
        "uptrend":    make_candles(drift=0.0012, seed=3),
        "downtrend":  make_candles(drift=-0.0012, seed=5),
        "choppy":     make_candles(drift=0.0, noise=0.002, seed=11),
    }
    grid = (-40, -20, 0, 20, 40)

    all_actions, flipped = set(), []
    for name, df in scenarios.items():
        acts = [generate_ai_signal(df, config, sentiment_adjust=a)["action"] for a in grid]
        all_actions |= set(acts)
        if len(set(acts)) > 1:
            flipped.append(name)

    assert "BUY" in all_actions, f"could never BUY: {all_actions}"
    assert "SELL" in all_actions, f"could never SELL: {all_actions}"
    assert flipped, f"sentiment never changed the action: {flipped}"


def test_sentiment_zero_is_noop(candles, config):
    a = generate_ai_signal(candles, config)
    b = generate_ai_signal(candles, config, sentiment_adjust=0)
    assert a["action"] == b["action"]
    assert a["confidence"] == b["confidence"]
    assert a["buy_score"] == b["buy_score"]


def test_compute_signal_uses_shared_path(candles, config, monkeypatch):
    """
    The dashboard and the live engine must return the same signal for the same
    inputs. Previously the API skipped MTF data so the two disagreed.
    """
    import bot.strategy as strategy

    monkeypatch.setattr(strategy, "get_klines", lambda *a, **k: candles)
    monkeypatch.setattr(strategy, "get_sentiment", lambda s, c: {})

    s1 = strategy.compute_signal("BTCUSDT", config, use_mtf=True,  use_sentiment=False)
    s2 = strategy.compute_signal("BTCUSDT", config, use_mtf=True,  use_sentiment=False)
    assert s1["action"] == s2["action"]
    assert s1["confidence"] == s2["confidence"]
    assert s1["buy_score"] == s2["buy_score"]

    # MTF actually reaching the signal
    assert s1["mtf_enabled"] is True
    assert s1["mtf"] is not None


def test_compute_signal_returns_none_without_data(config, monkeypatch):
    import pandas as pd
    import bot.strategy as strategy
    monkeypatch.setattr(strategy, "get_klines", lambda *a, **k: pd.DataFrame())
    assert strategy.compute_signal("BTCUSDT", config) is None


def test_compute_signal_normalises_symbol(candles, config, monkeypatch):
    import bot.strategy as strategy
    monkeypatch.setattr(strategy, "get_klines", lambda *a, **k: candles)
    monkeypatch.setattr(strategy, "get_sentiment", lambda s, c: {})
    s = strategy.compute_signal("btcusdt", config, use_mtf=False, use_sentiment=False)
    assert s["symbol"] == "BTCUSDT"


def test_extreme_greed_blocks_buy(config):
    greed = {"fear_greed": {"signal": "EXTREME_GREED"}}
    assert sentiment_blocks_buy(greed, config) is True

    neutral = {"fear_greed": {"signal": "NEUTRAL"}}
    assert sentiment_blocks_buy(neutral, config) is False

    # Filter off => never blocks
    off = dict(config, SENTIMENT_FILTER=False)
    assert sentiment_blocks_buy(greed, off) is False

    # No sentiment data => never blocks
    assert sentiment_blocks_buy({}, config) is False
