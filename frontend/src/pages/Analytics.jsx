import { useEffect, useState, useRef } from "react";
import { createChart, LineSeries, HistogramSeries } from "lightweight-charts";
import {
  TrendingUp, TrendingDown, BarChart2, Percent,
  DollarSign, Award, AlertTriangle, Zap, Activity
} from "lucide-react";
import { getAnalytics, getTradeStats } from "../services/api";

/* ── Mini Chart ─────────────────────────────────────────────────────────────── */
function MiniLineChart({ data, color = "#00c896", height = 140, isHistogram = false }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !data?.length) return;

    const chart = createChart(ref.current, {
      layout: { background: { color: "transparent" }, textColor: "#5a6a8a" },
      grid:   { vertLines: { color: "#1e2740" }, horzLines: { color: "#1e2740" } },
      rightPriceScale: { borderColor: "#1e2740", scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { borderColor: "#1e2740", timeVisible: false },
      crosshair: { mode: 1 },
      width:  ref.current.clientWidth,
      height,
    });

    const series = isHistogram
      ? chart.addSeries(HistogramSeries, { color, priceFormat: { type:"price", precision:4 } })
      : chart.addSeries(LineSeries, {
          color, lineWidth: 2,
          priceFormat: { type:"price", precision:4 },
          crosshairMarkerRadius: 4,
          crosshairMarkerBackgroundColor: color,
        });

    const seen = new Set();
    const formatted = data
      .filter(d => d.time && d.value != null)
      .map(d => ({
        time:  Math.floor(new Date(d.time).getTime() / 1000),
        value: d.value,
        ...(isHistogram ? { color: d.value >= 0 ? "#00c896" : "#ff3b5c" } : {}),
      }))
      .sort((a, b) => a.time - b.time)
      .filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; });

    if (formatted.length > 0) {
      series.setData(formatted);
      chart.timeScale().fitContent();
    }

    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.remove(); };
  }, [data, color, height, isHistogram]);

  return <div ref={ref} style={{ width:"100%", height }} />;
}

/* ── Monthly Bars ───────────────────────────────────────────────────────────── */
function MonthlyBars({ monthly }) {
  const entries = Object.entries(monthly)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-12);

  if (!entries.length) return (
    <div className="empty-state" style={{ padding:24 }}>
      <span>No monthly data yet</span>
    </div>
  );

  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.01);

  return (
    <div className="monthly-bars" style={{ padding:"12px 16px" }}>
      {entries.map(([month, pnl]) => {
        const pct = (Math.abs(pnl) / maxAbs) * 100;
        const pos = pnl >= 0;
        return (
          <div key={month} className="monthly-bar-item">
            <div className="monthly-bar-track">
              <div
                className={`monthly-bar-fill ${pos ? "green-fill" : "red-fill"}`}
                style={{ width:`${pct}%` }}
              />
            </div>
            <div className="monthly-bar-label">
              <span className="monthly-month">{month}</span>
              <span className={pos ? "pnl-pos" : "pnl-neg"}>
                {pos?"+":""}{pnl.toFixed(2)} USDT
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Symbol Table ───────────────────────────────────────────────────────────── */
function SymbolTable({ bySymbol }) {
  const rows = Object.entries(bySymbol).sort(([, a], [, b]) => b.pnl - a.pnl);

  if (!rows.length) return (
    <div className="empty-state" style={{ padding:24 }}>
      <span>No symbol data yet</span>
    </div>
  );

  return (
    <div className="table-wrapper" style={{ border:"none", borderRadius:0 }}>
      <table className="trade-table">
        <thead>
          <tr>
            <th>Symbol</th><th>Wins</th><th>Losses</th>
            <th>Win Rate</th><th>Total P&L</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([sym, d]) => {
            const total = d.wins + d.losses;
            const wr    = total > 0 ? ((d.wins / total) * 100).toFixed(1) : "0.0";
            const pos   = d.pnl >= 0;
            return (
              <tr key={sym}>
                <td><span className="symbol-tag">{sym}</span></td>
                <td className="pnl-pos">{d.wins}</td>
                <td className="pnl-neg">{d.losses}</td>
                <td>
                  <div className="confidence-bar" style={{ minWidth:80 }}>
                    <div className="confidence-fill" style={{ width:`${wr}%`, background:"rgba(0,200,150,0.4)" }}/>
                    <span className="confidence-text">{wr}%</span>
                  </div>
                </td>
                <td className={pos?"pnl-pos":"pnl-neg"}>
                  {pos?"+":""}{d.pnl.toFixed(4)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Metric Card ─────────────────────────────────────────────────────────────  */
function MetricCard({ icon: Icon, title, value, sub, color = "blue" }) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="stat-icon-wrap"><Icon size={22} strokeWidth={1.8} /></div>
      <div>
        <div className="stat-title">{title}</div>
        <div className="stat-value">{value ?? "—"}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

/* ── Chart Card wrapper ───────────────────────────────────────────────────────  */
function ChartCard({ icon: Icon, title, children, flex = 1 }) {
  return (
    <div className="analytics-chart-card" style={{ flex }}>
      <div className="chart-header">
        <Icon size={14} color="var(--text-dim)" />
        <span className="chart-symbol" style={{ fontSize:13 }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────────────────── */
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

  if (loading) return (
    <div className="page">
      <div className="loading-state">Loading analytics...</div>
    </div>
  );

  const equityData  = (data?.equity_curve   || []).map(e => ({ time: e.time, value: e.pnl }));
  const drawdownData= (data?.drawdown_series || []).map(d => ({ time: d.time, value: d.drawdown }));
  const hasData     = equityData.length > 0;

  const pnlPos      = (stats?.total_pnl || 0) >= 0;
  const maxDD       = drawdownData.length > 0
    ? Math.abs(Math.min(...drawdownData.map(d => d.value))).toFixed(4)
    : "—";

  return (
    <div className="page analytics-page">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-sub">Performance metrics & strategy analysis</p>
        </div>
      </div>

      {/* ── Key Metrics ── */}
      <div className="analytics-metrics-grid">
        <MetricCard icon={Award}        title="Sharpe Ratio"
          value={data?.sharpe ?? "—"}
          sub="Risk-adjusted return"
          color="blue" />
        <MetricCard icon={DollarSign}   title="Total P&L"
          value={stats ? `${pnlPos?"+":""}$${Number(stats.total_pnl||0).toFixed(4)}` : "—"}
          sub={`${stats?.total_trades||0} closed trades`}
          color={pnlPos?"green":"red"} />
        <MetricCard icon={Percent}      title="Win Rate"
          value={`${stats?.win_rate ?? "—"}%`}
          sub={`${stats?.winning_trades||0}W / ${stats?.losing_trades||0}L`}
          color="purple" />
        <MetricCard icon={AlertTriangle}title="Max Drawdown"
          value={`$${maxDD}`}
          sub="Peak-to-trough loss"
          color="red" />
        <MetricCard icon={Activity}     title="Open Trades"
          value={stats?.open_trades ?? "—"}
          sub="Active now"
          color="orange" />
      </div>

      {/* ── Charts Row ── */}
      <div className="analytics-charts-row">
        <ChartCard icon={TrendingUp} title="Cumulative P&L" flex={2}>
          {hasData
            ? <MiniLineChart data={equityData} color="#00c896" height={200} />
            : <div className="empty-state" style={{height:200}}>
                <BarChart2 size={28} color="var(--border2)" />
                <span>No data yet</span>
              </div>
          }
        </ChartCard>

        <ChartCard icon={TrendingDown} title="Drawdown" flex={1}>
          {hasData
            ? <MiniLineChart data={drawdownData} color="#ff3b5c" height={200} isHistogram />
            : <div className="empty-state" style={{height:200}}>
                <span>No data yet</span>
              </div>
          }
        </ChartCard>
      </div>

      {/* ── Bottom Row ── */}
      <div className="analytics-bottom-row">
        <ChartCard icon={Zap} title="Monthly P&L (last 12 months)" flex={1}>
          <MonthlyBars monthly={data?.monthly || {}} />
        </ChartCard>

        <ChartCard icon={BarChart2} title="Performance by Symbol" flex={1}>
          <SymbolTable bySymbol={data?.by_symbol || {}} />
        </ChartCard>
      </div>

    </div>
  );
}
