import { NavLink } from "react-router-dom";
import { LayoutDashboard, History, Settings, Zap, Wifi, WifiOff } from "lucide-react";

export default function Navbar({ connected, botRunning }) {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Zap size={18} color="#26a69a" fill="#26a69a" />
        <span className="brand-name">AI Trade<span className="brand-accent">Bot</span></span>
      </div>

      <div className="navbar-links">
        <NavLink to="/" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <LayoutDashboard size={14} />
          Dashboard
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <History size={14} />
          History
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <Settings size={14} />
          Settings
        </NavLink>
      </div>

      <div className="navbar-status">
        {connected
          ? <Wifi size={14} color="#2ecc71" />
          : <WifiOff size={14} color="#ef5350" />
        }
        <span className="status-text">{connected ? "Live" : "Offline"}</span>
        <div className={`bot-badge ${botRunning ? "running" : "stopped"}`}>
          {botRunning ? "● BOT ON" : "○ BOT OFF"}
        </div>
      </div>
    </nav>
  );
}
