// Vite config for the console front end. `npm run build` writes dist/, which
// the Python backend (tools/console/src) serves as static files under a
// `script-src 'self'` CSP, so the build must emit no inline scripts.
//
// `npm run dev` proxies /api to dev/mock-server.mjs on 127.0.0.1:8790. The
// real backend refuses proxied requests (their Host/Origin are Vite's), so
// test against it by building to dist/ and letting it serve the files.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const DEFAULT_BACKEND_PORT = 8790;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${process.env.CONSOLE_PORT ?? DEFAULT_BACKEND_PORT}`,
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Current browsers only; keeps the preload polyfill out of the bundle.
    modulePreload: { polyfill: false },
  },
  test: { include: ["tests/**/*.test.{ts,tsx}"], environment: "node" },
});
