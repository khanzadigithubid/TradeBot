"""
Forward-test recorder.

Runs the production engine against live market data on the configured interval
and appends one machine-readable row per cycle to <out>.jsonl, so a candidate
strategy's edge can be judged on out-of-sample forward data instead of
hindsight.

  python tools/forward_test.py                 # real TESTNET orders (default)
  python tools/forward_test.py --paper         # simulated fills, no orders sent
  python tools/forward_test.py --cycles 3      # run 3 cycles then stop (smoke)

The recorder never touches live money: mode is TESTNET unless --paper is used,
and engine.start() itself forces any unsafe config back to testnet.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.engine import TradingEngine  # noqa: E402
from bot.market_data import _try_binance  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def detect_provider() -> str:
    """Which market-data source actually responds from this machine."""
    if _try_binance("klines", {"symbol": "BTCUSDT", "interval": "15m", "limit": 1}):
        return "binance"
    try:
        import requests
        if requests.get("https://api.kraken.com/0/public/OHLC",
                        params={"pair": "XBTUSD", "interval": 15}, timeout=8).status_code == 200:
            return "kraken"
        if requests.get("https://api.coingecko.com/api/v3/simple/price",
                        params={"ids": "bitcoin", "vs_currencies": "usd"}, timeout=8).status_code == 200:
            return "coingecko"
    except Exception:
        pass
    return "unknown"


class ForwardTest:
    def __init__(self, out: Path):
        self.out = out
        self.seen = 0
        self.count = 0
        self.binance = detect_provider()

    def write(self, row: dict):
        with self.out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    async def record(self, data: dict):
        sig = data.get("signal") or {}
        row = {
            "ts":      data.get("ts") or datetime.now(timezone.utc).isoformat(),
            "symbol":  data.get("symbol"),
            "price":   sig.get("price"),
            "action":  sig.get("action"),
            "confidence": sig.get("confidence"),
            "buy_score":  sig.get("buy_score"),
            "sell_score": sig.get("sell_score"),
            "rsi":     sig.get("rsi"),
            "ema_fast": sig.get("ema_fast"),
            "ema_slow": sig.get("ema_slow"),
            "bb_lower": sig.get("bb_lower"),
            "bb_upper": sig.get("bb_upper"),
            "mtf":      sig.get("mtf_enabled"),
            "sentiment": bool(sig.get("sentiment")),
            "provider": self.binance,
            "open_trades": len(data.get("open_trades") or []),
            "balance_ok":  data.get("balance_ok"),
            "balance":     data.get("balance"),
        }
        self.write(row)

    async def stop_after(self, engine, limit: int):
        await asyncio.sleep(5)
        while True:
            if self.count >= limit and limit > 0:
                logger = logging.getLogger("forward")
                logger.info(f"Reached {limit} cycles — stopping")
                engine.stop()
                return
            await asyncio.sleep(2)


async def run(args) -> int:
    engine = TradingEngine()
    engine.interval = args.interval
    engine.config.update({
        "PAPER_TRADING": args.paper,
        "ACTIVE_SYMBOLS": args.symbols,
        "MULTI_SYMBOL_MODE": True,
        # A recorder must never self-halt: opening testnet positions parks USDT
        # in open trades, which looks like a spot-balance drop and trips the
        # 5% daily-loss interlock. Disable it for the data run; production uses
        # its own engine config.
        "DAILY_LOSS_LIMIT_PERCENT": 0,
        "INTERVAL": args.interval,
    })
    engine.active_symbols = args.symbols
    engine.client = None
    engine._build_client()
    engine.trade_manager.config = engine.config
    engine.trade_manager.client = engine.client

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    ft = ForwardTest(out)

    async def cb(data):
        if data.get("type") in ("SIGNAL_UPDATE", "TRADE_EXECUTED", "TRADE_CLOSED"):
            ft.count += 1
            await ft.record(data)

    engine.add_callback(cb)

    logging.getLogger("forward").info(
        f"Forward test starting | mode={'TESTNET' if not args.paper else 'PAPER'} "
        f"| provider={ft.binance} | symbols={args.symbols} | interval={args.interval} "
        f"| log={out}"
    )
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "event": "START", "ts": datetime.now(timezone.utc).isoformat(),
            "mode":  "PAPER" if args.paper else "TESTNET",
            "provider": ft.binance, "symbols": args.symbols, "interval": args.interval,
        }) + "\n")

    loop = asyncio.get_running_loop()
    if args.cycles:
        stop_task = asyncio.create_task(ft.stop_after(engine, args.cycles))
    try:
        await engine.start()
    finally:
        if args.cycles and not stop_task.done():
            stop_task.cancel()
    # 0 = reached the target cycle count (planned stop); 1 = the engine ran on
    # its own and exited (e.g. every symbol loop died) so main() can restart it.
    return 0 if (args.cycles and ft.count >= args.cycles) else 1


def main():
    parser = argparse.ArgumentParser(description="Forward-test the live engine.")
    parser.add_argument("--symbols", nargs="+", default=[
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
        "DOGEUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "LTCUSDT", "UNIUSDT",
        "ATOMUSDT", "TONUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
        "INJUSDT", "SUIUSDT"])
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--paper", action="store_true",
                        help="simulate fills locally instead of real testnet orders")
    parser.add_argument("--cycles", type=int, default=0,
                        help="stop after N recorded cycles (0 = run forever)")
    parser.add_argument("--out", default="forward_log.jsonl")
    args = parser.parse_args()

    crash_log = Path(args.out).with_name("forward_test.crash.log")
    attempts = 0
    while True:
        exit_code = 1
        try:
            exit_code = asyncio.run(run(args))
        except BaseException:
            # Record silently because stdout may be a null console (detached
            # launches). The crash file makes restart-vs-crash diagnosis possible.
            try:
                import traceback
                with crash_log.open("a", encoding="utf-8") as fh:
                    fh.write(f"\n--- {datetime.now(timezone.utc).isoformat()} ---\n")
                    traceback.print_exc(file=fh)
            except Exception:
                pass
        if exit_code == 0:
            return 0
        attempts += 1
        if attempts > 10:
            print(f"forward-test: gave up restarting after {attempts} attempts", flush=True)
            return 1
        print(f"forward-test: engine exited (code {exit_code}) — restarting in 5s (attempt {attempts})", flush=True)
        import time as _time
        _time.sleep(5)


if __name__ == "__main__":
    main()