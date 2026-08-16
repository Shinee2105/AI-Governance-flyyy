import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { ensureAuth, getToken, devAutologinEnabled } from "./api.js";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Assets from "./pages/Assets.jsx";
import AssetDetail from "./pages/AssetDetail.jsx";
import Interactions from "./pages/Interactions.jsx";
import Connectors from "./pages/Connectors.jsx";
import Limitations from "./pages/Limitations.jsx";
import Login from "./pages/Login.jsx";

export default function App() {
  const location = useLocation();
  const [state, setState] = useState("loading"); // loading | authed | login

  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (getToken()) {
        if (!cancelled) setState("authed");
        return;
      }
      await ensureAuth();
      if (!cancelled) {
        // If dev auto-login succeeded a token now exists; otherwise show login.
        setState(getToken() ? "authed" : "login");
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  if (state === "loading") return <div className="loading">Loading…</div>;
  if (state === "login") return <Login />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/assets/:id" element={<AssetDetail />} />
        <Route path="/interactions" element={<Interactions />} />
        <Route path="/connectors" element={<Connectors />} />
        <Route path="/limitations" element={<Limitations />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}
