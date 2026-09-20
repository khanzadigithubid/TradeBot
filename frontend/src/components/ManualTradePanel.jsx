/**
 * ManualTradePanel — Dashboard pe manual BUY/SELL karne ka panel
 * Features:
 *  - Symbol aur side (BUY/SELL) select
 *  - Confirm modal (accidental trade se bachao)
 *  - Live price dikhata hai before confirm
 *  - Success/error feedback
 */

import { useState } from "react";
import { TrendingUp, TrendingDown, AlertTriangle, X, Zap } from "lucide-react";
import { manualTrade, getPrice } from "../services/api";

const PAIRS = [
  "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT",
  "XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT",
];

export default function ManualTradePanel({ currentSymbol, onTradeExecuted }) {
  const [symbol,      setSymbol]      = useState(currentSymbol || "BTCUSDT");
  const [side,        setSide]        = useState(null);      // "BUY" | "SELL"
  const [showConfirm, setShowConfirm] = useState(false);
  const [livePrice,   setLivePrice]   = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [result,      setResult]      = useState(null);      // { type:"success"|"error", msg }

  // Confirm modal kholne se pehle live price fetch karo
  async function handleSideClick(s) {
    setSide(s);
    setResult(null);
    setLivePrice(null);
    setShowConfirm(true);
    try {
      const data = await getPrice(symbol);
      setLivePrice(data?.price ?? null);
    } catch (_) {}
  }

  // Actual trade execute
  async function handleConfirm() {
    setLoading(true);
    setResult(null);
    try {
      const res = await manualTrade({ symbol, side });
      setResult({
        type: "success",
        msg: side === "BUY"
          ? `✅ BUY placed — ${res.trade?.quantity} ${symbol.replace("USDT","")} @ $${res.trade?.entry_price}`
          : `✅ SELL done — ${res.trades?.length ?? 1} trade(s) closed`,
      });
      if (onTradeExecuted) onTradeExecuted();
    } catch (e) {
      setResult({ type: "error", msg: `❌ ${e.message}` });
    }
    setLoading(false);
    setShowConfirm(false);
  }

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
              {PAIRS.map((p) => <option key={p}>{p}</option>)}
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
          * Trade size = configured % of balance &nbsp;|&nbsp; SL/TP auto-set by AI
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
                <span>Current Price</span>
                <strong>
                  {livePrice ? `$${Number(livePrice).toLocaleString()}` : "Loading..."}
                </strong>
              </div>
              <div className="modal-row">
                <span>Trade Size</span>
                <strong>Configured % of USDT balance</strong>
              </div>

              {side === "SELL" && (
                <div className="modal-warn">
                  ⚠️ This will close all open {symbol} positions.
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
                disabled={loading}
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
