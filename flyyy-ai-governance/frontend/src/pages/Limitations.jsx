import React from "react";

const platforms = [
  {
    name: "Microsoft 365 Copilot",
    discovery: [
      "Copilot license SKUs present in the tenant (subscribedSkus)",
      "Per-user license assignment (user.assignedLicenses)",
      "Associated Microsoft 365 workloads",
    ],
    monitoring: [
      "User identity (UserId)",
      "Workload / application (Word, Teams, Outlook…)",
      "Operation & timestamp (unified audit log)",
    ],
    withheld: [
      "The actual prompt sent to the LLM",
      "The generated response",
      "The underlying model name",
      "Token / usage counts",
    ],
    note:
      "Microsoft exposes Copilot *activity* through the Office 365 Management Activity API (RecordType 305), not the content. This is a deliberate privacy/security boundary.",
  },
  {
    name: "Slack AI",
    discovery: ["Workspace AI settings / add-on state", "Channel-level enablement"],
    monitoring: ["Action type (summary, search, recap)", "User & channel"],
    withheld: ["The generated summary text", "Underlying model"],
    note:
      "Slack surfaces the *action* taken but not the conversational content it produced.",
  },
  {
    name: "Notion AI",
    discovery: ["Workspace add-on state", "Plan entitlements"],
    monitoring: [
      "Some plans expose model name (e.g. gpt-4)",
      "Usage / token counts on certain plans",
      "Request type",
    ],
    withheld: ["Full response text on most plans"],
    note:
      "Visibility varies by plan; Notion is one of the few that can surface model + usage metadata.",
  },
];

export default function Limitations() {
  return (
    <div>
      <h1>Visibility & Platform Limitations</h1>
      <p className="muted">
        A core part of this problem is understanding <em>what a SaaS platform
        actually lets you observe</em>. The platform below honestly distinguishes
        discovered evidence, monitored evidence, and data the vendor withholds.
        The application never fabricates withheld fields — it marks them
        “Not exposed” and records a visibility note.
      </p>

      {platforms.map((p) => (
        <div className="connector-card" key={p.name}>
          <h2>{p.name}</h2>
          <div className="cap-grid">
            <div>
              <h4>Discoverable</h4>
              <ul>{p.discovery.map((d) => <li key={d}>{d}</li>)}</ul>
            </div>
            <div>
              <h4>Monitorable (metadata)</h4>
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
  );
}
