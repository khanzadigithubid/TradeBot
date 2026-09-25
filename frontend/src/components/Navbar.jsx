import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, History, Settings, Zap,
  Wifi, WifiOff, BarChart2, FlaskConical, Menu, X
} from "lucide-react";

const LINKS = [
  { to: "/",          label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/history",   label: "History",   icon: History },
  { to: "/analytics", label: "Analytics", icon: BarChart2 },
  { to: "/backtest",  label: "Backtest",  icon: FlaskConical },
  { to: "/settings",  label: "Settings",  icon: Settings },
];

export default function Navbar({ connected, botRunning }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <nav className="navbar">
        {/* Brand */}
        <div className="navbar-brand">
          <div className="brand-icon-wrap">
            <Zap size={16} color="#00c896" fill="#00c896" />
          </div>
          <span className="brand-name">
            AI<span className="brand-accent">Trade</span>Bot
          </span>
        </div>

        {/* Desktop links */}
        <div className="navbar-links-desktop">
          {LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}
            >
              <Icon size={14} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </div>

        {/* Right: status + hamburger */}
        <div className="navbar-right">
          <div className="navbar-status">
            <div className={`ws-indicator ${connected ? "ws-on" : "ws-off"}`}>
              {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
              {/* "Connected", not "Live" — in a trading app "Live" reads as
                  real-money trading, but this is only the WebSocket feed. */}
              <span className="status-text">{connected ? "Connected" : "Offline"}</span>
            </div>
            <div className={`bot-badge ${botRunning ? "running" : "stopped"}`}>
              {botRunning ? "● BOT ON" : "○ BOT OFF"}
            </div>
          </div>
          <button
            className="hamburger-btn"
            onClick={() => setMenuOpen(v => !v)}
            aria-label="Toggle menu"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </nav>

      {/* Mobile drawer */}
      {menuOpen && (
        <>
          <div className="mobile-backdrop" onClick={() => setMenuOpen(false)} />
          <div className="mobile-drawer">
            <div className="mobile-drawer-brand">
              <Zap size={18} color="#00c896" fill="#00c896" />
              <span style={{ fontWeight:800, color:"var(--text-bright)", fontSize:16 }}>
                AI<span style={{ color:"var(--green)" }}>Trade</span>Bot
              </span>
            </div>
            {LINKS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to} to={to} end={end}
                className={({ isActive }) => isActive ? "mobile-nav-link active" : "mobile-nav-link"}
                onClick={() => setMenuOpen(false)}
              >
                <Icon size={16} strokeWidth={2} />
                {label}
              </NavLink>
            ))}
            <div className="mobile-drawer-status">
              <div
                className={`bot-badge ${botRunning ? "running" : "stopped"}`}
                style={{ fontSize:12, width:"100%", justifyContent:"center", display:"flex" }}
              >
                {botRunning ? "● BOT RUNNING" : "○ BOT STOPPED"}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
