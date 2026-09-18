import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import { getCandles } from "../services/api";

export default function PriceChart({ symbol = "BTCUSDT", interval = "15m", livePrice }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Create chart once on mount
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#111827" },
        textColor: "#7a8ba0",
      },
      grid: {
        vertLines: { color: "#1a2235" },
        horzLines: { color: "#1a2235" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#1e2d45" },
      timeScale: {
        borderColor: "#1e2d45",
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: 380,
    });

    // v5 API — addSeries with series type
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Load candles when symbol/interval changes
  useEffect(() => {
    if (!seriesRef.current) return;
    setLoading(true);
    setError(null);

    getCandles(symbol, interval, 150)
      .then((candles) => {
        if (!candles || candles.length === 0) {
          setError("No data available");
          return;
        }
        const seen = new Set();
        const data = candles
          .map((c) => ({
            time: Math.floor(new Date(c.timestamp).getTime() / 1000),
            open:  Number(c.open),
            high:  Number(c.high),
            low:   Number(c.low),
            close: Number(c.close),
          }))
          .filter((d) => {
            if (seen.has(d.time)) return false;
            seen.add(d.time);
            return true;
          })
          .sort((a, b) => a.time - b.time);

        if (seriesRef.current) {
          seriesRef.current.setData(data);
          chartRef.current?.timeScale().fitContent();
        }
      })
      .catch(() => setError("Could not load chart data"))
      .finally(() => setLoading(false));
  }, [symbol, interval]);

  // Live price tick update
  useEffect(() => {
    if (!seriesRef.current || !livePrice) return;
    try {
      const now = Math.floor(Date.now() / 1000);
      seriesRef.current.update({
        time: now,
        open:  livePrice,
        high:  livePrice,
        low:   livePrice,
        close: livePrice,
      });
    } catch (_) {}
  }, [livePrice]);

  return (
    <div className="chart-wrapper">
      <div className="chart-header">
        <span className="chart-symbol">{symbol}</span>
        <span className="chart-interval">{interval}</span>
        {livePrice && (
          <span className="chart-live-price">
            ${Number(livePrice).toLocaleString()}
          </span>
        )}
      </div>
      {loading && (
        <div className="chart-loading">Loading chart...</div>
      )}
      {error && (
        <div className="chart-error">{error}</div>
      )}
      <div
        ref={containerRef}
        className="chart-container"
        style={{ opacity: loading ? 0 : 1, transition: "opacity 0.3s" }}
      />
    </div>
  );
}
