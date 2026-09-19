import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useEffect, useState, Component } from "react";
import Navbar    from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Settings  from "./pages/Settings";
import History   from "./pages/History";
import Analytics from "./pages/Analytics";
import Backtest  from "./pages/Backtest";
import { useWebSocket } from "./hooks/useWebSocket";
import "./App.css";

// ── Error Boundary ─────────────────────────────────────────────────────────────
class ErrorBoundary extends Component {
  state = { hasError: false, error: null };
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display:"flex", flexDirection:"column", alignItems:"center",
          justifyContent:"center", height:"100vh",
          background:"#0b0e17", color:"#e2e8f0", gap:16,
        }}>
          <div style={{ fontSize:40 }}>⚠️</div>
          <div style={{ fontSize:20, fontWeight:700 }}>Something went wrong</div>
          <div style={{ color:"#ef4444", fontSize:13, maxWidth:500, textAlign:"center" }}>
            {this.state.error?.message}
          </div>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop:12, padding:"10px 24px", background:"#3b82f6",
              border:"none", borderRadius:8, color:"#fff", fontSize:14,
              fontWeight:600, cursor:"pointer" }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Main App ───────────────────────────────────────────────────────────────────
function AppInner() {
  const { connected, lastMessage } = useWebSocket();
  const [botRunning, setBotRunning] = useState(false);

  useEffect(() => {
    if (!lastMessage) return;
    const t = lastMessage.type;
    if (["CONNECTED","SIGNAL_UPDATE","HEARTBEAT"].includes(t)) {
      if (lastMessage.status?.running    !== undefined) setBotRunning(lastMessage.status.running);
      if (lastMessage.running            !== undefined) setBotRunning(lastMessage.running);
      if (lastMessage.stats?.bot_running !== undefined) setBotRunning(lastMessage.stats.bot_running);
    }
  }, [lastMessage]);

  return (
    <BrowserRouter>
      <div className="app">
        <Navbar connected={connected} botRunning={botRunning} />
        <main className="main-content">
          <Routes>
            <Route path="/"          element={<Dashboard wsMessage={lastMessage} />} />
            <Route path="/history"   element={<History />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/backtest"  element={<Backtest />} />
            <Route path="/settings"  element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AppInner />
    </ErrorBoundary>
  );
}
