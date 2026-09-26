"""
Watchlist Store

The pairs shown in the dashboard sidebar. The default list comes from
config.CRYPTO_PAIRS / config.FOREX_PAIRS, but the user can add any symbol they
want to monitor and remove the ones they do not care about.

A watchlist entry is a *monitoring* entry. It is not automatically tradeable:
a pair is only tradeable if the bot is configured for it (config.SUPPORTED_PAIRS)
and the exchange actually lists it. routes._tradeable() reports that, and the
UI blocks starting the bot on a pair that is not tradeable rather than failing
at order time.
"""

import json
import os

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "watchlist.json")

# Kept short on purpose: every entry is a live ticker subscription on both the
# bulk-price poll and the websocket, so a runaway list is a real cost.
MAX_WATCHLIST = 60


def default_watchlist() -> list:
    from bot.config import CRYPTO_PAIRS, FOREX_PAIRS
    return list(dict.fromkeys(CRYPTO_PAIRS + FOREX_PAIRS))


def load_watchlist() -> list:
    """
    Load saved watchlist. A missing or corrupt file falls back to the default
    list rather than an empty sidebar.
    """
    os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                clean = [s for s in data if isinstance(s, str) and s.strip()]
                if clean:
                    return clean[:MAX_WATCHLIST]
        except Exception:
            pass
    return default_watchlist()


def save_watchlist(symbols: list) -> list:
    """Persist the watchlist, preserving order and dropping duplicates."""
    seen, clean = set(), []
    for s in symbols:
        if not isinstance(s, str):
            continue
        s = s.strip().upper()
        if s and s not in seen:
            seen.add(s)
            clean.append(s)
    clean = clean[:MAX_WATCHLIST]

    os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(clean, f, indent=2)
    return clean


def add_symbol(symbol: str) -> list:
    """Add a symbol to the end of the watchlist if it is not already there."""
    current = load_watchlist()
    symbol = symbol.strip().upper()
    if symbol in current:
        return current
    if len(current) >= MAX_WATCHLIST:
        raise ValueError(f"watchlist is full (max {MAX_WATCHLIST})")
    return save_watchlist(current + [symbol])


def remove_symbol(symbol: str) -> list:
    """Remove a symbol. The last entry is kept so the sidebar is never empty."""
    symbol = symbol.strip().upper()
    current = load_watchlist()
    if symbol not in current:
        return current
    remaining = [s for s in current if s != symbol]
    if not remaining:
        raise ValueError("watchlist must keep at least one pair")
    return save_watchlist(remaining)
