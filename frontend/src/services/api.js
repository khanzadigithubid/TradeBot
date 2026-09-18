/**
 * API Service - Backend se communicate karne ke liye
 */

const BASE_URL = "http://localhost:8000/api";
const WS_URL = "ws://localhost:8000/ws";

// ─── REST API ──────────────────────────────────────────────────────────────────

async function request(endpoint, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Request failed");
    }
    return await res.json();
  } catch (e) {
    throw e;
  }
}

// Bot Control
export const getBotStatus = () => request("/status");
export const startBot = (data = {}) => request("/bot/start", { method: "POST", body: JSON.stringify(data) });
export const stopBot = () => request("/bot/stop", { method: "POST" });

// Settings
export const getSettings = () => request("/settings");
export const updateSettings = (data) => request("/settings", { method: "POST", body: JSON.stringify(data) });
export const testConnection = (data) => request("/settings/test-connection", { method: "POST", body: JSON.stringify(data) });

// Market
export const getPrice = (symbol) => request(`/market/${symbol}/price`);
export const getMarketStats = (symbol) => request(`/market/${symbol}/stats`);
export const getCandles = (symbol, interval = "15m", limit = 100) =>
  request(`/market/${symbol}/candles?interval=${interval}&limit=${limit}`);
export const getSignal = (symbol) => request(`/market/${symbol}/signal`);

// Trades
export const getOpenTrades = () => request("/trades/open");
export const getTradeHistory = (limit = 50) => request(`/trades/history?limit=${limit}`);
export const getTradeStats = () => request("/trades/stats");
export const manualTrade = (data) => request("/trades/manual", { method: "POST", body: JSON.stringify(data) });
export const closeTrade = (id) => request(`/trades/${id}`, { method: "DELETE" });

// ─── WebSocket ─────────────────────────────────────────────────────────────────

export function createWebSocket(onMessage, onConnect, onDisconnect) {
  let ws = null;
  let reconnectTimer = null;
  let alive = true;

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log("WebSocket connected");
      if (onConnect) onConnect();
      // Ping every 20s
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
      } catch (e) {}
    };

    ws.onclose = () => {
      if (onDisconnect) onDisconnect();
      if (alive) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  connect();

  return {
    send: (data) => ws && ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(data)),
    close: () => {
      alive = false;
      clearTimeout(reconnectTimer);
      ws && ws.close();
    },
  };
}
