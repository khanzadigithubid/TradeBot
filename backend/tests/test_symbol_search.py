"""
Type-ahead pair search.

This is what makes an invalid pair impossible to add rather than merely
reported afterwards, so the ranking and the "actually listed" filter are the
parts worth pinning down.
"""
import pytest
from fastapi.testclient import TestClient

import bot.market_data as md
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def listed(monkeypatch):
    """Stand in for exchangeInfo so the test does not depend on the venue."""
    syms = (
        "BTCUSDT", "WBTCUSDT", "ETHUSDT", "WETHUSDT", "ETHFIUSDT",
        "PEPEUSDT", "SOLUSDT", "SOLVUSDT", "BNSOLUSDT", "AVAXUSDT",
    )
    monkeypatch.setattr(md, "_LISTED_CACHE", {"at": 9e9, "symbols": syms})
    monkeypatch.setattr(
        md, "get_24h_stats",
        lambda s: {"lastPrice": "12.5", "priceChangePercent": "-1.25"},
    )
    return syms


# ── ranking ───────────────────────────────────────────────────────────────────

def test_an_exact_base_match_outranks_a_coin_that_merely_contains_it(listed):
    """Typing BTC has to mean BTCUSDT, not WBTCUSDT."""
    syms = [r["symbol"] for r in md.search_symbols("BTC", limit=10)]

    assert syms[0] == "BTCUSDT"
    assert "WBTCUSDT" in syms, "the rest of the matches are still offered"


def test_prefix_matches_follow_the_exact_match(listed):
    syms = [r["symbol"] for r in md.search_symbols("ETH", limit=10)]

    assert syms[0] == "ETHUSDT"
    assert syms.index("ETHUSDT") < syms.index("WETHUSDT")


def test_only_listed_symbols_are_offered(listed, monkeypatch):
    """A pair the exchange does not trade must not appear in the dropdown."""
    monkeypatch.setattr(
        md, "_LISTED_CACHE",
        {"at": 9e9, "symbols": ("BTCUSDT", "ETHUSDT")},
    )

    syms = [r["symbol"] for r in md.search_symbols("SOL", limit=10)]

    assert syms == []


def test_forex_pairs_are_offered_even_though_binance_does_not_list_them(listed):
    syms = [r["symbol"] for r in md.search_symbols("EUR", limit=10)]

    assert "EURUSDT" in syms
    assert syms[0] == "EURUSDT", "the exact match comes first"


def test_a_query_shorter_than_two_characters_returns_nothing(listed):
    """One character would match most of the market."""
    assert md.search_symbols("B") == []
    assert md.search_symbols("") == []
    assert md.search_symbols("  ") == []


def test_the_query_is_case_insensitive(listed):
    assert [r["symbol"] for r in md.search_symbols("pepe")] == ["PEPEUSDT"]


def test_results_carry_a_live_price_and_change(listed):
    row = md.search_symbols("BTC", limit=1)[0]

    assert row["price"] == 12.5
    assert row["change"] == -1.25


def test_the_result_count_is_capped(listed):
    syms = md.search_symbols("SOL", limit=2)

    assert len(syms) == 2


# ── resilience ────────────────────────────────────────────────────────────────

def test_a_ticker_failure_does_not_hide_the_pair(listed, monkeypatch):
    """A symbol that is listed must still be selectable if its price call fails."""
    def boom(sym):
        raise RuntimeError("timeout")

    monkeypatch.setattr(md, "get_24h_stats", boom)

    row = md.search_symbols("BTC", limit=1)[0]

    assert row["symbol"] == "BTCUSDT"
    assert row["price"] is None, "an unknown price must be None, not a fake 0"


def test_a_failed_exchange_info_keeps_the_previous_list(monkeypatch):
    monkeypatch.setattr(md, "_LISTED_CACHE", {"at": 0.0, "symbols": ("BTCUSDT",)})
    monkeypatch.setattr(
        md, "_try_binance",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    monkeypatch.setattr(md, "get_24h_stats", lambda s: {"lastPrice": "1", "priceChangePercent": "0"})

    syms = [r["symbol"] for r in md.search_symbols("BTC", limit=5)]

    assert syms == ["BTCUSDT"], "an empty list would silently break the dropdown"


# ── API ───────────────────────────────────────────────────────────────────────

def test_the_endpoint_returns_results_with_a_tradeable_flag(client, listed):
    body = client.get("/api/market/symbols", params={"q": "BTC"}).json()

    assert body["query"] == "BTC"
    assert body["results"]
    assert body["results"][0]["symbol"] == "BTCUSDT"
    assert "tradeable" in body["results"][0]


def test_the_endpoint_requires_two_characters(client, listed):
    assert client.get("/api/market/symbols", params={"q": "B"}).json()["results"] == []


def test_the_endpoint_clamps_a_silly_limit(client, listed):
    body = client.get("/api/market/symbols", params={"q": "SOL", "limit": 9999}).json()

    assert len(body["results"]) <= 50


def test_a_junk_query_is_rejected_not_crashed(client):
    assert client.get("/api/market/symbols", params={"q": "../../etc/passwd"}).status_code == 200
    assert client.get("/api/market/symbols", params={"q": "X" * 500}).status_code == 200
