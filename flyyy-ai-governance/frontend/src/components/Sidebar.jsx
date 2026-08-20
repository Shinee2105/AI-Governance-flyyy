import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getCurrentUser, logout } from "../api.js";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/assets", label: "AI Assets" },
  { to: "/interactions", label: "Interactions" },
  { to: "/connectors", label: "Connectors" },
  { to: "/limitations", label: "Visibility & Limits" },
];

export default function Sidebar({ onNavigate }) {
  const location = useLocation();
  const navigate = useNavigate();
  const currentUser = getCurrentUser();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-mark">FLYYY</div>
          <div className="brand-sub">SaaS AI Governance</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {links.map((l) => {
          const isActive = location.pathname === l.to;
          return (
            <button
              key={l.to}
              className={`nav-link ${isActive ? "active" : ""}`}
              onClick={() => {
                navigate(l.to);
                onNavigate && onNavigate(l.to);
              }}
            >
              <span>{l.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <div className="user-section">
          <div className="user-info">
            <div className="user-name">
              {currentUser || "Guest"}
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Sign out">
            Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}
