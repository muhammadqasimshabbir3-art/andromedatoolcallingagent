import { Client } from "@langchain/langgraph-sdk";
import { ASSISTANT_ID, LANGSMITH_API_KEY, LANGGRAPH_API_URL, GRAPH_RUN_CONFIG } from "../config";
import type { RunRequest } from "../types";

/** Shared SDK client — re-used across calls. */
function getClient(): Client {
  return new Client({
    apiUrl: LANGGRAPH_API_URL,
    // apiKey is sent as x-api-key; omit if empty so open deployments work too
    ...(LANGSMITH_API_KEY ? { apiKey: LANGSMITH_API_KEY } : {}),
  });
}

/** Check if the LangGraph server is reachable. */
export async function checkAgentHealth(): Promise<{ ok: boolean; latencyMs: number }> {
  const start = performance.now();
  try {
    // The SDK's assistants.search is a lightweight authenticated call
    const client = getClient();
    await client.assistants.search({ limit: 1 });
    return { ok: true, latencyMs: Math.round(performance.now() - start) };
  } catch {
    // Fallback: plain /ok ping (works for unauthenticated deployments)
    try {
      const res = await fetch(`${LANGGRAPH_API_URL}/ok`);
      return { ok: res.ok, latencyMs: Math.round(performance.now() - start) };
    } catch {
      return { ok: false, latencyMs: 0 };
    }
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
