import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on :8000 (FastAPI). The frontend dev server proxies
// /api/* to it so the browser never hits CORS issues during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
