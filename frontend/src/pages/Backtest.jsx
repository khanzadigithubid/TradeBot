import { useState, useEffect } from "react";
import {
  Play, BarChart2, TrendingUp, TrendingDown,
  DollarSign, Award, AlertTriangle, Target, Zap
} from "lucide-react";
import { runBacktest, getSettings } from "../services/api";

const INTERVALS = ["1m","5m","15m","30m","1h","4h","1d"];

/* ── Metric Card ── */
function MetricCard({ icon: Icon, title, value, sub, color = "blue" }) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="stat-icon-wrap"><Icon size={20} strokeWidth={1.8} /></div>
      <div>
        <div className="stat-title">{title}</div>
        <div className="stat-value">{value ?? "—"}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

export default function Backtest() {
  const [form, setForm] = useState({
    symbol:               "BTCUSDT",
    interval:             "15m",
    limit:                500,
    initial_balance:      1000,
    confidence_threshold: 60,
  });
  const [cryptoPairs, setCryptoPairs] = useState([]);
  const [forexPairs,  setForexPairs]  = useState([]);
  const [result,      setResult]      = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    getSettings().then(d => {
      if (d.crypto_pairs?.length) setCryptoPairs(d.crypto_pairs);
      if (d.forex_pairs?.length)  setForexPairs(d.forex_pairs);
    }).catch(() => {});
  }, []);

  function handleChange(e) {
    const { name, value, type } = e.target;
    setForm(f => ({ ...f, [name]: type === "number" ? parseFloat(value) : value }));
  }

  async function handleRun(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await runBacktest(form));
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  const m = result?.metrics;

  return (
    <div className="page backtest-page">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Backtesting</h1>
          <p className="page-sub">Simulate strategy on historical data — no real trades placed</p>
        </div>
      </div>

      {/* ── Config Card ── */}
      <div className="settings-card">
        <div className="settings-section-title">
          <BarChart2 size={14} /> Backtest Configuration
        </div>

        <form onSubmit={handleRun}>
          <div className="form-row">
            {/* Symbol */}
            <div className="form-group">
              <label>Symbol</label>
              <select name="symbol" value={form.symbol} onChange={handleChange} className="form-select">
                {cryptoPairs.length > 0 ? (
                  <>
                    <optgroup label="── Crypto ──">
                      {cryptoPairs.map(p => <option key={p}>{p}</option>)}
                    </optgroup>
                    {forexPairs.length > 0 && (
                      <optgroup label="── Forex ──">
                        {forexPairs.map(p => <option key={p}>{p}</option>)}
                      </optgroup>
                    )}
                  </>
                ) : <option>BTCUSDT</option>}
              </select>
            </div>

            {/* Interval */}
            <div className="form-group">
              <label>Interval</label>
              <select name="interval" value={form.interval} onChange={handleChange} className="form-select">
                {INTERVALS.map(i => <option key={i}>{i}</option>)}
              </select>
            </div>

            {/* Candles */}
            <div className="form-group">
              <label>Candles</label>
              <input type="number" name="limit" value={form.limit}
                onChange={handleChange} min="100" max="1000" step="50"
                className="form-input" />
              <small>More = longer history</small>
            </div>

            {/* Balance */}
            <div className="form-group">
              <label>Starting Balance (USDT)</label>
              <input type="number" name="initial_balance" value={form.initial_balance}
                onChange={handleChange} min="100" step="100"
                className="form-input" />
            </div>

            {/* Confidence */}
            <div className="form-group">
              <label>Min Confidence %</label>
              <input type="number" name="confidence_threshold" value={form.confidence_threshold}
                onChange={handleChange} min="50" max="99" step="1"
                className="form-input" />
              <small>Only enter above this</small>
            </div>
          </div>

          <div style={{ marginTop:16 }}>
            <button type="submit" className="btn-bot btn-start" disabled={loading}
              style={{ minWidth:200, justifyContent:"center" }}>
              {loading
                ? <><span className="spinner" /> Running...</>
                : <><Play size={13} fill="currentColor" /> Run Backtest</>}
            </button>
          </div>
        </form>
      </div>

      {/* ── Error ── */}
      {error && <div className="settings-note live-warning">{error}</div>}

      {/* ── Results ── */}
      {m && (
        <>
          {/* Summary banner */}
          <div className="bt-summary-banner">
            <div className="bt-banner-item">
              <span className="bt-banner-label">Symbol</span>
              <span className="symbol-tag" style={{fontSize:13}}>{form.symbol}</span>
            </div>
            <div className="bt-banner-item">
              <span className="bt-banner-label">Interval</span>
              <span className="bt-banner-val">{form.interval}</span>
            </div>
            <div className="bt-banner-item">
              <span className="bt-banner-label">Total Trades</span>
              <span className="bt-banner-val">{m.total_trades}</span>
            </div>
            <div className="bt-banner-item">
              <span className="bt-banner-label">Return</span>
              <span className={`bt-banner-val ${(m.total_pnl||0)>=0?"pnl-pos":"pnl-neg"}`}>
                {(m.total_pnl_percent||0)>=0?"+":""}{m.total_pnl_percent?.toFixed(2)}%
              </span>
            </div>
          </div>

          {/* Metrics Row 1 */}
          <div className="bt-metrics-grid">
            <MetricCard icon={DollarSign}    title="Final Balance"
              value={`$${m.final_balance?.toFixed(2)}`}
              sub={`Started $${m.initial_balance}`}
              color={(m.final_balance-m.initial_balance)>=0?"green":"red"} />
            <MetricCard icon={TrendingUp}    title="Total P&L"
              value={`${(m.total_pnl||0)>=0?"+":""}$${m.total_pnl?.toFixed(4)}`}
              sub={`${m.total_pnl_percent?.toFixed(2)}% return`}
              color={(m.total_pnl||0)>=0?"green":"red"} />
            <MetricCard icon={BarChart2}     title="Win Rate"
              value={`${m.win_rate}%`}
              sub={`${m.winning_trades}W / ${m.losing_trades}L`}
              color="purple" />
            <MetricCard icon={Award}         title="Sharpe Ratio"
              value={m.sharpe_ratio}
              sub="Risk-adjusted"
              color="blue" />
          </div>

          {/* Metrics Row 2 */}
          <div className="bt-metrics-grid">
            <MetricCard icon={AlertTriangle} title="Max Drawdown"
              value={`$${m.max_drawdown?.toFixed(4)}`}
              sub={`${m.max_drawdown_percent?.toFixed(2)}%`}
              color="red" />
            <MetricCard icon={Zap}           title="Profit Factor"
              value={m.profit_factor===Infinity?"∞":m.profit_factor?.toFixed(2)}
              sub="Gross profit / gross loss"
              color="green" />
            <MetricCard icon={TrendingUp}    title="Avg Win"
              value={`+$${m.avg_win?.toFixed(4)}`}
              sub="Per winning trade"
              color="green" />
            <MetricCard icon={TrendingDown}  title="Avg Loss"
              value={`-$${m.avg_loss?.toFixed(4)}`}
              sub="Per losing trade"
              color="red" />
          </div>

          {/* Trades list */}
          {result.trades?.length > 0 && (
            <div className="settings-card" style={{ padding:0, overflow:"hidden" }}>
              <div className="chart-header">
                <Target size={14} color="var(--text-dim)" />
                <span className="chart-symbol" style={{ fontSize:13 }}>
                  Simulated Trades ({result.trades.length})
                </span>
              </div>

              {/* Desktop table */}
              <div className="bt-table-desktop">
                <div className="table-wrapper" style={{ border:"none", borderRadius:0 }}>
                  <table className="trade-table">
                    <thead>
                      <tr>
                        <th>Symbol</th><th>Entry</th><th>Exit</th>
                        <th>P&L (USDT)</th><th>P&L %</th>
                        <th>Reason</th><th>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trades.map(t => {
                        const win = (t.pnl||0) > 0;
                        const rCls = {
                          TAKE_PROFIT:"reason-tp", STOP_LOSS:"reason-sl",
                          TRAILING_STOP:"reason-sl", SIGNAL:"reason-signal",
                          END_OF_DATA:"reason-manual",
                        };
                        return (
                          <tr key={t.id} className={win?"row-win":"row-loss"}>
                            <td><span className="symbol-tag">{t.symbol}</span></td>
                            <td>${Number(t.entry_price).toLocaleString()}</td>
                            <td>{t.exit_price?`$${Number(t.exit_price).toLocaleString()}`:"—"}</td>
                            <td className={win?"pnl-pos":"pnl-neg"}>{win?"+":""}{Number(t.pnl||0).toFixed(4)}</td>
                            <td className={win?"pnl-pos":"pnl-neg"}>{win?"+":""}{Number(t.pnl_percent||0).toFixed(2)}%</td>
                            <td><span className={`reason-tag ${rCls[t.close_reason]||""}`}>{t.close_reason}</span></td>
                            <td>
                              <div className="confidence-bar">
                                <div className="confidence-fill" style={{width:`${t.confidence||0}%`}}/>
                                <span className="confidence-text">{t.confidence||0}%</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Mobile cards */}
              <div className="bt-cards-mobile">
                {result.trades.map(t => {
                  const win = (t.pnl||0) > 0;
                  const rCls = {TAKE_PROFIT:"reason-tp",STOP_LOSS:"reason-sl",TRAILING_STOP:"reason-sl",SIGNAL:"reason-signal",END_OF_DATA:"reason-manual"};
                  return (
                    <div key={t.id} className={`bt-trade-card ${win?"bt-win":"bt-loss"}`}>
                      <div className="bt-card-row">
                        <span className="symbol-tag">{t.symbol}</span>
                        <span className={win?"pnl-pos":"pnl-neg"} style={{fontWeight:800,fontSize:14}}>
                          {win?"+":""}{Number(t.pnl||0).toFixed(4)} USDT
                        </span>
                      </div>
                      <div className="bt-card-row">
                        <span style={{color:"var(--text-dim)",fontSize:11}}>Entry</span>
                        <span>${Number(t.entry_price).toLocaleString()}</span>
                      </div>
                      <div className="bt-card-row">
                        <span style={{color:"var(--text-dim)",fontSize:11}}>Exit</span>
                        <span>{t.exit_price?`$${Number(t.exit_price).toLocaleString()}`:"—"}</span>
                      </div>
                      <div className="bt-card-row">
                        <span style={{color:"var(--text-dim)",fontSize:11}}>Reason</span>
                        <span className={`reason-tag ${rCls[t.close_reason]||""}`}>{t.close_reason}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
