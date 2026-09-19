import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import { getCandles, getIndicators } from "../services/api";

/**
 * PriceChart v2
 * - Main candlestick panel with EMA fast/slow + Bollinger Bands overlaid
 * - RSI sub-panel (separate chart, synced time-scale)
 * - MACD sub-panel (histogram + signal line)
 * - Toggle buttons: EMA | BB | RSI | MACD
 */
export default function PriceChart({ symbol = "BTCUSDT", interval = "15m", livePrice }) {
  const mainRef  = useRef(null);
  const rsiRef   = useRef(null);
  const macdRef  = useRef(null);

  // Chart instances
  const mainChart  = useRef(null);
  const rsiChart   = useRef(null);
  const macdChart  = useRef(null);

  // Series refs
  const candleRef   = useRef(null);
  const emaFastRef  = useRef(null);
  const emaSlowRef  = useRef(null);
  const bbUpperRef  = useRef(null);
  const bbMidRef    = useRef(null);
  const bbLowerRef  = useRef(null);
  const rsiSerRef   = useRef(null);
  const macdLineRef = useRef(null);
  const macdSigRef  = useRef(null);
  const macdHistRef = useRef(null);

  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [showEma,   setShowEma]   = useState(true);
  const [showBB,    setShowBB]    = useState(false);
  const [showRsi,   setShowRsi]   = useState(true);
  const [showMacd,  setShowMacd]  = useState(true);

  // ── Chart factory ──────────────────────────────────────────────────────────
  const makeChart = useCallback((container, height, opts = {}) => {
    return createChart(container, {
      layout: {
        background: { color: "#111827" },
        textColor:  "#7a8ba0",
      },
      grid: {
        vertLines: { color: "#1a2235" },
        horzLines: { color: "#1a2235" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#1e2d45", ...opts.priceScale },
      timeScale: {
        borderColor:    "#1e2d45",
        timeVisible:    true,
        secondsVisible: false,
        ...opts.timeScale,
      },
      width:  container.clientWidth,
      height,
    });
  }, []);

  // ── Build all charts on mount ──────────────────────────────────────────────
  useEffect(() => {
    if (!mainRef.current) return;

    // Main chart
    const mc = makeChart(mainRef.current, 320);
    mainChart.current = mc;
    candleRef.current = mc.addSeries(CandlestickSeries, {
      upColor:        "#22c55e",
      downColor:      "#ef4444",
      borderUpColor:  "#22c55e",
      borderDownColor:"#ef4444",
      wickUpColor:    "#22c55e",
      wickDownColor:  "#ef4444",
    });
    emaFastRef.current = mc.addSeries(LineSeries, { color: "#f5a623", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    emaSlowRef.current = mc.addSeries(LineSeries, { color: "#9c27b0", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    bbUpperRef.current = mc.addSeries(LineSeries, { color: "rgba(41,98,255,0.4)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    bbMidRef.current   = mc.addSeries(LineSeries, { color: "rgba(41,98,255,0.2)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    bbLowerRef.current = mc.addSeries(LineSeries, { color: "rgba(41,98,255,0.4)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });

    // RSI chart
    if (rsiRef.current) {
      const rc = makeChart(rsiRef.current, 90, {
        priceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
        timeScale:  { visible: false },
      });
      rsiChart.current = rc;
      rsiSerRef.current = rc.addSeries(LineSeries, { color: "#4c8dff", lineWidth: 2, priceLineVisible: false });
    }

    // MACD chart
    if (macdRef.current) {
      const xc = makeChart(macdRef.current, 90, {
        priceScale: { scaleMargins: { top: 0.2, bottom: 0.2 } },
        timeScale:  { visible: false },
      });
      macdChart.current = xc;
      macdHistRef.current = xc.addSeries(HistogramSeries, { priceLineVisible: false });
      macdLineRef.current = xc.addSeries(LineSeries, { color: "#4c8dff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      macdSigRef.current  = xc.addSeries(LineSeries, { color: "#f5a623", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    }

    // Sync crosshairs
    const syncCrosshair = (srcChart, targets) => {
      srcChart.subscribeCrosshairMove(({ time }) => {
        targets.forEach(t => {
          if (t && time !== undefined) t.setCrosshairPosition(0, time, t.series);
        });
      });
    };
    // (lightweight-charts v5 doesn't expose setCrosshairPosition on chart directly;
    //  time-scale sync is handled by shared time data)

    // ResizeObserver
    const ro = new ResizeObserver(() => {
      [
        [mainRef,  mc],
        [rsiRef,   rsiChart.current],
        [macdRef,  macdChart.current],
      ].forEach(([ref, chart]) => {
        if (ref.current && chart) {
          chart.applyOptions({ width: ref.current.clientWidth });
        }
      });
    });
    ro.observe(mainRef.current);

    return () => {
      ro.disconnect();
      mc.remove();
      rsiChart.current?.remove();
      macdChart.current?.remove();
      mainChart.current  = null;
      rsiChart.current   = null;
      macdChart.current  = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Serialize a series array → [{time, value}] ────────────────────────────
  const toSeries = (times, values) =>
    times
      .map((t, i) => ({ time: Math.floor(new Date(t).getTime() / 1000), value: values[i] }))
      .filter(d => d.value !== null && d.value !== undefined && !isNaN(d.value));

  const dedup = arr => {
    const seen = new Set();
    return arr.filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; });
  };

  // ── Load candles + indicators when symbol/interval changes ────────────────
  useEffect(() => {
    if (!candleRef.current) return;
    setLoading(true);
    setError(null);

    Promise.all([
      getCandles(symbol, interval, 200),
      getIndicators(symbol, interval, 200),
    ])
      .then(([candles, ind]) => {
        if (!candles?.length) { setError("No data"); return; }

        // Candlestick data
        const seen = new Set();
        const cData = candles
          .map(c => ({
            time:  Math.floor(new Date(c.timestamp).getTime() / 1000),
            open:  Number(c.open),
            high:  Number(c.high),
            low:   Number(c.low),
            close: Number(c.close),
          }))
          .filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; })
          .sort((a, b) => a.time - b.time);

        candleRef.current?.setData(cData);
        mainChart.current?.timeScale().fitContent();

        // Indicator overlays
        if (ind && ind.times) {
          const t = ind.times;
          emaFastRef.current?.setData(dedup(toSeries(t, ind.ema_fast).sort((a,b)=>a.time-b.time)));
          emaSlowRef.current?.setData(dedup(toSeries(t, ind.ema_slow).sort((a,b)=>a.time-b.time)));
          bbUpperRef.current?.setData(dedup(toSeries(t, ind.bb_upper).sort((a,b)=>a.time-b.time)));
          bbMidRef.current?.setData(dedup(toSeries(t, ind.bb_middle).sort((a,b)=>a.time-b.time)));
          bbLowerRef.current?.setData(dedup(toSeries(t, ind.bb_lower).sort((a,b)=>a.time-b.time)));

          rsiSerRef.current?.setData(
            dedup(toSeries(t, ind.rsi).sort((a,b)=>a.time-b.time))
          );

          macdHistRef.current?.setData(
            dedup(
              toSeries(t, ind.macd_hist)
                .map(d => ({ ...d, color: d.value >= 0 ? "#26a69a" : "#ef5350" }))
                .sort((a,b)=>a.time-b.time)
            )
          );
          macdLineRef.current?.setData(dedup(toSeries(t, ind.macd).sort((a,b)=>a.time-b.time)));
          macdSigRef.current?.setData(dedup(toSeries(t, ind.macd_signal).sort((a,b)=>a.time-b.time)));

          rsiChart.current?.timeScale().fitContent();
          macdChart.current?.timeScale().fitContent();
        }
      })
      .catch(() => setError("Could not load chart data"))
      .finally(() => setLoading(false));
  }, [symbol, interval]);

  // ── Live price tick ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!candleRef.current || !livePrice) return;
    try {
      const now = Math.floor(Date.now() / 1000);
      candleRef.current.update({
        time: now, open: livePrice, high: livePrice,
        low: livePrice, close: livePrice,
      });
    } catch (_) {}
  }, [livePrice]);

  // ── Visibility toggles ─────────────────────────────────────────────────────
  useEffect(() => {
    emaFastRef.current?.applyOptions({ visible: showEma });
    emaSlowRef.current?.applyOptions({ visible: showEma });
  }, [showEma]);

  useEffect(() => {
    bbUpperRef.current?.applyOptions({ visible: showBB });
    bbMidRef.current?.applyOptions({ visible: showBB });
    bbLowerRef.current?.applyOptions({ visible: showBB });
  }, [showBB]);

  return (
    <div className="chart-wrapper">
      {/* Header */}
      <div className="chart-header">
        <span className="chart-symbol">{symbol}</span>
        <span className="chart-interval">{interval}</span>
        {livePrice && (
          <span className="chart-live-price">${Number(livePrice).toLocaleString()}</span>
        )}
        {/* Toggle buttons */}
        <div className="chart-toggles">
          <button className={`chart-toggle-btn ${showEma ? "active" : ""}`} onClick={() => setShowEma(v => !v)}>EMA</button>
          <button className={`chart-toggle-btn ${showBB  ? "active" : ""}`} onClick={() => setShowBB(v  => !v)}>BB</button>
          <button className={`chart-toggle-btn ${showRsi  ? "active" : ""}`} onClick={() => setShowRsi(v => !v)}>RSI</button>
          <button className={`chart-toggle-btn ${showMacd ? "active" : ""}`} onClick={() => setShowMacd(v => !v)}>MACD</button>
        </div>
      </div>

      {loading && <div className="chart-loading">Loading chart...</div>}
      {error   && <div className="chart-error">{error}</div>}

      {/* Main candlestick */}
      <div
        ref={mainRef}
        className="chart-container"
        style={{ opacity: loading ? 0 : 1, transition: "opacity 0.3s" }}
      />

      {/* RSI panel */}
      {showRsi && (
        <div className="chart-sub-panel">
          <div className="chart-sub-label">
            RSI
            <span className="chart-sub-levels">
              <span style={{ color: "#ef5350" }}>─ 70</span>
              <span style={{ color: "#26a69a" }}>─ 30</span>
            </span>
          </div>
          <div ref={rsiRef} style={{ width: "100%", height: 90 }} />
        </div>
      )}

      {/* MACD panel */}
      {showMacd && (
        <div className="chart-sub-panel">
          <div className="chart-sub-label">
            MACD
            <span className="chart-sub-levels">
              <span style={{ color: "#4c8dff" }}>─ Line</span>
              <span style={{ color: "#f5a623" }}>─ Signal</span>
            </span>
          </div>
          <div ref={macdRef} style={{ width: "100%", height: 90 }} />
        </div>
      )}
    </div>
  );
}
