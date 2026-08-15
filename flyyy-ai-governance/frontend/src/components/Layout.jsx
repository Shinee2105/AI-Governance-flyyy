import React from "react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/assets", label: "AI Assets" },
  { to: "/interactions", label: "Interactions" },
  { to: "/connectors", label: "Connectors" },
  { to: "/limitations", label: "Visibility & Limits" },
];

export default function Layout({ children }) {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">FLYYY</div>
          <div className="brand-sub">SaaS AI Governance</div>
        </div>
        <nav>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <p>Discover • Monitor • Govern</p>
          <p className="muted">AI embedded in SaaS</p>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
