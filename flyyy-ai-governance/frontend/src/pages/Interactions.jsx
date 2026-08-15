import React, { useEffect, useState, useCallback } from "react";
import { api } from "../api.js";
import { Loading, ErrorBox, Avail, statusBadge } from "../components/ui.jsx";

export default function Interactions() {
  const [items, setItems] = useState(null);
  const [filters, setFilters] = useState({ applications: [], features: [], users: [] });
  const [app, setApp] = useState("");
  const [feature, setFeature] = useState("");
  const [user, setUser] = useState("");
  const [onlyLimited, setOnlyLimited] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState(null);

  const loadFilters = useCallback(() => {
    api.get("/interactions/filters").then(setFilters).catch(() => {});
  }, []);

  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (app) p.set("saas_application", app);
    if (feature) p.set("ai_feature", feature);
    if (user) p.set("user_email", user);
    if (onlyLimited) p.set("only_limited", "true");
    p.set("limit", "200");
    setItems(null);
    api
      .get(`/interactions?${p.toString()}`)
      .then(setItems)
      .catch(setError);
  }, [app, feature, user, onlyLimited]);

  useEffect(() => {
    loadFilters();
  }, [loadFilters]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorBox error={error} />;
  if (!items) return <Loading />;

  return (
    <div>
      <h1>AI Interaction Monitoring</h1>
      <p className="muted">
        Captured AI interactions across SaaS applications. Expand a row to see
        exactly what the platform exposed vs. withheld.
      </p>

      <div className="filters">
        <select value={app} onChange={(e) => setApp(e.target.value)}>
          <option value="">All applications</option>
          {filters.applications.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <select value={feature} onChange={(e) => setFeature(e.target.value)}>
          <option value="">All features</option>
          {filters.features.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
        <select value={user} onChange={(e) => setUser(e.target.value)}>
          <option value="">All users</option>
          {filters.users.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={onlyLimited}
            onChange={(e) => setOnlyLimited(e.target.checked)}
          />
          Metadata-only (no content)
        </label>
        <button onClick={load}>Apply</button>
        <span className="muted">{items.length} interactions</span>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th></th>
            <th>User</th>
            <th>Application</th>
            <th>Feature</th>
            <th>Model</th>
            <th>Time</th>
            <th>Visibility</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <React.Fragment key={i.id}>
              <tr onClick={() => setExpanded(expanded === i.id ? null : i.id)} className="row-click">
                <td>{expanded === i.id ? "▾" : "▸"}</td>
                <td>{i.user_display_name || i.user_email}</td>
                <td>{i.saas_application}</td>
                <td>{i.ai_feature}</td>
                <td>{i.model_available ? i.model : "—"}</td>
                <td className="muted small">{new Date(i.timestamp).toLocaleString()}</td>
                <td>
                  {(!i.request_available && !i.response_available)
                    ? statusBadge("Limited Visibility")
                    : statusBadge("Partial Visibility")}
                </td>
              </tr>
              {expanded === i.id && (
                <tr className="expanded">
                  <td colSpan={7}>
                    <div className="expand-grid">
                      <div>
                        <h4>Request</h4>
                        <p>{i.request_available ? i.request_info : "Not exposed by the SaaS platform."}</p>
                        <h4>Response</h4>
                        <p>{i.response_available ? i.response_info : "Not exposed by the SaaS platform."}</p>
                      </div>
                      <div>
                        <Avail value={i.request_available} label="Request" />
                        <Avail value={i.response_available} label="Response" />
                        <Avail value={i.model_available} label="Model" />
                        <Avail value={i.usage_available} label="Usage" />
                        {i.token_usage && (
                          <div className="tokens">
                            Tokens: {JSON.stringify(i.token_usage)}
                          </div>
                        )}
                        <div className="vis-note">
                          <strong>Source:</strong> {i.source}
                        </div>
                        {i.visibility_note && (
                          <div className="vis-note">{i.visibility_note}</div>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
