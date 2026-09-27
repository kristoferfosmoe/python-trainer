/// <reference types="vitest/config" />
import { createReadStream, existsSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");
const pyodideDir = resolve(here, "node_modules/pyodide");

// The Pyodide runtime files are served from our own domain (not a CDN),
// because some school networks block CDNs.
const PYODIDE_FILES = [
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
  "pyodide.mjs",
];

const CONTENT_TYPES: Record<string, string> = {
  ".mjs": "text/javascript",
  ".wasm": "application/wasm",
  ".zip": "application/zip",
  ".json": "application/json",
};

function pyodideAssets(): Plugin {
  return {
    name: "pyodide-assets",
    configureServer(server) {
      server.middlewares.use("/pyodide/", (req, res, next) => {
        const name = (req.url ?? "").split("?")[0].replace(/^\//, "");
        if (!PYODIDE_FILES.includes(name)) return next();
        const ext = name.slice(name.lastIndexOf("."));
        res.setHeader("Content-Type", CONTENT_TYPES[ext] ?? "application/octet-stream");
        createReadStream(join(pyodideDir, name)).pipe(res);
      });
    },
    writeBundle(options) {
      const out = join(options.dir ?? resolve(here, "dist"), "pyodide");
      if (!existsSync(out)) mkdirSync(out, { recursive: true });
      for (const name of PYODIDE_FILES) copyFileSync(join(pyodideDir, name), join(out, name));
    },
  };
}

// In development, the Django backend runs separately (see README).
const backendUrl = process.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const backendProxy = Object.fromEntries(
  ["/api", "/admin", "/static"].map((path) => [path, { target: backendUrl, changeOrigin: false }]),
);

export default defineConfig({
  plugins: [react(), pyodideAssets()],
  optimizeDeps: { exclude: ["pyodide"] },
  worker: { format: "es" },
  server: {
    port: 5173,
    // The simulator's Python files live outside frontend/.
    fs: { allow: [repoRoot] },
    proxy: backendProxy,
  },
  preview: {
    proxy: backendProxy,
  },
  build: {
    // CodeMirror + React; Pyodide itself loads separately from /pyodide/.
    chunkSizeWarningLimit: 1000,
  },
  test: {
    include: ["src/**/*.test.ts"],
  },
});
