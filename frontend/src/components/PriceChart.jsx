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

  // ── Main chart lifecycle (created once) ────────────────────────────────────
  useEffect(() => {
    if (!mainRef.current) return;

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

    // ResizeObserver for the main panel
    const ro = new ResizeObserver(() => {
      if (mainRef.current && mainChart.current) {
        mainChart.current.applyOptions({ width: mainRef.current.clientWidth });
      }
    });
    ro.observe(mainRef.current);

    return () => {
      ro.disconnect();
      mc.remove();
      mainChart.current = null;
      candleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── RSI sub-chart lifecycle (follows the showRsi toggle) ──────────────────
  // Previously both sub-charts were built once on mount, so hiding a panel
  // unmounted its container and re-showing it left a blank box with no chart.
  useEffect(() => {
    if (!showRsi || !rsiRef.current) {
      rsiChart.current?.remove();
      rsiChart.current = null;
      rsiSerRef.current = null;
      return;
    }
    const rc = makeChart(rsiRef.current, 90, {
      priceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale:  { visible: false },
    });
    rsiChart.current = rc;
    rsiSerRef.current = rc.addSeries(LineSeries, { color: "#4c8dff", lineWidth: 2, priceLineVisible: false });

    const ro = new ResizeObserver(() => {
      if (rsiRef.current && rsiChart.current) {
        rsiChart.current.applyOptions({ width: rsiRef.current.clientWidth });
      }
    });
    ro.observe(rsiRef.current);

    return () => {
      ro.disconnect();
      rsiChart.current?.remove();
      rsiChart.current = null;
      rsiSerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showRsi]);

  // ── MACD sub-chart lifecycle (follows the showMacd toggle) ────────────────
  useEffect(() => {
    if (!showMacd || !macdRef.current) {
      macdChart.current?.remove();
      macdChart.current = null;
      macdHistRef.current = null;
      macdLineRef.current = null;
      macdSigRef.current = null;
      return;
    }
    const xc = makeChart(macdRef.current, 90, {
      priceScale: { scaleMargins: { top: 0.2, bottom: 0.2 } },
      timeScale:  { visible: false },
    });
    macdChart.current = xc;
    macdHistRef.current = xc.addSeries(HistogramSeries, { priceLineVisible: false });
    macdLineRef.current = xc.addSeries(LineSeries, { color: "#4c8dff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    macdSigRef.current  = xc.addSeries(LineSeries, { color: "#f5a623", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });

    const ro = new ResizeObserver(() => {
      if (macdRef.current && macdChart.current) {
        macdChart.current.applyOptions({ width: macdRef.current.clientWidth });
      }
    });
    ro.observe(macdRef.current);

    return () => {
      ro.disconnect();
      macdChart.current?.remove();
      macdChart.current = null;
      macdHistRef.current = null;
      macdLineRef.current = null;
      macdSigRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showMacd]);

  // ── Timestamp parser — handles both ISO with/without timezone ───────────
  const parseTs = (ts) => {
    if (!ts) return 0;
    const s = String(ts);
    // Agar Z ya +/- timezone nahi hai to UTC mano
    const normalized = s.includes("Z") || s.match(/[+-]\d{2}:\d{2}$/)
      ? s
      : s + "Z";
    const ms = new Date(normalized).getTime();
    return isNaN(ms) ? 0 : Math.floor(ms / 1000);
  };

  // ── Serialize a series array → [{time, value}] ────────────────────────────
  const toSeries = (times, values) =>
    times
      .map((t, i) => ({ time: parseTs(t), value: values[i] }))
      .filter(d => d.time > 0 && d.value !== null && d.value !== undefined && !isNaN(d.value));

  const dedup = arr => {
    const seen = new Set();
    return arr.filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; });
  };

  // Cached indicator payload — lets a recreated sub-chart be refilled on toggle
  const indDataRef = useRef(null);

  // ── Push indicator series into whichever charts currently exist ───────────
  const applyIndicators = (ind) => {
    if (!ind || !ind.times) return;
    const t = ind.times;
    const asc = a => a.sort((x, y) => x.time - y.time);

    emaFastRef.current?.setData(dedup(asc(toSeries(t, ind.ema_fast))));
    emaSlowRef.current?.setData(dedup(asc(toSeries(t, ind.ema_slow))));
    bbUpperRef.current?.setData(dedup(asc(toSeries(t, ind.bb_upper))));
    bbMidRef.current?.setData(dedup(asc(toSeries(t, ind.bb_middle))));
    bbLowerRef.current?.setData(dedup(asc(toSeries(t, ind.bb_lower))));

    rsiSerRef.current?.setData(dedup(asc(toSeries(t, ind.rsi))));

    macdHistRef.current?.setData(
      dedup(asc(toSeries(t, ind.macd_hist)).map(d => ({
        ...d, color: d.value >= 0 ? "#26a69a" : "#ef5350",
      })))
    );
    macdLineRef.current?.setData(dedup(asc(toSeries(t, ind.macd))));
    macdSigRef.current?.setData(dedup(asc(toSeries(t, ind.macd_signal))));

    rsiChart.current?.timeScale().fitContent();
    macdChart.current?.timeScale().fitContent();
  };

  // ── Load candles + indicators when symbol/interval changes ────────────────
  useEffect(() => {
    if (!candleRef.current) return;
    setLoading(true);
    setError(null);

    Promise.all([
      getCandles(symbol, interval, 200),
      getIndicators(symbol, interval, 200).catch(() => null),  // Forex pe fail ho to null
    ])
      .then(([candles, ind]) => {
        if (!candles?.length) { setError("No data"); return; }

        // Candlestick data
        const seen = new Set();
        const cData = candles
          .map(c => ({
            time:  parseTs(c.timestamp),
            open:  Number(c.open),
            high:  Number(c.high),
            low:   Number(c.low),
            close: Number(c.close),
          }))
          .filter(d => { if (!d.time || seen.has(d.time)) return false; seen.add(d.time); return true; })
          .sort((a, b) => a.time - b.time);

        candleRef.current?.setData(cData);
        mainChart.current?.timeScale().fitContent();

        // Keep indicator payload so recreated sub-charts can be repopulated
        indDataRef.current = ind;
        applyIndicators(ind);
      })
      .catch(() => setError("Could not load chart data"))
      .finally(() => setLoading(false));
  }, [symbol, interval]);

  // ── Repopulate sub-charts after a toggle recreates them ───────────────────
  useEffect(() => {
    applyIndicators(indDataRef.current);
  }, [showRsi, showMacd]);

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
