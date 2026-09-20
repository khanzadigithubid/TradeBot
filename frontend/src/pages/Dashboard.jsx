import { useEffect, useState, useCallback } from "react";
import {
  Wallet, TrendingUp, Target, BarChart2, Activity,
  Play, Square, ChevronDown, ArrowUpRight, ArrowDownRight,
  AlertTriangle
} from "lucide-react";
import {
  getBotStatus, startBot, stopBot,
  getTradeStats, getOpenTrades, getSignal, getMarketStats, getSettings
} from "../services/api";
import StatCard from "../components/StatCard";
import SignalBadge from "../components/SignalBadge";
import OpenTradeCard from "../components/OpenTradeCard";
import PriceChart from "../components/PriceChart";
import ManualTradePanel from "../components/ManualTradePanel";

const PAIRS     = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT"];
const INTERVALS = ["1m","5m","15m","30m","1h","4h","1d"];

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

  const fetchAll = useCallback(async () => {
    const [s, st, tr, sig, mkt, sets] = await Promise.allSettled([
      getBotStatus(), getTradeStats(), getOpenTrades(),
      getSignal(symbol), getMarketStats(symbol),
      getSettings(),
    ]);
    if (s.status    === "fulfilled") setBotRunning(s.value.running);
    if (st.status   === "fulfilled") setStats(st.value);
    if (tr.status   === "fulfilled") setOpenTrades(tr.value);
    if (sig.status  === "fulfilled") { setSignal(sig.value); setLivePrice(sig.value?.price ?? null); }
    if (mkt.status  === "fulfilled") setMarketStats(mkt.value);
    if (sets.status === "fulfilled") {
      const d = sets.value;
      setAllPairs({
        crypto: d.crypto_pairs || d.supported_pairs || PAIRS,
        forex:  d.forex_pairs  || [],
      });
    }
  }, [symbol]);

  useEffect(() => {
    fetchAll();
    const id = window.setInterval(fetchAll, 15000);
    return () => window.clearInterval(id);
  }, [fetchAll]);

  useEffect(() => {
    if (!wsMessage) return;
    if (wsMessage.type === "SIGNAL_UPDATE") {
      if (wsMessage.signal)      { setSignal(wsMessage.signal); setLivePrice(wsMessage.signal.price); }
      if (wsMessage.stats)       setStats(wsMessage.stats);
      if (wsMessage.open_trades) setOpenTrades(wsMessage.open_trades);
    }
    if (wsMessage.type === "TRADE_EXECUTED" || wsMessage.type === "TRADE_CLOSED") fetchAll();
  }, [wsMessage, fetchAll]);

  async function handleToggle() {
    setBtnLoading(true);
    try {
      if (botRunning) { await stopBot(); setBotRunning(false); }
      else            { await startBot({ symbol, interval: timeframe }); setBotRunning(true); }
    } catch (e) { alert(e.message); }
    setBtnLoading(false);
  }

  // Symbol change hone pe livePrice reset karo
  function handleSymbolChange(e) {
    setSymbol(e.target.value);
    setLivePrice(null);
    setSignal(null);
  }

  const pnlPos   = (stats?.total_pnl || 0) >= 0;
  const change24 = marketStats ? parseFloat(marketStats.priceChangePercent) : null;
  const chgPos   = change24 != null && change24 >= 0;

  return (
    <div className="page dashboard-page">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">AI-powered auto trading — Binance Testnet</p>
        </div>
        <div className="header-controls">
          <div className="select-wrap">
            <select className="pair-select" value={symbol} onChange={handleSymbolChange}>
              <optgroup label="── Crypto ──">
                {allPairs.crypto.map((p) => <option key={p}>{p}</option>)}
              </optgroup>
              {allPairs.forex.length > 0 && (
                <optgroup label="── Forex ──">
                  {allPairs.forex.map((p) => <option key={p}>{p}</option>)}
                </optgroup>
              )}
            </select>
            <ChevronDown size={12} className="select-arrow" />
          </div>
          <div className="select-wrap">
            <select className="pair-select" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {INTERVALS.map((i) => <option key={i}>{i}</option>)}
            </select>
            <ChevronDown size={12} className="select-arrow" />
          </div>
          <button className={`btn-bot ${botRunning ? "btn-stop" : "btn-start"}`} onClick={handleToggle} disabled={btnLoading}>
            {btnLoading
              ? <span className="spinner" />
              : botRunning
                ? <><Square size={13} fill="currentColor" /> Stop Bot</>
                : <><Play  size={13} fill="currentColor" /> Start Bot</>
            }
          </button>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="stats-grid">
        <StatCard icon={Wallet}     title="USDT Balance"
          value={stats ? `$${Number(stats.usdt_balance||0).toFixed(2)}` : "—"}
          sub="Available" color="blue" />
        <StatCard icon={TrendingUp} title="Total P&L"
          value={stats ? `${pnlPos?"+":""}$${Number(stats.total_pnl||0).toFixed(4)}` : "—"}
          sub={`${stats?.total_trades||0} closed trades`} color={pnlPos?"green":"red"} />
        <StatCard icon={Target}     title="Win Rate"
          value={stats ? `${stats.win_rate||0}%` : "—"}
          sub={`${stats?.winning_trades||0}W  ${stats?.losing_trades||0}L`} color="purple" />
        <StatCard icon={BarChart2}  title="Open Trades"
          value={stats?.open_trades ?? "—"} sub="Active positions" color="orange" />
        <StatCard icon={Activity}   title="24h Change"
          value={change24!=null ? `${chgPos?"+":""}${change24.toFixed(2)}%` : "—"}
          sub={symbol} color={chgPos?"green":"red"} />
      </div>

      {/* ── Chart ── */}
      <PriceChart symbol={symbol} interval={timeframe} livePrice={livePrice} />

      {/* ── Signal ── */}
      {signal && (
        <div className="signal-panel">
          <div className="signal-panel-left">
            <div className="signal-label">AI Signal</div>
            <SignalBadge action={signal.action} confidence={signal.confidence} />
            <div className="signal-price">${Number(signal.price).toLocaleString()}</div>
            {/* MTF Trend */}
            {signal.mtf && (
              <div style={{ marginTop: 8 }}>
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
          </div>

          <div className="signal-indicators">
            <div className="ind-header">Indicators</div>
            {[
              { label:"RSI",         val: signal.rsi,        cls: signal.rsi>70?"red":signal.rsi<30?"green":"white" },
              { label:"Stoch K",     val: signal.stoch_k,    cls: signal.stoch_k>80?"red":signal.stoch_k<20?"green":"white" },
              { label:"Williams %R", val: signal.williams_r, cls: signal.williams_r>-20?"red":signal.williams_r<-80?"green":"white" },
              { label:"VWAP",        val: signal.vwap,       cls: signal.price > signal.vwap ? "green" : "red" },
              { label:"EMA Fast",    val: signal.ema_fast,   cls:"white" },
              { label:"EMA Slow",    val: signal.ema_slow,   cls:"white" },
              { label:"MACD",        val: signal.macd,       cls: signal.macd>0?"green":"red" },
              { label:"BB Upper",    val: signal.bb_upper,   cls:"white" },
              { label:"BB Lower",    val: signal.bb_lower,   cls:"white" },
              { label:"SuperTrend",  val: signal.supertrend, cls: signal.supertrend==="BULLISH"?"green":signal.supertrend==="BEARISH"?"red":"white", isText: true },
            ].map(({ label, val, cls, isText }) => (
              <div key={label} className="indicator-item">
                <span className="ind-label">{label}</span>
                <span className={`ind-value ${cls}`}>
                  {isText ? val : Number(val||0).toFixed(2)}
                </span>
              </div>
            ))}
            {/* Support / Resistance */}
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

          <div className="signal-reasons">
            <div className="ind-header">Active Signals</div>
            <ul className="signal-list">
              {(signal.signals||[]).map((s,i) => (
                <li key={i} className="signal-item">{s}</li>
              ))}
            </ul>
            <div className="score-row">
              <div className="score-bar-wrap">
                <div className="score-label green-text">BUY {signal.buy_score}</div>
                <div className="score-track">
                  <div className="score-fill green-fill" style={{width:`${Math.min(signal.buy_score/2.5,100)}%`}} />
                </div>
              </div>
              <div className="score-bar-wrap">
                <div className="score-label red-text">SELL {signal.sell_score}</div>
                <div className="score-track">
                  <div className="score-fill red-fill" style={{width:`${Math.min(signal.sell_score/2.5,100)}%`}} />
                </div>
              </div>
            </div>

            {/* Sentiment */}
            {signal.sentiment?.fear_greed && (
              <div style={{ marginTop: 10 }}>
                <div className="ind-header">Market Sentiment</div>
                <div className="indicator-item">
                  <span className="ind-label">Fear & Greed</span>
                  <span className={`ind-value ${signal.sentiment.fear_greed.value < 40 ? "green" : signal.sentiment.fear_greed.value > 60 ? "red" : "white"}`}>
                    {signal.sentiment.fear_greed.value} — {signal.sentiment.fear_greed.category}
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
          </div>

          {signal.stop_loss && (
            <div className="signal-levels">
              <div className="ind-header">Risk Levels</div>
              <div className="level-item sl">
                <span style={{display:"flex",alignItems:"center",gap:6}}>
                  <AlertTriangle size={12} /> Stop Loss
                </span>
                <span>${signal.stop_loss}</span>
              </div>
              <div className="level-item tp">
                <span style={{display:"flex",alignItems:"center",gap:6}}>
                  <Target size={12} /> Take Profit
                </span>
                <span>${signal.take_profit}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Manual Trade ── */}
      <ManualTradePanel currentSymbol={symbol} onTradeExecuted={fetchAll} />

      {/* ── Open Trades ── */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Open Positions</h2>
          <span className="section-badge">{openTrades.length}</span>
        </div>
        {openTrades.length === 0 ? (
          <div className="empty-state">
            <BarChart2 size={32} color="#2a2f45" />
            <span>No open positions</span>
            <small>Bot will buy automatically when AI confidence ≥ 60%</small>
          </div>
        ) : (
          <div className="trades-grid">
            {openTrades.map((trade) => (
              <OpenTradeCard key={trade.id} trade={trade} currentPrice={livePrice} onClose={fetchAll} />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
