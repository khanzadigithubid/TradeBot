import { useEffect, useState } from "react";
import {
  Download, TrendingUp, TrendingDown,
  BarChart2, Percent, DollarSign, Clock
} from "lucide-react";
import { getTradeHistory } from "../services/api";

const REASON_CLS = {
  TAKE_PROFIT:   "reason-tp",
  STOP_LOSS:     "reason-sl",
  TRAILING_STOP: "reason-sl",
  SIGNAL:        "reason-signal",
  MANUAL:        "reason-manual",
  MANUAL_CLOSE:  "reason-manual",
};
const REASON_LABEL = {
  TAKE_PROFIT:   "🎯 Take Profit",
  STOP_LOSS:     "🛑 Stop Loss",
  TRAILING_STOP: "📉 Trailing Stop",
  SIGNAL:        "📊 Signal",
  MANUAL:        "👤 Manual",
  MANUAL_CLOSE:  "👤 Manual",
};

export default function History() {
  const [trades,  setTrades]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter,  setFilter]  = useState("ALL");

  useEffect(() => {
    getTradeHistory(100)
      .then(h => setTrades(h))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const wins     = trades.filter(t => (t.pnl || 0) > 0);
  const losses   = trades.filter(t => (t.pnl || 0) <= 0);
  const totalPnl = trades.reduce((s, t) => s + (t.pnl || 0), 0);
  const winRate  = trades.length > 0
    ? ((wins.length / trades.length) * 100).toFixed(1) : 0;
  const filtered = filter === "WIN" ? wins : filter === "LOSS" ? losses : trades;

  function exportCSV() {
    const headers = ["Symbol","Side","Entry","Exit","Qty","PnL","PnL%","Reason","Time"];
    const rows = trades.map(t => [
      t.symbol, t.side, t.entry_price, t.exit_price,
      t.quantity, t.pnl, t.pnl_percent, t.close_reason,
      t.exit_time ? new Date(t.exit_time).toLocaleString() : "",
    ]);
    const csv = [headers, ...rows].map(r => r.join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "trade_history.csv";
    a.click();
  }

  return (
    <div className="page">

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Trade History</h1>
          <p className="page-sub">All closed positions</p>
        </div>
        <button className="btn-export" onClick={exportCSV} disabled={!trades.length}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Loading */}
      {loading && <div className="loading-state">Loading history...</div>}

      {/* ── Pro Empty State — no trades yet ── */}
      {!loading && trades.length === 0 && (
        <div className="pro-empty-state">
          <div className="pes-icon">📊</div>
          <h2 className="pes-title">No Trade History Yet</h2>
          <p className="pes-desc">
            Your completed trades will appear here once the bot executes its first buy and sell cycle.
          </p>
          <div className="pes-steps">
            <div className="pes-step">
              <span className="pes-step-num">1</span>
              <span>Go to <b>Dashboard</b> and start the bot</span>
            </div>
            <div className="pes-step">
              <span className="pes-step-num">2</span>
              <span>Bot analyzes market every 15 minutes</span>
            </div>
            <div className="pes-step">
              <span className="pes-step-num">3</span>
              <span>When AI confidence ≥ 60%, a trade is placed automatically</span>
            </div>
            <div className="pes-step">
              <span className="pes-step-num">4</span>
              <span>After Stop Loss / Take Profit hit, closed trade appears here</span>
            </div>
          </div>
          <div className="pes-status">
            <span className="pes-dot" />
            System ready — waiting for first trade
          </div>
        </div>
      )}

      {/* ── Data — only when trades exist ── */}
      {!loading && trades.length > 0 && (
        <>
          {/* Summary Cards */}
          <div className="history-summary">
            {[
              { label:"Total Trades", value: trades.length,  icon: BarChart2,   color:"blue" },
              { label:"Wins",         value: wins.length,    icon: TrendingUp,  color:"green" },
              { label:"Losses",       value: losses.length,  icon: TrendingDown,color:"red" },
              { label:"Win Rate",     value: `${winRate}%`,  icon: Percent,     color:"purple" },
              { label:"Total P&L",    value: `${totalPnl>=0?"+":""}${totalPnl.toFixed(4)}`,
                icon: DollarSign, color: totalPnl>=0?"green":"red" },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className={`summary-card ${color}`}>
                <div className="summary-label">{label}</div>
                <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                  <Icon size={16} />
                  <span className="summary-value">{value}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Filters */}
          <div className="filter-tabs">
            {[
              ["ALL",  `All (${trades.length})`],
              ["WIN",  `Wins (${wins.length})`],
              ["LOSS", `Losses (${losses.length})`],
            ].map(([k, label]) => (
              <button key={k}
                className={`filter-tab ${filter === k ? "active" : ""}`}
                onClick={() => setFilter(k)}>
                {label}
              </button>
            ))}
          </div>

          {/* No filtered results */}
          {filtered.length === 0 ? (
            <div className="empty-state">
              <BarChart2 size={28} color="var(--border2)" />
              <span>No {filter.toLowerCase()} trades found</span>
            </div>
          ) : (
            <>
              {/* Desktop Table */}
              <div className="table-wrapper history-table-desktop">
                <table className="trade-table">
                  <thead>
                    <tr>
                      <th>Symbol</th><th>Entry</th><th>Exit</th>
                      <th className="qty-col">Qty</th>
                      <th>P&L (USDT)</th><th>P&L %</th>
                      <th>Reason</th><th>AI Conf.</th>
                      <th className="time-col">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(t => {
                      const isWin = (t.pnl || 0) > 0;
                      return (
                        <tr key={t.id} className={isWin ? "row-win" : "row-loss"}>
                          <td><span className="symbol-tag">{t.symbol}</span></td>
                          <td>${Number(t.entry_price).toLocaleString()}</td>
                          <td>${Number(t.exit_price||0).toLocaleString()}</td>
                          <td className="qty-col">{t.quantity}</td>
                          <td className={isWin?"pnl-pos":"pnl-neg"}>
                            {isWin?"+":""}{Number(t.pnl||0).toFixed(4)}
                          </td>
                          <td className={isWin?"pnl-pos":"pnl-neg"}>
                            {isWin?"+":""}{Number(t.pnl_percent||0).toFixed(2)}%
                          </td>
                          <td>
                            <span className={`reason-tag ${REASON_CLS[t.close_reason]||""}`}>
                              {REASON_LABEL[t.close_reason] || t.close_reason || "—"}
                            </span>
                          </td>
                          <td>
                            <div className="confidence-bar">
                              <div className="confidence-fill" style={{width:`${t.confidence||0}%`}}/>
                              <span className="confidence-text">{t.confidence||0}%</span>
                            </div>
                          </td>
                          <td className="time-col">
                            {t.exit_time ? new Date(t.exit_time).toLocaleString() : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Mobile Cards */}
              <div className="history-cards-mobile">
                {filtered.map(t => {
                  const isWin = (t.pnl || 0) > 0;
                  return (
                    <div key={t.id} className={`history-card ${isWin?"hc-win":"hc-loss"}`}>
                      <div className="hc-header">
                        <div style={{display:"flex",alignItems:"center",gap:8}}>
                          <span className="symbol-tag">{t.symbol}</span>
                          <span className={`reason-tag ${REASON_CLS[t.close_reason]||""}`}>
                            {REASON_LABEL[t.close_reason] || t.close_reason}
                          </span>
                        </div>
                        <span className={`hc-pnl ${isWin?"pnl-pos":"pnl-neg"}`}>
                          {isWin?"+":""}{Number(t.pnl||0).toFixed(4)} USDT
                        </span>
                      </div>
                      <div className="hc-body">
                        <div className="hc-row">
                          <span>Entry</span><span>${Number(t.entry_price).toLocaleString()}</span>
                        </div>
                        <div className="hc-row">
                          <span>Exit</span><span>${Number(t.exit_price||0).toLocaleString()}</span>
                        </div>
                        <div className="hc-row">
                          <span>P&L %</span>
                          <span className={isWin?"pnl-pos":"pnl-neg"}>
                            {isWin?"+":""}{Number(t.pnl_percent||0).toFixed(2)}%
                          </span>
                        </div>
                      </div>
                      {t.exit_time && (
                        <div className="hc-footer">
                          <Clock size={10} style={{marginRight:4}}/>
                          {new Date(t.exit_time).toLocaleString()}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
