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
          <Zap size={18} color="#26a69a" fill="#26a69a" />
          <span className="brand-name">AI Trade<span className="brand-accent">Bot</span></span>
        </div>

        {/* Desktop links */}
        <div className="navbar-links navbar-links-desktop">
          {LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}
            >
              <Icon size={14} />{label}
            </NavLink>
          ))}
        </div>

        {/* Status + hamburger */}
        <div className="navbar-right">
          <div className="navbar-status">
            {connected
              ? <Wifi size={14} color="#2ecc71" />
              : <WifiOff size={14} color="#ef5350" />
            }
            <span className="status-text">{connected ? "Live" : "Offline"}</span>
            <div className={`bot-badge ${botRunning ? "running" : "stopped"}`}>
              {botRunning ? "● ON" : "○ OFF"}
            </div>
          </div>

          {/* Hamburger — only on mobile */}
          <button
            className="hamburger-btn"
            onClick={() => setMenuOpen(v => !v)}
            aria-label="Toggle menu"
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      {/* Mobile drawer */}
      {menuOpen && (
        <>
          {/* Backdrop */}
          <div
            className="mobile-backdrop"
            onClick={() => setMenuOpen(false)}
          />
          {/* Drawer */}
          <div className="mobile-drawer">
            {LINKS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to} to={to} end={end}
                className={({ isActive }) => isActive ? "mobile-nav-link active" : "mobile-nav-link"}
                onClick={() => setMenuOpen(false)}
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
            <div className="mobile-drawer-status">
              <div className={`bot-badge ${botRunning ? "running" : "stopped"}`} style={{ fontSize: 12 }}>
                {botRunning ? "● BOT RUNNING" : "○ BOT STOPPED"}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
