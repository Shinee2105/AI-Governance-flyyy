import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api.js";
import { Loading, ErrorBox, statusBadge, Avail } from "../components/ui.jsx";

export default function AssetDetail() {
  const { id } = useParams();
  const [asset, setAsset] = useState(null);
  const [interactions, setInteractions] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get(`/assets/${id}`)
      .then(setAsset)
      .catch(setError);
    api
      .get(`/interactions?asset_id=${id}&limit=50`)
      .then(setInteractions)
      .catch(() => setInteractions([]));
  }, [id]);

  if (error) return <ErrorBox error={error} />;
  if (!asset) return <Loading />;

  return (
    <div>
      <Link to="/assets" className="back">← All assets</Link>
      <h1>{asset.name}</h1>
      <p className="muted">{asset.ai_capability}</p>

      <div className="detail-grid">
        <Field label="Type" value={asset.asset_type} />
        <Field label="Provider" value={asset.provider} />
        <Field label="Platform" value={asset.saas_platform} />
        <Field label="Status" value={statusBadge(asset.status)} />
        <Field label="Enabled" value={asset.enabled ? "Yes" : "No"} />
        <Field label="Review" value={statusBadge(asset.review_status)} />
        <Field label="Monitoring" value={statusBadge(asset.monitoring_status)} />
        <Field label="Discovery source" value={asset.discovery_source} />
      </div>

      <h2>Purpose</h2>
      <p>{asset.purpose || "—"}</p>

      <h2>Accessible Resources</h2>
      <div className="chips">
        {(asset.accessible_resources || []).map((r) => (
          <span key={r} className="chip">{r}</span>
        ))}
      </div>

      <h2>Who can use it ({asset.access_count})</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Principal</th>
            <th>Type</th>
            <th>Access</th>
            <th>License</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {asset.accesses.map((a) => (
            <tr key={a.id}>
              <td>
                <strong>{a.display_name || a.principal_name}</strong>
                <div className="muted small">{a.email}</div>
              </td>
              <td>{a.principal_type}</td>
              <td>{a.access_level}</td>
              <td>{a.license_sku || "—"}</td>
              <td className="muted small">{a.source}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Observed Interactions ({asset.interaction_count})</h2>
      {interactions && interactions.length === 0 && (
        <p className="muted">No interactions captured yet for this asset.</p>
      )}
      <table className="table">
        <thead>
          <tr>
            <th>User</th>
            <th>App</th>
            <th>Model</th>
            <th>Time</th>
            <th>Content</th>
          </tr>
        </thead>
        <tbody>
          {(interactions || []).map((i) => (
            <tr key={i.id}>
              <td>{i.user_display_name || i.user_email}</td>
              <td>{i.saas_application}</td>
              <td>{i.model_available ? i.model : "—"}</td>
              <td className="muted small">{new Date(i.timestamp).toLocaleString()}</td>
              <td>
                <Avail value={i.request_available} label="Req" />
                <Avail value={i.response_available} label="Resp" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div className="field">
      <div className="field-label">{label}</div>
      <div className="field-value">{value}</div>
    </div>
  );
}
