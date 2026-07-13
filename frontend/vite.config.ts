import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { serveReportsPlugin } from "./vite.reportsPlugin";

/**
 * Andromeda Agent – Vite config
 *
 * Local dev:
 *   VITE_LANGGRAPH_API_URL=http://127.0.0.1:2024  (root .env, loaded via envDir)
 *   Leave blank → Vite dev-server proxies /api → LangGraph on LANGGRAPH_PORT
 *   Generated PDFs: /generated-reports/<name>.pdf → ../reports/
 */

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const reportsDir = path.join(rootDir, "reports");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootDir, "");
  const langgraphPort = env.LANGGRAPH_PORT || "2024";
  const frontendPort = Number(env.FRONTEND_PORT || "5173");

  return {
    envDir: rootDir,
    plugins: [react(), serveReportsPlugin(reportsDir)],
    server: {
      port: frontendPort,
      strictPort: true,
      fs: {
        allow: [rootDir],
      },
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${langgraphPort}`,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
    preview: {
      port: frontendPort,
    },
    build: {
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ["react", "react-dom"],
            langgraph: ["@langchain/langgraph-sdk"],
          },
        },
      },
    },
  };
});
