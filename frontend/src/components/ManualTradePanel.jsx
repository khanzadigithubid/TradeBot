/**
 * ManualTradePanel — Dashboard pe manual BUY/SELL karne ka panel
 * Features:
 *  - Symbol select (follows the dashboard's current symbol)
 *  - Optional quantity override (blank = configured % of balance)
 *  - Confirm modal (accidental trade se bachao)
 *  - Live price dikhata hai before confirm
 *  - Success/error feedback
 */

import { useState, useEffect } from "react";
import { TrendingUp, TrendingDown, AlertTriangle, X, Zap } from "lucide-react";
import { manualTrade, getPrice, getSettings } from "../services/api";

const FALLBACK_PAIRS = [
  "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT",
  "XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT",
];

export default function ManualTradePanel({ currentSymbol, onTradeExecuted }) {
  const [symbol,      setSymbol]      = useState(currentSymbol || "BTCUSDT");
  const [side,        setSide]        = useState(null);      // "BUY" | "SELL"
  const [showConfirm, setShowConfirm] = useState(false);
  const [livePrice,   setLivePrice]   = useState(null);
  const [qtyInput,    setQtyInput]    = useState("");
  const [loading,     setLoading]     = useState(false);
  const [result,      setResult]      = useState(null);      // { type:"success"|"error", msg }
  const [pairs,       setPairs]       = useState(FALLBACK_PAIRS);
  const [isTestnet,   setIsTestnet]   = useState(null);      // null = unknown

  // Dashboard ka symbol change ho to panel bhi follow kare
  useEffect(() => {
    if (currentSymbol) setSymbol(currentSymbol);
  }, [currentSymbol]);

  // Backend se full supported pair list + trading mode laao.
  // `effective_testnet` is what the bot will ACTUALLY trade with: the stored
  // preference can be "live" while the server refused it. Showing "LIVE MODE"
  // then would be both wrong and dangerously reassuring.
  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then(s => {
        if (cancelled) return;
        if (Array.isArray(s?.supported_pairs) && s.supported_pairs.length) {
          setPairs(s.supported_pairs);
        }
        setIsTestnet(s?.effective_testnet ?? s?.testnet ?? true);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Confirm modal kholne se pehle live price fetch karo
  async function handleSideClick(s) {
    setSide(s);
    setResult(null);
    setLivePrice(null);
    setQtyInput("");
    setShowConfirm(true);
    try {
      const data = await getPrice(symbol);
      setLivePrice(data?.price ?? null);
    } catch (_) {}
  }

  // Symbol badalne pe price refresh
  useEffect(() => {
    if (!showConfirm) return;
    let cancelled = false;
    getPrice(symbol)
      .then(d => { if (!cancelled) setLivePrice(d?.price ?? null); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [symbol, showConfirm]);

  // Actual trade execute
  async function handleConfirm() {
    setLoading(true);
    setResult(null);
    try {
      const qty = parseFloat(qtyInput);
      const payload = { symbol, side };
      if (Number.isFinite(qty) && qty > 0) payload.quantity = qty;

      const res = await manualTrade(payload);
      setResult({
        type: "success",
        msg: side === "BUY"
          ? `✅ BUY placed — ${res.trade?.quantity} ${symbol.replace("USDT","")} @ $${Number(res.trade?.entry_price).toLocaleString()}`
          : `✅ SELL done — ${res.trades?.length ?? 1} trade(s) closed`,
      });
      if (onTradeExecuted) onTradeExecuted();
    } catch (e) {
      // Backend ka exact error message dikhao
      const msg = e.message || "Trade failed";
      setResult({
        type: "error",
        msg: `❌ ${msg}`,
      });
    }
    setLoading(false);
    setShowConfirm(false);
  }

  const parsedQty = parseFloat(qtyInput);
  const qtyValid  = qtyInput.trim() === "" || (Number.isFinite(parsedQty) && parsedQty > 0);
  const notional  = qtyValid && Number.isFinite(parsedQty) && livePrice
    ? parsedQty * livePrice
    : null;

  return (
    <>
      {/* ── Panel ── */}
      <div className="manual-panel">
        <div className="manual-panel-header">
          <Zap size={14} color="#f5a623" />
          <span>Manual Trade</span>
        </div>

        <div className="manual-panel-body">
          {/* Symbol select */}
          <div className="manual-symbol-wrap">
            <label className="manual-label">Symbol</label>
            <select
              className="pair-select manual-select"
              value={symbol}
              onChange={(e) => { setSymbol(e.target.value); setResult(null); }}
            >
              {pairs.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>

          {/* BUY / SELL buttons */}
          <div className="manual-btns">
            <button
              className="manual-btn manual-buy"
              onClick={() => handleSideClick("BUY")}
            >
              <TrendingUp size={14} />
              BUY
            </button>
            <button
              className="manual-btn manual-sell"
              onClick={() => handleSideClick("SELL")}
            >
              <TrendingDown size={14} />
              SELL
            </button>
          </div>
        </div>

        {/* Result feedback */}
        {result && (
          <div className={`manual-result ${result.type}`}>
            {result.msg}
          </div>
        )}

        <p className="manual-note">
          {isTestnet === false
            ? "🔴 LIVE MODE — real funds at risk. "
            : "🟡 Testnet — simulated. "}
          Blank quantity = configured % of balance &nbsp;|&nbsp; SL/TP auto-set
        </p>
      </div>

      {/* ── Confirm Modal ── */}
      {showConfirm && (
        <div className="modal-overlay" onClick={() => setShowConfirm(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>

            <div className="modal-header">
              <div className="modal-title">
                <AlertTriangle size={16} color="#f5a623" />
                Confirm {side}
              </div>
              <button className="modal-close" onClick={() => setShowConfirm(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-row">
                <span>Symbol</span>
                <strong>{symbol}</strong>
              </div>
              <div className="modal-row">
                <span>Side</span>
                <strong className={side === "BUY" ? "modal-buy" : "modal-sell"}>
                  {side}
                </strong>
              </div>
              <div className="modal-row">
                <span>Mode</span>
                <strong style={{ color: isTestnet ? "#26a69a" : "#ef5350" }}>
                  {isTestnet ? "TESTNET (simulated)" : "🔴 LIVE (real funds)"}
                </strong>
              </div>
              <div className="modal-row">
                <span>Current Price</span>
                <strong>
                  {livePrice ? `$${Number(livePrice).toLocaleString()}` : "Loading..."}
                </strong>
              </div>

              {side === "BUY" && (
                <div className="modal-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}>
                  <span>Quantity (optional)</span>
                  <input
                    type="number"
                    className="pair-select manual-select"
                    placeholder="Blank = configured % of balance"
                    min="0"
                    step="any"
                    value={qtyInput}
                    onChange={(e) => setQtyInput(e.target.value)}
                  />
                  <small style={{ color: "var(--text3)", fontSize: 11 }}>
                    {qtyInput.trim() === ""
                      ? "Leave blank to size the order from TRADE_QUANTITY_PERCENT."
                      : qtyValid && notional != null
                        ? `Order value ≈ $${notional.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                        : "Enter a positive number."}
                  </small>
                </div>
              )}

              <div className="modal-row">
                <span>{side === "BUY" ? "Trade Size" : "Action"}</span>
                <strong>
                  {side === "BUY" ? "Configured % of USDT balance" : "Close open positions"}
                </strong>
              </div>

              {side === "SELL" && (
                <div className="modal-warn">
                  ⚠️ This will close all open {symbol} positions.
                </div>
              )}

              {side === "BUY" && isTestnet === false && (
                <div className="modal-warn">
                  🔴 LIVE MODE — this sends a real market order to Binance.
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button
                className="modal-btn-cancel"
                onClick={() => setShowConfirm(false)}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                className={`modal-btn-confirm ${side === "BUY" ? "confirm-buy" : "confirm-sell"}`}
                onClick={handleConfirm}
                disabled={loading || !qtyValid}
              >
                {loading
                  ? <span className="spinner" />
                  : `Confirm ${side}`
                }
              </button>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
