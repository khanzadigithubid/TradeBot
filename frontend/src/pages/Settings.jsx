import { useEffect, useState } from "react";
import { Shield, BarChart2, Bot, Save } from "lucide-react";
import { getSettings, updateSettings } from "../services/api";

export default function Settings() {
  const [form, setForm] = useState({
    testnet: false,
    symbol: "BTCUSDT",
    interval: "15m",
    trade_quantity_percent: 10,
    max_open_trades: 3,
    stop_loss_percent: 2.0,
    take_profit_percent: 4.0,
    ema_fast: 9,
    ema_slow: 21,
    rsi_period: 14,
    rsi_overbought: 70,
    rsi_oversold: 30,
  });

  const [pairs,     setPairs]     = useState([]);
  const [intervals, setIntervals] = useState([]);
  const [saving,    setSaving]    = useState(false);
  const [saveMsg,   setSaveMsg]   = useState(null);

  useEffect(() => {
    getSettings().then((d) => {
      setForm(f => ({
        ...f,
        testnet:                d.testnet                ?? false,
        symbol:                 d.symbol                 ?? "BTCUSDT",
        interval:               d.interval               ?? "15m",
        trade_quantity_percent: d.trade_quantity_percent ?? 10,
        max_open_trades:        d.max_open_trades        ?? 3,
        stop_loss_percent:      d.stop_loss_percent      ?? 2.0,
        take_profit_percent:    d.take_profit_percent    ?? 4.0,
        ema_fast:               d.ema_fast               ?? 9,
        ema_slow:               d.ema_slow               ?? 21,
        rsi_period:             d.rsi_period             ?? 14,
        rsi_overbought:         d.rsi_overbought         ?? 70,
        rsi_oversold:           d.rsi_oversold           ?? 30,
      }));
      setPairs(d.supported_pairs     || []);
      setIntervals(d.supported_intervals || []);
    }).catch(() => {});
  }, []);

  function handleChange(e) {
    const { name, value, type, checked } = e.target;
    setForm(f => ({
      ...f,
      [name]: type === "checkbox" ? checked
            : type === "number"   ? parseFloat(value)
            : value,
    }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    try {
      await updateSettings(form);
      setSaveMsg({ type: "success", text: "Settings saved — bot updated!" });
    } catch (err) {
      setSaveMsg({ type: "error", text: err.message });
    }
    setSaving(false);
    setTimeout(() => setSaveMsg(null), 3000);
  }

  return (
    <div className="page settings-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub">Bot configuration — changes apply instantly</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="settings-form">

        {/* Trading Settings */}
        <div className="settings-card">
          <div className="settings-section-title">
            <BarChart2 size={15} /> Trading Settings
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Trading Pair</label>
              <select name="symbol" value={form.symbol} onChange={handleChange} className="form-select">
                {pairs.map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Candle Interval</label>
              <select name="interval" value={form.interval} onChange={handleChange} className="form-select">
                {intervals.map(i => <option key={i}>{i}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Trade Size (% of balance)</label>
              <input type="number" name="trade_quantity_percent"
                value={form.trade_quantity_percent} onChange={handleChange}
                min="1" max="100" step="1" className="form-input" />
              <small>10 = Use 10% of USDT balance per trade</small>
            </div>
            <div className="form-group">
              <label>Max Open Trades</label>
              <input type="number" name="max_open_trades"
                value={form.max_open_trades} onChange={handleChange}
                min="1" max="10" step="1" className="form-input" />
            </div>
          </div>
        </div>

        {/* Risk Management */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Shield size={15} /> Risk Management
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Stop Loss %</label>
              <input type="number" name="stop_loss_percent"
                value={form.stop_loss_percent} onChange={handleChange}
                min="0.5" max="20" step="0.1" className="form-input" />
              <small>Auto-close position on this % loss</small>
            </div>
            <div className="form-group">
              <label>Take Profit %</label>
              <input type="number" name="take_profit_percent"
                value={form.take_profit_percent} onChange={handleChange}
                min="0.5" max="50" step="0.1" className="form-input" />
              <small>Auto-close position on this % profit</small>
            </div>
          </div>
        </div>

        {/* AI Indicators */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Bot size={15} /> AI Indicator Settings
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>EMA Fast</label>
              <input type="number" name="ema_fast" value={form.ema_fast}
                onChange={handleChange} min="3" max="50" className="form-input" />
            </div>
            <div className="form-group">
              <label>EMA Slow</label>
              <input type="number" name="ema_slow" value={form.ema_slow}
                onChange={handleChange} min="5" max="200" className="form-input" />
            </div>
            <div className="form-group">
              <label>RSI Period</label>
              <input type="number" name="rsi_period" value={form.rsi_period}
                onChange={handleChange} min="5" max="50" className="form-input" />
            </div>
            <div className="form-group">
              <label>RSI Overbought</label>
              <input type="number" name="rsi_overbought" value={form.rsi_overbought}
                onChange={handleChange} min="60" max="90" className="form-input" />
            </div>
            <div className="form-group">
              <label>RSI Oversold</label>
              <input type="number" name="rsi_oversold" value={form.rsi_oversold}
                onChange={handleChange} min="10" max="40" className="form-input" />
            </div>
          </div>
        </div>

        {/* Save */}
        <div className="settings-footer">
          {saveMsg && (
            <div className={`save-msg ${saveMsg.type}`}>{saveMsg.text}</div>
          )}
          <button type="submit" className="btn-save" disabled={saving}>
            <Save size={14} /> {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>

      </form>
    </div>
  );
}
