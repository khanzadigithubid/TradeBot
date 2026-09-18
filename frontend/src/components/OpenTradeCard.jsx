import { X, TrendingUp, ShieldAlert, Target } from "lucide-react";
import { closeTrade } from "../services/api";

export default function OpenTradeCard({ trade, currentPrice, onClose }) {
  const entry = trade.entry_price;
  const price = currentPrice || entry;
  const pnl   = (price - entry) * trade.quantity;
  const pnlPct = ((price - entry) / entry) * 100;
  const isProfit = pnl >= 0;

  async function handleClose() {
    try {
      await closeTrade(trade.id);
      if (onClose) onClose();
    } catch (e) {
      alert("Could not close: " + e.message);
    }
  }

  return (
    <div className="trade-card">
      <div className="trade-card-header">
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <TrendingUp size={14} color="#26a69a" />
          <span className="trade-symbol">{trade.symbol}</span>
        </div>
        <span className="trade-side buy">LONG</span>
      </div>

      <div className="trade-card-body">
        <div className="trade-row"><span>Entry Price</span><span>${Number(entry).toLocaleString()}</span></div>
        <div className="trade-row"><span>Current Price</span><span>${Number(price).toLocaleString()}</span></div>
        <div className="trade-row"><span>Quantity</span><span>{trade.quantity}</span></div>
        <div className="trade-row">
          <span style={{display:"flex",alignItems:"center",gap:4}}>
            <ShieldAlert size={11} color="#ef5350" /> Stop Loss
          </span>
          <span className="sl">${trade.stop_loss || "—"}</span>
        </div>
        <div className="trade-row">
          <span style={{display:"flex",alignItems:"center",gap:4}}>
            <Target size={11} color="#26a69a" /> Take Profit
          </span>
          <span className="tp">${trade.take_profit || "—"}</span>
        </div>
        <div className={`trade-pnl ${isProfit ? "profit" : "loss"}`}>
          {isProfit ? "+" : ""}{pnl.toFixed(4)} USDT
          <span style={{ fontSize:11, marginLeft:6, opacity:0.8 }}>
            ({pnlPct.toFixed(2)}%)
          </span>
        </div>
      </div>

      <div className="trade-card-footer">
        <span className="trade-confidence">AI {trade.confidence}% conf.</span>
        <button className="btn-close-trade" onClick={handleClose}>
          <X size={11} strokeWidth={3} style={{marginRight:3}} />
          Close
        </button>
      </div>
    </div>
  );
}
