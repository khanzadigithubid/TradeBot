import { useEffect, useState, useCallback } from "react";
import {
  Wallet, TrendingUp, Target, BarChart2, Activity,
  Play, Square, AlertTriangle, TrendingDown, Clock,
  Zap, SlidersHorizontal, X
} from "lucide-react";
import {
  getBotStatus, startBot, stopBot,
  getTradeStats, getOpenTrades, getSignal,
  getMarketStats, getSettings, getBulkPrices
} from "../services/api";
import StatCard         from "../components/StatCard";
import SignalBadge      from "../components/SignalBadge";
import OpenTradeCard    from "../components/OpenTradeCard";
import PriceChart       from "../components/PriceChart";
import ManualTradePanel from "../components/ManualTradePanel";

const PAIRS     = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT"];
const INTERVALS = ["1m","5m","15m","30m","1h","4h","1d"];

// ── Watchlist Item ─────────────────────────────────────────────────────────────
function WatchlistItem({ pair, active, onClick, priceData }) {
  const price  = priceData?.price  ?? null;
  const change = priceData?.change ?? null;
  const pos    = change != null ? change >= 0 : true;

  return (
    <button className={`wl-item ${active ? "wl-active" : ""}`} onClick={onClick}>
      <div className="wl-left">
        <span className="wl-pair">
          {pair.replace("USDT", "")}<span className="wl-usdt">/USDT</span>
        </span>
        {price > 0 && (
          <span className="wl-price">
            ${price >= 1
              ? Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })
              : Number(price).toFixed(6)}
          </span>
        )}
      </div>
      <div className="wl-right">
        {active && <div className="wl-dot" />}
        {change != null && (
          <span className={`wl-change ${pos ? "wl-pos" : "wl-neg"}`}>
            {pos ? "+" : ""}{Number(change).toFixed(2)}%
          </span>
        )}
      </div>
    </button>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function Dashboard({ wsMessage }) {
  const [botRunning,  setBotRunning]  = useState(false);
  const [stats,       setStats]       = useState(null);
  const [openTrades,  setOpenTrades]  = useState([]);
  const [signal,      setSignal]      = useState(null);
  const [marketStats, setMarketStats] = useState(null);
  const [symbol,      setSymbol]      = useState("BTCUSDT");
  const [timeframe,   setTimeframe]   = useState("15m");
  const [btnLoading,  setBtnLoading]  = useState(false);
  const [livePrice,   setLivePrice]   = useState(null);
  const [allPairs,    setAllPairs]    = useState({ crypto: PAIRS, forex: [] });
  const [wlPrices,    setWlPrices]    = useState({});
  const [wlOpen,      setWlOpen]      = useState(false);  // mobile watchlist drawer
  const [safety,      setSafety]      = useState(null);   // { effective_testnet, safety }

  // ── Fetch main data ──────────────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    const [s, st, tr, sig, mkt, sets] = await Promise.allSettled([
      getBotStatus(), getTradeStats(), getOpenTrades(),
      getSignal(symbol), getMarketStats(symbol), getSettings(),
    ]);
    if (s.status    === "fulfilled") setBotRunning(s.value.running);
    if (st.status   === "fulfilled") setStats(st.value);
    if (tr.status   === "fulfilled") setOpenTrades(tr.value);
    if (sig.status  === "fulfilled") {
      setSignal(sig.value);
      setLivePrice(sig.value?.price ?? null);
    }
    if (mkt.status  === "fulfilled") setMarketStats(mkt.value);
    if (sets.status === "fulfilled") {
      const d = sets.value;
      setAllPairs({
        crypto: d.crypto_pairs || d.supported_pairs || PAIRS,
        forex:  d.forex_pairs  || [],
      });
      setSafety({
        effective_testnet: d.effective_testnet ?? d.testnet ?? true,
        live_allowed:      d.safety?.live_allowed ?? false,
        requested_live:    d.testnet === false,
      });
    }
  }, [symbol]);

  useEffect(() => {
    fetchAll();
    const id = window.setInterval(fetchAll, 15000);
    return () => window.clearInterval(id);
  }, [fetchAll]);

  // ── Watchlist bulk prices — har 10 sec ─────────────────────────────────────
  useEffect(() => {
    const allSymbols = [...allPairs.crypto, ...allPairs.forex];
    if (!allSymbols.length) return;

    async function fetchPrices() {
      try {
        const data = await getBulkPrices(allSymbols);
        setWlPrices(data);
      } catch (_) {}
    }

    fetchPrices();
    const id = window.setInterval(fetchPrices, 10000);
    return () => window.clearInterval(id);
  }, [allPairs]);

  // ── WebSocket messages ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!wsMessage) return;
    if (wsMessage.type === "SIGNAL_UPDATE") {
      if (wsMessage.signal) {
        setSignal(wsMessage.signal);
        setLivePrice(wsMessage.signal.price);
      }
      if (wsMessage.stats)       setStats(wsMessage.stats);
      if (wsMessage.open_trades) setOpenTrades(wsMessage.open_trades);
    }
    if (
      wsMessage.type === "TRADE_EXECUTED" ||
      wsMessage.type === "TRADE_CLOSED"
    ) fetchAll();
  }, [wsMessage, fetchAll]);

  // ── Handlers ────────────────────────────────────────────────────────────────
  async function handleToggle() {
    setBtnLoading(true);
    try {
      if (botRunning) { await stopBot(); setBotRunning(false); }
      else { await startBot({ symbol, interval: timeframe }); setBotRunning(true); }
    } catch (e) { alert(e.message); }
    setBtnLoading(false);
  }

  function handleSymbolChange(sym) {
    setSymbol(sym);
    setLivePrice(null);
    setSignal(null);
  }

  const pnlPos      = (stats?.total_pnl || 0) >= 0;
  const change24    = marketStats ? parseFloat(marketStats.priceChangePercent) : null;
  const chgPos      = change24 != null && change24 >= 0;
  const allWatchlist = [...allPairs.crypto, ...allPairs.forex];

  return (
    <div className="dashboard-root">

      {/* ══ LEFT SIDEBAR — Watchlist ══ */}
      <aside className="dash-sidebar">
        <div className="sidebar-header">
          <BarChart2 size={13} />
          <span>Watchlist</span>
        </div>
        <div className="wl-list">
          {allWatchlist.map(p => (
            <WatchlistItem
              key={p}
              pair={p}
              active={symbol === p}
              onClick={() => handleSymbolChange(p)}
              priceData={wlPrices[p]}
            />
          ))}
        </div>
      </aside>

      {/* ══ MOBILE WATCHLIST DRAWER ══ */}
      {wlOpen && (
        <>
          <div className="mobile-backdrop" onClick={() => setWlOpen(false)} />
          <div className="mobile-wl-drawer">
            <div className="mobile-wl-header">
              <span>Watchlist</span>
              <button className="modal-close" onClick={() => setWlOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="wl-list">
              {allWatchlist.map(p => (
                <WatchlistItem
                  key={p}
                  pair={p}
                  active={symbol === p}
                  onClick={() => { handleSymbolChange(p); setWlOpen(false); }}
                  priceData={wlPrices[p]}
                />
              ))}
            </div>
          </div>
        </>
      )}

      {/* ══ CENTER — Chart + Stats ══ */}
      <main className="dash-center">

        {/* Top bar */}
        <div className="dash-topbar">
          <div className="dash-symbol-info">
            <span className="dash-sym-name">
              {symbol.replace("USDT", "")}
              <span style={{ color:"var(--text-dim)", fontWeight:500 }}>/USDT</span>
            </span>
            {livePrice && (
              <span className="dash-live-price">
                ${Number(livePrice).toLocaleString()}
              </span>
            )}
            {change24 != null && (
              <span className={`dash-change ${chgPos ? "chg-pos" : "chg-neg"}`}>
                {chgPos ? <TrendingUp size={11}/> : <TrendingDown size={11}/>}
                {chgPos ? "+" : ""}{change24.toFixed(2)}%
              </span>
            )}
          </div>

          <div className="dash-topbar-right">
            {/* Mobile watchlist toggle */}
            <button className="wl-mobile-btn" onClick={() => setWlOpen(v => !v)}>
              <SlidersHorizontal size={14} />
              <span>Watchlist</span>
            </button>
            <div className="tf-pills">
              {INTERVALS.map(tf => (
                <button
                  key={tf}
                  className={`tf-pill ${timeframe === tf ? "tf-active" : ""}`}
                  onClick={() => setTimeframe(tf)}
                >{tf}</button>
              ))}
            </div>
            <button
              className={`btn-bot ${botRunning ? "btn-stop" : "btn-start"}`}
              onClick={handleToggle}
              disabled={btnLoading}
            >
              {btnLoading
                ? <span className="spinner" />
                : botRunning
                  ? <><Square size={12} fill="currentColor" /> Stop</>
                  : <><Play   size={12} fill="currentColor" /> Start Bot</>
              }
            </button>
          </div>
        </div>

        {/* Stats row */}
        <div className="dash-stats-row">
          <StatCard icon={Wallet}     title="Balance"
            value={!stats ? "—"
              : stats.balance_ok === false ? "Unavailable"
              : `$${Number(stats.usdt_balance||0).toFixed(2)}`}
            sub={stats?.balance_ok === false ? "check API key" : "USDT"} color="blue" />
          <StatCard icon={TrendingUp} title="Total P&L"
            value={stats ? `${pnlPos?"+":""}$${Number(stats.total_pnl||0).toFixed(2)}` : "—"}
            sub={`${stats?.total_trades||0} trades`} color={pnlPos?"green":"red"} />
          <StatCard icon={Target}     title="Win Rate"
            value={stats ? `${stats.win_rate||0}%` : "—"}
            sub={`${stats?.winning_trades||0}W ${stats?.losing_trades||0}L`} color="purple" />
          <StatCard icon={BarChart2}  title="Open"
            value={stats?.open_trades ?? "—"} sub="Positions" color="orange" />
          <StatCard icon={Activity}   title="24h"
            value={change24!=null ? `${chgPos?"+":""}${change24.toFixed(2)}%` : "—"}
            sub={symbol} color={chgPos?"green":"red"} />
        </div>

        {/* Chart */}
        <PriceChart symbol={symbol} interval={timeframe} livePrice={livePrice} />

        {/* Manual Trade */}
        <ManualTradePanel currentSymbol={symbol} onTradeExecuted={fetchAll} />

        {/* Open Positions */}
        <div className="section">
          <div className="section-header">
            <h2 className="section-title">Open Positions</h2>
            <span className="section-badge">{openTrades.length}</span>
          </div>
          {openTrades.length === 0 ? (
            <div className="empty-state" style={{ padding:28 }}>
              <BarChart2 size={28} color="var(--border2)" />
              <span>No open positions</span>
              <small>Bot buys when AI confidence ≥ 60%</small>
            </div>
          ) : (
            <div className="trades-grid">
              {openTrades.map(trade => (
                <OpenTradeCard
                  key={trade.id}
                  trade={trade}
                  // Each trade must be valued at its OWN symbol's price.
                  // Passing the selected symbol's livePrice made every other
                  // position show a fabricated P&L.
                  currentPrice={
                    wlPrices?.[trade.symbol]?.price
                    ?? (trade.symbol === symbol ? livePrice : null)
                  }
                  onClose={fetchAll}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* ══ RIGHT PANEL — Signal ══ */}
      <aside className="dash-right-panel">

        <div className={`dash-bot-status ${botRunning ? "status-on" : "status-off"}`}>
          <Zap size={13} fill="currentColor" />
          {botRunning ? "Bot Running" : "Bot Stopped"}
        </div>

        {/* Trading-mode banner — the bot may be configured for live but blocked */}
        {safety && !safety.effective_testnet ? (
          <div className="safety-banner safety-live" title="Real funds are at risk">
            🔴 LIVE MODE — real orders
          </div>
        ) : safety?.requested_live && !safety.live_allowed ? (
          <div className="safety-banner safety-blocked"
               title="The server refused live trading because LIVE_TRADING_ENABLED is not set">
            🟡 Live blocked — running on testnet
          </div>
        ) : safety ? (
          <div className="safety-banner safety-testnet" title="Simulated trading">
            🟢 Testnet
          </div>
        ) : null}

        {signal ? (
          <>
            {/* Signal top */}
            <div className="rp-signal-top">
              <div className="ind-header" style={{ marginBottom:8 }}>AI Signal</div>
              <SignalBadge action={signal.action} confidence={signal.confidence} />
              <div className="rp-price">${Number(signal.price).toLocaleString()}</div>
            </div>

            {/* Risk levels */}
            {signal.stop_loss && (
              <div className="rp-section">
                <div className="ind-header">Risk Levels</div>
                <div className="level-item sl">
                  <span style={{ display:"flex", alignItems:"center", gap:5 }}>
                    <AlertTriangle size={11}/> Stop Loss
                  </span>
                  <span>${signal.stop_loss}</span>
                </div>
                <div className="level-item tp" style={{ marginTop:6 }}>
                  <span style={{ display:"flex", alignItems:"center", gap:5 }}>
                    <Target size={11}/> Take Profit
                  </span>
                  <span>${signal.take_profit}</span>
                </div>
              </div>
            )}

            {/* Score bars */}
            <div className="rp-section">
              <div className="ind-header">Signal Score</div>
              <div className="score-row">
                <div className="score-bar-wrap">
                  <div className="score-label green-text">BUY {signal.buy_score}</div>
                  <div className="score-track">
                    <div className="score-fill green-fill"
                      style={{ width:`${Math.min(signal.buy_score/2.5,100)}%` }} />
                  </div>
                </div>
                <div className="score-bar-wrap">
                  <div className="score-label red-text">SELL {signal.sell_score}</div>
                  <div className="score-track">
                    <div className="score-fill red-fill"
                      style={{ width:`${Math.min(signal.sell_score/2.5,100)}%` }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Indicators */}
            <div className="rp-section">
              <div className="ind-header">Indicators</div>
              {[
                { label:"RSI",         val:signal.rsi,        cls:signal.rsi>70?"red":signal.rsi<30?"green":"white" },
                { label:"Stoch K",     val:signal.stoch_k,    cls:signal.stoch_k>80?"red":signal.stoch_k<20?"green":"white" },
                { label:"Williams %R", val:signal.williams_r, cls:signal.williams_r>-20?"red":signal.williams_r<-80?"green":"white" },
                { label:"VWAP",        val:signal.vwap,       cls:signal.price>signal.vwap?"green":"red" },
                { label:"EMA Fast",    val:signal.ema_fast,   cls:"white" },
                { label:"EMA Slow",    val:signal.ema_slow,   cls:"white" },
                { label:"MACD",        val:signal.macd,       cls:signal.macd>0?"green":"red" },
                { label:"SuperTrend",  val:signal.supertrend, cls:signal.supertrend==="BULLISH"?"green":signal.supertrend==="BEARISH"?"red":"white", isText:true },
              ].map(({ label, val, cls, isText }) => (
                <div key={label} className="indicator-item">
                  <span className="ind-label">{label}</span>
                  <span className={`ind-value ${cls}`}>
                    {isText ? val : Number(val||0).toFixed(2)}
                  </span>
                </div>
              ))}
              {signal.support && (
                <>
                  <div className="indicator-item">
                    <span className="ind-label">Support</span>
                    <span className="ind-value green">${Number(signal.support).toFixed(2)}</span>
                  </div>
                  <div className="indicator-item">
                    <span className="ind-label">Resistance</span>
                    <span className="ind-value red">${Number(signal.resistance).toFixed(2)}</span>
                  </div>
                </>
              )}
            </div>

            {/* MTF */}
            {signal.mtf && (
              <div className="rp-section">
                <div className="ind-header">Multi-Timeframe</div>
                {Object.entries(signal.mtf.timeframes || {}).map(([tf, data]) => (
                  <div key={tf} className="indicator-item">
                    <span className="ind-label">{tf}</span>
                    <span className={`ind-value ${data.trend==="BULLISH"?"green":data.trend==="BEARISH"?"red":"white"}`}>
                      {data.trend}
                    </span>
                  </div>
                ))}
                <div className="indicator-item">
                  <span className="ind-label">Overall</span>
                  <span className={`ind-value ${signal.mtf.mtf_trend==="BULLISH"?"green":signal.mtf.mtf_trend==="BEARISH"?"red":"white"}`}>
                    {signal.mtf.mtf_trend}
                  </span>
                </div>
              </div>
            )}

            {/* Sentiment */}
            {signal.sentiment?.fear_greed && (
              <div className="rp-section">
                <div className="ind-header">Sentiment</div>
                <div className="indicator-item">
                  <span className="ind-label">Fear & Greed</span>
                  <span className={`ind-value ${signal.sentiment.fear_greed.value<40?"green":signal.sentiment.fear_greed.value>60?"red":"white"}`}>
                    {signal.sentiment.fear_greed.value} · {signal.sentiment.fear_greed.category}
                  </span>
                </div>
                <div className="indicator-item">
                  <span className="ind-label">Overall</span>
                  <span className={`ind-value ${signal.sentiment.overall==="BULLISH"?"green":signal.sentiment.overall==="BEARISH"?"red":"white"}`}>
                    {signal.sentiment.overall}
                  </span>
                </div>
              </div>
            )}

            {/* Active signals */}
            <div className="rp-section">
              <div className="ind-header">Active Signals</div>
              <ul className="signal-list">
                {(signal.signals||[]).slice(0,8).map((s, i) => (
                  <li key={i} className="signal-item">{s}</li>
                ))}
              </ul>
            </div>
          </>
        ) : (
          <div className="rp-empty">
            <Clock size={28} color="var(--border2)" />
            <span>Waiting for signal...</span>
          </div>
        )}
      </aside>

    </div>
  );
}
