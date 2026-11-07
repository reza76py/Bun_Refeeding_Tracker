import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the Django backend so the browser sees a
// single origin (http://localhost:5173) and session + CSRF cookies work
// without CORS. Change the target with the DJANGO_API env var if needed.
const apiTarget = process.env.DJANGO_API || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
});
