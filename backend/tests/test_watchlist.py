"""
Watchlist add/remove.

Two properties matter here and neither is obvious from the endpoint itself:

1. A watchlist entry is a *monitoring* entry. Adding a pair must not imply the
   bot can trade it, or the user clicks it, starts the bot, and the first order
   fails against an exchange that never listed the symbol.
2. The list is persisted. A watchlist that resets on every reload is useless.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

import bot.watchlist_store as wl_mod
from main import app


@pytest.fixture(autouse=True)
def isolated_watchlist(tmp_path, monkeypatch):
    """Point the store at a temp file and restore the real one afterwards."""
    real = wl_mod.WATCHLIST_FILE
    path = tmp_path / "watchlist.json"
    wl_mod.WATCHLIST_FILE = str(path)
    yield str(path)
    wl_mod.WATCHLIST_FILE = real


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def idle_engine():
    """
    A previous test may have left the engine running, and /bot/start refuses to
    start twice. Reset it so these tests exercise the symbol check rather than
    tripping over leaked state.
    """
    from bot.engine import engine
    was_running = engine.running
    engine.running = False
    yield engine
    engine.running = was_running


def read(path):
    with open(path) as f:
        return json.load(f)


# ── store ─────────────────────────────────────────────────────────────────────

def test_default_list_is_used_when_nothing_is_saved(isolated_watchlist):
    from bot.config import CRYPTO_PAIRS

    got = wl_mod.load_watchlist()

    assert got, "a fresh install must not show an empty sidebar"
    assert "BTCUSDT" in got
    assert set(got) == set(CRYPTO_PAIRS) | set(wl_mod.default_watchlist())


def test_add_then_reload_keeps_the_pair(isolated_watchlist):
    # Symbols deliberately outside config.CRYPTO_PAIRS, so the assertion below
    # tests persistence rather than the no-op of re-adding a default pair.
    wl_mod.add_symbol("PEPEUSDT")
    wl_mod.add_symbol("WIFUSDT")

    assert wl_mod.load_watchlist()[-2:] == ["PEPEUSDT", "WIFUSDT"]
    assert "PEPEUSDT" in read(isolated_watchlist), "the list must survive a restart"


def test_adding_the_same_pair_twice_does_not_duplicate_it(isolated_watchlist):
    wl_mod.add_symbol("AVAXUSDT")
    before = len(wl_mod.load_watchlist())
    wl_mod.add_symbol("avaxusdt")

    assert len(wl_mod.load_watchlist()) == before


def test_symbols_are_normalised_to_uppercase(isolated_watchlist):
    wl_mod.add_symbol("  avaxusdt ")

    assert "AVAXUSDT" in wl_mod.load_watchlist()
    assert "  avaxusdt " not in wl_mod.load_watchlist()


def test_a_corrupt_file_falls_back_instead_of_blanking_the_sidebar(isolated_watchlist):
    with open(isolated_watchlist, "w") as f:
        f.write("{not json")

    assert wl_mod.load_watchlist(), "a bad file must not produce an empty watchlist"


def test_the_list_is_capped(isolated_watchlist):
    """Every entry is a live ticker subscription; the list cannot grow forever."""
    for i in range(wl_mod.MAX_WATCHLIST + 25):
        try:
            wl_mod.add_symbol(f"COIN{i}USDT")
        except ValueError:
            break

    assert len(wl_mod.load_watchlist()) == wl_mod.MAX_WATCHLIST
    with pytest.raises(ValueError, match="full"):
        wl_mod.add_symbol("ONETOOUSDT")


def test_the_last_pair_cannot_be_removed(isolated_watchlist):
    wl_mod.save_watchlist(["BTCUSDT"])

    with pytest.raises(ValueError, match="at least one"):
        wl_mod.remove_symbol("BTCUSDT")


# ── API ───────────────────────────────────────────────────────────────────────

def test_get_returns_the_list_with_a_tradeable_flag(client):
    body = client.get("/api/watchlist").json()

    assert "symbols" in body and "tradeable" in body
    assert set(body["tradeable"]) <= set(body["symbols"]), \
        "a pair cannot be tradeable without being on the list"


def test_add_rejects_junk_before_hitting_the_exchange(client, monkeypatch):
    import bot.market_data as md
    monkeypatch.setattr(md, "get_24h_stats", lambda s: {"lastPrice": 1.0})

    assert client.post("/api/watchlist", json={"symbol": "BTC USDT"}).status_code == 422
    assert client.post("/api/watchlist", json={"symbol": "../../etc"}).status_code == 422
    assert client.post("/api/watchlist", json={"symbol": "X" * 40}).status_code == 422


def test_add_reports_a_pair_the_exchange_does_not_list(client, monkeypatch):
    import bot.market_data as md

    def boom(sym):
        raise RuntimeError("400 Client Error")

    monkeypatch.setattr(md, "get_24h_stats", boom)

    res = client.post("/api/watchlist", json={"symbol": "NOTAREALPAIR"})

    assert res.status_code == 404
    assert "NOTAREALPAIR" in res.json()["detail"]


def test_add_rejects_a_pair_with_no_price(client, monkeypatch):
    """A listed symbol can still return lastPrice=0; that is not a usable row."""
    import bot.market_data as md
    monkeypatch.setattr(md, "get_24h_stats", lambda s: {"lastPrice": "0.00000000"})

    assert client.post("/api/watchlist", json={"symbol": "ZEROPRICE"}).status_code == 404


def test_added_pair_appears_in_the_list(client, monkeypatch):
    import bot.market_data as md
    monkeypatch.setattr(md, "get_24h_stats", lambda s: {"lastPrice": "35.5"})

    res = client.post("/api/watchlist", json={"symbol": "AVAXUSDT"})

    assert res.status_code == 200
    assert res.json()["added"] == "AVAXUSDT"
    assert "AVAXUSDT" in client.get("/api/watchlist").json()["symbols"]


def test_remove_takes_the_pair_out(client):
    wl_mod.add_symbol("AVAXUSDT")
    client.post("/api/watchlist", json={"symbol": "AVAXUSDT"})

    res = client.request("DELETE", "/api/watchlist/AVAXUSDT")

    assert res.status_code == 200
    assert "AVAXUSDT" not in res.json()["symbols"]


# ── the monitoring/trading distinction ────────────────────────────────────────

def test_a_monitor_only_pair_is_flagged_and_cannot_start_the_bot(client, idle_engine, monkeypatch):
    """
    The whole point of the tradeable flag: adding a pair to the watchlist must
    not let the user start the bot on a symbol the bot cannot trade.
    """
    import bot.market_data as md
    monkeypatch.setattr(md, "get_24h_stats", lambda s: {"lastPrice": "1.0"})

    client.post("/api/watchlist", json={"symbol": "NOTCONFIGURED"})
    body = client.get("/api/watchlist").json()
    assert "NOTCONFIGURED" in body["symbols"]
    assert "NOTCONFIGURED" not in body["tradeable"]

    res = client.post("/api/bot/start", json={"symbol": "NOTCONFIGURED"})

    assert res.status_code == 400
    assert "CRYPTO_PAIRS" in res.json()["detail"], \
        "the error must say how to make the pair tradeable"


def test_start_still_works_for_a_configured_pair(client, idle_engine):
    from bot.config import CRYPTO_PAIRS

    res = client.post("/api/bot/start", json={"symbol": CRYPTO_PAIRS[0]})

    assert res.status_code == 200


def test_start_rejects_a_malformed_symbol(client, idle_engine):
    assert client.post("/api/bot/start", json={"symbol": "BTC USDT"}).status_code == 422
