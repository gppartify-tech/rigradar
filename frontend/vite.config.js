import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the React app runs on :5173 and forwards API calls to FastAPI on :8000.
// In production (Docker) nginx does the same forwarding - see nginx.conf.
const API_URL = process.env.API_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": API_URL,
      "/uploads": API_URL,
    },
  },
});
