import type { AgentRunSettings } from "../types";

function envBool(key: string, fallback: boolean): boolean {
  const raw = import.meta.env[key];
  if (raw == null || String(raw).trim() === "") return fallback;
  const value = String(raw).trim().toLowerCase();
  return ["1", "true", "yes", "on"].includes(value);
}


function envStr(key: string, fallback: string): string {
  const raw = import.meta.env[key];
  return raw != null && String(raw).trim() !== "" ? String(raw).trim() : fallback;
}

export function defaultRunSettings(): AgentRunSettings {
  return {
    user_input: envStr("VITE_DEFAULT_USER_INPUT", "What is log(1000) + sin(30)?"),
    web_search_enabled: envBool("VITE_DEFAULT_WEB_SEARCH", false),
    user_latitude: 0,
    user_longitude: 0,
  };
}

