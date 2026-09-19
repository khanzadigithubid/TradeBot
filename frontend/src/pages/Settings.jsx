import { useEffect, useState } from "react";
import { Shield, BarChart2, Bot, Save, Wifi, Layers, Eye, EyeOff, Mail, Bell } from "lucide-react";
import { getSettings, updateSettings, testConnection, testTelegram, testEmail } from "../services/api";

const PAIRS     = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","DOTUSDT","MATICUSDT"];
const INTERVALS = ["1m","5m","15m","30m","1h","4h","1d"];

export default function Settings() {
  const [form, setForm] = useState({
    // API
    api_key:    "",
    secret_key: "",
    testnet:    true,
    // Trading
    symbol:                 "BTCUSDT",
    interval:               "15m",
    trade_quantity_percent: 10,
    max_open_trades:        3,
    // Risk
    stop_loss_percent:      2.0,
    take_profit_percent:    4.0,
    trailing_stop:          true,
    trailing_stop_percent:  1.0,
    // AI
    ema_fast:       9,
    ema_slow:       21,
    rsi_period:     14,
    rsi_overbought: 70,
    rsi_oversold:   30,
    // Multi-symbol
    multi_symbol_mode: false,
    active_symbols:    ["BTCUSDT","ETHUSDT","BNBUSDT"],
    // Telegram
    telegram_bot_token: "",
    telegram_chat_id:   "",
    // Email
    email_sender:       "",
    email_app_password: "",
    email_receiver:     "",
  });

  const [showKey,      setShowKey]      = useState(false);
  const [showSecret,   setShowSecret]   = useState(false);
  const [showTgToken,  setShowTgToken]  = useState(false);
  const [showEmailPwd, setShowEmailPwd] = useState(false);

  const [connResult,  setConnResult]  = useState(null);
  const [tgResult,    setTgResult]    = useState(null);
  const [emailResult, setEmailResult] = useState(null);

  const [testingConn,  setTestingConn]  = useState(false);
  const [testingTg,    setTestingTg]    = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);

  const [saving,  setSaving]  = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);

  const [telegramOk, setTelegramOk] = useState(false);
  const [emailOk,    setEmailOk]    = useState(false);

  useEffect(() => {
    getSettings().then(d => {
      setForm(f => ({
        ...f,
        testnet:                d.testnet                ?? true,
        symbol:                 d.symbol                 ?? "BTCUSDT",
        interval:               d.interval               ?? "15m",
        trade_quantity_percent: d.trade_quantity_percent ?? 10,
        max_open_trades:        d.max_open_trades        ?? 3,
        stop_loss_percent:      d.stop_loss_percent      ?? 2.0,
        take_profit_percent:    d.take_profit_percent    ?? 4.0,
        trailing_stop:          d.trailing_stop          ?? true,
        trailing_stop_percent:  d.trailing_stop_percent  ?? 1.0,
        ema_fast:               d.ema_fast               ?? 9,
        ema_slow:               d.ema_slow               ?? 21,
        rsi_period:             d.rsi_period             ?? 14,
        rsi_overbought:         d.rsi_overbought         ?? 70,
        rsi_oversold:           d.rsi_oversold           ?? 30,
        multi_symbol_mode:      d.multi_symbol_mode      ?? false,
        active_symbols:         d.active_symbols         ?? ["BTCUSDT","ETHUSDT","BNBUSDT"],
      }));
      setTelegramOk(!!d.telegram_configured);
      setEmailOk(!!d.email_configured);
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

  function toggleSymbol(sym) {
    setForm(f => {
      const cur = f.active_symbols || [];
      return {
        ...f,
        active_symbols: cur.includes(sym)
          ? cur.filter(s => s !== sym)
          : [...cur, sym],
      };
    });
  }

  async function handleTestConnection() {
    setTestingConn(true);
    setConnResult(null);
    try {
      const res = await testConnection({
        api_key: form.api_key, secret_key: form.secret_key, testnet: form.testnet,
      });
      setConnResult(res);
    } catch (e) {
      setConnResult({ connected: false, error: e.message });
    }
    setTestingConn(false);
  }

  async function handleTestTelegram() {
    setTestingTg(true);
    setTgResult(null);
    try {
      // Save first then test
      if (form.telegram_bot_token && form.telegram_chat_id) {
        await updateSettings({
          telegram_bot_token: form.telegram_bot_token,
          telegram_chat_id:   form.telegram_chat_id,
        });
      }
      const res = await testTelegram();
      setTgResult(res);
      if (res.success) setTelegramOk(true);
    } catch (e) {
      setTgResult({ success: false, message: e.message });
    }
    setTestingTg(false);
  }

  async function handleTestEmail() {
    setTestingEmail(true);
    setEmailResult(null);
    try {
      // Save first then test
      if (form.email_sender && form.email_app_password && form.email_receiver) {
        await updateSettings({
          email_sender:       form.email_sender,
          email_app_password: form.email_app_password,
          email_receiver:     form.email_receiver,
        });
      }
      const res = await testEmail();
      setEmailResult(res);
      if (res.success) setEmailOk(true);
    } catch (e) {
      setEmailResult({ success: false, message: e.message });
    }
    setTestingEmail(false);
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    try {
      const payload = { ...form };
      if (!payload.api_key)            delete payload.api_key;
      if (!payload.secret_key)         delete payload.secret_key;
      if (!payload.telegram_bot_token) delete payload.telegram_bot_token;
      if (!payload.telegram_chat_id)   delete payload.telegram_chat_id;
      if (!payload.email_sender)       delete payload.email_sender;
      if (!payload.email_app_password) delete payload.email_app_password;
      if (!payload.email_receiver)     delete payload.email_receiver;
      await updateSettings(payload);
      setSaveMsg({ type: "success", text: "Settings saved!" });
    } catch (err) {
      setSaveMsg({ type: "error", text: err.message });
    }
    setSaving(false);
    setTimeout(() => setSaveMsg(null), 4000);
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

        {/* ── Binance API Keys ── */}
        <div className="settings-card">
          <div className="settings-section-title"><Wifi size={15}/> Binance API Keys</div>

          {form.testnet
            ? <div className="settings-note">Testnet mode ON — real funds NOT used. Get free keys: <a className="link" href="https://testnet.binance.vision" target="_blank" rel="noreferrer">testnet.binance.vision</a></div>
            : <div className="settings-note live-warning">⚠️ LIVE mode — real funds will be used!</div>
          }

          <div className="form-row">
            <div className="form-group" style={{ flex: 2 }}>
              <label htmlFor="api_key">API Key</label>
              <div className="input-with-icon">
                <input
                  id="api_key"
                  type={showKey ? "text" : "password"}
                  name="api_key"
                  placeholder="Paste your Binance API key"
                  value={form.api_key} onChange={handleChange}
                  className="form-input" autoComplete="off" />
                <button type="button" className="icon-btn" onClick={() => setShowKey(v => !v)}>
                  {showKey ? <EyeOff size={14}/> : <Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group" style={{ flex: 2 }}>
              <label htmlFor="secret_key">Secret Key</label>
              <div className="input-with-icon">
                <input
                  id="secret_key"
                  type={showSecret ? "text" : "password"}
                  name="secret_key"
                  placeholder="Paste your Binance Secret key"
                  value={form.secret_key} onChange={handleChange}
                  className="form-input" autoComplete="off" />
                <button type="button" className="icon-btn" onClick={() => setShowSecret(v => !v)}>
                  {showSecret ? <EyeOff size={14}/> : <Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group" style={{ justifyContent: "flex-end", minWidth: 140 }}>
              <label>Mode</label>
              <label className="toggle-label">
                <input type="checkbox" name="testnet" checked={form.testnet} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.testnet ? "Testnet" : "Live"}</span>
              </label>
            </div>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:12, flexWrap:"wrap" }}>
            <button type="button" className="btn-test" onClick={handleTestConnection}
              disabled={testingConn || (!form.api_key && !form.secret_key)}>
              <Wifi size={13}/> {testingConn ? "Testing..." : "Test Connection"}
            </button>
            {connResult && (
              <div className={`conn-result ${connResult.connected ? "success" : "error"}`}>
                {connResult.connected
                  ? `✅ Connected — $${Number(connResult.usdt_balance||0).toFixed(2)} USDT`
                  : `❌ ${connResult.error}`}
              </div>
            )}
          </div>
        </div>

        {/* ── Trading Settings ── */}
        <div className="settings-card">
          <div className="settings-section-title"><BarChart2 size={15}/> Trading Settings</div>
          <div className="form-row">
            <div className="form-group">
              <label>Symbol</label>
              <select name="symbol" value={form.symbol} onChange={handleChange} className="form-select">
                {PAIRS.map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Interval</label>
              <select name="interval" value={form.interval} onChange={handleChange} className="form-select">
                {INTERVALS.map(i => <option key={i}>{i}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Trade Size %</label>
              <input type="number" name="trade_quantity_percent"
                value={form.trade_quantity_percent} onChange={handleChange}
                min="1" max="100" step="1" className="form-input"/>
              <small>10 = 10% of balance per trade</small>
            </div>
            <div className="form-group">
              <label>Max Open Trades</label>
              <input type="number" name="max_open_trades"
                value={form.max_open_trades} onChange={handleChange}
                min="1" max="20" step="1" className="form-input"/>
            </div>
          </div>
        </div>

        {/* ── Multi-Symbol ── */}
        <div className="settings-card">
          <div className="settings-section-title"><Layers size={15}/> Multi-Symbol Mode</div>
          <div className="form-row" style={{ alignItems:"center" }}>
            <div className="form-group" style={{ flex:"none" }}>
              <label>Enable Multi-Symbol</label>
              <label className="toggle-label">
                <input type="checkbox" name="multi_symbol_mode" checked={form.multi_symbol_mode} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.multi_symbol_mode ? "ON" : "OFF"}</span>
              </label>
            </div>
          </div>
          <div>
            <label style={{ color:"var(--text-dim)", fontSize:11, fontWeight:600, textTransform:"uppercase", letterSpacing:"0.6px" }}>
              Active Pairs
            </label>
            <div className="symbol-pill-grid" style={{ marginTop:8 }}>
              {PAIRS.map(sym => (
                <button key={sym} type="button"
                  className={`symbol-pill ${(form.active_symbols||[]).includes(sym) ? "active" : ""}`}
                  onClick={() => toggleSymbol(sym)}>{sym}</button>
              ))}
            </div>
            <small style={{ color:"var(--text-dim)", fontSize:11 }}>
              Selected: {(form.active_symbols||[]).join(", ")||"none"}
            </small>
          </div>
        </div>

        {/* ── Risk Management ── */}
        <div className="settings-card">
          <div className="settings-section-title"><Shield size={15}/> Risk Management</div>
          <div className="form-row">
            <div className="form-group">
              <label>Stop Loss %</label>
              <input type="number" name="stop_loss_percent"
                value={form.stop_loss_percent} onChange={handleChange}
                min="0.5" max="20" step="0.1" className="form-input"/>
              <small>Auto-close on loss</small>
            </div>
            <div className="form-group">
              <label>Take Profit %</label>
              <input type="number" name="take_profit_percent"
                value={form.take_profit_percent} onChange={handleChange}
                min="0.5" max="50" step="0.1" className="form-input"/>
              <small>Auto-close on profit</small>
            </div>
            <div className="form-group">
              <label>Trailing Stop</label>
              <label className="toggle-label">
                <input type="checkbox" name="trailing_stop" checked={form.trailing_stop} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.trailing_stop ? "ON" : "OFF"}</span>
              </label>
              <small>SL moves up with price</small>
            </div>
            {form.trailing_stop && (
              <div className="form-group">
                <label>Trail %</label>
                <input type="number" name="trailing_stop_percent"
                  value={form.trailing_stop_percent} onChange={handleChange}
                  min="0.1" max="10" step="0.1" className="form-input"/>
                <small>% below peak price</small>
              </div>
            )}
          </div>
        </div>

        {/* ── AI Indicators ── */}
        <div className="settings-card">
          <div className="settings-section-title"><Bot size={15}/> AI Indicator Settings</div>
          <div className="form-row">
            <div className="form-group">
              <label>EMA Fast</label>
              <input type="number" name="ema_fast" value={form.ema_fast}
                onChange={handleChange} min="3" max="50" className="form-input"/>
            </div>
            <div className="form-group">
              <label>EMA Slow</label>
              <input type="number" name="ema_slow" value={form.ema_slow}
                onChange={handleChange} min="5" max="200" className="form-input"/>
            </div>
            <div className="form-group">
              <label>RSI Period</label>
              <input type="number" name="rsi_period" value={form.rsi_period}
                onChange={handleChange} min="5" max="50" className="form-input"/>
            </div>
            <div className="form-group">
              <label>RSI Overbought</label>
              <input type="number" name="rsi_overbought" value={form.rsi_overbought}
                onChange={handleChange} min="60" max="90" className="form-input"/>
            </div>
            <div className="form-group">
              <label>RSI Oversold</label>
              <input type="number" name="rsi_oversold" value={form.rsi_oversold}
                onChange={handleChange} min="10" max="40" className="form-input"/>
            </div>
          </div>
        </div>

        {/* ── Telegram ── */}
        <div className="settings-card">
          <div className="settings-section-title"><Bell size={15}/> Telegram Notifications</div>
          <div className="settings-note">
            Bot banao: <a className="link" href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a> &nbsp;|&nbsp;
            Chat ID: <a className="link" href="https://t.me/userinfobot" target="_blank" rel="noreferrer">@userinfobot</a>
          </div>
          {telegramOk && <div className="key-status saved">✅ Telegram active — notifications on</div>}
          <div className="form-row">
            <div className="form-group" style={{ flex:2 }}>
              <label>Bot Token</label>
              <div className="input-with-icon">
                <input type={showTgToken ? "text" : "password"} name="telegram_bot_token"
                  placeholder="1234567890:ABCdefGhIjKl..."
                  value={form.telegram_bot_token} onChange={handleChange}
                  className="form-input" autoComplete="off"/>
                <button type="button" className="icon-btn" onClick={() => setShowTgToken(v => !v)}>
                  {showTgToken ? <EyeOff size={14}/> : <Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group">
              <label>Chat ID</label>
              <input type="text" name="telegram_chat_id"
                placeholder="987654321"
                value={form.telegram_chat_id} onChange={handleChange}
                className="form-input"/>
            </div>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <button type="button" className="btn-test" onClick={handleTestTelegram}
              disabled={testingTg || (!form.telegram_bot_token && !telegramOk)}>
              <Bell size={13}/> {testingTg ? "Sending..." : "Send Test Message"}
            </button>
            {tgResult && (
              <div className={`conn-result ${tgResult.success ? "success" : "error"}`}>
                {tgResult.success ? "✅ " : "❌ "}{tgResult.message}
              </div>
            )}
          </div>
        </div>

        {/* ── Gmail ── */}
        <div className="settings-card">
          <div className="settings-section-title"><Mail size={15}/> Gmail Notifications</div>
          <div className="settings-note">
            Normal password kaam nahi karega — <b>App Password</b> chahiye:&nbsp;
            <a className="link" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">
              myaccount.google.com/apppasswords
            </a>
          </div>
          {emailOk && <div className="key-status saved">✅ Gmail active — email alerts on</div>}
          <div className="form-row">
            <div className="form-group" style={{ flex:2 }}>
              <label>Your Gmail</label>
              <input type="email" name="email_sender"
                placeholder="yourbot@gmail.com"
                value={form.email_sender} onChange={handleChange}
                className="form-input" autoComplete="off"/>
              <small>Is gmail se alerts bheje jayenge</small>
            </div>
            <div className="form-group" style={{ flex:2 }}>
              <label>App Password</label>
              <div className="input-with-icon">
                <input type={showEmailPwd ? "text" : "password"} name="email_app_password"
                  placeholder="xxxx xxxx xxxx xxxx"
                  value={form.email_app_password} onChange={handleChange}
                  className="form-input" autoComplete="off"/>
                <button type="button" className="icon-btn" onClick={() => setShowEmailPwd(v => !v)}>
                  {showEmailPwd ? <EyeOff size={14}/> : <Eye size={14}/>}
                </button>
              </div>
              <small>16 character App Password</small>
            </div>
            <div className="form-group" style={{ flex:2 }}>
              <label>Receive Alerts At</label>
              <input type="email" name="email_receiver"
                placeholder="you@gmail.com"
                value={form.email_receiver} onChange={handleChange}
                className="form-input"/>
              <small>Yahan alerts aayenge</small>
            </div>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <button type="button" className="btn-test" onClick={handleTestEmail}
              disabled={testingEmail || (!form.email_sender && !emailOk)}>
              <Mail size={13}/> {testingEmail ? "Sending..." : "Send Test Email"}
            </button>
            {emailResult && (
              <div className={`conn-result ${emailResult.success ? "success" : "error"}`}>
                {emailResult.success ? "✅ " : "❌ "}{emailResult.message}
              </div>
            )}
          </div>
        </div>

        {/* ── Save ── */}
        <div className="settings-footer">
          {saveMsg && <div className={`save-msg ${saveMsg.type}`}>{saveMsg.text}</div>}
          <button type="submit" className="btn-save" disabled={saving}>
            <Save size={14}/> {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>

      </form>
    </div>
  );
}
