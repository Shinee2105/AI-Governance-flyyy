import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Loading, ErrorBox, statusBadge, DemoBadge } from "../components/ui.jsx";

const REVIEW_OPTIONS = ["Pending", "In Review", "Approved", "Rejected"];

export default function Assets() {
  const [assets, setAssets] = useState(null);
  const [error, setError] = useState(null);
  const [platform, setPlatform] = useState("");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (platform) params.set("saas_platform", platform);
    if (search) params.set("search", search);
    setAssets(null);
    api
      .get(`/assets?${params.toString()}`)
      .then(setAssets)
      .catch(setError);
  }, [platform, search]);

  useEffect(() => {
    load();
  }, [load]);

  async function changeReview(id, value) {
    try {
      await api.patch(`/assets/${id}`, { review_status: value });
      load();
    } catch (e) {
      setError(e);
    }
  }

  if (error) return <ErrorBox error={error} />;
  if (!assets) return <Loading />;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">AI Asset Inventory</h1>
          <p className="page-subtitle">
            Every AI capability discovered inside your SaaS estate, represented
            as a governed asset with its access and monitoring posture.
          </p>
        </div>
      </div>

      <div className="filters">
        <input
          className="input"
          placeholder="Search name / capability / provider"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="select"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          <option value="">All platforms</option>
          <option value="Microsoft 365">Microsoft 365 (demo)</option>
          <option value="Salesforce">Salesforce</option>
          <option value="Slack">Slack</option>
          <option value="Notion">Notion</option>
        </select>
        <button className="btn btn-secondary" onClick={load}>Search</button>
        <span className="muted">{assets.length} assets</span>
      </div>

      <div className="assets-table">
        <table className="table">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Provider</th>
              <th>Platform</th>
              <th>Capability</th>
              <th>Monitoring</th>
              <th>Accesses</th>
              <th>Interactions</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr
                key={a.id}
                onClick={() => navigate(`/assets/${a.id}`)}
                className="row-click"
              >
                <td>
                  <div className="asset-name">
                    <strong>{a.name}</strong>
                    {a.simulated && <DemoBadge label="SIM" />}
                  </div>
                  <div className="muted small">{a.ai_capability}</div>
                </td>
                <td>{a.provider}</td>
                <td>{a.saas_platform}</td>
                <td>{statusBadge(a.capability_status)}</td>
                <td>{statusBadge(a.monitoring_status)}</td>
                <td>{a.access_count}</td>
                <td>{a.interaction_count}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <select
                    className="select small"
                    value={a.review_status}
                    onChange={(e) => changeReview(a.id, e.target.value)}
                  >
                    {REVIEW_OPTIONS.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
