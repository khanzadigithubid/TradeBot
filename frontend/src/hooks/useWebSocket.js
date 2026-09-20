import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "wss://tradebot-omuy.onrender.com/ws";

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const aliveRef = useRef(true);

  const connect = useCallback(() => {
    if (!aliveRef.current) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type !== "PONG" && data.type !== "HEARTBEAT") {
            setLastMessage(data);
          }
          // Update running state from heartbeat too
          if (data.type === "HEARTBEAT") {
            setLastMessage(data);
          }
        } catch (_) {}
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        // Reconnect after 4 seconds
        if (aliveRef.current) {
          timerRef.current = setTimeout(connect, 4000);
        }
      };

      ws.onerror = () => {
        // onclose will fire after onerror — handles reconnect
        setConnected(false);
      };

      // Ping every 25s to keep alive
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "PING" }));
        }
      }, 25000);

      ws.addEventListener("close", () => clearInterval(ping));

    } catch (e) {
      // WebSocket not available — retry
      timerRef.current = setTimeout(connect, 4000);
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    connect();
    return () => {
      aliveRef.current = false;
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, lastMessage };
}
