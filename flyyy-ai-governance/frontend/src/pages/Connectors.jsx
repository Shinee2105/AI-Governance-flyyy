import React, { useEffect, useState, useCallback } from "react";
import { api, getToken } from "../api.js";
import { Loading, ErrorBox } from "../components/ui.jsx";
import { ConnectorCard, CreateConnectorForm } from "../components/ConnectorCard.jsx";

export default function Connectors() {
  const [connections, setConnections] = useState(null);
  const [runs, setRuns] = useState({});
  const [caps, setCaps] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

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
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Connectors &amp; SaaS Environments</h1>
          <p className="page-subtitle">
            Each connector talks to a SaaS platform to discover AI capabilities
            and monitor interactions. The Salesforce connector uses real
            Salesforce REST APIs; the Demo connector ships so the app runs
            with no credentials.
          </p>
        </div>
        {!showCreate && (
          <button className="btn btn-ghost" onClick={() => setShowCreate(true)}>
            + Add connector
          </button>
        )}
      </div>

      {showCreate && (
        <CreateConnectorForm
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      <div className="connectors-list">
        {connections
          .filter((c) => c.connector_type === "salesforce" || c.connector_type === "demo")
          .map((conn) => (
            <ConnectorCard
              key={conn.id}
              conn={conn}
              caps={caps[conn.id]}
              runs={runs[conn.id]}
              busy={busy}
              onRun={run}
            />
          ))}
      </div>
    </div>
  );
}
