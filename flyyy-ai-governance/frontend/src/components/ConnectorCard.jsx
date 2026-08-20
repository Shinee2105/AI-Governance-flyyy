import React, { useState } from "react";
import { Badge, statusBadge, DemoBadge } from "./ui.jsx";
import { api } from "../api.js";

export function ConnectorCard({ conn, caps, runs, busy, onRun }) {
  const [expanded, setExpanded] = useState(false);

  const isSalesforce = conn.connector_type === "salesforce";
  const isDemo = conn.connector_type === "demo";

  let statusColor = "neutral";
  if (conn.status === "Configured" || conn.status === "Connected") {
    statusColor = "ok";
  } else if (conn.status === "Error") {
    statusColor = "bad";
  } else if (conn.status === "Not Configured") {
    statusColor = "warn";
  }

  return (
    <div className="connector-card">
      <div className="connector-header" onClick={() => setExpanded(!expanded)}>
        <div className="connector-main">
          <div className="connector-info">
            <h3 className="connector-name">{conn.name}</h3>
            <div className="connector-meta">
              <span className="muted small">{conn.connector_type}</span>
              <span className="muted small">{conn.platform}</span>
            </div>
          </div>
          {isDemo && <DemoBadge label="DEMO" />}
          {!isDemo && caps && (
            <Badge kind={caps.configured ? "ok" : "warn"}>
              {caps.configured ? "Live" : "Setup Required"}
            </Badge>
          )}
        </div>
        <div className="connector-actions">
          <Badge kind={statusColor}>{conn.status}</Badge>
        </div>
      </div>

      {expanded && (
        <div className="connector-details">
          {!isDemo && caps && <EvidenceSection title="Discovery Evidence" items={caps.discovery || []} />}
          {!isDemo && caps && <EvidenceSection title="Monitoring Evidence" items={caps.monitoring || []} />}
          {!isDemo && caps && caps.not_exposed && caps.not_exposed.length > 0 && (
            <EvidenceSection title="Not Exposed by Platform" items={caps.not_exposed || []} variant="warning" />
          )}

          <div className="connector-actions-row">
            <button
              className="btn btn-primary" disabled={busy === conn.id + "-discover"} onClick={() => onRun(conn.id, "discover")}>
              {busy === conn.id + "-discover" ? "Running…" : "Run Discovery"}
            </button>
            <button
              className="btn btn-secondary" disabled={busy === conn.id + "-monitor"} onClick={() => onRun(conn.id, "monitor")}>
              {busy === conn.id + "-monitor" ? "Running…" : "Run Monitoring"}
            </button>
          </div>

          <RunHistory runs={runs || []} />
        </div>
      )}
    </div>
  );
}

function EvidenceSection({ title, items, variant }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className={"evidence-section" + (variant === "warning" ? " warning" : "")}>
      <div
        className="evidence-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span>{title}</span>
      </div>
      {expanded && (
        <ul className="evidence-list">
          {items.map((item, i) => (
            <li key={i} className="evidence-item"><span>{item}</span></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RunHistory({ runs }) {
  if (!runs || runs.length === 0) {
    return <p className="muted small">No runs yet.</p>;
  }
  return (
    <div className="run-history">
      <h4>Recent Runs</h4>
      <table className="table small-table">
        <thead><tr><th>Type</th><th>Status</th><th>Assets</th><th>Accesses</th><th>Interactions</th><th>Started</th></tr></thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>{r.run_type}</td>
              <td>{statusBadge(r.status)}</td>
              <td>{r.assets_found}</td>
              <td>{r.accesses_found}</td>
              <td>{r.interactions_found}</td>
              <td className="muted small">{new Date(r.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CreateConnectorForm({ onCreated, onCancel }) {
  const [form, setForm] = useState({ name: "", platform: "Salesforce", connector_type: "salesforce", config: "{}" });
  const [err, setErr] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true); setErr(null);
    try {
      const config = JSON.parse(form.config || "{}");
      await api.post("/connections", { ...form, config });
      onCreated();
    } catch (e) { setErr(e); } finally { setSubmitting(false); }
  }

  return (
    <div className="connector-card create-form">
      <h3>Add a connector</h3>
      {err && <div className="error-box">{String(err.message || err)}</div>}
      <div className="form-grid">
        <input className="input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="input" placeholder="Platform" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} />
        <select className="select" value={form.connector_type} onChange={(e) => setForm({ ...form, connector_type: e.target.value })}>
          <option value="salesforce">salesforce</option>
          <option value="demo">demo</option>
        </select>
        <textarea className="input" value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })} />
      </div>
      <div className="form-actions">
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? "Creating…" : "Create"}
        </button>
      </div>
    </div>
  );
}
