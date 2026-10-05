import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const api = ["/auth", "/incidents", "/actions", "/assets", "/documents", "/notifications", "/settings"];
export default defineConfig({
  plugins: [react()], base: "/app/",
  build: { outDir: "../backend/static_react", emptyOutDir: true },
  server: { proxy: Object.fromEntries(api.map((p) => [p, "http://localhost:8000"])) },
});
