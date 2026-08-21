import React from "react";

export function Badge({ kind = "neutral", children, className = "" }) {
  const classes = className ? `badge badge-${kind} ${className}` : `badge badge-${kind}`;
  return <span className={classes}>{children}</span>;
}

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

export function DemoBadge({ label = "SIMULATED" }) {
  return <span className="badge badge-demo">{label}</span>;
}

export function isSimulated(obj) {
  return Boolean(obj && obj.simulated);
}

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
  return <div className="error-box">{String(error.message || error)}</div>;
}

export function VisibilityIndicator({ available, label }) {
  return (
    <div className={`vis-indicator ${available ? "yes" : "no"}`}>
      <span className={`dot ${available ? "dot-yes" : "dot-no"}`} />
      <span className="vis-label">{label}</span>
      <span className="vis-status">{available ? "Available" : "Not exposed"}</span>
    </div>
  );
}
