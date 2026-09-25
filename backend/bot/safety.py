"""
Safety Interlocks
Guards that stop the bot from placing real money orders by accident.

The engine auto-starts on server boot, so a leftover `TESTNET: false` in
settings.json (or a UI toggle) was enough to trade real funds with no prompt.
Every path that can enable live trading must now pass through `assert_live_allowed`.
"""

import logging
import os

logger = logging.getLogger(__name__)


class LiveTradingBlocked(RuntimeError):
    """Raised when live trading is requested without explicit authorisation."""


def live_opt_in() -> bool:
    """
    Live trading requires the operator to set LIVE_TRADING_ENABLED=true in the
    environment. Absent that, the bot stays in testnet no matter what the
    settings file or UI says.
    """
    return os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


def assert_live_allowed(testnet_flag: bool, context: str = "") -> None:
    """
    Raise LiveTradingBlocked if live trading is requested without opt-in.
    Callers treat this as a hard stop — no order may be placed.
    """
    if testnet_flag:
        return
    if live_opt_in():
        logger.warning("🔴 LIVE TRADING ENABLED — real orders will be sent")
        return
    raise LiveTradingBlocked(
        "Live trading is disabled. Set LIVE_TRADING_ENABLED=true in the "
        "environment to allow real Binance orders, or keep TESTNET=true. "
        f"Blocked: {context or 'live mode requested'}"
    )


def describe_mode(testnet_flag: bool) -> dict:
    """Mode summary surfaced on /api/status for the UI."""
    return {
        "testnet":       bool(testnet_flag),
        "live_opt_in":   live_opt_in(),
        "live_allowed":  bool(testnet_flag) or live_opt_in(),
    }
