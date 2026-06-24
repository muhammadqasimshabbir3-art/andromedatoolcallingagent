import { LANGGRAPH_API_URL } from "../config";
import type { RunRequest } from "../types";

export async function checkAgentHealth(): Promise<{ ok: boolean; latencyMs: number }> {
  const start = performance.now();
  try {
    const res = await fetch(`${LANGGRAPH_API_URL}/health`, { method: "GET" });
    return { ok: res.ok, latencyMs: Math.round(performance.now() - start) };
  } catch {
    return { ok: false, latencyMs: 0 };
  }
}

export async function runAgentChat(request: RunRequest): Promise<string> {
  const payload = {
    user_input: request.user_input.trim(),
    web_search_enabled: request.web_search_enabled,
    messages: []
  };

  const res = await fetch(`${LANGGRAPH_API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    let errorDetail = "Agent run failed";
    try {
      const errData = await res.json();
      errorDetail = errData.detail || errorDetail;
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  const data = await res.json();
  return data.response;
}
