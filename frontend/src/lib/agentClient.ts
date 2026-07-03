import { Client } from "@langchain/langgraph-sdk";
import { ASSISTANT_ID, LANGSMITH_API_KEY, LANGGRAPH_API_URL, GRAPH_RUN_CONFIG } from "../config";
import type { RunRequest } from "../types";

function resolveApiUrlForSdk(apiUrl: string): string {
  // LangGraph SDK expects an absolute URL. In local/dev-proxy mode we may have "/api".
  if (apiUrl.startsWith("/")) {
    return new URL(apiUrl, window.location.origin).toString().replace(/\/$/, "");
  }
  return apiUrl.replace(/\/$/, "");
}

export function healthCheckUrl(): string {
  return `${resolveApiUrlForSdk(LANGGRAPH_API_URL)}/ok`;
}

/** Shared SDK client — re-used across calls. */
function getClient(): Client {
  return new Client({
    apiUrl: resolveApiUrlForSdk(LANGGRAPH_API_URL),
    // apiKey is sent as x-api-key; omit if empty so open deployments work too
    ...(LANGSMITH_API_KEY ? { apiKey: LANGSMITH_API_KEY } : {}),
  });
}

/** Check if the LangGraph server is reachable. */
export async function checkAgentHealth(): Promise<{ ok: boolean; latencyMs: number }> {
  const start = performance.now();
  const elapsed = () => Math.round(performance.now() - start);

  // Prefer /ok — fast, no auth, matches LangGraph health endpoint.
  // However a static frontend can return index.html at /api/ok (HTTP 200 HTML),
  // which would incorrectly indicate the backend is healthy. We require a
  // JSON response with { ok: true } to consider the health check successful.
  try {
    const res = await fetch(healthCheckUrl(), {
      method: "GET",
      credentials: "include",
      headers: {
        "Accept": "application/json",
      },
    });
    if (res.ok) {
      try {
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const body = await res.json();
          if (body && body.ok === true) return { ok: true, latencyMs: elapsed() };
        }
        // Otherwise treat as not a real health response and fall through.
      } catch {
        // JSON parse failed - likely HTML index page. Fall through to SDK check.
      }
    }
  } catch {
    // fall through to SDK check
  }

  try {
    const client = getClient();
    await client.assistants.search({ limit: 1 });
    return { ok: true, latencyMs: elapsed() };
  } catch {
    return { ok: false, latencyMs: 0 };
  }
}

/**
 * Create a thread, stream a run, and return the final AI response text.
 * Uses the official LangGraph SDK which handles auth + SSE correctly.
 */
export async function runAgentChat(
  request: RunRequest,
  onChunk?: (event: string, data: unknown) => void,
): Promise<{ threadId: string; response: string }> {
  const client = getClient();

  // 1. Create thread
  const thread = await client.threads.create();
  const threadId = thread.thread_id;

  // 2. Stream the run
  const stream = client.runs.stream(threadId, ASSISTANT_ID, {
    input: {
      user_input: request.user_input.trim(),
      web_search_enabled: request.web_search_enabled,
      messages: [],
    },
    config: GRAPH_RUN_CONFIG,
    streamMode: ["updates", "values"],
  });

  let lastMessages: Array<{ content?: string; type?: string }> = [];

  for await (const chunk of stream) {
    const { event, data } = chunk as { event: string; data: unknown };
    onChunk?.(event, data);

    if (event === "values" && data && typeof data === "object") {
      const vals = data as Record<string, unknown>;
      if (Array.isArray(vals.messages)) {
        lastMessages = vals.messages as Array<{ content?: string; type?: string }>;
      }
    }
  }

  // 3. Extract last AI message
  const lastAI = [...lastMessages]
    .reverse()
    .find((m) => m.type === "ai" || m.type === "AIMessage");

  return {
    threadId,
    response: (lastAI?.content as string | undefined) ?? "Agent completed.",
  };
}
