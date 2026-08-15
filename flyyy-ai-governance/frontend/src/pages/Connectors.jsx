import React, { useEffect, useState, useCallback } from "react";
import { api, getToken } from "../api.js";
import { Loading, ErrorBox, statusBadge } from "../components/ui.jsx";

export default function Connectors() {
  const [connections, setConnections] = useState(null);
  const [runs, setRuns] = useState({});
  const [caps, setCaps] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(() => {
    api
      .get("/connections")
      .then(async (conns) => {
        setConnections(conns);
        const r = {};
        const c = {};
        for (const conn of conns) {
          r[conn.id] = await api.get(`/connections/${conn.id}/runs`).catch(() => []);
          c[conn.id] = await api
            .get(`/connections/${conn.id}/capabilities`)
            .catch(() => null);
        }
        setRuns(r);
        setCaps(c);
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(connId, type) {
    if (!getToken()) {
      setError(new Error("Not authenticated — please log in."));
      return;
    }
    setBusy(`${connId}-${type}`);
    try {
      await api.post(`/connections/${connId}/${type}`);
      load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorBox error={error} />;
  if (!connections) return <Loading />;

  return (
    <div>
      <h1>Connectors & SaaS Environments</h1>
      <p className="muted">
        Each connector talks to a SaaS platform to discover AI capabilities and
        monitor interactions. The Microsoft 365 connector is built on real
        Microsoft Graph + Management Activity APIs; configure it via environment
        variables to discover genuine evidence.
      </p>

      {connections.map((conn) => {
        const c = caps[conn.id];
        return (
          <div className="connector-card" key={conn.id}>
            <div className="connector-head">
              <div>
                <h2>{conn.name}</h2>
                <span className="muted">{conn.connector_type} · {conn.platform}</span>
              </div>
              <div className="connector-actions">
                <button
                  disabled={busy === `${conn.id}-discover`}
                  onClick={() => run(conn.id, "discover")}
                >
                  {busy === `${conn.id}-discover` ? "Running…" : "Run Discovery"}
                </button>
                <button
                  disabled={busy === `${conn.id}-monitor`}
                  onClick={() => run(conn.id, "monitor")}
                >
                  {busy === `${conn.id}-monitor` ? "Running…" : "Run Monitoring"}
                </button>
                <span>{statusBadge(conn.status)}</span>
              </div>
            </div>

            {c && (
              <div className="cap-grid">
                <div>
                  <h4>Discovery evidence</h4>
                  <ul>{c.discovery.map((d) => <li key={d}>{d}</li>)}</ul>
                </div>
                <div>
                  <h4>Monitoring evidence</h4>
                  <ul>{c.monitoring.map((m) => <li key={m}>{m}</li>)}</ul>
                </div>
                <div>
                  <h4 className="bad">Not exposed by platform</h4>
                  <ul>{c.not_exposed.map((n) => <li key={n}>{n}</li>)}</ul>
                </div>
              </div>
            )}

            <h4>Recent Runs</h4>
            <table className="table small-table">
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
                {(runs[conn.id] || []).map((r) => (
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
      })}

      <CreateConnector onCreated={load} />
    </div>
  );
}

function CreateConnector({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    platform: "Microsoft 365",
    connector_type: "microsoft365",
    config: "{}",
  });
  const [err, setErr] = useState(null);

  if (!open) {
    return (
      <button className="ghost" onClick={() => setOpen(true)}>
        + Add connector
      </button>
    );
  }

  async function submit() {
    try {
      const config = JSON.parse(form.config || "{}");
      await api.post("/connections", { ...form, config });
      setOpen(false);
      onCreated();
    } catch (e) {
      setErr(e);
    }
  }

  return (
    <div className="connector-card">
      <h3>Add a connector</h3>
      {err && <ErrorBox error={err} />}
      <div className="form-grid">
        <input
          placeholder="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          placeholder="Platform"
          value={form.platform}
          onChange={(e) => setForm({ ...form, platform: e.target.value })}
        />
        <select
          value={form.connector_type}
          onChange={(e) => setForm({ ...form, connector_type: e.target.value })}
        >
          <option value="microsoft365">microsoft365</option>
          <option value="demo">demo</option>
        </select>
        <textarea
          placeholder='Config JSON, e.g. {"tenant_name":"Contoso"}'
          value={form.config}
          onChange={(e) => setForm({ ...form, config: e.target.value })}
        />
      </div>
      <button onClick={submit}>Create</button>
    </div>
  );
}
