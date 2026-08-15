import React, { useEffect } from "react";
import { Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import { ensureAuth } from "./api.js";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Assets from "./pages/Assets.jsx";
import AssetDetail from "./pages/AssetDetail.jsx";
import Interactions from "./pages/Interactions.jsx";
import Connectors from "./pages/Connectors.jsx";
import Limitations from "./pages/Limitations.jsx";

export default function App() {
  const location = useLocation();

  useEffect(() => {
    ensureAuth();
  }, [location.pathname]);

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
