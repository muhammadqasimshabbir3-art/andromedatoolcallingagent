import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Andromeda Agent – Vite config
 *
 * Local dev:
 *   VITE_LANGGRAPH_API_URL=http://127.0.0.1:2024  (root .env, loaded via envDir)
 *   Leave blank → Vite dev-server proxies /api → LangGraph on LANGGRAPH_PORT
 *
 * Production (Vercel):
 *   VITE_LANGGRAPH_API_URL=https://<your-railway-app>.up.railway.app
 *   VITE_LANGGRAPH_ASSISTANT_ID=agent   (optional, defaults to "agent")
 */

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootDir, "");
  const langgraphPort = env.LANGGRAPH_PORT || "2024";
  const frontendPort = Number(env.FRONTEND_PORT || "5173");

  return {
    /** Load env vars from the monorepo root (.env / .env.local etc.) */
    envDir: rootDir,

    plugins: [react()],

    server: {
      port: frontendPort,
      strictPort: true,
      /** Dev proxy: /api → LangGraph server (avoids CORS in local dev) */
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
      /** Emit source-maps for easier Railway/Vercel debugging */
      sourcemap: false,
      rollupOptions: {
        output: {
          /** Chunk vendor libs separately for better cache hit rates */
          manualChunks: {
            react: ["react", "react-dom"],
            langgraph: ["@langchain/langgraph-sdk"],
          },
        },
      },
    },
  };
});
