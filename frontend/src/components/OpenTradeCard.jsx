import { X, TrendingUp, ShieldAlert, Target, Clock } from "lucide-react";
import { closeTrade } from "../services/api";

export default function OpenTradeCard({ trade, currentPrice, onClose }) {
  const entry = trade.entry_price;
  // Without a price for THIS trade's symbol we must not invent one — showing
  // the entry price back would read as a flat 0.00 position.
  const hasPrice = Number.isFinite(currentPrice) && currentPrice > 0;
  const price    = hasPrice ? currentPrice : entry;
  const pnl      = (price - entry) * trade.quantity;
  const pnlPct   = ((price - entry) / entry) * 100;
  const isProfit = pnl >= 0;

  async function handleClose() {
    try {
      await closeTrade(trade.id);
      if (onClose) onClose();
    } catch (e) {
      alert("Could not close: " + e.message);
    }
  }

  // Progress bar for price between SL and TP
  const sl  = trade.stop_loss;
  const tp  = trade.take_profit;
  let progress = 50;
  if (sl && tp && tp !== sl) {
    progress = Math.max(0, Math.min(100, ((price - sl) / (tp - sl)) * 100));
  }

  return (
    <div className={`trade-card ${isProfit ? "tc-profit" : "tc-loss"}`}>

      {/* Header */}
      <div className="trade-card-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <TrendingUp size={13} color="var(--green)" />
          <span className="trade-symbol">{trade.symbol}</span>
          <span className="trade-side buy">LONG</span>
          <span
            className="trade-venue"
            title={
              trade.simulated
                ? "Paper trade — no order was sent to the exchange"
                : "Order placed on the exchange"
            }
          >
            {trade.simulated ? "PAPER" : "LIVE ORDER"}
          </span>
        </div>
        <div className={`tc-pnl-badge ${hasPrice ? (isProfit ? "tc-pnl-pos" : "tc-pnl-neg") : ""}`}>
          {hasPrice ? `${isProfit ? "+" : ""}${pnl.toFixed(4)}` : "—"}
        </div>
      </div>

      {/* Body */}
      <div className="trade-card-body">
        <div className="trade-row">
          <span>Entry</span>
          <span>${Number(entry).toLocaleString()}</span>
        </div>
        <div className="trade-row">
          <span>Current</span>
          <span style={{ color: hasPrice ? (isProfit ? "var(--green)" : "var(--red)") : "var(--text3)", fontWeight: 700 }}>
            {hasPrice ? `$${Number(price).toLocaleString()}` : "Waiting for price…"}
          </span>
        </div>
        <div className="trade-row">
          <span>Qty</span>
          <span>{trade.quantity}</span>
        </div>

        {/* SL/TP progress bar */}
        {sl && tp && (
          <div className="tc-progress-wrap">
            <div className="tc-progress-labels">
              <span className="sl" style={{ fontSize: 10 }}>
                <ShieldAlert size={9} /> {sl}
              </span>
              <span className="tp" style={{ fontSize: 10 }}>
                {tp} <Target size={9} />
              </span>
            </div>
            <div className="tc-progress-track">
              <div
                className="tc-progress-fill"
                style={{
                  width: `${progress}%`,
                  background: isProfit ? "var(--grad-green)" : "var(--grad-red)",
                }}
              />
              <div className="tc-progress-dot" style={{ left: `${progress}%` }} />
            </div>
          </div>
        )}

        <div className={`trade-pnl ${hasPrice ? (isProfit ? "profit" : "loss") : ""}`}>
          {hasPrice ? (
            <>
              {isProfit ? "+" : ""}{pnl.toFixed(4)} USDT
              <span style={{ fontSize: 11, marginLeft: 6, opacity: 0.8 }}>
                ({pnlPct.toFixed(2)}%)
              </span>
            </>
          ) : (
            <span style={{ opacity: 0.7 }}>Unrealised P&amp;L unavailable</span>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="trade-card-footer">
        <span className="trade-confidence">
          <Clock size={10} style={{ marginRight: 3 }} />
          AI {trade.confidence}%
        </span>
        <button className="btn-close-trade" onClick={handleClose}>
          <X size={10} strokeWidth={3} /> Close
        </button>
      </div>
    </div>
  );
}
