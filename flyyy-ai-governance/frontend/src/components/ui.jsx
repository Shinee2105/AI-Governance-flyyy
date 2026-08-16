import React from "react";

// Status pill with colour coding.
export function Badge({ kind = "neutral", children }) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

// Maps a status string to a colour class.
export function statusBadge(status) {
  if (!status) return <Badge>—</Badge>;
  const s = status.toLowerCase();
  let kind = "neutral";
  if (s.includes("pending")) kind = "warn";
  else if (s.includes("approved") || s.includes("enabled") || s.includes("connected") || s.includes("success") || s.includes("licensed"))
    kind = "ok";
  else if (s.includes("rejected") || s.includes("error") || s.includes("failed")) kind = "bad";
  else if (s.includes("partial") || s.includes("limited") || s.includes("review") || s.includes("unknown") || s.includes("not observable")) kind = "warn";
  else if (s.includes("not ")) kind = "muted";
  return <Badge kind={kind}>{status}</Badge>;
}

// Prominent marker for demonstration / simulated data so it is never mistaken
// for real evidence from a SaaS tenant.
export function DemoBadge({ label = "SIMULATED" }) {
  return <span className="badge badge-demo">⚠ {label}</span>;
}

export function isSimulated(obj) {
  return Boolean(obj && obj.simulated);
}

// Small dot indicating whether a piece of evidence is available.
export function Avail({ value, label }) {
  return (
    <span className={`avail ${value ? "avail-yes" : "avail-no"}`}>
      <span className="dot" /> {label}: {value ? "Available" : "Not exposed"}
    </span>
  );
}

export function Loading({ label = "Loading…" }) {
  return <div className="loading">{label}</div>;
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return <div className="error-box">⚠ {String(error.message || error)}</div>;
}
