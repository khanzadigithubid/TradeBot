import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const root = document.getElementById("root");

try {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} catch (e) {
  root.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
    height:100vh;background:#0b0e17;color:#e2e8f0;gap:16px;font-family:sans-serif;">
      <div style="font-size:40px">⚠️</div>
      <div style="font-size:20px;font-weight:700">Startup Error</div>
      <div style="color:#ef4444;font-size:13px;max-width:600px;text-align:center;padding:0 20px">
        ${e.message}
      </div>
      <button onclick="location.reload()" 
        style="padding:10px 24px;background:#3b82f6;border:none;border-radius:8px;
        color:#fff;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px">
        Reload
      </button>
    </div>
  `;
}
