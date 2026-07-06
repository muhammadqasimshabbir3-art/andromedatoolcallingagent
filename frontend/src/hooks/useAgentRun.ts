import { useCallback, useState } from "react";
import { runAgentChat } from "../lib/agentClient";
import { initialStepStates } from "../lib/workflowSteps";
import type { AgentState, LogEntry, RunRequest, StepState } from "../types";

/** Keywords that trigger automatic browser geolocation lookup. */
const LOCATION_TRIGGERS = [
  "where am i",
  "my location",
  "current location",
  "live location",
  "show live location",
  "show my location",
  "what's my location",
  "what is my location",
  "nearby",
  "near me",
  "around me",
  "what's around me",
  "what is around me",
  "close to me",
  "places near",
  "find nearby",
  "search nearby",
];

function isLocationQuery(text: string): boolean {
  const lowered = text.toLowerCase();
  return LOCATION_TRIGGERS.some((kw) => lowered.includes(kw));
}

function getBrowserLocation(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({ lat: 0, lng: 0 });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve({ lat: 0, lng: 0 }),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  });
}

export function useAgentRun() {
  const [running, setRunning] = useState(false);
  const [reconnected, setReconnected] = useState(false);
  const [steps, setSteps] = useState<StepState[]>(initialStepStates());
  const [result, setResult] = useState<AgentState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const pushLog = useCallback((level: LogEntry["level"], message: string) => {
    setLogs((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        time: new Date().toLocaleTimeString(),
        level,
        message,
      },
    ]);
  }, []);

  const run = useCallback(async (request: RunRequest) => {
    if (!request.user_input?.trim()) {
      setError("User input is required.");
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    setLogs([]);
    setReconnected(false);
    setThreadId(null);
    setRunId(null);

    // Mark first step as running
    setSteps((prev) =>
      prev.map((s, i) => i === 0 ? { ...s, status: "running" } : { ...s, status: "pending" })
    );

    // Auto-detect browser location for location-related queries
    let finalRequest = { ...request };
    if (isLocationQuery(request.user_input)) {
      pushLog("info", "📍 Detecting your location...");
      try {
        const coords = await getBrowserLocation();
        if (coords.lat !== 0 || coords.lng !== 0) {
          finalRequest.user_latitude = coords.lat;
          finalRequest.user_longitude = coords.lng;
          pushLog("info", `📍 Location detected: ${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)}`);
        } else {
          pushLog("warn", "📍 Location unavailable — sending request without coordinates");
        }
      } catch {
        pushLog("warn", "📍 Could not detect location");
      }
    }

    pushLog("info", "🚀 Sending request to Andromeda agent...");

    try {
      const { threadId: tid, response } = await runAgentChat(
        finalRequest,
        (eventType, data) => {
          // Live progress from SSE stream
          if (eventType === "updates" && data && typeof data === "object") {
            const upd = data as Record<string, unknown>;
            const nodeName = Object.keys(upd)[0];
            if (nodeName) {
              pushLog("info", `⚙️ Node active: ${nodeName}`);
            }
          }
        },
      );

      setThreadId(tid);

      // Update result state with the text returned
      setResult({ task_plan_summary: response } as AgentState);

      // Mark all steps completed
      setSteps((prev) =>
        prev.map((s) => ({ ...s, status: "completed", detail: "Done" }))
      );

      pushLog("success", "✅ Agent request completed successfully!");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      pushLog("error", `❌ Error: ${message}`);

      setSteps((prev) =>
        prev.map((s) => s.status === "running" ? { ...s, status: "error", detail: message } : s)
      );
    } finally {
      setRunning(false);
    }
  }, [pushLog]);

  const cancel = useCallback(() => {
    if (running) {
      setRunning(false);
      pushLog("warn", "⏹️ Agent run stopped (UI only)");
    }
  }, [running, pushLog]);

  const reset = useCallback(() => {
    setRunning(false);
    setReconnected(false);
    setSteps(initialStepStates());
    setResult(null);
    setError(null);
    setLogs([]);
    setThreadId(null);
    setRunId(null);
  }, []);

  return {
    running,
    reconnected,
    steps,
    result,
    error,
    logs,
    threadId,
    runId,
    run,
    cancel,
    reset,
  };
}
