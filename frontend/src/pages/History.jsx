import { useEffect, useState } from "react";
import { Download, TrendingUp, TrendingDown, BarChart2, Percent, DollarSign } from "lucide-react";
import { getTradeHistory, getTradeStats } from "../services/api";

export default function History() {
  const [trades,  setTrades]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter,  setFilter]  = useState("ALL");

  useEffect(() => {
    Promise.all([getTradeHistory(100), getTradeStats()])
      .then(([h]) => setTrades(h))
      .catch(()=>{})
      .finally(()=>setLoading(false));
  }, []);

  const wins   = trades.filter(t=>(t.pnl||0)>0);
  const losses = trades.filter(t=>(t.pnl||0)<=0);
  const totalPnl = trades.reduce((s,t)=>s+(t.pnl||0),0);
  const winRate  = trades.length>0?((wins.length/trades.length)*100).toFixed(1):0;

  const filtered = filter==="WIN"?wins : filter==="LOSS"?losses : trades;

  function exportCSV() {
    const headers = ["Symbol","Side","Entry","Exit","Qty","PnL","PnL%","Reason","Time"];
    const rows = trades.map(t=>[t.symbol,t.side,t.entry_price,t.exit_price,t.quantity,t.pnl,t.pnl_percent,t.close_reason,t.exit_time?new Date(t.exit_time).toLocaleString():""]);
    const csv = [headers,...rows].map(r=>r.join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv],{type:"text/csv"}));
    a.download = "trade_history.csv";
    a.click();
  }

  return (
    <div className="page history-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Trade History</h1>
          <p className="page-sub">All closed positions</p>
        </div>
        <button className="btn-export" onClick={exportCSV} disabled={!trades.length}>
          <Download size={14}/> Export CSV
        </button>
      </div>

      {/* Summary */}
      <div className="history-summary">
        <div className="summary-card">
          <span className="summary-label">Total Trades</span>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <BarChart2 size={18} color="#787b86"/>
            <span className="summary-value">{trades.length}</span>
          </div>
        </div>
        <div className="summary-card green">
          <span className="summary-label">Wins</span>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <TrendingUp size={18} color="#26a69a"/>
            <span className="summary-value">{wins.length}</span>
          </div>
        </div>
        <div className="summary-card red">
          <span className="summary-label">Losses</span>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <TrendingDown size={18} color="#ef5350"/>
            <span className="summary-value">{losses.length}</span>
          </div>
        </div>
        <div className="summary-card purple">
          <span className="summary-label">Win Rate</span>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <Percent size={18} color="#ce93d8"/>
            <span className="summary-value">{winRate}%</span>
          </div>
        </div>
        <div className={`summary-card ${totalPnl>=0?"green":"red"}`}>
          <span className="summary-label">Total P&L</span>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <DollarSign size={18} color={totalPnl>=0?"#26a69a":"#ef5350"}/>
            <span className="summary-value">{totalPnl>=0?"+":""}{totalPnl.toFixed(4)}</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="filter-tabs">
        {[["ALL",`All (${trades.length})`],["WIN",`Wins (${wins.length})`],["LOSS",`Losses (${losses.length})`]].map(([k,label])=>(
          <button key={k} className={`filter-tab ${filter===k?"active":""}`} onClick={()=>setFilter(k)}>{label}</button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="loading-state">Loading history...</div>
      ) : filtered.length===0 ? (
        <div className="empty-state">
          <BarChart2 size={32} color="#2a2f45"/>
          <span>No trades found</span>
          <small>Completed trades will appear here</small>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="trade-table">
            <thead>
              <tr>
                <th>Symbol</th><th>Entry</th><th>Exit</th>
                <th>Qty</th><th>P&L (USDT)</th><th>P&L %</th>
                <th>Close Reason</th><th>AI Conf.</th><th>Time</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t=>{
                const isWin = (t.pnl||0)>0;
                const reasonCls = {TAKE_PROFIT:"reason-tp",STOP_LOSS:"reason-sl",SIGNAL:"reason-signal",MANUAL:"reason-manual",MANUAL_CLOSE:"reason-manual"};
                return (
                  <tr key={t.id} className={isWin?"row-win":"row-loss"}>
                    <td><span className="symbol-tag">{t.symbol}</span></td>
                    <td>${Number(t.entry_price).toLocaleString()}</td>
                    <td>${Number(t.exit_price||0).toLocaleString()}</td>
                    <td>{t.quantity}</td>
                    <td className={isWin?"pnl-pos":"pnl-neg"}>{isWin?"+":""}{Number(t.pnl||0).toFixed(4)}</td>
                    <td className={isWin?"pnl-pos":"pnl-neg"}>{isWin?"+":""}{Number(t.pnl_percent||0).toFixed(2)}%</td>
                    <td><span className={`reason-tag ${reasonCls[t.close_reason]||""}`}>{t.close_reason||"—"}</span></td>
                    <td>
                      <div className="confidence-bar">
                        <div className="confidence-fill" style={{width:`${t.confidence||0}%`}}/>
                        <span className="confidence-text">{t.confidence||0}%</span>
                      </div>
                    </td>
                    <td className="time-col">{t.exit_time?new Date(t.exit_time).toLocaleString():"—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
