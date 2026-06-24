import { ASSISTANT_ID, LANGSMITH_API_KEY, LANGGRAPH_API_URL, GRAPH_RUN_CONFIG } from "../config";
import type { RunRequest } from "../types";

/** Build common headers for every LangGraph API request. */
function buildHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  // LangGraph Cloud / hosted deployments require the LangSmith API key
  if (LANGSMITH_API_KEY) {
    headers["x-api-key"] = LANGSMITH_API_KEY;
  }
  return headers;
}

/** Check if the LangGraph server is reachable at /ok */
export async function checkAgentHealth(): Promise<{ ok: boolean; latencyMs: number }> {
  const start = performance.now();
  try {
    const res = await fetch(`${LANGGRAPH_API_URL}/ok`, {
      method: "GET",
      headers: buildHeaders(),
    });
    return { ok: res.ok, latencyMs: Math.round(performance.now() - start) };
  } catch {
    return { ok: false, latencyMs: 0 };
  }
}

/** Create a new LangGraph thread and return its thread_id. */
export async function createThread(): Promise<string> {
  const res = await fetch(`${LANGGRAPH_API_URL}/threads`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Failed to create thread (${res.status}): ${text}`);
  }
  const data = await res.json() as { thread_id: string };
  return data.thread_id;
}

/**
 * Stream a run on the given thread and collect the final assistant message.
 * Uses the LangGraph REST API: POST /threads/{id}/runs/stream
 */
export async function runAgentOnThread(
  threadId: string,
  request: RunRequest,
  onChunk?: (event: string, data: unknown) => void,
): Promise<string> {
  const payload = {
    assistant_id: ASSISTANT_ID,
    input: {
      user_input: request.user_input.trim(),
      web_search_enabled: request.web_search_enabled,
      messages: [],
    },
    config: GRAPH_RUN_CONFIG,
    stream_mode: ["updates", "values"],
  };

  let res: Response;
  try {
    res = await fetch(`${LANGGRAPH_API_URL}/threads/${threadId}/runs/stream`, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    });
  } catch (networkErr) {
    // Typically a CORS or network error — give a clear message
    throw new Error(
      `Cannot reach the backend at "${LANGGRAPH_API_URL}". ` +
      `Check that LANGGRAPH_ALLOWED_ORIGINS is set on Railway and the service is running. ` +
      `(${String(networkErr)})`
    );
  }

  if (!res.ok) {
    let detail = `Agent run failed (${res.status})`;
    try {
      const errData = await res.json() as { detail?: string };
      detail = errData.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }

  // Parse SSE stream
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body from stream");

  const decoder = new TextDecoder();
  let buffer = "";
  let lastMessages: Array<{ content?: string; type?: string }> = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE lines
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let eventType = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const rawData = line.slice(6).trim();
        if (!rawData || rawData === "[DONE]") continue;
        try {
          const parsed = JSON.parse(rawData) as unknown;
          onChunk?.(eventType, parsed);
          // Pull the latest messages array from "values" events
          if (eventType === "values" && parsed && typeof parsed === "object") {
            const vals = parsed as Record<string, unknown>;
            if (Array.isArray(vals.messages)) {
              lastMessages = vals.messages as Array<{ content?: string; type?: string }>;
            }
          }
        } catch { /* non-JSON SSE line, skip */ }
      }
    }
  }

  // Extract the last AI message content
  const lastAI = [...lastMessages].reverse().find(
    (m) => m.type === "ai" || m.type === "AIMessage",
  );
  return (lastAI?.content as string | undefined) ?? "Agent completed.";
}

/** Convenience wrapper: create thread then stream the run. */
export async function runAgentChat(
  request: RunRequest,
  onChunk?: (event: string, data: unknown) => void,
): Promise<{ threadId: string; response: string }> {
  const threadId = await createThread();
  const response = await runAgentOnThread(threadId, request, onChunk);
  return { threadId, response };
}
