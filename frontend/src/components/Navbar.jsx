import { NavLink } from "react-router-dom";
import { LayoutDashboard, History, Settings, Zap, Wifi, WifiOff, BarChart2, FlaskConical } from "lucide-react";

export default function Navbar({ connected, botRunning }) {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Zap size={18} color="#26a69a" fill="#26a69a" />
        <span className="brand-name">AI Trade<span className="brand-accent">Bot</span></span>
      </div>

      <div className="navbar-links">
        <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <LayoutDashboard size={14} />
          Dashboard
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <History size={14} />
          History
        </NavLink>
        <NavLink to="/analytics" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <BarChart2 size={14} />
          Analytics
        </NavLink>
        <NavLink to="/backtest" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
          <FlaskConical size={14} />
          Backtest
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
