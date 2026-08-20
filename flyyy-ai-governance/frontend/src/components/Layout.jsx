import React from "react";
import Sidebar from "./Sidebar.jsx";

export default function Layout({ children }) {
  return (
    <div className="app">
      <Sidebar />
      <main className="content">{children}</main>
    </div>
  );
}
