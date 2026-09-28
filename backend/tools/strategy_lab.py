"""
Strategy lab: search simple long-only rulesets on real 15m Binance data.

Every candidate gets the same engine-like simulation: next-bar fill, entry
price dragged by slippage, 0.10% round-trip fee, SL 2% / TP 4%, and exit on
opposite signal. Metrics are always AFTER those costs.

  python tools/strategy_lab.py                # 6 symbols x 180d
  python tools/strategy_lab.py --days 60      # shorter run

Data is cached under backend/data/cache so re-runs are cheap.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.market_data import get_klines  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
DEFAULT_INTERVAL = "15m"
CPD = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}
FEE = 0.0010      # round trip (two 0.05% takers)
SLIP = 0.0002     # per leg, always against the trade
SL, TP = 0.02, 0.04


# ── indicators (compact, Wilder-style) ────────────────────────────────────────

def rsi(close, period=14):
    d = close.diff()
    up = d.clip(lower=0.0).ewm(alpha=1 / period, adjust=False).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def ema(close, n):
    return close.ewm(span=n, adjust=False).mean()


# ── candidate signal builders: return 'BUY'/'SELL'/'HOLD' per bar ─────────────

def signal_ema_pullback(df):
    e9, e21 = ema(df.close, 9), ema(df.close, 21)
    r = rsi(df.close)
    r1 = r.shift(1)
    buy = (e9 > e21) & (r1 < 40) & (r >= 40)          # dip bought back in uptrend
    sell = (e9 < e21) | (r > 68)
    return _to_series(buy, sell)


def signal_rsi_reversion(df):
    r = rsi(df.close)
    return _to_series(r < 28, r > 55)


def signal_donchian(df, n=20):
    upper = df.high.rolling(n).max().shift(1)
    lower = df.low.rolling(n).min().shift(1)
    return _to_series(df.close > upper, df.close < lower)


def signal_bb_bounce(df):
    mid = df.close.rolling(20).mean()
    sd = df.close.rolling(20).std()
    lower = mid - 2 * sd
    sell_up = df.close > mid + 2 * sd
    return _to_series(df.close < lower, sell_up)


def signal_ema12cross(df):
    a, b = ema(df.close, 12), ema(df.close, 26)
    return _to_series(a > b, a < b)


def _to_series(buy, sell):
    out = pd.Series("HOLD", index=buy.index, dtype=object)
    out[buy & ~sell] = "BUY"
    out[sell] = "SELL"
    return out


# ── simulation (next-bar fill, costs, SL/TP, signal exit) ─────────────────────

def simulate(df, sig, rfee=FEE, slip=SLIP, sl=SL, tp=TP):
    close = df.close.to_numpy()
    sigv = sig.to_numpy()
    n = len(close)
    cash = 1000.0
    shares = 0.0
    entry = 0.0
    trades = []
    eq = np.zeros(n)
    for i in range(n - 1):
        if shares == 0 and sigv[i] == "BUY":
            px = close[i + 1] * (1 + slip)         # next bar: no lookahead
            if np.isnan(px):
                continue
            entry = px
            shares = cash / (px * (1 + rfee / 2))
            cash = 0.0
        elif shares > 0:
            px = close[i] * (1 - slip)
            stop = entry * (1 - sl)
            goal = entry * (1 + tp)
            if close[i] <= stop:
                px, why = stop * (1 - slip), "SL"
            elif close[i] >= goal:
                px, why = goal * (1 - slip), "TP"
            elif sigv[i] == "SELL":
                px, why = close[i] * (1 - slip), "SIGNAL"
            else:
                px, why = None, None
            if why:
                cash = shares * px * (1 - rfee / 2)
                shares = 0.0
                trades.append((entry, px, why))
        eq[i] = (cash + shares * close[i]) / 1000 - 1
    cash = cash + shares * close[-1] * (1 - slip) * (1 - rfee / 2)
    if shares:
        trades.append((entry, close[-1], "EOD"))
    eq[-1] = cash / 1000 - 1
    return _stats(trades, eq)


def _stats(trades, eq):
    if not trades:
        return {"ret": 0.0, "trades": 0, "pf": 0.0, "win": 0.0,
                "avg": 0.0, "dd": 0.0}
    rets = [t[1] / t[0] - 1 for t in trades]
    prof = sum(max(r, 0) for r in rets)
    loss = -sum(min(r, 0) for r in rets)
    eq2 = eq
    peak = np.maximum.accumulate(eq2)
    dd = float(np.max(peak - eq2)) if eq2.size else 0.0
    return {
        "ret":   float(eq2[-1]) if eq2.size else 0.0,
        "trades": len(trades),
        "pf":    prof / loss if loss > 0 else (9.9 if prof > 0 else 0.0),
        "win":    sum(1 for r in rets if r > 0) / len(rets),
        "avg":   float(np.mean(rets)),
        "dd":    dd,
    }


# ── data + walk-forward ───────────────────────────────────────────────────────

def load_df(sym, days, interval):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sym}_{interval}_{days}d.pkl"
    if f.exists():
        return pd.read_pickle(f)
    cpd = CPD[interval]
    limit = days * cpd + 100
    df = get_klines(sym, interval, limit)
    df = df.tail(days * cpd).reset_index(drop=True)
    df = df.dropna().reset_index(drop=True)
    df.to_pickle(f)
    return df


def report(name, rows):
    m = pd.DataFrame(rows)
    mean_ret = m["ret"].mean()
    print(f"  {name:<26} ret={mean_ret:8.2f}%  trades={int(m['trades'].mean()):5d} "
          f"pf={m['pf'].mean():4.2f}  win={m['win'].mean():4.2f}  dd={m['dd'].mean():6.2f}")


def main():
    ap = argparse.ArgumentParser(description="simple strategy lab")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--symbols", nargs="+", default=SYMBOLS)
    ap.add_argument("--interval", choices=list(CPD), default=DEFAULT_INTERVAL)
    args = ap.parse_args()
    interval = args.interval

    builders = {
        "ema9/21 pullback":  signal_ema_pullback,
        "rsi<28 reversion":  signal_rsi_reversion,
        "donchian20 break":  signal_donchian,
        "bb_lower bounce":   signal_bb_bounce,
        "ema12/26 cross":    signal_ema12cross,
    }

    print(f"interval={interval} days={args.days} fee={FEE:.4f} slip={SLIP:.4f} "
          f"SL={SL:.0%} TP={TP:.0%}")
    t0 = time.time()
    data = {s: load_df(s, args.days, interval) for s in args.symbols}
    print(f"data ready ({time.time() - t0:.0f}s)")

    print("\nFULL-PERIOD, after costs:")
    for name, fn in builders.items():
        rows = []
        for s in args.symbols:
            rows.append(simulate(data[s], fn(data[s])))
        report(name, rows)

    print("\nWALK-FORWARD (3 folds, after costs):")
    for name, fn in builders.items():
        rows = []
        for s in args.symbols:
            df = data[s]
            folds = np.array_split(np.arange(len(df)), 3)
            for ix in folds:
                fold = df.iloc[ix].reset_index(drop=True)
                rows.append(simulate(fold, fn(fold)))
        report(name, rows)


if __name__ == "__main__":
    main()