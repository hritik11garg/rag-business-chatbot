import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: the SPA calls same-origin paths and Vite forwards them to
// FastAPI — no CORS involved during development.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/auth": backend,
      "/chat": backend,
      "/documents": backend,
      "/me": backend,
      "/health": backend,
    },
  },
});
