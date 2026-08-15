import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Loading, ErrorBox, statusBadge } from "../components/ui.jsx";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/stats/dashboard")
      .then(setStats)
      .catch(setError);
  }, []);

  if (error) return <ErrorBox error={error} />;
  if (!stats) return <Loading />;

  const cards = [
    { label: "AI Assets Discovered", value: stats.total_assets, to: "/assets" },
    { label: "Enabled", value: stats.enabled_assets },
    { label: "User/Group Accesses", value: stats.total_accesses },
    { label: "Unique Users Exposed", value: stats.unique_users_exposed },
    { label: "AI Interactions", value: stats.total_interactions, to: "/interactions" },
    { label: "Limited Monitoring", value: stats.monitoring_limited },
  ];

  return (
    <div>
      <h1>Governance Dashboard</h1>
      <p className="muted">
        Centralised view of AI capabilities embedded in your SaaS estate, who can
        use them, and the interactions observed.
      </p>

      <div className="card-grid">
        {cards.map((c) => (
          <Link to={c.to || "#"} key={c.label} className="stat-card">
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </Link>
        ))}
      </div>

      <h2>Monitoring Visibility</h2>
      <p className="muted">
        How much of each interaction the connected platforms actually expose.
        This is the core transparency signal of the platform.
      </p>
      <div className="vis-grid">
        <VisBar label="Request content" value={stats.visibility_summary.request_available} total={stats.total_interactions} />
        <VisBar label="Response content" value={stats.visibility_summary.response_available} total={stats.total_interactions} />
        <VisBar label="Model name" value={stats.visibility_summary.model_available} total={stats.total_interactions} />
        <VisBar label="Token usage" value={stats.visibility_summary.usage_available} total={stats.total_interactions} />
        <VisBar label="No content (metadata only)" value={stats.visibility_summary.no_content} total={stats.total_interactions} />
      </div>

      <h2>Recent Runs</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Status</th>
            <th>Assets</th>
            <th>Accesses</th>
            <th>Interactions</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {stats.recent_runs.map((r) => (
            <tr key={r.id}>
              <td>{r.run_type}</td>
              <td>{statusBadge(r.status)}</td>
              <td>{r.assets_found}</td>
              <td>{r.accesses_found}</td>
              <td>{r.interactions_found}</td>
              <td>{new Date(r.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VisBar({ label, value, total }) {
  const pct = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="vis-bar">
      <div className="vis-head">
        <span>{label}</span>
        <span className="muted">{value} / {total}</span>
      </div>
      <div className="vis-track">
        <div className="vis-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
