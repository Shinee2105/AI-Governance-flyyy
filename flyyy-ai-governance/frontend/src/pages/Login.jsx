import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, login, devAutologinEnabled } from "../api.js";
import { ErrorBox } from "../components/ui.jsx";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand-mark">FLYYY</div>
        <h2>Sign in to the governance console</h2>
        <p className="muted">
          Mutation endpoints require authentication. Read-only pages are public.
        </p>
        {devAutologinEnabled() && (
          <p className="vis-note">
            Development mode: auto-login is enabled with the configured dev
            credentials, so you normally will not see this screen.
          </p>
        )}
        <form onSubmit={submit}>
          <input
            className="input"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <input
            className="input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="submit"
            disabled={busy}
            className="btn btn-primary"
            style={{ width: "100%" }}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <ErrorBox error={error} />
      </div>
    </div>
  );
}
