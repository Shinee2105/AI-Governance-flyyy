import React from "react";

const platforms = [
  {
    name: "Salesforce Agentforce",
    discovery: [
      "Agentforce agents (BotDefinition SOQL query)",
      "Active users who can invoke agents (User SOQL query)",
      "Agent metadata: name, type, AgentType",
    ],
    monitoring: [
      "Session Trace OTel API (one session per request, 72h window)",
      "Model name (from LLM span attributes)",
      "Request / prompt content (from LLM request events)",
      "Response / output content (from LLM response events)",
      "Token usage counts (prompt / completion / total)",
      "User identity (from resource attributes)",
      "Session and turn timestamps",
    ],
    withheld: [
      "Programmatic session-listing (session IDs from UI only)",
      "Sessions older than 72 hours",
      "Sessions when Session Tracing is not enabled",
    ],
    note:
      "Salesforce Agentforce exposes session traces via the OTel API, which returns one session per request. Session IDs must be obtained from the Salesforce Session Trace UI and supplied to the connector.",
  },
];

export default function Limitations() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Visibility &amp; Platform Limitations</h1>
          <p className="page-subtitle">
            A core part of this problem is understanding what a SaaS platform
            actually lets you observe. The platform below honestly distinguishes
            discovered evidence, monitored evidence, and data the vendor
            withholds. The application never fabricates withheld fields.
          </p>
        </div>
      </div>

      {platforms.map((p) => (
        <div className="connector-card" key={p.name}>
          <h2>{p.name}</h2>
          <div className="cap-grid">
            <div>
              <h4>Discoverable</h4>
              <ul>{p.discovery.map((d) => <li key={d}>{d}</li>)}</ul>
            </div>
            <div>
              <h4>Monitorable (metadata + content)</h4>
              <ul>{p.monitoring.map((m) => <li key={m}>{m}</li>)}</ul>
            </div>
            <div>
              <h4 className="bad">Withheld by vendor</h4>
              <ul>{p.withheld.map((w) => <li key={w}>{w}</li>)}</ul>
            </div>
          </div>
          <p className="vis-note">{p.note}</p>
        </div>
      ))}

      <div className="info-section">
        <h2>Why this matters for governance</h2>
        <p>
          Governance does not require seeing every prompt. Even with metadata-only
          visibility you can answer: <strong>which AI is enabled, who can use it,
          how often, in which app, and by whom</strong> — the questions this
          challenge poses. Where a vendor does expose content (e.g. via a
          dedicated compliance or DLP export), the same connector framework can
          capture it by flipping the relevant <code>*_available</code> flag.
        </p>
      </div>
    </div>
  );
}
