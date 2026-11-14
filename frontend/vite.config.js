import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` (cổng 5173) proxy /api sang FastAPI ở 8000.
// Build: `npm run build` → frontend/dist, FastAPI tự phục vụ thư mục này (xem src/main.py).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
