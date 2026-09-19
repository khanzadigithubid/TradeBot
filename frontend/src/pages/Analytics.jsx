import { useEffect, useState, useRef } from "react";
import { createChart, LineSeries, HistogramSeries } from "lightweight-charts";
import {
  TrendingUp, TrendingDown, BarChart2, Percent,
  DollarSign, Award, AlertTriangle, Zap
} from "lucide-react";
import { getAnalytics, getTradeStats } from "../services/api";

// ── Mini chart component ───────────────────────────────────────────────────────
function MiniLineChart({ data, color = "#26a69a", height = 120, isHistogram = false }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !data || data.length === 0) return;

    const chart = createChart(ref.current, {
      layout: { background: { color: "transparent" }, textColor: "#787b86" },
      grid:   { vertLines: { color: "#1a2235" }, horzLines: { color: "#1a2235" } },
      rightPriceScale: { borderColor: "#1e2d45", scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { borderColor: "#1e2d45", timeVisible: false },
      crosshair: { mode: 1 },
      width:  ref.current.clientWidth,
      height,
    });

    let series;
    if (isHistogram) {
      series = chart.addSeries(HistogramSeries, {
        color,
        priceFormat: { type: "price", precision: 4 },
      });
    } else {
      series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceFormat: { type: "price", precision: 4 },
      });
    }

    const formatted = data
      .filter(d => d.time && d.value !== null && d.value !== undefined)
      .map(d => ({
        time:  Math.floor(new Date(d.time).getTime() / 1000),
        value: d.value,
        ...(isHistogram ? { color: d.value >= 0 ? "#26a69a" : "#ef5350" } : {}),
      }))
      .sort((a, b) => a.time - b.time);

    // Deduplicate times
    const seen = new Set();
    const deduped = formatted.filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; });

    if (deduped.length > 0) {
      series.setData(deduped);
      chart.timeScale().fitContent();
    }

    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, [data, color, height, isHistogram]);

  return <div ref={ref} style={{ width: "100%", height }} />;
}

// ── Bar chart (monthly) using simple CSS ──────────────────────────────────────
function MonthlyBars({ monthly }) {
  const entries = Object.entries(monthly).sort(([a], [b]) => a.localeCompare(b)).slice(-12);
  if (entries.length === 0) return <div className="empty-state" style={{ padding: 20 }}><span>No monthly data yet</span></div>;

  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.01);

  return (
    <div className="monthly-bars">
      {entries.map(([month, pnl]) => {
        const pct  = (Math.abs(pnl) / maxAbs) * 100;
        const pos  = pnl >= 0;
        return (
          <div key={month} className="monthly-bar-item">
            <div className="monthly-bar-track">
              <div
                className={`monthly-bar-fill ${pos ? "green-fill" : "red-fill"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="monthly-bar-label">
              <span className="monthly-month">{month}</span>
              <span className={pos ? "pnl-pos" : "pnl-neg"}>
                {pos ? "+" : ""}{pnl.toFixed(2)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Symbol breakdown table ─────────────────────────────────────────────────────
function SymbolTable({ bySymbol }) {
  const rows = Object.entries(bySymbol).sort(([, a], [, b]) => b.pnl - a.pnl);
  if (rows.length === 0) return <div className="empty-state" style={{ padding: 20 }}><span>No data yet</span></div>;

  return (
    <div className="table-wrapper">
      <table className="trade-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Wins</th>
            <th>Losses</th>
            <th>Win Rate</th>
            <th>Total P&L</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([sym, d]) => {
            const total  = d.wins + d.losses;
            const wr     = total > 0 ? ((d.wins / total) * 100).toFixed(1) : "0.0";
            const pos    = d.pnl >= 0;
            return (
              <tr key={sym}>
                <td><span className="symbol-tag">{sym}</span></td>
                <td style={{ color: "var(--green)", fontWeight: 700 }}>{d.wins}</td>
                <td style={{ color: "var(--red)",   fontWeight: 700 }}>{d.losses}</td>
                <td>
                  <div className="confidence-bar" style={{ minWidth: 80 }}>
                    <div className="confidence-fill" style={{ width: `${wr}%`, background: "rgba(38,166,154,0.5)" }} />
                    <span className="confidence-text">{wr}%</span>
                  </div>
                </td>
                <td className={pos ? "pnl-pos" : "pnl-neg"}>
                  {pos ? "+" : ""}{d.pnl.toFixed(4)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Analytics Page ────────────────────────────────────────────────────────
export default function Analytics() {
  const [data,    setData]    = useState(null);
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getAnalytics(), getTradeStats()])
      .then(([a, s]) => { setData(a); setStats(s); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page"><div className="loading-state">Loading analytics...</div></div>;

  const equityCurveData = (data?.equity_curve || []).map(e => ({ time: e.time, value: e.pnl }));
  const drawdownData    = (data?.drawdown_series || []).map(d => ({ time: d.time, value: d.drawdown }));
  const hasData         = equityCurveData.length > 0;

  return (
    <div className="page analytics-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-sub">Performance metrics & strategy analysis</p>
        </div>
      </div>

      {/* ── Key Metrics ── */}
      <div className="stats-grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
        <div className="stat-card blue">
          <div className="stat-icon-wrap"><Award size={22} /></div>
          <div>
            <div className="stat-title">Sharpe Ratio</div>
            <div className="stat-value">{data?.sharpe ?? "—"}</div>
            <div className="stat-sub">Risk-adjusted return</div>
          </div>
        </div>
        <div className={`stat-card ${(stats?.total_pnl || 0) >= 0 ? "green" : "red"}`}>
          <div className="stat-icon-wrap"><DollarSign size={22} /></div>
          <div>
            <div className="stat-title">Total P&L</div>
            <div className="stat-value">
              {stats ? `${(stats.total_pnl||0)>=0?"+":""}$${Number(stats.total_pnl||0).toFixed(4)}` : "—"}
            </div>
            <div className="stat-sub">{stats?.total_trades || 0} closed trades</div>
          </div>
        </div>
        <div className="stat-card purple">
          <div className="stat-icon-wrap"><Percent size={22} /></div>
          <div>
            <div className="stat-title">Win Rate</div>
            <div className="stat-value">{stats?.win_rate ?? "—"}%</div>
            <div className="stat-sub">{stats?.winning_trades || 0}W / {stats?.losing_trades || 0}L</div>
          </div>
        </div>
        <div className="stat-card red">
          <div className="stat-icon-wrap"><AlertTriangle size={22} /></div>
          <div>
            <div className="stat-title">Max Drawdown</div>
            <div className="stat-value">
              {drawdownData.length > 0
                ? `$${Math.abs(Math.min(...drawdownData.map(d => d.value))).toFixed(4)}`
                : "—"}
            </div>
            <div className="stat-sub">Peak-to-trough loss</div>
          </div>
        </div>
      </div>

      {/* ── Charts Row ── */}
      <div className="analytics-charts-row">

        {/* Cumulative P&L */}
        <div className="analytics-chart-card" style={{ flex: 2 }}>
          <div className="chart-header">
            <TrendingUp size={14} />
            <span className="chart-symbol" style={{ fontSize: 13 }}>Cumulative P&L</span>
          </div>
          {hasData
            ? <MiniLineChart data={equityCurveData} color="#26a69a" height={200} />
            : <div className="empty-state" style={{ height: 200 }}><BarChart2 size={28} color="#2a2f45" /><span>No data yet</span></div>
          }
        </div>

        {/* Drawdown */}
        <div className="analytics-chart-card" style={{ flex: 1 }}>
          <div className="chart-header">
            <TrendingDown size={14} />
            <span className="chart-symbol" style={{ fontSize: 13 }}>Drawdown</span>
          </div>
          {hasData
            ? <MiniLineChart data={drawdownData} color="#ef5350" height={200} isHistogram />
            : <div className="empty-state" style={{ height: 200 }}><span>No data yet</span></div>
          }
        </div>
      </div>

      {/* ── Bottom Row ── */}
      <div className="analytics-bottom-row">
        {/* Monthly */}
        <div className="analytics-chart-card" style={{ flex: 1 }}>
          <div className="chart-header">
            <Zap size={14} />
            <span className="chart-symbol" style={{ fontSize: 13 }}>Monthly P&L (last 12 months)</span>
          </div>
          <div style={{ padding: "12px 16px" }}>
            <MonthlyBars monthly={data?.monthly || {}} />
          </div>
        </div>

        {/* By Symbol */}
        <div className="analytics-chart-card" style={{ flex: 1 }}>
          <div className="chart-header">
            <BarChart2 size={14} />
            <span className="chart-symbol" style={{ fontSize: 13 }}>Performance by Symbol</span>
          </div>
          <div style={{ padding: "8px 0" }}>
            <SymbolTable bySymbol={data?.by_symbol || {}} />
          </div>
        </div>
      </div>
    </div>
  );
}
