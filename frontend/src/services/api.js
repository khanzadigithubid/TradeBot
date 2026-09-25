/**
 * API Service — All backend communication
 */

// Local development mein: VITE_API_URL set karo frontend/.env.local mein
// Production (Vercel): VITE_API_URL set karo Vercel environment variables mein
const BASE_URL = import.meta.env.VITE_API_URL || "https://tradebot-omuy.onrender.com/api";

// The socket must point at the SAME backend as the REST calls. Otherwise local
// dev mixes the production bot's live data with the local API.
function deriveWsUrl(base) {
  try {
    const u = new URL(base);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    u.pathname = "/ws";
    u.search = "";
    return u.toString();
  } catch (_) {
    return null;
  }
}

export const WS_URL =
  import.meta.env.VITE_WS_URL ||
  deriveWsUrl(BASE_URL) ||
  "wss://tradebot-omuy.onrender.com/ws";

// Matches the backend's API_SECRET. When the server has API_SECRET set this
// header is required for /api/bot/*, /api/settings and /api/trades/manual.
const API_SECRET = import.meta.env.VITE_API_SECRET || "";

function authHeaders() {
  return API_SECRET ? { "X-API-Secret": API_SECRET } : {};
}

async function request(endpoint, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(options.headers || {}),
      },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    return await res.json();
  } catch (e) {
    throw e;
  }
}

// ── Bot Control ────────────────────────────────────────────────────────────────
export const getBotStatus    = ()     => request("/status");
export const startBot        = (data) => request("/bot/start", { method: "POST", body: JSON.stringify(data) });
export const stopBot         = ()     => request("/bot/stop",  { method: "POST" });

// ── Settings ──────────────────────────────────────────────────────────────────
export const getSettings     = ()     => request("/settings");
export const updateSettings  = (data) => request("/settings", { method: "POST", body: JSON.stringify(data) });
export const testConnection  = (data) => request("/settings/test-connection", { method: "POST", body: JSON.stringify(data) });
export const testTelegram    = ()     => request("/settings/test-telegram",   { method: "POST" });
export const testEmail       = ()     => request("/settings/test-email",       { method: "POST" });

// ── Market ────────────────────────────────────────────────────────────────────
export const getPrice        = (sym)               => request(`/market/${sym}/price`);
export const getMarketStats  = (sym)               => request(`/market/${sym}/stats`);
export const getCandles      = (sym, int="15m", lim=200) =>
  request(`/market/${sym}/candles?interval=${int}&limit=${lim}`);
export const getSignal       = (sym)               => request(`/market/${sym}/signal`);
export const getIndicators   = (sym, int="15m", lim=200) =>
  request(`/market/${sym}/indicators?interval=${int}&limit=${lim}`);
export const getBulkPrices   = (symbols)           =>
  request(`/market/prices?symbols=${symbols.join(",")}`);


// ── Trades ────────────────────────────────────────────────────────────────────
export const getOpenTrades   = ()         => request("/trades/open");
export const getTradeHistory = (lim=100)  => request(`/trades/history?limit=${lim}`);
export const getTradeStats   = ()         => request("/trades/stats");
export const manualTrade     = (data)     => request("/trades/manual", { method: "POST", body: JSON.stringify(data) });
export const closeTrade      = (id)       => request(`/trades/${id}`,  { method: "DELETE" });

// ── Backtesting ───────────────────────────────────────────────────────────────
export const runBacktest     = (data)     => request("/backtest", { method: "POST", body: JSON.stringify(data) });

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getAnalytics    = ()         => request("/analytics");

// ── WebSocket ─────────────────────────────────────────────────────────────────
export function createWebSocket(onMessage, onConnect, onDisconnect) {
  let ws = null;
  let reconnectTimer = null;
  let alive = true;

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      if (onConnect) onConnect();
      const pingInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "PING" }));
        } else {
          clearInterval(pingInterval);
        }
      }, 20000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (_) {}
    };

    ws.onclose = () => {
      if (onDisconnect) onDisconnect();
      if (alive) reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }

  connect();

  return {
    send:  (data) => ws && ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(data)),
    close: () => { alive = false; clearTimeout(reconnectTimer); ws && ws.close(); },
  };
}
