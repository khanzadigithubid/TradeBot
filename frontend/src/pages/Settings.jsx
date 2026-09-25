import { useEffect, useState } from "react";
import {
  Shield, BarChart2, Save, Wifi, Layers,
  Eye, EyeOff, Mail, Bell, TrendingDown, Brain,
  CheckCircle, XCircle, Key, Zap, Globe
} from "lucide-react";
import { getSettings, updateSettings, testConnection, testTelegram, testEmail } from "../services/api";

const INTERVALS = ["1m","5m","15m","30m","1h","4h","1d"];

/* ── Section Card ── */
function SectionCard({ icon: Icon, title, color = "var(--blue)", children }) {
  return (
    <div className="settings-card">
      <div className="settings-section-title">
        <div className="sc-icon" style={{ background:`rgba(${color},0.12)`, color }}>
          <Icon size={13} />
        </div>
        {title}
      </div>
      {children}
    </div>
  );
}

/* ── Test Button ── */
function TestBtn({ onClick, loading, success, label, loadingLabel = "Testing..." }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap" }}>
      <button type="button" className="btn-test" onClick={onClick} disabled={loading}>
        {loading ? <><span className="spinner" style={{width:12,height:12,borderWidth:1.5}}/> {loadingLabel}</> : label}
      </button>
      {success === true  && <span style={{color:"var(--green)",fontSize:12,fontWeight:600,display:"flex",alignItems:"center",gap:4}}><CheckCircle size={13}/> Connected!</span>}
      {success === false && <span style={{color:"var(--red)",fontSize:12,fontWeight:600,display:"flex",alignItems:"center",gap:4}}><XCircle size={13}/> Failed</span>}
    </div>
  );
}

export default function Settings() {
  const [form, setForm] = useState({
    api_key:"", secret_key:"", testnet:true,
    symbol:"BTCUSDT", interval:"15m",
    trade_quantity_percent:10, max_open_trades:3,
    stop_loss_percent:2.0, take_profit_percent:4.0,
    trailing_stop:true, trailing_stop_percent:1.0,
    ema_fast:9, ema_slow:21, rsi_period:14,
    rsi_overbought:70, rsi_oversold:30,
    multi_symbol_mode:false,
    active_symbols:["BTCUSDT","ETHUSDT","BNBUSDT"],
    daily_loss_limit_percent:5.0,
    sentiment_filter:true, mtf_enabled:true,
    telegram_bot_token:"", telegram_chat_id:"",
    email_sender:"", email_app_password:"", email_receiver:"",
  });

  const [cryptoPairs,    setCryptoPairs]    = useState([]);
  const [forexPairs,     setForexPairs]     = useState([]);
  const [showKey,        setShowKey]        = useState(false);
  const [showSecret,     setShowSecret]     = useState(false);
  const [showTgToken,    setShowTgToken]    = useState(false);
  const [showEmailPwd,   setShowEmailPwd]   = useState(false);
  const [connResult,     setConnResult]     = useState(null);   // {connected,usdt_balance,error}
  const [tgOk,           setTgOk]           = useState(null);
  const [emailOk,        setEmailOk]        = useState(null);
  const [testingConn,    setTestingConn]    = useState(false);
  const [testingTg,      setTestingTg]      = useState(false);
  const [testingEmail,   setTestingEmail]   = useState(false);
  const [saving,         setSaving]         = useState(false);
  const [saveMsg,        setSaveMsg]        = useState(null);
  const [telegramOk,     setTelegramOk]     = useState(false);
  const [emailConfigOk,  setEmailConfigOk]  = useState(false);

  useEffect(() => {
    getSettings().then(d => {
      setForm(f => ({
        ...f,
        testnet:                  d.testnet                  ?? true,
        symbol:                   d.symbol                   ?? "BTCUSDT",
        interval:                 d.interval                 ?? "15m",
        trade_quantity_percent:   d.trade_quantity_percent   ?? 10,
        max_open_trades:          d.max_open_trades          ?? 3,
        stop_loss_percent:        d.stop_loss_percent        ?? 2.0,
        take_profit_percent:      d.take_profit_percent      ?? 4.0,
        trailing_stop:            d.trailing_stop            ?? true,
        trailing_stop_percent:    d.trailing_stop_percent    ?? 1.0,
        ema_fast:                 d.ema_fast                 ?? 9,
        ema_slow:                 d.ema_slow                 ?? 21,
        rsi_period:               d.rsi_period               ?? 14,
        rsi_overbought:           d.rsi_overbought           ?? 70,
        rsi_oversold:             d.rsi_oversold             ?? 30,
        multi_symbol_mode:        d.multi_symbol_mode        ?? false,
        active_symbols:           d.active_symbols           ?? ["BTCUSDT","ETHUSDT","BNBUSDT"],
        daily_loss_limit_percent: d.daily_loss_limit         ?? 5.0,
        sentiment_filter:         d.sentiment_filter         ?? true,
        mtf_enabled:              d.mtf_enabled              ?? true,
      }));
      if (d.crypto_pairs?.length) setCryptoPairs(d.crypto_pairs);
      if (d.forex_pairs?.length)  setForexPairs(d.forex_pairs);
      setTelegramOk(!!d.telegram_configured);
      setEmailConfigOk(!!d.email_configured);
    }).catch(() => {});
  }, []);

  function handleChange(e) {
    const { name, value, type, checked } = e.target;
    setForm(f => ({
      ...f,
      [name]: type === "checkbox" ? checked : type === "number" ? parseFloat(value) : value,
    }));
  }

  function toggleSymbol(sym) {
    setForm(f => {
      const cur = f.active_symbols || [];
      return { ...f, active_symbols: cur.includes(sym) ? cur.filter(s=>s!==sym) : [...cur,sym] };
    });
  }

  async function handleTestConnection() {
    setTestingConn(true); setConnResult(null);
    try {
      const r = await testConnection({ api_key:form.api_key, secret_key:form.secret_key, testnet:form.testnet });
      setConnResult(r);
    } catch(e) { setConnResult({ connected:false, error:e.message }); }
    setTestingConn(false);
  }

  async function handleTestTelegram() {
    setTestingTg(true); setTgOk(null);
    try {
      if (form.telegram_bot_token && form.telegram_chat_id) {
        await updateSettings({ telegram_bot_token:form.telegram_bot_token, telegram_chat_id:form.telegram_chat_id });
      }
      const r = await testTelegram();
      setTgOk(r.success);
      if (r.success) setTelegramOk(true);
    } catch(e) { setTgOk(false); }
    setTestingTg(false);
  }

  async function handleTestEmail() {
    setTestingEmail(true); setEmailOk(null);
    try {
      if (form.email_sender && form.email_app_password && form.email_receiver) {
        await updateSettings({ email_sender:form.email_sender, email_app_password:form.email_app_password, email_receiver:form.email_receiver });
      }
      const r = await testEmail();
      setEmailOk(r.success);
      if (r.success) setEmailConfigOk(true);
    } catch(e) { setEmailOk(false); }
    setTestingEmail(false);
  }

  async function handleSave(e) {
    e.preventDefault(); setSaving(true); setSaveMsg(null);
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
      setSaveMsg({ type:"success", text:"✅ Settings saved successfully!" });
    } catch(err) {
      setSaveMsg({ type:"error", text:`❌ ${err.message}` });
    }
    setSaving(false);
    setTimeout(() => setSaveMsg(null), 4000);
  }

  const allPairs = [...cryptoPairs, ...forexPairs];

  return (
    <div className="page settings-page">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub">Bot configuration — changes apply instantly</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="settings-form">

        {/* ════════════════════════════════
            BINANCE API
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Key size={14} /> Binance API Keys
          </div>

          {form.testnet
            ? <div className="settings-note">
                🧪 Testnet ON — using fake funds.
                &nbsp;<a className="link" href="https://testnet.binance.vision" target="_blank" rel="noreferrer">Get testnet keys →</a>
              </div>
            : <div className="settings-note live-warning">
                ⚠️ LIVE mode — real funds will be used. Trade carefully!
              </div>
          }

          <div className="form-row">
            <div className="form-group" style={{flex:2}}>
              <label>API Key</label>
              <div className="input-with-icon">
                <input id="api_key" type={showKey?"text":"password"} name="api_key"
                  placeholder="Paste your Binance API key"
                  value={form.api_key} onChange={handleChange}
                  className="form-input" autoComplete="off"/>
                <button type="button" className="icon-btn" onClick={()=>setShowKey(v=>!v)}>
                  {showKey?<EyeOff size={14}/>:<Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group" style={{flex:2}}>
              <label>Secret Key</label>
              <div className="input-with-icon">
                <input id="secret_key" type={showSecret?"text":"password"} name="secret_key"
                  placeholder="Paste your Binance Secret"
                  value={form.secret_key} onChange={handleChange}
                  className="form-input" autoComplete="off"/>
                <button type="button" className="icon-btn" onClick={()=>setShowSecret(v=>!v)}>
                  {showSecret?<EyeOff size={14}/>:<Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group" style={{justifyContent:"flex-end",minWidth:130}}>
              <label>Mode</label>
              <label className="toggle-label">
                <input type="checkbox" name="testnet" checked={form.testnet} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.testnet?"Testnet":"Live 🔴"}</span>
              </label>
            </div>
          </div>

          <div style={{display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
            <button type="button" className="btn-test" onClick={handleTestConnection}
              disabled={testingConn||(!form.api_key&&!form.secret_key)}>
              <Wifi size={13}/> {testingConn?"Testing...":"Test Connection"}
            </button>
            {connResult && (
              <div className={`conn-result ${connResult.connected&&!connResult.error?"success":"error"}`}>
                {connResult.connected
                  ? connResult.error
                    ? `⚠️ ${connResult.error}`
                    : `✅ Connected — $${Number(connResult.usdt_balance||0).toFixed(2)} USDT`
                  : `❌ ${connResult.error}`}
              </div>
            )}
          </div>
        </div>

        {/* ════════════════════════════════
            TRADING SETTINGS
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <BarChart2 size={14}/> Trading Settings
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Symbol</label>
              <select name="symbol" value={form.symbol} onChange={handleChange} className="form-select">
                {cryptoPairs.length > 0 ? (
                  <>
                    <optgroup label="── Crypto ──">
                      {cryptoPairs.map(p=><option key={p}>{p}</option>)}
                    </optgroup>
                    {forexPairs.length > 0 && (
                      <optgroup label="── Forex ──">
                        {forexPairs.map(p=><option key={p}>{p}</option>)}
                      </optgroup>
                    )}
                  </>
                ) : <option>BTCUSDT</option>}
              </select>
            </div>
            <div className="form-group">
              <label>Interval</label>
              <select name="interval" value={form.interval} onChange={handleChange} className="form-select">
                {INTERVALS.map(i=><option key={i}>{i}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Trade Size %</label>
              <input type="number" name="trade_quantity_percent" value={form.trade_quantity_percent}
                onChange={handleChange} min="1" max="100" step="1" className="form-input"/>
              <small>% of balance per trade</small>
            </div>
            <div className="form-group">
              <label>Max Open Trades</label>
              <input type="number" name="max_open_trades" value={form.max_open_trades}
                onChange={handleChange} min="1" max="20" step="1" className="form-input"/>
            </div>
          </div>
        </div>

        {/* ════════════════════════════════
            MULTI-SYMBOL
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Layers size={14}/> Multi-Symbol Mode
          </div>
          <div className="form-row" style={{alignItems:"center"}}>
            <div className="form-group" style={{flex:"none"}}>
              <label>Enable Multi-Symbol</label>
              <label className="toggle-label">
                <input type="checkbox" name="multi_symbol_mode" checked={form.multi_symbol_mode} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.multi_symbol_mode?"ON":"OFF"}</span>
              </label>
            </div>
          </div>
          {/* Grouped pills */}
          <div>
            <label style={{color:"var(--text-dim)",fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:"0.6px"}}>
              Active Pairs
            </label>
            {cryptoPairs.length > 0 && (
              <>
                <div style={{color:"var(--text-dim)",fontSize:10,marginTop:10,marginBottom:5,fontWeight:700,letterSpacing:"0.5px"}}>CRYPTO</div>
                <div className="symbol-pill-grid">
                  {cryptoPairs.map(sym=>(
                    <button key={sym} type="button"
                      className={`symbol-pill ${(form.active_symbols||[]).includes(sym)?"active":""}`}
                      onClick={()=>toggleSymbol(sym)}>{sym.replace("USDT","")}</button>
                  ))}
                </div>
              </>
            )}
            {forexPairs.length > 0 && (
              <>
                <div style={{color:"var(--text-dim)",fontSize:10,marginTop:10,marginBottom:5,fontWeight:700,letterSpacing:"0.5px"}}>FOREX</div>
                <div className="symbol-pill-grid">
                  {forexPairs.map(sym=>(
                    <button key={sym} type="button"
                      className={`symbol-pill ${(form.active_symbols||[]).includes(sym)?"active":""}`}
                      onClick={()=>toggleSymbol(sym)}>{sym.replace("USDT","")}</button>
                  ))}
                </div>
              </>
            )}
            <small style={{color:"var(--text-dim)",fontSize:11,marginTop:8,display:"block"}}>
              Selected: {(form.active_symbols||[]).join(", ") || "none"}
            </small>
          </div>
        </div>

        {/* ════════════════════════════════
            RISK MANAGEMENT
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Shield size={14}/> Risk Management
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Stop Loss %</label>
              <input type="number" name="stop_loss_percent" value={form.stop_loss_percent}
                onChange={handleChange} min="0.5" max="20" step="0.1" className="form-input"/>
            </div>
            <div className="form-group">
              <label>Take Profit %</label>
              <input type="number" name="take_profit_percent" value={form.take_profit_percent}
                onChange={handleChange} min="0.5" max="50" step="0.1" className="form-input"/>
            </div>
            <div className="form-group">
              <label>Trailing Stop</label>
              <label className="toggle-label">
                <input type="checkbox" name="trailing_stop" checked={form.trailing_stop} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.trailing_stop?"ON":"OFF"}</span>
              </label>
              <small>SL moves up with price</small>
            </div>
            {form.trailing_stop && (
              <div className="form-group">
                <label>Trail %</label>
                <input type="number" name="trailing_stop_percent" value={form.trailing_stop_percent}
                  onChange={handleChange} min="0.1" max="10" step="0.1" className="form-input"/>
              </div>
            )}
          </div>
        </div>

        {/* ════════════════════════════════
            ADVANCED RISK & AI
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <TrendingDown size={14}/> Advanced Risk & AI
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Daily Loss Limit %</label>
              <input type="number" name="daily_loss_limit_percent" value={form.daily_loss_limit_percent}
                onChange={handleChange} min="1" max="50" step="0.5" className="form-input"/>
              <small>Bot auto-stops if daily loss exceeds this</small>
            </div>
            <div className="form-group">
              <label>Sentiment Filter</label>
              <label className="toggle-label">
                <input type="checkbox" name="sentiment_filter" checked={form.sentiment_filter} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.sentiment_filter?"ON":"OFF"}</span>
              </label>
              <small>Fear & Greed + news signals</small>
            </div>
            <div className="form-group">
              <label>Multi-Timeframe (MTF)</label>
              <label className="toggle-label">
                <input type="checkbox" name="mtf_enabled" checked={form.mtf_enabled} onChange={handleChange}/>
                <span className="toggle-track"/>
                <span className="toggle-text">{form.mtf_enabled?"ON — 15m+1h+4h":"OFF"}</span>
              </label>
              <small>Stronger signals from 3 timeframes</small>
            </div>
          </div>
        </div>

        {/* ════════════════════════════════
            AI INDICATORS
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Brain size={14}/> AI Indicator Settings
          </div>
          <div className="form-row">
            {[
              {name:"ema_fast",      label:"EMA Fast",       min:3,  max:50},
              {name:"ema_slow",      label:"EMA Slow",       min:5,  max:200},
              {name:"rsi_period",    label:"RSI Period",     min:5,  max:50},
              {name:"rsi_overbought",label:"RSI Overbought", min:60, max:90},
              {name:"rsi_oversold",  label:"RSI Oversold",   min:10, max:40},
            ].map(({name, label, min, max}) => (
              <div key={name} className="form-group">
                <label>{label}</label>
                <input type="number" name={name} value={form[name]}
                  onChange={handleChange} min={min} max={max} className="form-input"/>
              </div>
            ))}
          </div>
        </div>

        {/* ════════════════════════════════
            TELEGRAM
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Bell size={14}/> Telegram Notifications
          </div>
          <div className="settings-note">
            Create bot: <a className="link" href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a>
            &nbsp;·&nbsp;
            Get Chat ID: <a className="link" href="https://t.me/userinfobot" target="_blank" rel="noreferrer">@userinfobot</a>
          </div>
          {telegramOk && (
            <div style={{display:"flex",alignItems:"center",gap:6,color:"var(--green)",fontSize:12,fontWeight:600}}>
              <CheckCircle size={13}/> Telegram configured & active
            </div>
          )}
          <div className="form-row">
            <div className="form-group" style={{flex:2}}>
              <label>Bot Token</label>
              <div className="input-with-icon">
                <input type={showTgToken?"text":"password"} name="telegram_bot_token"
                  placeholder="1234567890:ABCdef..."
                  value={form.telegram_bot_token} onChange={handleChange}
                  className="form-input" autoComplete="off"/>
                <button type="button" className="icon-btn" onClick={()=>setShowTgToken(v=>!v)}>
                  {showTgToken?<EyeOff size={14}/>:<Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group">
              <label>Chat ID</label>
              <input type="text" name="telegram_chat_id" placeholder="987654321"
                value={form.telegram_chat_id} onChange={handleChange} className="form-input"/>
            </div>
          </div>
          <TestBtn onClick={handleTestTelegram} loading={testingTg} success={tgOk}
            label={<><Bell size={13}/> Send Test Message</>} />
        </div>

        {/* ════════════════════════════════
            EMAIL (GMAIL)
        ════════════════════════════════ */}
        <div className="settings-card">
          <div className="settings-section-title">
            <Mail size={14}/> Gmail Notifications
          </div>
          <div className="settings-note">
            Need App Password (not regular password):&nbsp;
            <a className="link" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">
              myaccount.google.com/apppasswords →
            </a>
          </div>
          {emailConfigOk && (
            <div style={{display:"flex",alignItems:"center",gap:6,color:"var(--green)",fontSize:12,fontWeight:600}}>
              <CheckCircle size={13}/> Gmail configured & active
            </div>
          )}
          <div className="form-row">
            <div className="form-group" style={{flex:2}}>
              <label>Gmail Address</label>
              <input type="email" name="email_sender" placeholder="yourbot@gmail.com"
                value={form.email_sender} onChange={handleChange}
                className="form-input" autoComplete="off"/>
            </div>
            <div className="form-group" style={{flex:2}}>
              <label>App Password</label>
              <div className="input-with-icon">
                <input type={showEmailPwd?"text":"password"} name="email_app_password"
                  placeholder="xxxx xxxx xxxx xxxx"
                  value={form.email_app_password} onChange={handleChange}
                  className="form-input" autoComplete="off"/>
                <button type="button" className="icon-btn" onClick={()=>setShowEmailPwd(v=>!v)}>
                  {showEmailPwd?<EyeOff size={14}/>:<Eye size={14}/>}
                </button>
              </div>
            </div>
            <div className="form-group" style={{flex:2}}>
              <label>Receive Alerts At</label>
              <input type="email" name="email_receiver" placeholder="you@gmail.com"
                value={form.email_receiver} onChange={handleChange} className="form-input"/>
            </div>
          </div>
          <TestBtn onClick={handleTestEmail} loading={testingEmail} success={emailOk}
            label={<><Mail size={13}/> Send Test Email</>} />
        </div>

        {/* ════════════════════════════════
            SAVE BUTTON
        ════════════════════════════════ */}
        <div className="settings-footer">
          {saveMsg && (
            <div className={`save-msg ${saveMsg.type}`}>{saveMsg.text}</div>
          )}
          <button type="submit" className="btn-save" disabled={saving}>
            <Save size={14}/> {saving?"Saving...":"Save All Settings"}
          </button>
        </div>

      </form>
    </div>
  );
}
